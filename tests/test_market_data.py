"""Checks against the real OptionMetrics data. Skipped when the licensed data isn't available."""

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import brentq

from barrierhedge import black_scholes as bs
from barrierhedge.market import DATA_DIR
from barrierhedge.pde import price_down_in_put

pytestmark = pytest.mark.skipif(not (DATA_DIR / "svi_params.parquet").exists(), reason="needs the OptionMetrics data")
DATE = pd.Timestamp("2024-03-01")


@pytest.fixture(scope="module")
def market():
    from barrierhedge.market import OptionMetrics
    return OptionMetrics()


@pytest.mark.parametrize("date, tolerance", [("2024-03-01", 0.003), ("2020-03-16", 0.01), ("2008-10-10", 0.01)])
def test_local_vol_reprices_listed_puts(market, date, tolerance):
    """Price listed puts in the local-vol model and compare implied vols with the market's: within 0.3 vol
    points on a calm day, within 1 point in the middle of the 2008 and 2020 crashes."""
    day, quotes = market.fit_quotes(pd.Timestamp(date))
    surf = market.surface(pd.Timestamp(date))
    days = int(quotes.loc[(quotes["days"] - 80).abs().idxmin(), "days"])
    expiry = quotes[quotes["days"] == days]
    T, r = days / 365, day.r(days / 365)
    vol = surf.local_vol_function(r=r, q=day.q)
    for pct in (0.85, 0.90, 0.95, 1.00):
        row = expiry.iloc[(expiry["strike"] - pct * day.spot).abs().argmin()]
        model = price_down_in_put(day.spot, row["strike"], 0.3 * day.spot, days, r, day.q, vol, n_space=800)
        price = model.value(day.spot, activated=True)
        model_iv = brentq(lambda s: bs.put(day.spot, row["strike"], T, r, day.q, s) - price, 0.01, 3)
        assert model_iv == pytest.approx(row["iv"], abs=tolerance)


def test_pde_agrees_with_monte_carlo_under_local_vol(market):
    day, surf = market.day(DATE), market.surface(DATE)
    checks = market.trading_dates[market.trading_dates > DATE][:63]
    offsets = [(d - DATE).days for d in checks]
    n_days, T = offsets[-1], offsets[-1] / 365
    r, q, S0 = day.r(T), day.q, day.spot
    K, B = S0, 0.9 * S0
    vol = surf.local_vol_function(r=r, q=q)
    pde = price_down_in_put(S0, K, B, n_days, r, q, vol, monitor_days=offsets, n_space=800).value(S0)

    rng = np.random.default_rng(1)
    n, sub = 60_000, 6
    dt = 1 / 365 / sub
    log_s, hit = np.full(n, np.log(S0)), np.zeros(n, bool)
    check_set = set(offsets)
    for step in range(n_days * sub):
        sigma = vol(step * dt + dt / 2, np.exp(log_s))
        log_s += (r - q - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n)
        if (step + 1) % sub == 0 and (step + 1) // sub in check_set:
            hit |= np.exp(log_s) <= B
    payoff = np.where(hit, np.maximum(K - np.exp(log_s), 0.0), 0.0) * np.exp(-r * T)
    standard_error = payoff.std() / np.sqrt(n)
    assert abs(payoff.mean() - pde) < 3 * standard_error
