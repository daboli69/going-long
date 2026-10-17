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
    sub.add_parser("readiness")
    sc = sub.add_parser("scheduled")
    sc.add_argument("--no-refresh", action="store_true")
    sub.add_parser("score")
    rs = sub.add_parser("research")
    rs.add_argument("--skip-refresh", action="store_true")
    rs.add_argument("--season", type=int)
    rs.add_argument("--week", type=int)
    sub.add_parser("errors")
    sub.add_parser("audit")
    sub.add_parser("phase7-test")
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
    elif a.cmd == "scheduled":
        from .prospective import run_scheduled
        log = run_scheduled(refresh=not a.no_refresh)
        print(json.dumps({k: v for k, v in log.items() if k != "actions"}, indent=2, default=str))
        if log["errors"]:
            raise SystemExit(1)
    elif a.cmd == "score":
        from .prospective import score
        print(json.dumps(score()["overall"], indent=2))
    elif a.cmd == "readiness":
        from .readiness import run
        print(json.dumps({k: (v.get("ok") if isinstance(v, dict) else v) for k, v in run().items()}, indent=2, default=str))
    elif a.cmd == "research":
        from .research import run_research
        print(json.dumps(run_research(refresh=not a.skip_refresh, season=a.season, week=a.week), indent=2, default=str))
    elif a.cmd == "errors":
        from .errors import build
        r = build()
        print(json.dumps({"effective_models": r["effective_models"], "all_six_wrong_share": r["all_six_wrong_share"]}, indent=2))
    elif a.cmd == "audit":
        from .audit7 import run
        for c in run()["checks"]:
            print(("OK   " if c["ok"] else "FAIL ") + c["check"] + " | " + c["detail"])
    elif a.cmd == "phase7-test":
        from .study7 import run
        print(run()["results"].to_string())


if __name__ == "__main__":
    main()
