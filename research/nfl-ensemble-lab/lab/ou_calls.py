"""Over and under calls from the newest FantasyPoints weekly run (shadow revision): the model's projection against the consensus line."""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CACHE_DIR

ROOT = CACHE_DIR / "fpds" / "amendment6" / "weekly"
STAT_NAME = {"rec_yds": "Receiving yards", "rec": "Receptions", "rush_yds": "Rushing yards", "pass_yds": "Passing yards", "pass_tds": "Passing TDs"}
_CACHE: dict = {}


def latest_file() -> Path | None:
    fs = sorted(glob.glob(str(ROOT / "*_r*" / "presentations" / "*" / "leans.csv")))
    return Path(fs[-1]) if fs else None


def calls() -> dict:
    f = latest_file()
    if f is None:
        return {"ok": False, "reason": "No FantasyPoints weekly run has been saved yet. Run the Tuesday refresh."}
    key = (str(f), f.stat().st_mtime)
    if _CACHE.get("key") == key:
        return _CACHE["val"]
    d = pd.read_csv(f)
    d = d[(d["arm"] == "frozen") & d["stat"].isin(STAT_NAME) & d["consensus_line"].notna() & d["name"].notna()].copy()
    rng = np.maximum(d["q90"] - d["q10"], 1.0)
    d["opp"] = np.where(d["team"] == d["home_team"], d["away_team"], d["home_team"])
    d["gap"] = d["median"] - d["consensus_line"]
    d["strength"] = d["gap"].abs() / rng
    d["call"] = np.where(d["gap"] > 0, "Over", np.where(d["gap"] < 0, "Under", "Even"))
    d["p_call"] = np.where(d["call"] == "Over", d["p_over"], d["p_under"])
    rows = [{"player": r.name, "team": r.team, "opp": r.opp, "pos": r.position, "stat": STAT_NAME[r.stat], "gid": r.game_id, "kickoff_utc": r.kickoff_utc, "projection": float(r.median), "mean": float(r.mean),
             "low": float(r.q10), "high": float(r.q90), "line": float(r.consensus_line), "call": r.call, "chance": float(r.p_call), "gap": float(r.gap), "strength": float(r.strength),
             "line_status": r.line_status, "tier": r.confidence_tier} for r in d.itertuples()]
    first = d.iloc[0] if len(d) else None
    val = {"ok": True, "week": int(first["week"]) if first is not None else None, "through_week": int(first["training_last_completed_week"]) if first is not None else None,
           "created_at": str(first["forecast_created_at"]) if first is not None else None, "rows": rows,
           "status": "Shadow revision trained on this whole season through the last completed week plus earlier seasons, with FantasyPoints data included. Not promoted, and no historical edge against prop prices is established."}
    _CACHE.update(key=key, val=val)
    return val
