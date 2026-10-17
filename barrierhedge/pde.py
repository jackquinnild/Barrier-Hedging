"""Finite-difference pricer for a down-and-in put whose barrier is checked at daily closes.

The grid carries two value functions, exactly like the binomial tree:

    active   - the barrier has been hit, so the option is a plain put
    waiting  - the barrier has not been hit yet

Both are rolled back from expiry with the same pricing equation. At every checked close, grid
points at or below the barrier take the active value. Volatility can be a constant or a function
of time and spot (local volatility), which is the main reason to use a grid instead of a tree.

The equation, written in x = ln(S):

    V_t + 0.5 sigma^2 V_xx + (r - q - 0.5 sigma^2) V_x - r V = 0

Time stepping is Crank-Nicolson. Right after expiry and after each barrier check the values have a
jump, and Crank-Nicolson rings around jumps, so those steps are replaced by two fully implicit
half steps (Rannacher smoothing).
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.linalg import solve_banded


@dataclass
class Solution:
    """Option values on the spot grid at one point in time."""
    spots: np.ndarray
    waiting: np.ndarray
    active: np.ndarray
    _slopes: dict = field(default_factory=dict, repr=False)

    def value(self, S, activated=False):
        return float(np.interp(S, self.spots, self.active if activated else self.waiting))

    def delta(self, S, activated=False):
        return float(np.interp(S, self.spots, self._derivatives(activated)[0]))

    def gamma(self, S, activated=False):
        return float(np.interp(S, self.spots, self._derivatives(activated)[1]))

    def _derivatives(self, activated):
        if activated not in self._slopes:
            v = self.active if activated else self.waiting
            first = np.gradient(v, self.spots)
            self._slopes[activated] = (first, np.gradient(first, self.spots))
        return self._slopes[activated]


def price_down_in_put(S0, K, B, n_days, r, q, vol, days_per_year=365, monitor_days=None,
                      steps_per_day=8, n_space=600, grid_vol=None, width_sd=5.0, keep_daily=False):
    """Value a down-and-in put today, just after today's close has been checked.

    n_days        days until expiry on the chosen clock (expiry is always a checked close)
    vol           a number, or a function vol(t, S) returning local vols for an array of spots
    days_per_year 365 for calendar time (how market volatilities are quoted), 252 for trading days
    monitor_days  day offsets whose close checks the barrier; every day if not given
    grid_vol      volatility used only to size the grid; defaults to vol, or 30% for a function
    keep_daily    also return the solution at the end of every day, so one solve gives the value
                  function at every future close

    Returns a Solution (and a {day: Solution} dict if keep_daily).
    """
    vol_fn = vol if callable(vol) else (lambda t, S: np.full_like(S, float(vol)))
    grid_vol = grid_vol if grid_vol is not None else (0.3 if callable(vol) else float(vol))
    T = n_days / days_per_year
    checks = set(range(1, n_days + 1)) if monitor_days is None else set(monitor_days)

    # Log-spaced grid that covers several standard deviations plus the strike and barrier, shifted so
    # the barrier sits halfway between two nodes. That placement keeps the barrier switch accurate.
    half_width = width_sd * grid_vol * np.sqrt(max(T, 1 / days_per_year)) + abs(np.log(K / S0)) + abs(np.log(B / S0))
    dx = 2 * half_width / n_space
    start = np.log(B) + dx * (np.floor((np.log(S0) - half_width - np.log(B)) / dx) - 0.5)
    S = np.exp(start + dx * np.arange(n_space + 1))
    below = S <= B

    active = np.maximum(K - S, 0.0)
    waiting = np.where(below, active, 0.0)
    daily = {n_days: Solution(S, waiting.copy(), active.copy())} if keep_daily else None

    dt = 1 / (days_per_year * steps_per_day)
    smoothing_steps = 2
    for step in range(n_days * steps_per_day, 0, -1):
        sigma2 = vol_fn((step - 0.5) * dt, S) ** 2
        a = 0.5 * sigma2 / dx**2
        b = (r - q - 0.5 * sigma2) / (2 * dx)
        lower, diag, upper = a - b, -2 * a - r, a + b

        tau = T - (step - 1) * dt
        deep_itm = K * np.exp(-r * tau) - S[0] * np.exp(-q * tau)

        theta, substeps = (1.0, 2) if smoothing_steps else (0.5, 1)
        for _ in range(substeps):
            active = _theta_step(active, lower, diag, upper, dt / substeps, theta, deep_itm)
            waiting = _theta_step(waiting, lower, diag, upper, dt / substeps, theta, deep_itm)
        smoothing_steps = max(smoothing_steps - 1, 0)

        if (step - 1) % steps_per_day == 0:
            day = (step - 1) // steps_per_day
            if day in checks:
                waiting = np.where(below, active, waiting)
                smoothing_steps = 2
            if keep_daily:
                daily[day] = Solution(S, waiting.copy(), active.copy())

    result = Solution(S, waiting, active)
    return (result, daily) if keep_daily else result


def _theta_step(v, lower, diag, upper, h, theta, deep_itm):
    """One step back in time: (I - theta h L) v_new = (I + (1 - theta) h L) v_old."""
    n = len(v)
    rhs = v.copy()
    rhs[1:-1] += (1 - theta) * h * (lower[1:-1] * v[:-2] + diag[1:-1] * v[1:-1] + upper[1:-1] * v[2:])
    bands = np.zeros((3, n))
    bands[0, 2:] = -theta * h * upper[1:-1]
    bands[1, 1:-1] = 1 - theta * h * diag[1:-1]
    bands[2, :-2] = -theta * h * lower[1:-1]
    bands[1, 0] = bands[1, -1] = 1.0
    # Far below the grid the put is certain to be exercised; far above it is worthless.
    rhs[0], rhs[-1] = deep_itm, 0.0
    return solve_banded((1, 1), bands, rhs)
