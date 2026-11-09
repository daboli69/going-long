"""Run nflfastR PR 618 on one or more local seasons (see scripts/ep_pr618/README.md). Usage: python scripts/ep_pr618.py 2022 2023 ..."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RSCRIPT = Path(r"C:\Users\travi\R\R-4.6.2\bin\Rscript.exe")


def main(seasons):
    for s in seasons:
        csv = ROOT / "data" / "cache" / f"pbp{s}_for_r.csv"
        pd.read_parquet(ROOT / "data" / "raw" / f"play_by_play_{s}.parquet").to_csv(csv, index=False)
        subprocess.run([str(RSCRIPT), "scripts/ep_pr618/run.R", str(s)], cwd=ROOT, check=True)
        csv.unlink()
        print("done", s)


if __name__ == "__main__":
    main(sys.argv[1:] or ["2026"])
