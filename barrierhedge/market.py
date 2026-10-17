"""Access to the cleaned OptionMetrics data: index closes, rates, dividends, put quotes and fitted surfaces.

The data itself is licensed and not part of this repository. scripts/build_dataset.py turns the WRDS
downloads into the Parquet files read here; the folder can be set with the BARRIER_DATA environment
variable (default: data/clean inside the repository).
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from barrierhedge.vol_surface import SVISlice, VolSurface

DATA_DIR = Path(os.environ.get("BARRIER_DATA", Path(__file__).resolve().parent.parent / "data" / "clean"))


@dataclass
class MarketDay:
    date: pd.Timestamp
    spot: float
    q: float
    rate_days: np.ndarray
    rate_values: np.ndarray

    def r(self, T):
        """Zero rate for maturity T years (linear in days, flat beyond the curve's ends)."""
        return float(np.interp(T * 365, self.rate_days, self.rate_values))

    def forward(self, T):
        return self.spot * np.exp((self.r(T) - self.q) * T)


@dataclass
class Quote:
    bid: float
    ask: float
    mid: float
    delta: float


class Chain:
    """Listed puts for one date and one expiry.

    Asking for a strike that isn't quoted that day returns a quote interpolated between the
    neighbouring strikes rather than jumping to a different contract, so a position's mark doesn't
    lurch on days a strike drops out of the data.
    """

    def __init__(self, strikes, bid, ask, delta):
        order = np.argsort(strikes)
        self.strikes = np.asarray(strikes, float)[order]
        self.bid = np.asarray(bid, float)[order]
        self.ask = np.asarray(ask, float)[order]
        self.delta = np.asarray(delta, float)[order]
        self.settlement_spot = None

    def fill_missing_deltas(self, model_delta):
        """About 1% of quotes come without a delta; use model_delta(strike) for those."""
        for i in np.flatnonzero(np.isnan(self.delta)):
            self.delta[i] = model_delta(self.strikes[i])
        return self

    @classmethod
    def at_expiry(cls, spot):
        chain = cls([], [], [], [])
        chain.settlement_spot = spot
        return chain

    def quote(self, k):
        if self.settlement_spot is not None:
            value = max(k - self.settlement_spot, 0.0)
            return Quote(value, value, value, -1.0 if k > self.settlement_spot else 0.0)
        bid, ask, delta = (float(np.interp(k, self.strikes, arr)) for arr in (self.bid, self.ask, self.delta))
        return Quote(bid, ask, 0.5 * (bid + ask), delta)

    def nearest(self, level):
        if self.settlement_spot is not None or len(self.strikes) == 0:
            return float(level)
        return float(self.strikes[np.abs(self.strikes - level).argmin()])

    def bracket(self, level, width):
        """Two listed strikes roughly `width` apart with `level` between them, for a put spread."""
        if self.settlement_spot is not None or len(self.strikes) < 2:
            return float(level + width / 2), float(level - width / 2)
        above, below = self.strikes[self.strikes > level], self.strikes[self.strikes < level]
        if len(above) == 0 or len(below) == 0:
            return float(level + width / 2), float(level - width / 2)
        hi = above[np.abs(above - (level + width / 2)).argmin()]
        lo = below[np.abs(below - (level - width / 2)).argmin()]
        return float(hi), float(lo)


class OptionMetrics:
    def __init__(self, data_dir=DATA_DIR):
        self.dir = Path(data_dir)
        spot = pd.read_parquet(self.dir / "spot.parquet").set_index("date").sort_index()
        self.close = spot["close"]
        self.open = spot["open"]
        self.div_yield = pd.read_parquet(self.dir / "divyield.parquet").set_index("date")["q"]
        rates = pd.read_parquet(self.dir / "rates.parquet")
        self.rates = {d: (g["days"].to_numpy(float), g["rate"].to_numpy(float)) for d, g in rates.groupby("date")}
        self.trading_dates = pd.DatetimeIndex(self.close.index)
        self._svi = None

    def day(self, date):
        curve_date = date
        while curve_date not in self.rates:     # bond-market holidays such as Veterans Day
            curve_date -= pd.Timedelta(days=1)
        days, values = self.rates[curve_date]
        return MarketDay(date, float(self.close[date]), float(self.div_yield[date]), days, values)

    def options(self, year):
        return _load_options(self.dir, year)

    def fit_quotes(self, date):
        """One day's put quotes in the form the surface fit wants (standard monthly expiries only)."""
        day = self.day(date)
        o = self.options(date.year)
        o = o[(o["date"] == date) & (o["am_settled"] == 1) & (o["bid"] > 0) & o["iv"].notna()].copy()
        T = o["days"] / 365
        forward = day.spot * np.exp((np.array([day.r(t) for t in T]) - day.q) * T)
        o["k"] = np.log(o["strike"] / forward)
        return day, o

    def monthly_expiries(self, date):
        o = self.options(date.year)
        return np.sort(o.loc[(o["date"] == date) & (o["am_settled"] == 1), "exdate"].unique())

    def chain(self, date, exdate):
        o = self.options(date.year)
        g = o[(o["date"] == date) & (o["exdate"] == exdate)]
        return Chain(g["strike"].to_numpy(), g["bid"].to_numpy(), g["ask"].to_numpy(), g["delta"].to_numpy())

    def surface(self, date):
        """The fitted surface for `date` (or the latest earlier day with one), from the SVI cache."""
        if self._svi is None:
            params = pd.read_parquet(self.dir / "svi_params.parquet").dropna(subset=["T"])
            self._svi = {d: g for d, g in params.groupby("date")}
        fit_date = date
        while fit_date not in self._svi:
            fit_date -= pd.Timedelta(days=1)
        day = self.day(date)
        slices = [SVISlice(r.T, r.a, r.b, r.rho, r.m, r.s, r.rmse_vol) for r in self._svi[fit_date].itertuples()]
        return VolSurface(slices, day.spot, day.r(0.25), day.q)


@lru_cache(maxsize=3)
def _load_options(data_dir, year):
    return pd.read_parquet(Path(data_dir) / f"options_{year}.parquet")
