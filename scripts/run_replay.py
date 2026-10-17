"""Run the historical replay for one or more configurations.

    python scripts/run_replay.py                 # every configuration
    python scripts/run_replay.py base tenor_1m   # selected ones
    python scripts/run_replay.py base --limit 20 # quick check on 20 contracts

Results go to output/<configuration>/ (daily.parquet, final.parquet, contracts.parquet). The base run
takes about 40 minutes on 13 processes; the others 10-30 minutes each.
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from barrierhedge.replay import CONFIGS, run  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("configs", nargs="*", default=list(CONFIGS))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--processes", type=int, default=13)
    args = parser.parse_args()
    for name in args.configs:
        start = time.time()
        daily, final, contracts = run(CONFIGS[name], processes=args.processes, limit=args.limit)
        out = ROOT / "output" / (name if not args.limit else f"{name}_sample")
        out.mkdir(parents=True, exist_ok=True)
        daily.to_parquet(out / "daily.parquet", index=False)
        final.to_parquet(out / "final.parquet", index=False)
        contracts.to_parquet(out / "contracts.parquet", index=False)
        print(f"{name}: {len(contracts)} contracts, {contracts['knocked_in'].sum()} knocked in, "
              f"{time.time() - start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
