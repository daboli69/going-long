"""One-click Phase 2 research workflow (run on demand, NOT by the scheduled refresh).

  1. refresh free public NFL data (schedule, play-by-play, injuries, snaps)
  2. readiness gate on real data (aborts on any critical failure)
  3. load the frozen out-of-sample Phase 1 predictions (no retraining)
  4-7. run discovery, validate candidates, write the immutable catalog
  8. experimental upcoming-week forecasts (archived in an immutable snapshot)
  9. Excel: training, weekly and NFL_Upset_Discovery workbooks

The Phase 1 production champion is never retrained or replaced here.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import ARTIFACTS_DIR

RUN_LOG = ARTIFACTS_DIR / "research_runs.jsonl"


def run_research(refresh: bool = True, season: int | None = None, week: int | None = None, progress=print,
                 discovery_config: dict | None = None) -> dict:
    from . import discovery, readiness, reports, weekly
    from .data_pipeline import refresh_data
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log = {"started_at": started, "steps": []}
    try:
        if refresh:
            progress("1/6 refreshing public NFL data and injury reports ...")
            refresh_data(progress=progress)
            log["steps"].append("data refreshed")
        progress("2/6 readiness gate ...")
        gate = readiness.run(progress=progress)
        log["readiness_ok"] = gate["ok"]
        if not gate["ok"]:
            raise RuntimeError("Readiness gate failed; see artifacts/readiness_report.json. Discovery was not run.")
        progress("3-5/6 discovery experiment on frozen out-of-sample predictions ...")
        exp = discovery.run_experiment(discovery_config, progress=progress)
        log["experiment"] = exp["summary"]["experiment"]
        progress("6/6 weekly forecasts with experimental adjustments + Excel reports ...")
        wk = weekly.run_weekly(season=season, week=week, refresh=False, progress=progress)
        log["weekly"] = {k: str(v) for k, v in wk["paths"].items()}
        log["discovery_workbook"] = str(reports.discovery_workbook(weekly_disc=wk["discovery"]))
        log["training_workbook"] = str(reports.training_workbook())
        log["status"] = "ok"
    except Exception as exc:
        log["status"] = "failed"
        log["error"] = repr(exc)
        raise
    finally:
        log["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(RUN_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(log, default=str) + "\n")
    return log


def run_history() -> list[dict]:
    if not RUN_LOG.exists():
        return []
    return [json.loads(line) for line in RUN_LOG.read_text(encoding="utf-8").splitlines() if line.strip()][::-1]
