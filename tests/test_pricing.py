import math

import pytest

from barrierhedge import black_scholes as bs
from barrierhedge.binomial import price_down_and_in_tree
from barrierhedge.pde import price_down_in_put

S, K, B, R, Q, SIGMA, DAYS = 100.0, 100.0, 90.0, 0.04, 0.015, 0.20, 63
T = DAYS / 252


def daily_pde(**kw):
    return price_down_in_put(S, K, B, DAYS, R, Q, SIGMA, days_per_year=252, **kw)


def test_tree_reference_case():
    assert price_down_and_in_tree(100.0, 105.0, 95.0, 100, 2, 1.1, 0.9, 0.5, 1.0, {1, 2}) == pytest.approx(750.0)


def test_closed_form_matches_quantlib():
    ql = pytest.importorskip("QuantLib")
    today = ql.Date(2, 1, 2024)
    ql.Settings.instance().evaluationDate = today
    dc = ql.Actual365Fixed()
    expiry = today + 91
    process = ql.BlackScholesMertonProcess(
        ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, Q, dc)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, R, dc)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), SIGMA, dc)))
    option = ql.BarrierOption(ql.Barrier.DownIn, B, 0.0, ql.PlainVanillaPayoff(ql.Option.Put, K),
                              ql.EuropeanExercise(expiry))
    option.setPricingEngine(ql.AnalyticBarrierEngine(process))
    tq = dc.yearFraction(today, expiry)
    assert bs.down_in_put(S, K, B, tq, R, Q, SIGMA) == pytest.approx(option.NPV(), rel=1e-9)


def test_knocked_in_state_is_a_plain_put():
    assert daily_pde().value(S, activated=True) == pytest.approx(bs.put(S, K, T, R, Q, SIGMA), rel=1e-4)


def test_daily_checks_match_bgk_shift():
    assert daily_pde().value(S) == pytest.approx(bs.down_in_put_daily(S, K, B, T, R, Q, SIGMA), rel=0.005)


def test_pde_matches_binomial_tree():
    steps_per_day = 40
    n = DAYS * steps_per_day
    dt = T / n
    up = math.exp(SIGMA * math.sqrt(dt))
    p = (math.exp((R - Q) * dt) - 1 / up) / (up - 1 / up)
    tree = price_down_and_in_tree(S, K, B, 1, n, up, 1 / up, p, math.exp(-R * dt),
                                  {k * steps_per_day for k in range(1, DAYS + 1)})
    assert daily_pde().value(S) == pytest.approx(tree, rel=0.015)


def test_fewer_checks_make_knock_in_cheaper():
    assert daily_pde().value(S) < bs.down_in_put(S, K, B, T, R, Q, SIGMA)


def test_grid_convergence():
    coarse = daily_pde(n_space=400, steps_per_day=4).value(S)
    fine = daily_pde(n_space=1600, steps_per_day=16).value(S)
    assert coarse == pytest.approx(fine, rel=0.003)


def test_daily_snapshots_match_a_fresh_solve():
    _, snapshots = daily_pde(keep_daily=True)
    later = price_down_in_put(S, K, B, DAYS - 10, R, Q, SIGMA, days_per_year=252)
    for spot in (92.0, 100.0, 108.0):
        assert snapshots[10].value(spot) == pytest.approx(later.value(spot), rel=0.01)


def test_black_scholes_greeks_match_bumps():
    h = 1e-4
    assert bs.put_delta(S, K, T, R, Q, SIGMA) == pytest.approx(
        (bs.put(S + h, K, T, R, Q, SIGMA) - bs.put(S - h, K, T, R, Q, SIGMA)) / (2 * h), rel=1e-5)
    assert bs.vega(S, K, T, R, Q, SIGMA) == pytest.approx(
        bs.put(S, K, T, R, Q, SIGMA + 0.01) - bs.put(S, K, T, R, Q, SIGMA), rel=0.02)
