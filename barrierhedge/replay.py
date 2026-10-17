"""Historical replay: buy a hypothetical down-and-in put every week from 2005 to 2025 and hedge it
every day with real market data.

For each contract and each close:
  - load that day's index close, rates, dividend yield and fitted volatility surface,
  - re-price the barrier option with the local-vol PDE (this is also the mark, since barrier options
    have no public quotes) and compute every model's delta,
  - let each hedging rule decide what to hold, using nothing but that close's information,
  - trade the index at a small cost and listed puts at that day's actual bid/ask.

The ledger then turns each rule's decisions into a daily P&L.
"""

from dataclasses import dataclass
from multiprocessing import Pool

import numpy as np
import pandas as pd

from barrierhedge import black_scholes as bs
from barrierhedge.contract import DownInPut, check_offsets, contract_schedule
from barrierhedge.hedges import DeltaHedge, SpreadOverlay, StaticHedge, Unhedged, VegaHedge, View
from barrierhedge.ledger import DayInput, run_ledger
from barrierhedge.market import Chain, OptionMetrics
from barrierhedge.pde import price_down_in_put

GRID = dict(days_per_year=365, n_space=400, steps_per_day=6, grid_vol=0.3)
SHIFTS = {"shift_up_1": -1.0, "shift_up_0.5": -0.5, "shift_down_0.5": 0.5, "shift_down_1": 1.0}


@dataclass(frozen=True)
class Config:
    name: str = "base"
    strike_pct: float = 1.00
    barrier_pct: float = 0.90
    target_days: int = 63            # trading days to expiry
    rules: str = "full"              # "full" for the main run, "core" for the robustness runs
    index_cost: float = 0.0001       # 1 basis point per unit of index traded
    spread_width: float = 0.01       # put spreads span about 1% of the barrier level
    start: str = "2005-01-03"
    end: str = "2025-06-27"          # last date with option quotes in the data
    every: int = 5                   # issue a new contract every 5 trading days


CONFIGS = {
    "base": Config(),
    "barrier_85": Config(name="barrier_85", barrier_pct=0.85, rules="core"),
    "barrier_95": Config(name="barrier_95", barrier_pct=0.95, rules="core"),
    "tenor_1m": Config(name="tenor_1m", target_days=21, rules="core"),
    "tenor_6m": Config(name="tenor_6m", target_days=126, rules="core"),
}


def make_rules(K, B, width, cfg):
    rules = [Unhedged(K, B)] + [DeltaHedge(K, B, m) for m in ("bs_strike", "bs_atm", "bs_barrier", "local_vol")]
    if cfg.rules == "full":
        rules += [DeltaHedge(K, B, m) for m in SHIFTS]
        rules += [SpreadOverlay(K, B, enter, width) for enter in (1.0, 2.0, 3.0, 5.0)]
    else:
        rules += [SpreadOverlay(K, B, 3.0, width)]
    rules += [SpreadOverlay(K, B, 3.0, width, at_mid=True),
              StaticHedge(K, B, width), StaticHedge(K, B, width, at_mid=True),
              VegaHedge(K, B), VegaHedge(K, B, at_mid=True)]
    return rules


@dataclass
class Close:
    """What the replay knows about the contract at one close."""
    value: float                  # local-vol value of the barrier option: its daily mark
    deltas: dict
    vega: float = 0.0
    gap: float = 0.0
    distance: float = np.inf      # ln(spot / barrier) in typical daily moves
    days_left: int = 0
    chain: Chain = None
    put_vega: object = None
    snapshots: dict = None        # the local-vol solution at every later day, for the volatility attribution


def settle(S, K, activated):
    deltas = {name: 0.0 for name in ("bs_strike", "bs_atm", "bs_barrier", "local_vol", *SHIFTS)}
    return Close(max(K - S, 0.0) if activated else 0.0, deltas, chain=Chain.at_expiry(S), put_vega=lambda k: 0.0)


def price_close(market, cfg, date, day, K, B, checks, activated, exdate):
    """Price the barrier option at one close and gather everything the hedging rules need."""
    S = day.spot
    surf = market.surface(date)
    offsets = check_offsets(date, checks)
    n_days = offsets[-1]
    T = n_days / 365
    r = day.r(T)
    forward = day.forward(T)

    def implied_vol(strike):
        return float(surf.iv(np.log(strike / forward), T))

    def solve(vol, barrier=B, **kw):
        return price_down_in_put(S, K, barrier, n_days, r, day.q, vol, monitor_days=offsets, **GRID, **kw)

    lv = surf.local_vol_function(r=r, q=day.q)
    solution, snapshots = solve(lv, keep_daily=True)
    value = solution.value(S, activated)

    deltas = {"local_vol": solution.delta(S, activated)}
    flat_vols = {"bs_strike": implied_vol(K), "bs_atm": implied_vol(forward), "bs_barrier": implied_vol(B)}
    for name, sigma in flat_vols.items():
        deltas[name] = solve(sigma).delta(S, activated)

    daily_move = flat_vols["bs_atm"] / np.sqrt(252)
    if cfg.rules == "full":
        for name, shift in SHIFTS.items():
            deltas[name] = deltas["local_vol"] if activated else \
                solve(lv, barrier=B * np.exp(-shift * daily_move)).delta(S, False)

    chain = market.chain(date, exdate).fill_missing_deltas(
        lambda k: bs.put_delta(S, k, T, r, day.q, implied_vol(k)))
    return Close(value=value, deltas=deltas,
                 vega=solve(lv.with_bump(0.01)).value(S, activated) - value,
                 gap=solution.value(S, True) - solution.value(S, False),
                 distance=np.log(S / B) / daily_move, days_left=len(offsets), chain=chain,
                 put_vega=lambda k: bs.vega(S, k, T, r, day.q, implied_vol(k)), snapshots=snapshots)


def run_contract(market, cfg, row):
    dates = market.trading_dates
    path = dates[(dates >= row["issue"]) & (dates <= row["settle"])]
    checks = path[1:]
    c = DownInPut(row["issue"], row["exdate"], row["settle"], market.day(row["issue"]).spot,
                  cfg.strike_pct, cfg.barrier_pct)
    K, B = c.strike, c.barrier
    rules = make_rules(K, B, cfg.spread_width * B, cfg)
    books = {rule.name: [] for rule in rules}
    traded, rows = set(), []
    activated, premium, yesterday = False, None, None

    for j, date in enumerate(path):
        last = j == len(path) - 1
        day = market.day(date)
        S = day.spot
        activated = activated or (j > 0 and S <= B)
        now = settle(S, K, activated) if last else \
            price_close(market, cfg, date, day, K, B, checks, activated, row["exdate"])
        if j == 0:
            premium = now.value
        if not last and len(now.chain.strikes) == 0:     # no quotes for this expiry today: reuse yesterday's
            now.chain = yesterday.chain

        # The part of today's change in value caused by the volatility surface (and rates) moving: compare
        # today's value with yesterday's solution carried forward to today's index level.
        vol_effect = 0.0
        if yesterday is not None:
            vol_effect = now.value - yesterday.snapshots[(date - path[j - 1]).days].value(S, activated)

        view = View(j, S, activated, now.deltas, now.vega, now.gap, now.distance, now.chain, now.put_vega, last)
        decisions = {}
        for rule in rules:
            decisions[rule.name] = rule.step(view)
            traded |= set(decisions[rule.name][1])
        marks = {k: now.chain.quote(k).mid for k in traded}
        dt_next = (path[j + 1] - date).days / 365 if not last else 0.0
        for name, (units, trades) in decisions.items():
            books[name].append(DayInput(str(date.date()), S, now.value, units, trades, marks, dt_next,
                                        day.r(max(dt_next, 1 / 365)), day.q))
        rows.append(dict(date=date, spot=S, activated=activated, distance=np.nan if last else now.distance,
                         days_left=now.days_left, value=now.value, gap=now.gap, vega=now.vega, vol_effect=vol_effect))
        yesterday = now

    state = pd.DataFrame(rows)
    daily, final = [], []
    for rule in rules:
        ledger = run_ledger(books[rule.name], premium, cfg.index_cost)
        daily.append(state.assign(rule=rule.name, issue=c.issue, units=[x["units"] for x in ledger],
                                  daily_pnl=[x["daily_pnl"] for x in ledger]))
        final.append(dict(issue=c.issue, rule=rule.name, pnl=ledger[-1]["portfolio_value"],
                          index_costs=ledger[-1]["cum_costs"]))
    info = dict(issue=c.issue, exdate=c.exdate, settle=c.settle, spot0=c.spot_at_issue, strike=K, barrier=B,
                premium=premium, knocked_in=activated, min_distance=float(np.nanmin(state["distance"])))
    return pd.concat(daily, ignore_index=True), pd.DataFrame(final), info


_market = None


def _worker_init():
    global _market
    _market = OptionMetrics()


def _worker(args):
    cfg, row = args
    return run_contract(_market, cfg, row)


def run(cfg, processes=13, limit=None, progress=print):
    """Replay every contract in the configuration. Returns (daily, final, contracts) DataFrames."""
    market = OptionMetrics()
    schedule = contract_schedule(market, pd.Timestamp(cfg.start), pd.Timestamp(cfg.end), cfg.target_days, cfg.every)
    if limit:
        schedule = schedule.iloc[np.linspace(0, len(schedule) - 1, limit).astype(int)]
    jobs = [(cfg, row) for row in schedule.to_dict("records")]
    daily, final, info = [], [], []
    with Pool(processes, initializer=_worker_init) as pool:
        for i, (d, f, meta) in enumerate(pool.imap_unordered(_worker, jobs, chunksize=2), 1):
            daily.append(d)
            final.append(f)
            info.append(meta)
            if i % 100 == 0:
                progress(f"  {cfg.name}: {i}/{len(jobs)} contracts")
    return (pd.concat(daily, ignore_index=True), pd.concat(final, ignore_index=True),
            pd.DataFrame(info).sort_values("issue", ignore_index=True))
