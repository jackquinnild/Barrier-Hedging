"""Fit an SVI volatility surface to every trading day's SPX put quotes and save the parameters.

    python scripts/calibrate_surfaces.py

Writes svi_params.parquet (one row per day and expiry) into the data folder. Takes about half an hour
on 13 processes for 2005-2025.
"""

import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from barrierhedge.market import OptionMetrics  # noqa: E402
from barrierhedge.vol_surface import VolSurface  # noqa: E402

START, END = pd.Timestamp("2005-01-01"), pd.Timestamp("2025-06-30")
_market = None


def _init():
    global _market
    _market = OptionMetrics()


def fit_day(date):
    try:
        day, quotes = _market.fit_quotes(date)
        surf = VolSurface.calibrate(quotes, day.spot, day.r(0.25), day.q)
        return [dict(date=date, T=s.T, a=s.a, b=s.b, rho=s.rho, m=s.m, s=s.s, rmse_vol=s.rmse_vol,
                     density_ok=s.density_ok()) for s in surf.slices]
    except Exception as exc:
        return [dict(date=date, T=np.nan, error=repr(exc)[:100])]


def main():
    market = OptionMetrics()
    dates = [d for d in market.trading_dates if START <= d <= END]
    with Pool(13, initializer=_init) as pool:
        rows = [r for day in pool.imap(fit_day, dates, chunksize=20) for r in day]
    params = pd.DataFrame(rows)
    params.to_parquet(market.dir / "svi_params.parquet", index=False)
    fitted = params.dropna(subset=["T"])
    print(f"{fitted['date'].nunique()} of {len(dates)} days fitted, {len(fitted)} expiries; "
          f"median fit error {100 * fitted['rmse_vol'].median():.2f} vol points; "
          f"butterfly condition holds on {fitted['density_ok'].mean():.1%} of expiries")


if __name__ == "__main__":
    main()
