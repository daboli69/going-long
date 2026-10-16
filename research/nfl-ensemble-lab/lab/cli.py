"""Command line entry points (the dashboard calls the same functions).

  python -m lab.cli refresh [--force]
  python -m lab.cli train
  python -m lab.cli predict [--season S --week W]
  python -m lab.cli report
"""
from __future__ import annotations

import argparse
import json


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="lab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--force", action="store_true")
    sub.add_parser("train")
    p = sub.add_parser("predict")
    p.add_argument("--season", type=int)
    p.add_argument("--week", type=int)
    sub.add_parser("report")
    a = ap.parse_args(argv)
    if a.cmd == "refresh":
        from .data_pipeline import refresh_data
        print(json.dumps(refresh_data(force=a.force), indent=2))
    elif a.cmd == "train":
        from .training import run_training
        print(json.dumps(run_training()["summary"], indent=2, default=str))
    elif a.cmd == "predict":
        from .weekly import run_weekly
        out = run_weekly(season=a.season, week=a.week)
        print(json.dumps({k: str(v) for k, v in out["paths"].items()}, indent=2))
    elif a.cmd == "report":
        from .reports import training_workbook
        print(training_workbook())


if __name__ == "__main__":
    main()
