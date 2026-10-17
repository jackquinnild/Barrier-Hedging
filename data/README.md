# Data

The study uses OptionMetrics IvyDB US through WRDS. The data is licensed, so it isn't in this
repository; anyone with WRDS access (many universities have it) can rebuild it.

## Queries

Download each as gzipped CSV with dates as YYYY-MM-DD, from 2005-01-01 onward, into `data/raw/`.
The S&P 500 index has SECID 108105.

| Query (WRDS menu) | Filters | Variables |
|---|---|---|
| Option Prices | SECID 108105, puts only, European, index (the build script keeps expiries up to 400 days out) | secid, date, exdate, cp_flag, strike_price, best_bid, best_offer, impl_volatility, delta, vega, optionid, am_settlement |
| Security Prices | SECID 108105 | date, open, close |
| Zero Coupon Yield Curve | none | date, days, rate |
| Index Dividend Yield | SECID 108105 | secid, date, rate |

Large option queries are easier in a few date chunks. File names don't matter; the build script
recognises each file from its columns.

## Build

```
python scripts/build_dataset.py        # data/raw -> data/clean
python scripts/calibrate_surfaces.py   # adds data/clean/svi_params.parquet
```

Set `BARRIER_DATA` to use a different folder for the cleaned files.
