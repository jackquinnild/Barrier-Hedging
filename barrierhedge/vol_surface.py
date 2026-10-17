"""Implied-volatility surface for one day, and the local volatility it implies.

Steps:
  1. For each listed expiry, fit an SVI curve to total implied variance w = iv^2 * T as a function
     of log-moneyness k = ln(K / F). Raw quotes are too noisy to differentiate, the fitted curve isn't.
  2. Between expiries, interpolate w linearly in T at fixed k.
  3. Turn the surface into local volatility with Dupire's formula.

Time is in years of 365 calendar days, which is how OptionMetrics quotes implied vols.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares


@dataclass
class SVISlice:
    """Raw SVI (Gatheral, 2004):  w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + s^2)).

    a sets the overall level, b how steep the wings are, rho the tilt (negative means puts are
    dearer), m shifts the smile sideways and s rounds off its bottom.
    """
    T: float
    a: float
    b: float
    rho: float
    m: float
    s: float
    rmse_vol: float = np.nan

    def w(self, k):
        d = np.asarray(k) - self.m
        return self.a + self.b * (self.rho * d + np.sqrt(d * d + self.s * self.s))

    def iv(self, k):
        return np.sqrt(np.maximum(self.w(k), 1e-12) / self.T)

    def density_ok(self, k=np.linspace(-0.8, 0.3, 221)):
        """Gatheral's butterfly condition g(k) >= 0. A negative g would mean a butterfly spread with a
        negative price. Returns True if the condition holds on the grid."""
        w = self.w(k)
        d = k - self.m
        root = np.sqrt(d * d + self.s * self.s)
        w1 = self.b * (self.rho + d / root)
        w2 = self.b * self.s**2 / root**3
        g = (1 - k * w1 / (2 * w)) ** 2 - w1**2 / 4 * (1 / w + 0.25) + w2 / 2
        return bool((g >= 0).all())


def fit_svi(k, iv, T, weights=None):
    """Fit one smile by weighted least squares on implied vol, from a few starting points."""
    k, iv = np.asarray(k, float), np.asarray(iv, float)
    w_market = iv**2 * T
    weights = np.ones_like(k) if weights is None else np.asarray(weights, float)
    weights = weights / weights.mean()

    def residuals(p):
        a, b, rho, m, s = p
        w = a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + s * s))
        return np.sqrt(weights) * (np.sqrt(np.maximum(w, 1e-12) / T) - iv)

    bounds = ([-1.0, 1e-4, -0.999, -1.0, 1e-3], [w_market.max(), 5.0, 0.999, 1.0, 2.0])
    best = None
    for rho0 in (-0.7, -0.3):
        for s0 in (0.05, 0.2):
            start = [max(0.5 * w_market.min(), 1e-4), 0.1, rho0, 0.0, s0]
            fit = least_squares(residuals, start, bounds=bounds)
            if best is None or fit.cost < best.cost:
                best = fit
    fitted = SVISlice(T, *best.x)
    fitted.rmse_vol = float(np.sqrt(np.mean((fitted.iv(k) - iv) ** 2)))
    return fitted


class VolSurface:
    def __init__(self, slices, spot, r, q):
        self.slices = _calendar_consistent(slices)
        self.T_nodes = np.array([s.T for s in self.slices])
        self.spot, self.r, self.q = spot, r, q

    @classmethod
    def calibrate(cls, quotes, spot, r, q, min_days=5, max_days=400, k_range=(-0.8, 0.10), min_quotes=8):
        """Fit a smile to each expiry in `quotes` (one day of put quotes with columns exdate, days, k, iv, vega).

        Puts only, from deep out of the money up to slightly in the money, each quote weighted by its
        vega so the fit listens most to the prices that carry the most information about volatility.
        """
        q_ = quotes[quotes["days"].between(min_days, max_days) & quotes["k"].between(*k_range)]
        slices = [fit_svi(g["k"], g["iv"], g["days"].iloc[0] / 365, weights=g["vega"].clip(lower=1e-6))
                  for _, g in q_.groupby("exdate") if len(g) >= min_quotes]
        return cls(slices, spot, r, q)

    def w(self, k, T):
        """Total implied variance at log-moneyness k and maturity T."""
        k = np.asarray(k, float)
        if T <= self.T_nodes[0]:
            return self.slices[0].w(k) * T / self.T_nodes[0]
        if T >= self.T_nodes[-1]:
            return self.slices[-1].w(k) * T / self.T_nodes[-1]
        j = np.searchsorted(self.T_nodes, T)
        near, far = self.slices[j - 1], self.slices[j]
        x = (T - near.T) / (far.T - near.T)
        return (1 - x) * near.w(k) + x * far.w(k)

    def iv(self, k, T):
        return np.sqrt(np.maximum(self.w(k, T), 1e-12) / T)

    def local_vol(self, k, T, dk=1e-3, dT=1 / 365):
        """Dupire local volatility in terms of total implied variance (Gatheral, eq. 1.10):

            sigma_loc^2 = w_T / (1 - (k/w) w_k + 0.25 (-0.25 - 1/w + k^2/w^2) w_k^2 + 0.5 w_kk)

        with the derivatives taken numerically. The result is clipped to [3%, 200%] because the
        short-dated far wings can produce extreme values.
        """
        k = np.asarray(k, float)
        T = max(T, dT)
        w = self.w(k, T)
        t_lo = max(T - dT / 2, 1e-6)
        w_T = (self.w(k, T + dT / 2) - self.w(k, t_lo)) / (T + dT / 2 - t_lo)
        w_up, w_dn = self.w(k + dk, T), self.w(k - dk, T)
        w_k = (w_up - w_dn) / (2 * dk)
        w_kk = (w_up - 2 * w + w_dn) / dk**2
        denom = 1 - k * w_k / w + 0.25 * (-0.25 - 1 / w + k**2 / w**2) * w_k**2 + 0.5 * w_kk
        local_var = w_T / np.maximum(denom, 1e-3)
        return np.sqrt(np.clip(local_var, 0.03**2, 2.0**2))

    def local_vol_function(self, r=None, q=None):
        """vol(t, S) for the PDE engine, measured from this surface's date.

        Results are cached by time step, so pricing several options on the same grid on the same day
        (for instance a base solve and a vega bump) only evaluates the surface once.
        vol.with_bump(0.01) gives the same function shifted up by one volatility point.
        """
        r = self.r if r is None else r
        q = self.q if q is None else q
        cache = {}

        def vol(t, S):
            key = (round(t, 12), len(S), float(S[0]))
            if key not in cache:
                forward = self.spot * np.exp((r - q) * t)
                cache[key] = self.local_vol(np.log(np.asarray(S) / forward), t)
            return cache[key]

        vol.with_bump = lambda size: (lambda t, S: vol(t, S) + size)
        return vol


def _calendar_consistent(slices):
    """Drop any expiry whose at-the-money total variance is not above the previous one's.
    Total variance that falls with maturity would allow a calendar-spread arbitrage."""
    kept = []
    for s in sorted(slices, key=lambda s: s.T):
        if not kept or s.w(0.0) > kept[-1].w(0.0):
            kept.append(s)
    return kept
