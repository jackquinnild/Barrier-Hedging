"""Draw every figure used in the paper, README and slides.

    python scripts/make_figures.py

Figures 1-2 need only the pricing code. Figure 3 needs the market data, and the rest need the replay
output in output/base.
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from barrierhedge.pde import price_down_in_put  # noqa: E402

FIG = ROOT / "figures"
INK, MUTED, GRID, SURFACE = "#1f1f1d", "#6b6a66", "#e6e5e1", "#ffffff"
BLUE, ORANGE, AQUA, GREY, RED = "#2a78d6", "#eb6834", "#1baf7a", "#a3a29d", "#c0392b"

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10.5, "axes.edgecolor": GREY, "axes.labelcolor": INK, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.major.size": 0, "ytick.major.size": 0, "axes.titlesize": 11.5, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.titlecolor": INK, "legend.frameon": False, "figure.dpi": 100,
    "savefig.dpi": 200, "savefig.bbox": "tight", "savefig.facecolor": SURFACE, "lines.linewidth": 2,
    "lines.solid_capstyle": "round",
})


def save(fig, name):
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)
    print("saved", name)


def signed(v):
    return "0" if round(v) == 0 else f"{v:+.0f}"


def note(ax, x, y, text, **kw):
    ax.annotate(text, (x, y), fontsize=9.5, color=MUTED, **kw)


# ---------- 1. what the contract pays ----------

def contract_diagram():
    days = np.arange(64)

    def path(drift_to, wiggle, seed_shift):
        r = np.random.default_rng(seed_shift)
        base = np.interp(days, [0, 20, 35, 63], drift_to)
        return base + np.cumsum(r.normal(0, wiggle, len(days))) * 0.25

    hit = path([100, 93, 88.5, 95], 0.9, 11)
    miss = path([100, 94, 91.5, 104], 0.9, 4)
    hit_day = int(np.argmax(hit <= 90))
    assert (hit <= 90).any() and not (miss[1:] <= 90).any()

    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.axhline(100, color=GREY, lw=1)
    ax.axhline(90, color=INK, lw=1.2)
    ax.plot(days, miss, color=GREY, lw=1.8)
    ax.plot(days, hit, color=BLUE, lw=2.2)
    ax.scatter([hit_day], [hit[hit_day]], s=55, color=BLUE, zorder=5, edgecolor="white", linewidth=1.5)
    ax.text(64.5, 100, "strike 100", va="center", fontsize=9.5, color=MUTED)
    ax.text(64.5, 90, "barrier 90", va="center", fontsize=9.5, color=INK)
    ax.annotate("closes below the barrier:\nthe put comes alive", (hit_day, hit[hit_day]), xytext=(6, 86),
                fontsize=9.5, color=MUTED, arrowprops=dict(arrowstyle="-", color=GREY, lw=0.8))
    ax.text(64.5, hit[-1], f"pays {100 - hit[-1]:.0f}", va="center", fontsize=9.5, color=BLUE, weight="bold")
    ax.text(64.5, miss[-1], "pays 0", va="center", fontsize=9.5, color=MUTED, weight="bold")
    closest = int(np.argmin(miss))
    ax.annotate("gets close but never closes below:\nexpires worthless", (closest, miss[closest]), xytext=(9, 104),
                fontsize=9.5, color=MUTED, arrowprops=dict(arrowstyle="-", color=GREY, lw=0.8))
    ax.set_xlim(0, 63)
    ax.set_ylim(84, 108)
    ax.set_xlabel("trading days after the dealer buys the option")
    ax.set_ylabel("S&P 500 (issue level = 100)")
    ax.set_title("A down-and-in put pays only if the index closes at or below the barrier")
    save(fig, "fig1_contract")


# ---------- 2. why it is hard to hedge near the barrier ----------

def near_barrier_profile():
    spots = np.linspace(86, 106, 500)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0))
    colors = {63: GREY, 21: AQUA, 5: ORANGE, 1: BLUE}
    for days, color in colors.items():
        sol = price_down_in_put(100.0, 100.0, 90.0, days, 0.04, 0.015, 0.20, days_per_year=252, n_space=1600)
        above = spots > 90.05
        below = spots < 89.95
        for mask in (above, below):
            knocked = not mask[-1]
            axes[0].plot(spots[mask], [sol.value(s, knocked) for s in spots[mask]], color=color)
            axes[1].plot(spots[mask], [sol.delta(s, knocked) for s in spots[mask]], color=color,
                         label=f"{days} day{'s' if days > 1 else ''} left" if not knocked else None)
    for ax in axes:
        ax.axvline(90, color=INK, lw=1)
        ax.set_xlabel("index level (strike 100, barrier 90)")
    axes[1].axhline(-1, color=GREY, lw=1)
    note(axes[1], 99, -1.55, "a normal put never\ngoes below -1")
    axes[0].set_title("Value")
    axes[1].set_title("Delta: index units to hold per option")
    axes[1].set_ylim(-4.6, 0.3)
    axes[1].legend(loc="lower right")
    axes[0].annotate("closing just below the barrier\nis worth far more than closing\njust above it", (90.1, 7.5),
                     xytext=(95.5, 9.5), fontsize=9.5, color=MUTED, arrowprops=dict(arrowstyle="-", color=GREY, lw=0.8))
    for ax in axes:
        ax.set_xticks(range(86, 107, 4))
    fig.tight_layout(w_pad=3)
    save(fig, "fig2_near_barrier")


# ---------- 3. models disagree on the same day ----------

def model_disagreement(date="2024-03-01"):
    from barrierhedge.market import OptionMetrics
    market = OptionMetrics()
    date = pd.Timestamp(date)
    day, surf = market.day(date), market.surface(date)
    dates = market.trading_dates
    checks = dates[dates > date][:63]
    offsets = [(d - date).days for d in checks]
    n_days, T = offsets[-1], offsets[-1] / 365
    r, q, S0 = day.r(T), day.q, day.spot
    K, B = S0, 0.9 * S0
    F = day.forward(T)
    vols = {"Black-Scholes, vol at the strike": (float(surf.iv(np.log(K / F), T)), ORANGE),
            "Black-Scholes, vol at the barrier": (float(surf.iv(np.log(B / F), T)), AQUA),
            "Local vol (uses the whole smile)": (surf.local_vol_function(r=r, q=q), BLUE)}
    spots = np.linspace(B * 1.003, S0 * 1.02, 300)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0))
    for label, (vol, color) in vols.items():
        sol = price_down_in_put(S0, K, B, n_days, r, q, vol, monitor_days=offsets, n_space=1000, grid_vol=0.3)
        axes[0].plot(spots / S0 * 100, [sol.value(s) / S0 * 100 for s in spots], color=color, label=label)
        axes[1].plot(spots / S0 * 100, [sol.delta(s) for s in spots], color=color)
    for ax in axes:
        ax.axvline(90, color=INK, lw=1)
        ax.set_xlabel("index level (issue = 100, barrier 90)")
    axes[0].set_title("Price (% of notional)")
    axes[1].set_title("Delta: index units to hold per option")
    axes[0].legend(loc="upper right", fontsize=9)
    fig.suptitle(f"Same option, same day ({date:%b %-d, %Y}), three answers", x=0.01, ha="left",
                 fontsize=12, weight="bold", color=INK)
    fig.tight_layout(w_pad=3)
    save(fig, "fig3_models_disagree")


# ---------- figures from the replay ----------

def load_base():
    out = ROOT / "output" / "base"
    daily = pd.read_parquet(out / "daily.parquet")
    final = pd.read_parquet(out / "final.parquet")
    contracts = pd.read_parquet(out / "contracts.parquet")
    return daily, final, contracts


def bp_axis(ax, axis="y"):
    fmt = FuncFormatter(lambda v, _: f"{v:,.0f}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def one_contract(daily, contracts, issue="2012-04-17"):
    issue = pd.Timestamp(issue)
    if issue not in set(contracts["issue"]):
        issue = contracts.iloc[(contracts["issue"] - issue).abs().argmin()]["issue"]
    c = contracts.set_index("issue").loc[issue]
    d = daily[(daily["issue"] == issue) & (daily["rule"] == "local_vol")].sort_values("date")
    cum = (d["daily_pnl"].cumsum() / c["spot0"] * 1e4)
    fig, axes = plt.subplots(3, 1, figsize=(8.2, 7.2), sharex=True, gridspec_kw={"height_ratios": [1.3, 1, 1]})
    axes[0].plot(d["date"], d["spot"], color=INK, lw=1.8)
    axes[0].axhline(c["barrier"], color=RED, lw=1.2)
    axes[0].text(d["date"].iloc[0], c["barrier"] + 6, "barrier", va="bottom", color=RED, fontsize=9.5)
    axes[0].set_title("S&P 500")
    axes[1].plot(d["date"], d["units"], color=BLUE)
    axes[1].axhline(1, color=GREY, lw=1)
    axes[1].set_title("Hedge: index units held per option")
    axes[2].plot(d["date"], cum, color=ORANGE)
    axes[2].axhline(0, color=GREY, lw=1)
    axes[2].set_title("Running hedged P&L (bp of notional)")
    low = d["spot"].idxmin()
    axes[0].scatter([d.loc[low, "date"]], [d.loc[low, "spot"]], s=45, color=INK, zorder=5, edgecolor="white", linewidth=1.5)
    axes[0].annotate(f"closest close: {100 * (d.loc[low, 'spot'] / c['barrier'] - 1):.1f}% above the barrier",
                     (d.loc[low, "date"], d.loc[low, "spot"]), xytext=(12, -4), textcoords="offset points",
                     fontsize=9.5, color=MUTED, va="top")
    import matplotlib.dates as mdates
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    fig.tight_layout(h_pad=1.5)
    save(fig, "fig6_one_contract")
    return issue, float(cum.iloc[-1])


def which_delta(final, contracts):
    from barrierhedge.stats import block_bootstrap
    w = final.merge(contracts[["issue", "spot0"]]).assign(bp=lambda x: x.pnl / x.spot0 * 1e4)
    w = w.pivot_table(index="issue", columns="rule", values="bp").reset_index()
    rules = [("bs_strike", "Black-Scholes, strike vol", ORANGE), ("bs_atm", "Black-Scholes, at-the-money vol", GREY),
             ("bs_barrier", "Black-Scholes, barrier vol", AQUA), ("local_vol", "Local vol", BLUE)]
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    for i, (rule, label, color) in enumerate(rules):
        std = w[rule].std()
        lo, hi = block_bootstrap(w, lambda x, rule=rule: x[rule].std(), n=1000)
        ax.barh(i, std, color=color, height=0.55)
        ax.plot([lo, hi], [i, i], color=INK, lw=1.2)
        ax.text(hi + 4, i, f"{std:.0f}", va="center", fontsize=10, color=INK)
    ax.set_yticks(range(len(rules)), [r[1] for r in rules])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("spread of hedged P&L across contracts (standard deviation, bp of notional)")
    ax.set_title("Which volatility the hedge uses matters more than which model")
    save(fig, "fig4_which_delta")


def risk_concentration(daily, contracts):
    d = daily[daily["rule"] == "local_vol"].merge(contracts[["issue", "spot0"]]).sort_values(["issue", "date"])
    g = d.groupby("issue")
    d["prev_distance"], d["prev_activated"] = g["distance"].shift(1), g["activated"].shift(1)
    d = d[d["prev_distance"].notna()]
    live = ~d["prev_activated"].astype(bool)
    zones = [("within 1 move", live & (d.prev_distance < 1)), ("1 to 2 moves", live & d.prev_distance.between(1, 2, "left")),
             ("2 to 3 moves", live & d.prev_distance.between(2, 3, "left")), ("3 to 5 moves", live & d.prev_distance.between(3, 5, "left")),
             ("more than 5 moves", live & (d.prev_distance >= 5)), ("after knock-in", ~live)]
    sq = (d["daily_pnl"] / d["spot0"] * 1e4) ** 2
    days = [100 * m.mean() for _, m in zones]
    risk = [100 * sq[m].sum() / sq.sum() for _, m in zones]
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    y = np.arange(len(zones))
    ax.barh(y - 0.19, days, height=0.36, color=GREY, label="share of days")
    ax.barh(y + 0.19, risk, height=0.36, color=BLUE, label="share of hedging risk")
    for i in range(len(zones)):
        ax.text(max(days[i], risk[i]) + 1, i, f"{days[i]:.1f}% of days, {risk[i]:.0f}% of risk", va="center", fontsize=9, color=MUTED)
    ax.set_yticks(y, [z for z, _ in zones])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 115)
    ax.set_xlabel("percent (risk = share of squared daily hedged P&L)")
    ax.set_title("Distance to the barrier at the previous close, in typical daily moves")
    ax.legend(loc="lower right")
    save(fig, "fig5_risk_concentration")
    near = zones[0][1] | zones[1][1] | zones[2][1]
    return 100 * near.mean(), 100 * sq[near].sum() / sq.sum()


def outcomes_and_attribution(daily, final, contracts):
    from barrierhedge.stats import block_bootstrap
    f = final.merge(contracts, on="issue").assign(bp=lambda x: x.pnl / x.spot0 * 1e4)
    f["outcome"] = np.where(f.knocked_in, "knocked in", np.where(f.min_distance < 2, "near miss", "stayed away"))
    lv = f[f.rule == "local_vol"]
    d = daily[daily.rule == "local_vol"].merge(contracts[["issue", "spot0"]])
    per = d.groupby("issue").apply(lambda g: pd.Series({"vol": (g.vol_effect / g.spot0).sum() * 1e4,
                                                        "total": (g.daily_pnl / g.spot0).sum() * 1e4}))
    per = per.join(lv.set_index("issue")["outcome"])
    order = ["stayed away", "near miss", "knocked in"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), gridspec_kw={"width_ratios": [1, 1.2]})
    for i, o in enumerate(order):
        g = lv[lv.outcome == o]
        mean = g.bp.mean()
        lo, hi = block_bootstrap(g, lambda x: x.bp.mean(), n=1000)
        color = ORANGE if o == "near miss" else GREY
        axes[0].bar(i, mean, color=color, width=0.55)
        axes[0].plot([i, i], [lo, hi], color=INK, lw=1.2)
        axes[0].text(i + 0.31, mean, signed(mean), ha="left", va="center", fontsize=10, color=INK)
    axes[0].axhline(0, color=GREY, lw=1)
    axes[0].set_xticks(range(3), [f"{o}\n({(lv.outcome == o).sum()})" for o in order])
    axes[0].grid(axis="x", visible=False)
    axes[0].set_title("Average hedged P&L (bp), local-vol delta")
    parts = per.groupby("outcome")[["vol", "total"]].mean().loc[order]
    parts["other"] = parts["total"] - parts["vol"]
    x = np.arange(3)
    axes[1].bar(x - 0.18, parts["vol"], width=0.34, color=BLUE, label="from volatility moving")
    axes[1].bar(x + 0.18, parts["other"], width=0.34, color=GREY, label="from index moves, time and hedging")
    axes[1].axhline(0, color=GREY, lw=1)
    axes[1].set_xticks(x, order)
    axes[1].grid(axis="x", visible=False)
    axes[1].legend(loc="upper center", fontsize=9)
    axes[1].set_title("Where it came from (bp)")
    fig.tight_layout(w_pad=3)
    save(fig, "fig7_near_misses")
    return parts


def option_hedges(final, contracts):
    from barrierhedge.stats import block_bootstrap
    w = final.merge(contracts[["issue", "spot0"]]).assign(bp=lambda x: x.pnl / x.spot0 * 1e4)
    w = w.pivot_table(index="issue", columns="rule", values="bp").reset_index()
    rows = [("Static hedge (textbook)", "static", "static_mid"), ("Put spread near the barrier", "spread_3", "spread_3_mid"),
            ("Volatility hedge", "vega", "vega_mid")]
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    for i, (label, paid, mid) in enumerate(rows):
        for rule, color, dy, tag in ((paid, ORANGE, -0.13, "paying bid/ask"), (mid, BLUE, 0.13, "at mid price")):
            diff = lambda x, rule=rule: (x[rule] - x["local_vol"]).mean()
            v = diff(w)
            lo, hi = block_bootstrap(w, diff, n=1000)
            ax.plot([lo, hi], [i + dy, i + dy], color=color, lw=1.4)
            ax.scatter([v], [i + dy], color=color, s=60, zorder=5, edgecolor="white", linewidth=1.5,
                       label=tag if i == 0 else None)
            ax.text(max(hi, 0) + 8, i + dy, signed(v), va="center", fontsize=9.5, color=INK)
    ax.axvline(0, color=INK, lw=1)
    ax.set_yticks(range(3), [r[0] for r in rows])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("average P&L versus a plain local-vol delta hedge (bp per contract, 90% interval)")
    ax.set_title("Adding listed puts: what it earns once you pay to trade")
    ax.legend(loc="lower left", fontsize=9)
    save(fig, "fig8_option_hedges")


def volatility_hedge(final, contracts):
    from barrierhedge.stats import block_bootstrap
    f = final.merge(contracts, on="issue").assign(bp=lambda x: x.pnl / x.spot0 * 1e4)
    f["outcome"] = np.where(f.knocked_in, "knocked in", np.where(f.min_distance < 2, "near miss", "stayed away"))
    order = ["stayed away", "near miss", "knocked in"]
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    x = np.arange(3)
    for rule, label, color, dx in (("local_vol", "local-vol delta only", GREY, -0.19),
                                   ("vega", "plus selling puts to hedge volatility", BLUE, 0.19)):
        for i, o in enumerate(order):
            g = f[(f.rule == rule) & (f.outcome == o)]
            mean = g.bp.mean()
            lo, hi = block_bootstrap(g, lambda d: d.bp.mean(), n=1000)
            ax.bar(i + dx, mean, width=0.36, color=color, label=label if i == 0 else None)
            ax.plot([i + dx, i + dx], [lo, hi], color=INK, lw=1.1)
            ax.text(i + dx, hi + 8 if mean >= 0 else lo - 8, signed(mean), ha="center",
                    va="bottom" if mean >= 0 else "top", fontsize=9.5, color=INK)
    ax.axhline(0, color=INK, lw=1)
    counts = f[f.rule == "local_vol"].outcome.value_counts()
    ax.set_xticks(x, [f"{o}\n({counts[o]} contracts)" for o in order])
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("average hedged P&L (bp)")
    ax.set_title("Hedging volatility moves the losses into crashes rather than removing them")
    ax.legend(loc="lower left", fontsize=9)
    ax.set_ylim(-230, 150)
    save(fig, "fig9_volatility_hedge")


def main():
    contract_diagram()
    near_barrier_profile()
    model_disagreement()
    if (ROOT / "output" / "base" / "final.parquet").exists():
        daily, final, contracts = load_base()
        issue, pnl = one_contract(daily, contracts)
        which_delta(final, contracts)
        days, risk = risk_concentration(daily, contracts)
        outcomes_and_attribution(daily, final, contracts)
        option_hedges(final, contracts)
        volatility_hedge(final, contracts)
        (ROOT / "results" / "figure_notes.json").write_text(json.dumps(
            {"story_contract": str(issue.date()), "story_pnl_bp": round(pnl), "near_days_pct": round(days, 1),
             "near_risk_pct": round(risk, 1)}, indent=2))


if __name__ == "__main__":
    main()
