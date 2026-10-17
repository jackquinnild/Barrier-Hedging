# Hedging a barrier option near the barrier

This project studies how a bank should hedge a down-and-in put on the S&P 500 as the market falls toward the barrier. A new hypothetical contract is bought every week from 2005 to 2025 (1,018 in total) and hedged every trading day with that day's fitted volatility surface and actual listed-option bid/ask quotes. Seventeen hedging strategies are compared. The emphasis is on the approach to the barrier, where the hedge is hardest to get right, and on judging every rule on years that weren't used to choose it.

The full write-up is [paper/paper.pdf](paper/paper.pdf) (also readable as [paper/paper.md](paper/paper.md)).

![Two paths of the index: one closes below the barrier and the put pays, one comes close and pays nothing](figures/fig1_contract.png)

## Why I built it

I first came across barrier options in a derivatives course at the London School of Economics. On paper they're a small twist on an ordinary put: the option only comes alive if the index closes at or below a trigger level. What caught my attention was what that twist does to the Greeks. Near the barrier, delta can call for several times more stock than an ordinary put ever needs, and it can flip within a day. I wanted to know what that means for the person who actually has to hedge one, and whether the textbook answers hold up on real prices.

I developed the idea with mentors in Carnegie Mellon's Sales and Trading Academy, who pushed me toward the version a dealer actually faces. Banks usually end up owning these options, because investors sell them inside structured notes in exchange for a higher coupon, and the question on a desk is less "what is it worth" than "how do I hedge it this week". Their questions shaped which hedges I tested and how I judged them.

The result changed my emphasis. I expected the interesting answer to be which listed options to add near the barrier. None of them reduced risk once trading costs were paid; the one that made money did it by selling crash protection. The biggest improvement came from something much simpler: which volatility the delta is computed with. And the losses for the option's owner turned out to sit in near misses, not in the crashes the option exists for.

## Main result

Local volatility gave the steadiest hedged P&L, but most of its advantage comes from using the right volatility rather than from the model. A plain Black-Scholes delta that uses the implied volatility at the barrier gets within 10% of local vol, and the remaining gap isn't statistically significant.

| Delta used for the hedge | Average P&L (bp) | Spread of P&L (bp) | Worst 5% average (bp) |
|---|---:|---:|---:|
| Black-Scholes, volatility at the strike | -40 | 185 | -241 |
| Black-Scholes, at-the-money volatility | -44 | 162 | -241 |
| Black-Scholes, volatility at the barrier | -22 | 139 | -271 |
| Local volatility | -3 | 125 | -274 |

P&L is in basis points of the notional at issue, per contract, across 1,018 contracts issued 2005-01 to 2025-03 (145 knocked in). "Spread" is the standard deviation across contracts, which is what a hedge is meant to shrink.

Local vol's spread is 0.68 times that of strike-vol Black-Scholes (90% interval 0.57 to 0.81) and 0.57 on the 2017-2025 test years (0.42 to 0.80). Against barrier-vol Black-Scholes the ratio is 0.90 (0.82 to 1.04). The advantage isn't steady: local vol beat strike-vol Black-Scholes in 11 of 21 years, winning large in stressed years (2018: 71 versus 369) and losing in calm ones (2023: 110 versus 35). Without the contracts alive during the 2008 crisis and the 2020 crash, barrier-vol Black-Scholes hedges as well as local vol (ratio 1.05, 0.98 to 1.13), so the full model's extra edge comes from the worst periods.

![Spread of hedged P&L by delta](figures/fig4_which_delta.png)

## Where the losses come from

**The risk sits near the barrier.** Days within three typical daily moves of the barrier are 2.8% of contract-days and produce 23% of the squared daily hedged P&L. Days within one move are 0.5% of the sample and 5% of the risk.

**Near misses lose; knock-ins don't.** With the local-vol hedge, contracts that came within two daily moves of the barrier and never closed below it lost 83 bp on average (-132 to -33). Contracts that knocked in made 23 (-39 to 83) and those that stayed away made 0. Splitting each day's P&L into the part caused by the volatility surface moving and everything else puts about half of the near-miss loss on volatility falling after the scare. The grouping uses hindsight, so it describes outcomes rather than a trading rule.

**Many knock-ins can't be hedged by trading the index.** Of the 145 knock-ins, 27% came from more than two daily moves away in a single day, and 15% opened below the barrier, gapping through it overnight.

![Average hedged P&L by outcome, and how much came from volatility](figures/fig7_near_misses.png)

## Adding listed options

| Strategy, compared with a plain local-vol delta hedge | Paying bid/ask (bp) | At mid prices (bp) |
|---|---:|---:|
| Static hedge (Carr, Ellis and Gupta, 1998) | -168 | +39 |
| Put spread sold within three daily moves of the barrier | -12 | 0 |
| Volatility hedge: sell puts struck at the barrier | +40 | +65 |

The static hedge copies the barrier with a fixed portfolio of puts, including a narrow put spread around the barrier sized to the jump. That spread needs dozens of contracts per option, paid for twice: once when sold and again, often in a crisis, when bought back. At mid prices the idea works, partly because selling S&P 500 puts has historically paid; after costs it loses badly.

The put-spread rule, with its entry distance chosen on 2005-2016, cut near-barrier daily risk by 13% in those years and by 3% in 2017-2025 (0 to 6%). It didn't survive.

The volatility hedge targets the near-miss loss directly and does cut it, from -83 to -19 bp. Contracts that stayed away earned 78 instead of 0. But contracts that knocked in lost 160 instead of making 23, because the sold puts gain exactly when the market breaks through. It earns 40 bp more on average (21 to 57) with the same spread of results and a worse bad tail (-324 versus -274). It moves the risk into crashes rather than removing it.

## Model design

**Contract.** A European down-and-in put on the S&P 500, strike at the issue-day close, barrier 10% below. The barrier is checked at every daily close up to expiry; if any close is at or below it, the option pays like an ordinary put, otherwise nothing. Expiry is matched to the standard monthly SPX expiry nearest three months out, so listed puts with the same expiry exist as hedges.

**Volatility surface.** For each listed expiry, an SVI curve (a five-parameter shape for the skew) is fitted to that day's put quotes by vega-weighted least squares. Total implied variance is interpolated linearly across expiries, expiries that would allow a calendar arbitrage are dropped, and Dupire's formula converts the surface into local volatility. 5,154 trading days are fitted, with a median fit error of 0.25 volatility points.

**Pricing.** A Crank-Nicolson finite-difference grid in log-spot, which is the continuous version of a binomial tree. Each grid point carries two values: one if the barrier has already been hit (a plain put) and one if it hasn't. At every checked close, points at or below the barrier take the first value. The jump this creates is smoothed with Rannacher time-stepping. One solve gives the price, delta and gamma at every index level. Keeping the solution at each later day lets the replay split each day's change in value into what came from the index moving and what came from the surface moving.

**Hedging rules.** Every rule holds index units equal to minus the total delta of what it owns:
- Black-Scholes delta at three choices of volatility (strike, at the money, barrier)
- local-vol delta
- local-vol delta with the barrier shifted half a move or one move either way, a habit some desks use to smooth the hedge
- a put spread around the barrier switched on at 1, 2, 3 or 5 daily moves away
- the Carr-Ellis-Gupta static hedge
- a volatility hedge, resized only when it drifts more than 25% from target

The three option strategies are also run at mid prices to separate the idea from the cost of trading it.

**Trading and bookkeeping.** Decisions use only that close's information and execute at the close. The index costs 1 bp to trade; listed puts are bought at the ask and sold at the bid. Positions are matched to listed strikes when opened. A ledger tracks cash, interest at the zero-curve rate, dividends on index held, and option positions, and produces each day's P&L.

## Testing the result

- Anything with a setting (the put-spread entry distance) is chosen on contracts issued 2005-2016 and judged on 2017-2025.
- Contracts overlap, since one starts every week and each lasts three months, so confidence intervals come from a block bootstrap that resamples whole calendar quarters of issue dates.
- The study is repeated with the barrier at 85% and 95%, with one-month and six-month contracts, with 5 bp index costs, and without the 2008 and 2020 crises ([results/12_robustness.md](results/12_robustness.md)). Every pattern repeats. With the barrier only 5% away, the strike's and barrier's volatilities are close, and local vol's edge over strike-vol Black-Scholes is no longer significant.
- Contracts that approached the barrier and retreated are included, not only those that knocked in.

The machinery is checked separately:
- The pricer matches the closed-form continuous barrier price to nine decimal places (against QuantLib), the Broadie-Glasserman-Kou daily-monitoring approximation within 0.5%, a binomial tree within 1.5%, and a Monte Carlo simulation under real local volatility within three standard errors.
- Fitted surfaces reprice listed puts within about 0.1 volatility points on a calm day and within 1 point in the 2008 and 2020 crashes.
- An end-to-end replay on a synthetic flat-volatility market reproduces the exact unhedged P&L.
- In a simulated world where local vol is the true model, the local-vol hedge leaves 95 bp of spread against 224 for Black-Scholes ([results/13_synthetic_check.md](results/13_synthetic_check.md)).

## What I'd test next

The barrier is decided by the 4pm closing print, and every hedge in this study trades at that same close, after the outcome is known. With intraday data, the obvious next question is whether adjusting the hedge during the day, on days the index is near the barrier, reduces the near-miss loss. The other gap is the volatility model. Local vol is known to misjudge how the skew moves when the index moves, and the near-miss attribution depends on it; repeating the replay with a stochastic-local-volatility comparator would show how much of the "volatility" share survives a model with more realistic dynamics.

## Reading path and repository map

| Path | Purpose |
|---|---|
| `barrierhedge/black_scholes.py` | Closed-form put, Greeks, continuous barrier price and the BGK daily-check approximation |
| `barrierhedge/binomial.py` | Binomial-tree barrier pricer, the starting point of the project |
| `barrierhedge/pde.py` | Crank-Nicolson pricer with daily barrier checks and local volatility |
| `barrierhedge/vol_surface.py` | SVI fitting, surface interpolation and Dupire local volatility |
| `barrierhedge/market.py` | Reads the cleaned OptionMetrics data; option chains with interpolation for missing strikes |
| `barrierhedge/contract.py` | Contract terms and the issue/expiry schedule |
| `barrierhedge/hedges.py` | The hedging strategies |
| `barrierhedge/ledger.py` | Cash, positions and daily P&L |
| `barrierhedge/replay.py` | The day-by-day historical replay |
| `barrierhedge/stats.py` | Expected shortfall and the block bootstrap |
| `scripts/build_dataset.py` | Turns the WRDS downloads into Parquet tables |
| `scripts/calibrate_surfaces.py` | Fits and caches the volatility surface for every trading day |
| `scripts/run_replay.py` | Runs the replay for the five contract designs |
| `scripts/run_synthetic.py` | The known-model sanity check |
| `scripts/convergence.py` | How fine the pricing grid needs to be |
| `scripts/analyze.py` | Every results table, written to `results/` |
| `scripts/make_figures.py` | Every figure, written to `figures/` |
| `scripts/build_paper.py` | Renders the paper to PDF |
| `results/` | The tables quoted in the paper; [results/all_results.md](results/all_results.md) has them on one page |
| `tests/` | 42 tests: pricing, surfaces, hedges, ledger, an end-to-end replay on a synthetic market, and four checks against the real data that skip without it |

## Reproduce

Python 3.11 was used for the saved results.

```
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

The OptionMetrics data is licensed and can't be shared. [data/README.md](data/README.md) lists the WRDS queries. With the downloads in `data/raw/`, run the scripts in this order:

```
python scripts/build_dataset.py
python scripts/calibrate_surfaces.py   # about 25 minutes on 13 cores
python scripts/run_replay.py           # about 75 minutes for all five designs
python scripts/run_synthetic.py
python scripts/convergence.py
python scripts/analyze.py
python scripts/make_figures.py
python scripts/build_paper.py          # needs Google Chrome for the PDF
```

## Limitations

- The barrier options are hypothetical and have no market quotes, so their daily value and purchase price come from the local-vol model. Every strategy shares the same mark, which mostly cancels in the comparisons but affects average P&L.
- The split of near-miss losses into "volatility" and "everything else" depends on local vol's view of how the skew moves and is approximate.
- Trades happen at the close with that close's information. Standard monthly SPX options settle on the next morning's opening prices; the study treats them as settling at the close.
- One strike level (100% of the issue-day close) is tested. Barrier level and maturity are varied; strike is not.
- Many strategies and settings were compared on the same history, and the intervals are not adjusted for multiple comparisons.
