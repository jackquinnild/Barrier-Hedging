"""Turn the OptionMetrics downloads from WRDS into the Parquet tables the code reads.

    python scripts/build_dataset.py [raw_folder] [output_folder]

Defaults are data/raw and data/clean. WRDS gives the CSVs random names, so each file is identified
from its header. See data/README.md for exactly which queries to run.

Output:
    spot.parquet          SPX open and close by day
    rates.parquet         zero-coupon curve (decimal, continuously compounded)
    divyield.parquet      SPX dividend yield (decimal)
    options_YYYY.parquet  SPX put quotes: strike in index points, bid, ask, implied vol, delta, vega
"""

import gzip
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SPX = 108105
MAX_DAYS = 400


def kind_of(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as f:
        cols = f.readline().strip().split(",")
    if "exdate" in cols and "strike_price" in cols:
        return "options"
    if "close" in cols:
        return "spot"
    if cols == ["date", "days", "rate"]:
        return "rates"
    if "rate" in cols and "secid" in cols:
        return "divyield"
    return "other"


def clean_options(chunk):
    c = chunk[(chunk["secid"] == SPX) & (chunk["cp_flag"] == "P")].copy()
    c["date"] = pd.to_datetime(c["date"])
    c["exdate"] = pd.to_datetime(c["exdate"])
    c["days"] = (c["exdate"] - c["date"]).dt.days
    c = c[c["days"].between(1, MAX_DAYS)]
    return pd.DataFrame({
        "date": c["date"],
        "exdate": c["exdate"],
        "days": c["days"].astype("int16"),
        "strike": c["strike_price"] / 1000.0,          # OptionMetrics stores strike x 1000
        "bid": c["best_bid"].astype("float32"),
        "ask": c["best_offer"].astype("float32"),
        "iv": c["impl_volatility"].astype("float32"),
        "delta": c["delta"].astype("float32"),
        "vega": c["vega"].astype("float32"),
        "optionid": c["optionid"].astype("int64"),
        # Standard monthly SPX options settle on the opening print; weeklies and dailies settle at the close.
        "am_settled": c["am_settlement"].fillna(0).astype("int8"),
    })


def main(raw=ROOT / "data" / "raw", out=ROOT / "data" / "clean"):
    raw, out = Path(raw), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for path in sorted(raw.glob("*.csv*")):
        files.setdefault(kind_of(path), []).append(path)

    spot = pd.concat(pd.read_csv(p, parse_dates=["date"]) for p in files["spot"])
    spot[["date", "open", "close"]].sort_values("date").to_parquet(out / "spot.parquet", index=False)

    rates = pd.concat(pd.read_csv(p, parse_dates=["date"]) for p in files["rates"])
    rates["rate"] /= 100
    rates.sort_values(["date", "days"]).to_parquet(out / "rates.parquet", index=False)

    div = pd.concat(pd.read_csv(p, parse_dates=["date"]) for p in files["divyield"])
    div = div.rename(columns={"rate": "q"})[["date", "q"]]
    div["q"] /= 100
    div.sort_values("date").to_parquet(out / "divyield.parquet", index=False)

    by_year = {}
    for path in files["options"]:
        for chunk in pd.read_csv(path, chunksize=2_000_000, low_memory=False):
            clean = clean_options(chunk)
            for year, part in clean.groupby(clean["date"].dt.year):
                by_year.setdefault(year, []).append(part)
    for year, parts in sorted(by_year.items()):
        df = pd.concat(parts).drop_duplicates(["date", "optionid"]).sort_values(["date", "exdate", "strike"])
        df.to_parquet(out / f"options_{year}.parquet", index=False)
        print(f"options_{year}: {len(df):,} quotes over {df['date'].nunique()} days")


if __name__ == "__main__":
    main(*sys.argv[1:3])
