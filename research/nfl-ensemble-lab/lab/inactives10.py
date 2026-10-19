"""Read-only reuse of GOING's official inactive-list parser; no alert functions."""
from __future__ import annotations

import importlib.util
import sys
import types
from functools import lru_cache

import pandas as pd

from .archive10 import save
from .market81 import GOING_ROOT


@lru_cache(maxsize=1)
def parser_module():
    directory = GOING_ROOT / "scripts" / "topdown"
    package = types.ModuleType("_phase10_topdown")
    package.__path__ = [str(directory)]
    sys.modules[package.__name__] = package
    spec = importlib.util.spec_from_file_location("_phase10_topdown.inactives", directory / "inactives.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def archive_report(html, url, event, observed_at, *, root=None):
    module = parser_module()
    report = module.parse_official_report(html, url, event, pd.Timestamp(observed_at).timestamp())
    if not report:
        return {"ok": False, "reason": "no complete verified official lists for this game"}
    args = {"root": root} if root is not None else {}
    archived = save("inactives", "official", report, {"source": url, "retrieved_at": observed_at,
                    "parser": module.METHOD, "read_only_context": True}, **args)
    return {"ok": True} | archived


def collect(games, now=None):
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    due = games[(games["kickoff_utc"] > now) & (games["kickoff_utc"] <= now + pd.Timedelta(minutes=90))]
    if due.empty:
        return {"ok": True, "games": 0, "reason": "no game inside T-90 window"}
    from .market81 import NAME_TO_ABBR
    names = {abbr: name for name, abbr in NAME_TO_ABBR.items()}
    events = [{"event": g.game_id, "home": names.get(g.home_team, g.home_team),
               "away": names.get(g.away_team, g.away_team), "kickoff": g.kickoff_utc.isoformat()} for g in due.itertuples(index=False)]
    # retrieve_official_reports only GETs public NFL HTML. update_inactives, the
    # alert/notification path, is deliberately never called.
    module = parser_module()
    reports, failures = module.retrieve_official_reports(events, now.timestamp())
    files = []
    for report in reports.values():
        files.append(save("inactives", "official", report, {"source": "NFL.com official reports",
                     "retrieved_at": report["observed_at"], "parser": module.METHOD, "read_only_context": True}))
    return {"ok": not failures, "games": len(events), "files": files, "failures": failures}
