import numpy as np
import pytest

from barrierhedge.hedges import SpreadOverlay, StaticHedge, VegaHedge, View, static_weights
from barrierhedge.market import Chain

K, B = 100.0, 90.0


def put_payoff(strike, s):
    return np.maximum(strike - s, 0.0)


def test_static_portfolio_reproduces_the_reflected_payoff():
    hi, lo = 90.01, 89.99
    legs = static_weights(K, B, hi, lo)
    s = np.array([60.0, 75.0, 81.0, 85.0, 89.9, 90.1, 95.0, 110.0])
    portfolio = sum(q * put_payoff(k, s) for k, q in legs.items())
    target = np.where(s < B, (K - s) + (K / B) * np.maximum(s - B * B / K, 0.0), 0.0)
    assert np.allclose(portfolio, target, atol=1e-6)


def chain(strikes=np.arange(70.0, 111.0, 1.0), spot=95.0):
    mids = put_payoff(strikes, spot) + 1.0
    return Chain(strikes, mids - 0.1, mids + 0.1, -np.clip((strikes - 70) / 40, 0, 1))


def view(day=0, distance=10.0, activated=False, gap=2.0, vega=0.5, c=None, last=False):
    return View(day, 95.0, activated, {"local_vol": -0.4}, vega, gap, distance, c or chain(),
                lambda k: 0.1, last)


def test_trades_cross_the_spread_unless_at_mid():
    rule = StaticHedge(K, B, width=2.0)
    _, trades = rule.step(view())
    for k, (qty, price) in trades.items():
        q = chain().quote(k)
        assert price == (q.ask if qty > 0 else q.bid)
    rule_mid = StaticHedge(K, B, width=2.0, at_mid=True)
    _, trades = rule_mid.step(view())
    assert all(price == chain().quote(k).mid for k, (_, price) in trades.items())


def test_static_hedge_sells_the_portfolio_then_closes_at_knock_in():
    rule = StaticHedge(K, B, width=2.0)
    rule.step(view())
    assert sum(rule.held.values()) < 0          # net short puts
    rule.step(view(day=1))
    assert rule.held                            # held while the barrier hasn't been hit
    rule.step(view(day=2, activated=True))
    assert not rule.held


def test_spread_overlay_enters_near_the_barrier_and_leaves_on_retreat():
    rule = SpreadOverlay(K, B, enter=2.0, width=2.0)
    rule.step(view(distance=5.0))
    assert not rule.held
    rule.step(view(distance=1.5, gap=4.0))
    (hi, short), (lo, long_) = sorted(rule.held.items(), reverse=True)
    assert hi > B > lo and short < 0 < long_ and long_ == pytest.approx(4.0 / (hi - lo))
    rule.step(view(distance=2.5))                # inside the exit band: keep it
    assert rule.held
    rule.step(view(distance=3.5))
    assert not rule.held


def test_vega_hedge_sells_puts_and_only_resizes_outside_its_band():
    rule = VegaHedge(K, B, band=0.25)
    rule.step(view(vega=0.5))
    assert rule.held[rule.strike] == pytest.approx(-5.0)
    _, trades = rule.step(view(day=1, vega=0.55))   # 10% change: inside the band
    assert not trades
    _, trades = rule.step(view(day=2, vega=0.8))
    assert rule.held[rule.strike] == pytest.approx(-8.0)


def test_hedge_offsets_the_options_delta():
    rule = SpreadOverlay(K, B, enter=2.0, width=2.0)
    units, _ = rule.step(view(distance=1.0))
    assert units == pytest.approx(0.4 - rule.option_delta(view()))


def test_chain_interpolates_missing_strikes_and_fills_missing_deltas():
    c = Chain([90.0, 100.0], [1.0, 5.0], [1.2, 5.4], [np.nan, -0.5]).fill_missing_deltas(lambda k: -0.2)
    q = c.quote(95.0)
    assert (q.bid, q.ask) == pytest.approx((3.0, 3.3))
    assert c.quote(90.0).delta == pytest.approx(-0.2)
    assert c.bracket(95.0, 4.0) == (100.0, 90.0)
    settled = Chain.at_expiry(92.0)
    assert settled.quote(100.0).mid == 8.0 and settled.quote(90.0).mid == 0.0
