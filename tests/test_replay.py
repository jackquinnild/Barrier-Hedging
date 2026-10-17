"""End-to-end replay on a made-up market where every answer is known: flat 20% volatility, constant
rates, and listed puts priced by Black-Scholes with a fixed bid/ask spread."""

import math

import numpy as np
import pandas as pd
import pytest

from barrierhedge import black_scholes as bs
from barrierhedge.market import Chain, MarketDay
from barrierhedge.replay import Config, run_contract
from barrierhedge.vol_surface import SVISlice, VolSurface

VOL, R, Q = 0.20, 0.03, 0.01


class FlatMarket:
    def __init__(self, closes):
        self.trading_dates = pd.bdate_range("2024-01-02", periods=len(closes))
        self.close = pd.Series(closes, index=self.trading_dates)
        self.exdate = self.trading_dates[-1]

    def day(self, date):
        return MarketDay(date, float(self.close[date]), Q, np.array([1.0, 730.0]), np.array([R, R]))

    def surface(self, date):
        slices = [SVISlice(T, VOL**2 * T, 0.0, 0.0, 0.0, 0.1) for T in (0.05, 0.25, 1.0)]
        return VolSurface(slices, float(self.close[date]), R, Q)

    def monthly_expiries(self, date):
        return [self.exdate]

    def chain(self, date, exdate):
        S, T = float(self.close[date]), (exdate - date).days / 365
        strikes = np.arange(60.0, 121.0)
        mids = np.array([bs.put(S, k, T, R, Q, VOL) for k in strikes])
        deltas = [bs.put_delta(S, k, T, R, Q, VOL) for k in strikes]
        return Chain(strikes, np.maximum(mids - 0.05, 0), mids + 0.05, deltas)


def replay(closes):
    market = FlatMarket(closes)
    row = dict(issue=market.trading_dates[0], exdate=market.exdate, settle=market.exdate)
    return market, *run_contract(market, Config(rules="core"), row)


NEAR_MISS = list(np.linspace(100, 91, 15)) + list(np.linspace(91.5, 99, 15))
KNOCK_IN = list(np.linspace(100, 92, 12)) + [88.0] + list(np.linspace(89, 86, 12))


@pytest.fixture(scope="module", params=[NEAR_MISS, KNOCK_IN], ids=["near_miss", "knock_in"])
def result(request):
    return replay(request.param)


def test_unhedged_pnl_is_payoff_minus_financed_premium(result):
    market, daily, final, info = result
    days = (info["settle"] - info["issue"]).days
    payoff = max(info["strike"] - market.close.iloc[-1], 0.0) if info["knocked_in"] else 0.0
    expected = payoff - info["premium"] * math.exp(R * days / 365)
    assert final.set_index("rule").loc["unhedged", "pnl"] == pytest.approx(expected, abs=1e-9)


def test_daily_pnl_adds_up(result):
    _, daily, final, _ = result
    total = daily.groupby("rule")["daily_pnl"].sum()
    assert np.allclose(final.set_index("rule")["pnl"], total.loc[final["rule"]].to_numpy(), atol=1e-9)


def test_knock_in_flag(result):
    market, _, _, info = result
    assert info["knocked_in"] == bool((market.close.iloc[1:] <= info["barrier"]).any())


def test_all_deltas_agree_when_volatility_is_flat(result):
    _, daily, _, _ = result
    units = daily.pivot_table(index="date", columns="rule", values="units").iloc[:-1]
    for rule in ("bs_strike", "bs_atm", "bs_barrier"):
        assert np.allclose(units[rule], units["local_vol"], atol=0.02)


def test_no_volatility_effect_when_the_surface_never_moves(result):
    _, daily, _, info = result
    state = daily[daily.rule == "local_vol"]
    assert state["vol_effect"].abs().max() < 0.01 * max(info["premium"], 1.0)


def test_vega_hedge_sells_puts_before_knock_in(result):
    _, daily, _, _ = result
    state = daily[daily.rule == "local_vol"].iloc[0]
    assert state["vega"] > 0
