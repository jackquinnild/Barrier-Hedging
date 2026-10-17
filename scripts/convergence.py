"""How fine does the PDE grid need to be? Compare coarser grids with a very fine reference.

The hard case is one day before expiry with the index just above the barrier, where delta and
gamma change fastest. Strike 100, barrier 90, 20% volatility, trading-day clock.

    python scripts/convergence.py
"""

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from barrierhedge.pde import price_down_in_put  # noqa: E402

R, Q, SIGMA = 0.04, 0.015, 0.20


def solve(days, **grid):
    return price_down_in_put(100, 100, 90, days, R, Q, SIGMA, days_per_year=252, **grid)


def main():
    ref_3m = solve(63, n_space=4800, steps_per_day=64)
    ref_1d = solve(1, n_space=4800, steps_per_day=64)
    rows = []
    for levels, steps in [(600, 1), (600, 2), (600, 4), (600, 8), (600, 16), (150, 8), (300, 8), (2400, 8)]:
        start = time.time()
        three_months = solve(63, n_space=levels, steps_per_day=steps)
        ms = 1000 * (time.time() - start)
        one_day = solve(1, n_space=levels, steps_per_day=steps)
        rows.append({"spot levels": levels, "steps per day": steps,
                     "price error, 3 months (%)": 100 * abs(three_months.value(100) / ref_3m.value(100) - 1),
                     "delta error at 90.4, 1 day": abs(one_day.delta(90.4) - ref_1d.delta(90.4)),
                     "gamma error at 91, 1 day (%)": 100 * abs(one_day.gamma(91) / ref_1d.gamma(91) - 1),
                     "ms per solve": ms})
    table = pd.DataFrame(rows).set_index(["spot levels", "steps per day"]).round(3)
    text = ("## Grid convergence\n\nErrors against a 4,800-level, 64-steps-per-day reference.\n\n"
            + table.reset_index().to_markdown(index=False) + "\n")
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "14_grid_convergence.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
