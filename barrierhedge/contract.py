"""The contract studied and how its dates are laid out."""

from dataclasses import dataclass

import pandas as pd


@dataclass
class DownInPut:
    """A European down-and-in put on the S&P 500, bought by the dealer on `issue`.

    The barrier is checked at every close after issue up to and including the settlement close. If
    any of those closes is at or below the barrier, the option pays max(strike - S, 0) at settlement;
    otherwise it expires worthless. Strike and barrier are set as fractions of the issue-day close.
    """
    issue: pd.Timestamp
    exdate: pd.Timestamp          # the listed expiry the contract is matched to
    settle: pd.Timestamp          # last trading day on or before the expiry date
    spot_at_issue: float
    strike_pct: float = 1.00
    barrier_pct: float = 0.90

    @property
    def strike(self):
        return self.strike_pct * self.spot_at_issue

    @property
    def barrier(self):
        return self.barrier_pct * self.spot_at_issue


def check_offsets(valuation_date, check_dates):
    """Calendar-day offsets of the remaining barrier checks, as the PDE engine wants them."""
    remaining = check_dates[check_dates > valuation_date]
    return [(d - valuation_date).days for d in remaining]


def contract_schedule(market, start, end, target_days=63, every=5):
    """Issue dates and matched expiries for the replay.

    A new contract is issued every `every` trading days. Each one is matched to the standard monthly
    SPX expiry whose number of remaining closes is closest to `target_days` (and within roughly
    +/-40% of it), so listed puts with exactly the same expiry are available as hedges.
    """
    dates = market.trading_dates
    rows = []
    for issue in dates[(dates >= start) & (dates <= end)][::every]:
        best = None
        for exdate in market.monthly_expiries(issue):
            settle = dates[dates <= exdate][-1]
            n = int(((dates > issue) & (dates <= settle)).sum())
            if 0.65 * target_days <= n <= 1.45 * target_days and (best is None or abs(n - target_days) < abs(best[2] - target_days)):
                best = (pd.Timestamp(exdate), settle, n)
        if best and best[1] <= end:
            rows.append(dict(issue=issue, exdate=best[0], settle=best[1], n_checks=best[2]))
    return pd.DataFrame(rows)
