"""Turn the replay output into the tables quoted in the paper and README.

    python scripts/analyze.py

Reads output/<configuration>/ and writes results/*.md plus results/headline.json. All P&L figures are
in basis points of the notional at issue (index points / issue level x 10,000), per contract.
Rules are chosen on contracts issued 2005-2016 and judged on contracts issued 2017-2025.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from barrierhedge.market import DATA_DIR  # noqa: E402
from barrierhedge.stats import block_bootstrap, expected_shortfall, to_bp  # noqa: E402

OUT, RESULTS = ROOT / "output", ROOT / "results"
SPLIT = pd.Timestamp("2017-01-01")
NEAR_MISS = 2.0         # came within this many daily moves without knocking in
ZONES = [(-np.inf, 1, "under 1"), (1, 2, "1 to 2"), (2, 3, "2 to 3"), (3, 5, "3 to 5"), (5, np.inf, "over 5")]
LABELS = {
    "unhedged": "No hedge", "bs_strike": "Black-Scholes, strike vol", "bs_atm": "Black-Scholes, at-the-money vol",
    "bs_barrier": "Black-Scholes, barrier vol", "local_vol": "Local vol",
    "shift_up_1": "Local vol, barrier moved 1 move closer", "shift_up_0.5": "Local vol, barrier moved 0.5 move closer",
    "shift_down_0.5": "Local vol, barrier moved 0.5 move away", "shift_down_1": "Local vol, barrier moved 1 move away",
    "spread_1": "Put spread within 1 move", "spread_2": "Put spread within 2 moves", "spread_3": "Put spread within 3 moves",
    "spread_5": "Put spread within 5 moves", "spread_3_mid": "Put spread within 3 moves, at mid",
    "static": "Static hedge", "static_mid": "Static hedge, at mid", "vega": "Volatility hedge", "vega_mid": "Volatility hedge, at mid",
}
headline = {}


def load(name):
    folder = OUT / name
    daily = pd.read_parquet(folder / "daily.parquet")
    final = pd.read_parquet(folder / "final.parquet")
    contracts = pd.read_parquet(folder / "contracts.parquet")
    final = final.merge(contracts, on="issue")
    final["bp"] = to_bp(final["pnl"], final["spot0"])
    final["cost_bp"] = to_bp(final["index_costs"], final["spot0"])
    final["period"] = np.where(final["issue"] < SPLIT, "2005-16", "2017-25")
    final["outcome"] = np.where(final["knocked_in"], "knocked in",
                                np.where(final["min_distance"] < NEAR_MISS, "near miss", "stayed away"))
    daily = daily.merge(contracts[["issue", "spot0", "knocked_in"]], on="issue").sort_values(["rule", "issue", "date"])
    daily["bp"] = to_bp(daily["daily_pnl"], daily["spot0"])
    daily["vol_bp"] = to_bp(daily["vol_effect"], daily["spot0"])
    daily["period"] = np.where(daily["issue"] < SPLIT, "2005-16", "2017-25")
    # A day's P&L is earned on the hedge set at the previous close, so classify it by that close's state.
    g = daily.groupby(["rule", "issue"])
    daily["prev_distance"] = g["distance"].shift(1)
    daily["prev_activated"] = g["activated"].shift(1)
    daily = daily[daily["prev_distance"].notna()].copy()
    daily["zone"] = "knocked in"
    live = ~daily["prev_activated"].astype(bool)
    for lo, hi, label in ZONES:
        daily.loc[live & (daily["prev_distance"] >= lo) & (daily["prev_distance"] < hi), "zone"] = label
    return daily, final, contracts


def wide(final):
    return final.pivot_table(index=["issue", "period", "outcome"], columns="rule", values="bp").reset_index()


def fmt_ci(value, ci, digits=2):
    return f"{value:.{digits}f} [{ci[0]:.{digits}f}, {ci[1]:.{digits}f}]"


def table(df, path, title, note=""):
    text = f"## {title}\n\n" + (f"{note}\n\n" if note else "") + df.reset_index().to_markdown(index=False) + "\n"
    path.write_text(text)
    return text


def summary_table(final):
    rows = []
    for rule, g in final.groupby("rule"):
        row = {"rule": LABELS.get(rule, rule)}
        for period, p in [("all", g)] + list(g.groupby("period")):
            row[f"mean {period}"] = p["bp"].mean()
            row[f"std {period}"] = p["bp"].std()
        row["worst 5% avg"] = expected_shortfall(g["bp"])
        rows.append(row)
    order = [LABELS[r] for r in LABELS if r in set(final["rule"])]
    return pd.DataFrame(rows).set_index("rule").loc[order].round(0)


def delta_comparison(w):
    rows = []
    for rule in ("bs_strike", "bs_atm", "bs_barrier", "shift_up_0.5", "shift_up_1", "shift_down_0.5", "shift_down_1"):
        if rule not in w:
            continue
        row = {"compared with": LABELS[rule]}
        for period, g in [("all years", w)] + list(w.groupby("period")):
            ratio = lambda x, rule=rule: x["local_vol"].std() / x[rule].std()
            row[f"local vol / rule, {period}"] = fmt_ci(ratio(g), block_bootstrap(g, ratio, n=1000))
        rows.append(row)
    return pd.DataFrame(rows).set_index("compared with")


def concentration(daily, rule="local_vol"):
    d = daily[daily["rule"] == rule]
    total = (d["bp"] ** 2).sum()
    t = d.groupby("zone").agg(days=("bp", "size"), sq=("bp", lambda x: (x ** 2).sum()))
    t["share of days %"] = 100 * t["days"] / t["days"].sum()
    t["share of squared daily P&L %"] = 100 * t["sq"] / total
    order = [z for *_, z in ZONES] + ["knocked in"]
    return t.loc[[z for z in order if z in t.index], ["days", "share of days %", "share of squared daily P&L %"]].round(1)


def outcomes(final, rules=("unhedged", "local_vol", "bs_strike", "bs_barrier", "vega", "vega_mid")):
    rows = []
    for outcome, g in final.groupby("outcome"):
        for rule in rules:
            p = g[g["rule"] == rule]
            if p.empty:
                continue
            ci = block_bootstrap(p, lambda x: x["bp"].mean(), n=1000)
            rows.append({"outcome": outcome, "rule": LABELS[rule], "contracts": len(p),
                         "mean": fmt_ci(p["bp"].mean(), ci, 0), "worst 5% avg": round(expected_shortfall(p["bp"]))})
    return pd.DataFrame(rows).set_index(["outcome", "rule"])


def near_miss_attribution(daily, final):
    """Split each contract's local-vol-hedged P&L into the part from volatility (and rate) moves and the rest."""
    d = daily[daily["rule"] == "local_vol"]
    per = d.groupby("issue").agg(total=("bp", "sum"), volatility=("vol_bp", "sum"))
    per["index moves, time and hedging"] = per["total"] - per["volatility"]
    per = per.join(final[final["rule"] == "local_vol"].set_index("issue")[["outcome"]])
    t = per.groupby("outcome")[["total", "volatility", "index moves, time and hedging"]].mean().round(0)
    t["contracts"] = per.groupby("outcome").size()
    return t


def knock_in_paths(daily, market_open, contracts):
    d = daily[daily["rule"] == "local_vol"]
    rows = []
    for issue, g in d.groupby("issue"):
        hit = g[g["activated"].astype(bool) & ~g["prev_activated"].astype(bool)]
        if hit.empty:
            continue
        first = hit.iloc[0]
        barrier = contracts.set_index("issue").loc[issue, "barrier"]
        rows.append({"distance before": first["prev_distance"],
                     "opened below barrier": bool(market_open.get(first["date"], np.nan) <= barrier)})
    k = pd.DataFrame(rows)
    bins = pd.cut(k["distance before"], [-np.inf, 1, 2, 3, np.inf], labels=["under 1", "1 to 2", "2 to 3", "over 3"])
    t = bins.value_counts().sort_index().rename("knock-ins").to_frame()
    t["share %"] = (100 * t["knock-ins"] / len(k)).round(0)
    return t, k


def option_rules(w):
    rows = []
    for rule in ("spread_1", "spread_2", "spread_3", "spread_5", "spread_3_mid", "static", "static_mid", "vega", "vega_mid"):
        if rule not in w:
            continue
        row = {"rule": LABELS[rule]}
        for period, g in [("all years", w)] + list(w.groupby("period")):
            diff = lambda x, rule=rule: (x[rule] - x["local_vol"]).mean()
            row[f"mean vs local vol, {period}"] = fmt_ci(diff(g), block_bootstrap(g, diff, n=1000), 0)
            row[f"std ratio, {period}"] = round(g[rule].std() / g["local_vol"].std(), 2)
        rows.append(row)
    return pd.DataFrame(rows).set_index("rule")


def spread_selection(daily):
    """Pick the put-spread entry distance on 2005-16 by near-barrier daily risk, then check it on 2017-25."""
    near = daily[~daily["prev_activated"].astype(bool) & (daily["prev_distance"] < 3) & (daily["days_left"] > 0)]
    rms = lambda d: np.sqrt((d["bp"] ** 2).mean())
    picks = {e: rms(near[(near.period == "2005-16") & (near.rule == f"spread_{e}")]) for e in (1, 2, 3, 5)}
    best = min(picks, key=picks.get)
    rows = []
    for period in ("2005-16", "2017-25"):
        a = near[(near.period == period) & (near.rule == "local_vol")].set_index(["issue", "date"])["bp"]
        b = near[(near.period == period) & (near.rule == f"spread_{best}")].set_index(["issue", "date"])["bp"]
        j = pd.concat([a.rename("lv"), b.rename("sp")], axis=1).reset_index()
        ratio = lambda x: np.sqrt((x["sp"] ** 2).mean() / (x["lv"] ** 2).mean())
        rows.append({"period": period, "near-barrier days": len(j),
                     "daily risk, spread / local vol": fmt_ci(ratio(j), block_bootstrap(j, ratio, n=1000))})
    return best, pd.DataFrame(rows).set_index("period")


def by_year(w):
    t = w.groupby(w["issue"].dt.year).apply(lambda g: pd.Series({
        "contracts": len(g), "std BS strike vol": g["bs_strike"].std(), "std BS barrier vol": g["bs_barrier"].std(),
        "std local vol": g["local_vol"].std()}))
    t["local vol beats BS strike vol"] = t["std local vol"] < t["std BS strike vol"]
    t["local vol beats BS barrier vol"] = t["std local vol"] < t["std BS barrier vol"]
    return t.round(0)


def without_crises(final):
    """Drop every contract alive during the 2008 crisis (Sep 2008 - Mar 2009) or the 2020 crash (Feb - Apr 2020)."""
    crises = [(pd.Timestamp("2008-09-01"), pd.Timestamp("2009-03-31")), (pd.Timestamp("2020-02-01"), pd.Timestamp("2020-04-30"))]
    alive = lambda r: any(r["issue"] <= end and r["settle"] >= start for start, end in crises)
    keep = final[~final.apply(alive, axis=1)]
    w = wide(keep)
    rows = []
    for rule in ("bs_strike", "bs_atm", "bs_barrier", "static", "vega"):
        row = {"rule": LABELS[rule], "contracts": len(w)}
        if rule.startswith("bs"):
            ratio = lambda x, rule=rule: x["local_vol"].std() / x[rule].std()
            row["local vol std / rule std"] = fmt_ci(ratio(w), block_bootstrap(w, ratio, n=1000))
        else:
            diff = lambda x, rule=rule: (x[rule] - x["local_vol"]).mean()
            row["mean minus local vol (bp)"] = fmt_ci(diff(w), block_bootstrap(w, diff, n=1000), 0)
        rows.append(row)
    return pd.DataFrame(rows).set_index("rule")


def robustness(names):
    rows = []
    for name in names:
        if not (OUT / name / "final.parquet").exists():
            continue
        daily, final, contracts = load(name)
        w = wide(final)
        d = daily[daily["rule"] == "local_vol"]
        near = ~d["prev_activated"].astype(bool) & (d["prev_distance"] < 3)
        nm = final[(final.rule == "local_vol") & (final.outcome == "near miss")]
        row = {"design": name, "contracts": len(contracts), "knocked in": int(contracts["knocked_in"].sum())}
        for rule in ("bs_strike", "bs_atm", "bs_barrier"):
            ratio = lambda x, rule=rule: x["local_vol"].std() / x[rule].std()
            row[f"LV / {LABELS[rule]}"] = fmt_ci(ratio(w), block_bootstrap(w, ratio, n=500))
        row["days within 3 moves %"] = round(100 * near.mean(), 1)
        row["their share of squared P&L %"] = round(100 * (d["bp"][near] ** 2).sum() / (d["bp"] ** 2).sum(), 1)
        row["near-miss mean"] = np.round(nm["bp"].mean())
        for rule in ("static", "static_mid", "vega", "vega_mid", "spread_3", "spread_3_mid"):
            row[f"{LABELS[rule]} minus LV"] = round((w[rule] - w["local_vol"]).mean())
        rows.append(row)
    return pd.DataFrame(rows).set_index("design").T


def main():
    RESULTS.mkdir(exist_ok=True)
    daily, final, contracts = load("base")
    w = wide(final)
    market_open = pd.read_parquet(DATA_DIR / "spot.parquet").set_index("date")["open"]

    parts = []
    parts.append(table(summary_table(final), RESULTS / "01_summary.md", "Hedged P&L per contract (basis points of notional)",
                       f"{len(contracts)} contracts issued weekly, {contracts['issue'].min():%Y-%m} to {contracts['issue'].max():%Y-%m}; "
                       f"{int(contracts['knocked_in'].sum())} knocked in. Worst 5% avg is the average of the worst 5% of contracts."))
    parts.append(table(delta_comparison(w), RESULTS / "02_which_delta.md", "Spread of hedged P&L: local vol relative to other deltas",
                       "Ratio of standard deviations, with 90% intervals from a block bootstrap by issue quarter. Below 1 means local vol hedged better."))
    parts.append(table(concentration(daily), RESULTS / "03_where_risk_comes_from.md", "Where the hedging risk comes from (local-vol delta)",
                       "Days grouped by distance to the barrier at the previous close, in typical daily moves."))
    parts.append(table(outcomes(final), RESULTS / "04_outcomes.md", "P&L by what happened to the contract",
                       f"Near miss: came within {NEAR_MISS:g} daily moves of the barrier but never closed below it. This grouping uses hindsight; it describes outcomes and is not a trading rule."))
    parts.append(table(near_miss_attribution(daily, final), RESULTS / "05_why_near_misses_lose.md", "Where local-vol-hedged P&L comes from, by outcome",
                       "Average per contract. 'Volatility' is the change in the option's value caused by the day's volatility surface (and rates) moving, measured against yesterday's solution rolled forward to today's index level."))
    paths, raw = knock_in_paths(daily, market_open, contracts)
    parts.append(table(paths, RESULTS / "06_how_knock_ins_happen.md", "How far away the index was the day before it knocked in",
                       f"{len(raw)} knock-ins. {100 * raw['opened below barrier'].mean():.0f}% opened below the barrier, i.e. gapped through it overnight."))
    parts.append(table(option_rules(w), RESULTS / "07_option_hedges.md", "Hedges that use listed puts, compared with local-vol delta",
                       "Mean difference in bp per contract (90% interval) and ratio of standard deviations."))
    best, spread_test = spread_selection(daily)
    parts.append(table(spread_test, RESULTS / "08_spread_out_of_sample.md", f"Put-spread rule chosen on 2005-16 (enter within {best} daily moves), tested on 2017-25",
                       "Root-mean-square daily P&L on days within 3 moves of the barrier."))
    yearly = by_year(w)
    parts.append(table(yearly, RESULTS / "09_by_year.md", "Year by year (by issue year)"))
    cost5 = final.copy()
    cost5["bp"] -= 4 * cost5["cost_bp"]
    w5 = wide(cost5)
    parts.append(table(delta_comparison(w5).iloc[:3], RESULTS / "10_index_cost_5bp.md",
                       "Index trading at 5bp instead of 1bp", "The rules' decisions don't depend on costs, so the extra cost is added to the same trades."))
    parts.append(table(without_crises(final), RESULTS / "11_without_crises.md", "Leaving out the 2008 and 2020 crises",
                       "Contracts alive at any point in Sep 2008 - Mar 2009 or Feb - Apr 2020 are dropped."))
    robust = robustness(["base", "barrier_85", "barrier_95", "tenor_1m", "tenor_6m"])
    parts.append(table(robust, RESULTS / "12_robustness.md", "The main numbers under five contract designs",
                       "base: barrier 90%, 3 months. barrier_85 / barrier_95: other barrier levels. tenor_1m / tenor_6m: other maturities."))
    (RESULTS / "all_results.md").write_text("# All results\n\nGenerated by `scripts/analyze.py` from the replay output.\n\n" + "\n".join(parts))

    lv = w["local_vol"]
    headline.update({
        "contracts": len(contracts), "knock_ins": int(contracts["knocked_in"].sum()),
        "std": {r: round(float(w[r].std()), 1) for r in LABELS if r in w},
        "mean": {r: round(float(w[r].mean()), 1) for r in LABELS if r in w},
        "lv_over_bs_strike": round(float(lv.std() / w["bs_strike"].std()), 3),
        "lv_over_bs_barrier": round(float(lv.std() / w["bs_barrier"].std()), 3),
        "lv_over_bs_atm": round(float(lv.std() / w["bs_atm"].std()), 3),
        "years_lv_beats_bs_strike": int(yearly["local vol beats BS strike vol"].sum()),
        "years": len(yearly),
        "spread_entry_chosen": best,
        "knock_ins_from_over_2_moves_pct": round(float(100 * (raw["distance before"] >= 2).mean()), 1),
        "knock_ins_gapped_pct": round(float(100 * raw["opened below barrier"].mean()), 1),
    })
    (RESULTS / "headline.json").write_text(json.dumps(headline, indent=2, default=str))
    print((RESULTS / "all_results.md").read_text())


if __name__ == "__main__":
    main()
