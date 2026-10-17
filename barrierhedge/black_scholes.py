"""Closed-form Black-Scholes prices and Greeks.

Units used across the project: index levels in points, time in years, rates and dividend yields
continuously compounded, volatility annualised. Prices are per one unit of the index.
"""

import math

from scipy.stats import norm

# Broadie, Glasserman and Kou (1997): a barrier checked every dt behaves like a continuously
# monitored barrier moved away from spot by exp(BGK_BETA * sigma * sqrt(dt)).
BGK_BETA = 0.5826


def _d1(S, K, T, r, q, sigma):
    return (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))


def put(S, K, T, r, q, sigma):
    if T <= 0:
        return max(K - S, 0.0)
    d1 = _d1(S, K, T, r, q, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def put_delta(S, K, T, r, q, sigma):
    if T <= 0:
        return -1.0 if K > S else 0.0
    return -math.exp(-q * T) * norm.cdf(-_d1(S, K, T, r, q, sigma))


def vega(S, K, T, r, q, sigma):
    """Change in price for a one-point (0.01) rise in volatility. Same for puts and calls."""
    if T <= 0:
        return 0.0
    return 0.01 * S * math.exp(-q * T) * norm.pdf(_d1(S, K, T, r, q, sigma)) * math.sqrt(T)


def down_in_put(S, K, B, T, r, q, sigma):
    """Continuously monitored down-and-in put with strike above the barrier and no rebate.

    Reiner and Rubinstein (1991), in the notation of Haug's formula collection. If spot is already
    at or below the barrier the option has knocked in and is worth a vanilla put.
    """
    if S <= B:
        return put(S, K, T, r, q, sigma)
    if T <= 0:
        return 0.0
    v = sigma * math.sqrt(T)
    mu = (r - q - 0.5 * sigma**2) / sigma**2
    disc_s, disc_k = S * math.exp(-q * T), K * math.exp(-r * T)
    x2 = math.log(S / B) / v + (1 + mu) * v
    y1 = math.log(B * B / (S * K)) / v + (1 + mu) * v
    y2 = math.log(B / S) / v + (1 + mu) * v
    reflect_s, reflect_k = (B / S) ** (2 * (mu + 1)), (B / S) ** (2 * mu)
    term_b = -disc_s * norm.cdf(-x2) + disc_k * norm.cdf(-x2 + v)
    term_c = -disc_s * reflect_s * norm.cdf(y1) + disc_k * reflect_k * norm.cdf(y1 - v)
    term_d = -disc_s * reflect_s * norm.cdf(y2) + disc_k * reflect_k * norm.cdf(y2 - v)
    return term_b - term_c + term_d


def down_in_put_daily(S, K, B, T, r, q, sigma, dt=1 / 252):
    """Approximate price when the barrier is only checked once per dt, using the BGK barrier shift."""
    shifted = B * math.exp(-BGK_BETA * sigma * math.sqrt(dt))
    return down_in_put(S, K, shifted, T, r, q, sigma)
