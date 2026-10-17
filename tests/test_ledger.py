"""Ledger tests. The expected numbers were computed independently of the ledger code."""

import pytest

from barrierhedge.ledger import DayInput, run_ledger

KEYS = ["units", "cash", "option_value", "portfolio_value", "daily_pnl", "cum_costs"]


def check(result, expected):
    assert len(result) == len(expected)
    for got, want in zip(result, expected):
        for key, value in zip(KEYS, want):
            assert got[key] == pytest.approx(value, abs=1e-6), key


def test_1_no_hedge_pnl_is_payoff_minus_premium():
    days = [DayInput("d0", 100, 5, 0), DayInput("d1", 95, 8, 0), DayInput("d2", 92, 8, 0)]
    result = run_ledger(days, premium=5, index_cost=0.001)
    assert result[-1]["portfolio_value"] == pytest.approx(3.0)
    assert sum(r["daily_pnl"] for r in result) == pytest.approx(3.0)


def test_2_index_hedge_with_costs():
    days = [DayInput("d0", 100, 5, 0.5), DayInput("d1", 95, 8, 0.8), DayInput("d2", 92, 8, 0)]
    check(run_ledger(days, premium=5, index_cost=0.001), [
        (0.5, -55.05, 0, -0.05, -0.05, 0.05),
        (0.8, -83.5785, 0, 0.4215, 0.4715, 0.0785),
        (0.0, -2.0521, 0, -2.0521, -2.4736, 0.1521),
    ])


def test_3_options_interest_and_dividends():
    dt = 1 / 252
    days = [
        DayInput("d0", 100, 5, 0.5, {"P81": (-1.11, 0.40)}, {"P81": 0.45}, dt, 0.05, 0.015),
        DayInput("d1", 95, 8, 0.8, {"P81": (0.50, 0.95)}, {"P81": 0.90}, dt, 0.05, 0.015),
        DayInput("d2", 92, 8, 0, {}, {"P81": 0.0}, 0, 0.05, 0.015),
    ]
    check(run_ledger(days, premium=5, index_cost=0.0005), [
        (0.5, -54.581, -0.4995, -0.0805, -0.0805, 0.025),
        (0.8, -83.578104, -0.549, -0.127104, -0.046604, 0.03925),
        (0.0, -2.026964, 0.0, -2.026964, -1.89986, 0.07605),
    ])


def test_4_daily_pnl_adds_up_to_final_value():
    dt = 1 / 252
    days = [DayInput(f"d{i}", s, v, h, {}, {}, dt, 0.04, 0.01)
            for i, (s, v, h) in enumerate([(100, 3, 0.4), (98, 4, 0.55), (99, 3.5, 0.5), (97, 0, 0)])]
    days[-1].dt_next = 0
    result = run_ledger(days, premium=3, index_cost=0.0002)
    assert sum(r["daily_pnl"] for r in result) == pytest.approx(result[-1]["portfolio_value"])
