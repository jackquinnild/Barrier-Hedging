"""Sanity check in a world where the right answer is known.

Simulate index paths from the local-vol model fitted on 2024-03-01, then delta-hedge the same
barrier option in that world with the true model (local vol) and with Black-Scholes at the strike's
implied vol. If the hedging machinery works, the true model's delta should leave far less risk.

    python scripts/run_synthetic.py [n_paths]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from barrierhedge.contract import check_offsets  # noqa: E402
from barrierhedge.ledger import DayInput, run_ledger  # noqa: E402
from barrierhedge.market import OptionMetrics  # noqa: E402
from barrierhedge.pde import price_down_in_put  # noqa: E402
from barrierhedge.stats import to_bp  # noqa: E402

DATE, TRADING_DAYS, INDEX_COST, SUBSTEPS = pd.Timestamp("2024-03-01"), 63, 0.0001, 8


def main(n_paths=2000, seed=7):
    market = OptionMetrics()
    day = market.day(DATE)
    surf = market.surface(DATE)
    dates = market.trading_dates
    path_dates = dates[dates >= DATE][: TRADING_DAYS + 1]
    offsets = check_offsets(DATE, path_dates[1:])
    n_days = offsets[-1]
    T = n_days / 365
    r, q = day.r(T), day.q
    K, B = day.spot, 0.9 * day.spot
    lv = surf.local_vol_function(r=r, q=q)
    strike_vol = float(surf.iv(np.log(K / day.forward(T)), T))

    grid = dict(days_per_year=365, monitor_days=offsets, n_space=800, keep_daily=True)
    _, true_model = price_down_in_put(day.spot, K, B, n_days, r, q, lv, **grid)
    _, black_scholes = price_down_in_put(day.spot, K, B, n_days, r, q, strike_vol, **grid)
    premium = true_model[0].value(day.spot)

    rng = np.random.default_rng(seed)
    dt = 1 / 365 / SUBSTEPS
    log_s = np.full(n_paths, np.log(day.spot))
    closes = {0: np.exp(log_s)}
    for step in range(n_days * SUBSTEPS):
        sigma = lv(step * dt + dt / 2, np.exp(log_s))
        log_s += (r - q - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal(n_paths)
        if (step + 1) % SUBSTEPS == 0 and (step + 1) // SUBSTEPS in offsets:
            closes[(step + 1) // SUBSTEPS] = np.exp(log_s)
    close_days = [0] + offsets
    S = np.column_stack([closes[d] for d in close_days])
    hit = np.maximum.accumulate(S <= B, axis=1)
    hit[:, 0] = False
    distance = np.log(S / B) / (float(surf.iv(0.0, T)) / np.sqrt(252))

    rows = []
    for p in range(n_paths):
        books = {"unhedged": [], "bs_strike": [], "local_vol": []}
        for j, d in enumerate(close_days):
            last = j == len(close_days) - 1
            spot, knocked = S[p, j], bool(hit[p, j])
            value = max(K - spot, 0.0) * knocked if last else true_model[d].value(spot, knocked)
            dt_next = (close_days[j + 1] - d) / 365 if not last else 0.0
            units = {"unhedged": 0.0,
                     "bs_strike": 0.0 if last else -black_scholes[d].delta(spot, knocked),
                     "local_vol": 0.0 if last else -true_model[d].delta(spot, knocked)}
            for rule in books:
                books[rule].append(DayInput(str(d), spot, value, units[rule], {}, {}, dt_next, r, q))
        outcome = "knocked in" if hit[p, -1] else ("near miss" if distance[p, 1:-1].min() < 2 else "stayed away")
        for rule, days in books.items():
            rows.append(dict(path=p, rule=rule, outcome=outcome,
                             bp=to_bp(run_ledger(days, premium, INDEX_COST)[-1]["portfolio_value"], day.spot)))

    df = pd.DataFrame(rows)
    table = df.pivot_table(index="rule", columns="outcome", values="bp", aggfunc="std").round(0)
    table["all paths"] = df.groupby("rule")["bp"].std().round(0)
    table.loc["paths"] = df[df.rule == "local_vol"].groupby("outcome").size().tolist() + [n_paths]
    table = table.rename(index={"bs_strike": "Black-Scholes, strike vol", "local_vol": "Local vol (the true model here)",
                                "unhedged": "No hedge", "paths": "number of paths"})
    text = ("## Synthetic check: local vol is the true model\n\n"
            f"{n_paths} paths simulated from the local-vol surface fitted on {DATE.date()}. "
            "Standard deviation of hedged P&L (bp of notional), by outcome.\n\n" + table.reset_index(names="").to_markdown(index=False) + "\n")
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "13_synthetic_check.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2000)
