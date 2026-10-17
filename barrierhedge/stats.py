"""Statistics used to compare hedging rules.

Contracts are issued weekly and live about three months, so neighbouring contracts share most of
their market history. Confidence intervals therefore come from a block bootstrap that resamples whole
calendar quarters of issue dates instead of single contracts.
"""

import numpy as np
import pandas as pd


def expected_shortfall(x, tail=0.05):
    """Average of the worst `tail` fraction of outcomes."""
    x = np.sort(np.asarray(x, float))
    return x[: max(1, int(np.ceil(tail * len(x))))].mean()


def block_bootstrap(df, statistic, n=2000, seed=0, block="Q"):
    """90% interval for statistic(df), resampling blocks of contracts grouped by issue period."""
    rng = np.random.default_rng(seed)
    groups = [g for _, g in df.groupby(df["issue"].dt.to_period(block))]
    draws = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        draws.append(statistic(pd.concat([groups[i] for i in pick])))
    return tuple(np.percentile(draws, [5, 95]))


def to_bp(pnl, spot0):
    """Index points per option -> basis points of the notional at issue."""
    return pnl / spot0 * 1e4
