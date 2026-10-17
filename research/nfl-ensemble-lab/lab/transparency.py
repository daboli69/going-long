"""Phase 7.1: what each model version knew, versus what live monitoring knows now.

Three separate views, never mixed:
  1. champion   - the frozen champion's inputs (QB rule v1, its verified injury report, no player model)
  2. challengers- each shadow challenger's own inputs (Phase 5: v1 QB + 2025-participation player model;
                  Phase 7: v1 and v2 QB + 2026-snap player model)
  3. live       - monitoring-only best available QB projection from official report, weekly roster,
                  Sleeper and QB v2. It NEVER changes any model prediction.
Status vocabulary: confirmed (only after kickoff, from play-by-play), projected, unavailable, conflicting.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from .config import SNAPSHOTS_DIR

CHAMPION_LABEL = "Champion"
UNAVAILABLE = ("Out", "Doubtful")


def _clean(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    return x


def qb_rule(features) -> str:
    return "v2 (returning starter)" if any("qb7" in c for c in features) else "v1 (previous starter)"


def version_inputs(row: pd.Series, features: list[str]) -> dict:
    """The inputs one model version actually used for this game (from the feature row it was given)."""
    v2 = any("qb7" in c for c in features)
    out = {"qb_rule": qb_rule(features)}
    for side in ("home", "away"):
        out[f"{side}_qb_id"] = _clean(row.get(f"{side}_qb7_projected_id" if v2 else f"{side}_qb_projected_id"))
        out[f"{side}_qb_v1_id"] = _clean(row.get(f"{side}_qb_projected_id"))
        out[f"{side}_qb_starter_out"] = _clean(row.get(f"{side}_qb7_projected_out" if v2 else f"{side}_qb_projected_out"))
        out[f"{side}_qb_returning"] = _clean(row.get(f"{side}_qb7_returning")) if v2 else None
        out[f"{side}_injury_report"] = ("verified pregame report" if row.get(f"{side}_inj_report_available") == 1
                                        else "none verified (QB-out rule cannot fire)")
        out[f"{side}_injury_report_time"] = _clean(row.get(f"{side}_inj_report_time"))
    pm = []
    if any(c.startswith(("diff_p5_", "p5mx_")) for c in features):
        pm.append(f"Phase 5 RAPM (play participation through 2025; {_clean(row.get('home_p5_model_staleness_days'))} days stale)")
    if any("p7s" in c for c in features):
        pm.append(f"Phase 7 snap model (2026 snap counts; {_clean(row.get('home_p7s_staleness_days'))} days since newest game)")
    out["player_model"] = "; ".join(pm) if pm else "none (team-level features only)"
    vals = row.reindex(features)
    out["features_missing"] = int(vals.isna().sum())
    out["features_missing_names"] = [c for c in features if pd.isna(vals.get(c))][:12]
    out["n_features"] = len(features)
    return out


# --------------------------------------------------------------------------- live (monitoring only)

def live_qb(team: str, season: int, week: int, row: pd.Series | None = None, side: str | None = None, names: dict | None = None,
            official: dict | None = None, sleeper: pd.DataFrame | None = None, roster: pd.DataFrame | None = None) -> dict:
    """Best available live projection for one team, with every source shown. Never a model input."""
    from . import extra_sources as X
    from .availability import player_names
    names = names if names is not None else player_names()
    if official is None:
        from .live import official_qb_status
        official = official_qb_status(season)
    if sleeper is None:
        sleeper, _ = X.sleeper_latest()
    if roster is None:
        roster = X.weekly_rosters(season)
    rep = official if official.get("_week") == week else {}
    out_names = {k[1] for k, s in rep.items() if isinstance(k, tuple) and k[0] == team and s in UNAVAILABLE}
    srcs = {}
    if len(sleeper):
        s1 = sleeper[(sleeper["team"] == team) & (sleeper["position"] == "QB")].sort_values("depth_chart_order")
        s1 = s1[s1["depth_chart_order"].notna()]
        if len(s1):
            srcs["Sleeper depth #1"] = s1["full_name"].iloc[0]
    if row is not None and side:
        v2 = names.get(row.get(f"{side}_qb7_projected_id"))
        if v2:
            srcs["QB projection v2"] = v2
        v1 = names.get(row.get(f"{side}_qb_projected_id"))
        if v1:
            srcs["champion rule v1"] = v1
    unavailable_roster = set()
    if len(roster):
        r = roster[(roster["team"] == team) & (roster["position"] == "QB")]
        if len(r):
            r = r[r["week"] == r["week"].max()]
            unavailable_roster = set(r[r["status"].isin(["RES", "INA"])]["full_name"])
    N = X._norm
    out_n, res_n = {N(x) for x in out_names}, {N(x) for x in unavailable_roster}
    qb_names = {N(v) for v in srcs.values()} | res_n
    out_names = {x for x in out_names if N(x) in qb_names or (len(roster) and N(x) in set(roster[(roster["team"] == team) & (roster["position"] == "QB")]["full_name"].map(N)))}
    # the champion's v1 rule is shown for reference but is not live information, so it does not vote
    cands = {k: v for k, v in srcs.items() if k != "champion rule v1" and N(v) not in out_n and N(v) not in res_n}
    by_norm = {}
    for k, v in cands.items():
        by_norm.setdefault(N(v), v)
    distinct = sorted(by_norm.values())
    if not distinct:
        status, qb = "unavailable", None
    elif len(distinct) == 1:
        status, qb = "projected (sources agree)", distinct[0]
    else:
        qb = cands.get("Sleeper depth #1") or cands.get("QB projection v2") or distinct[0]
        status = "conflicting"
    return {"team": team, "live_qb": qb, "status": status, "sources": srcs,
            "official_out_or_doubtful": sorted(out_names), "roster_reserve_or_inactive": sorted(unavailable_roster),
            "official_report_week": official.get("_week"), "note": "monitoring only: never changes a model prediction"}


def confirmed_qb(game_id: str, side: str) -> str | None:
    """Actual starter, available only after the game (play-by-play). Post-hoc; never an input."""
    from .availability import player_names
    from .data_pipeline import GAMES_TABLE
    g = pd.read_parquet(GAMES_TABLE).set_index("game_id")
    if game_id not in g.index or not bool(g.loc[game_id, "completed"]):
        return None
    return player_names().get(g.loc[game_id, f"{side}_qb_id"])


def conflict_warning(row: pd.Series, side: str, live: dict, names: dict) -> str | None:
    from .extra_sources import _norm
    champ = names.get(row.get(f"{side}_qb_projected_id"))
    if live["live_qb"] and champ and _norm(champ) != _norm(live["live_qb"]):
        return (f"{row[f'{side}_team']}: the champion assumes {champ}, but live monitoring now projects {live['live_qb']} "
                f"({live['status']}). The archived champion forecast does not reflect this.")
    if champ and _norm(champ) in {_norm(x) for x in live["official_out_or_doubtful"]}:
        return f"{row[f'{side}_team']}: the champion assumes {champ}, whom the official report now lists Out/Doubtful."
    return None


# --------------------------------------------------------------------------- archived history

def snapshot_history(game_id: str) -> pd.DataFrame:
    """Every archived pregame forecast for a game (immutable files), oldest first."""
    from .prospective import load_ledger
    led = load_ledger()
    if led.empty:
        return led
    led = led[led["game_id"] == game_id].sort_values("predicted_at")
    names = None
    rows = []
    for r in led.itertuples(index=False):
        p = SNAPSHOTS_DIR / str(r.path).replace("\\", os.sep)
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if names is None:
            from .availability import player_names
            names = player_names()
        av = s.get("availability", {})
        row = {"stage": s.get("stage_label") or s.get("window"), "archived_at": s.get("predicted_at"),
               "hours_before_kickoff": s.get("hours_to_kickoff"), "champion": s.get("model_version"), "p_home_champion": s.get("p_champion"),
               "margin_champion": s.get("margin_ensemble")}
        for v, c in (s.get("shadow_challengers") or {}).items():
            row[f"p_home {v}"] = (c or {}).get("p_champion") if isinstance(c, dict) else None
        for side in ("home", "away"):
            a = av.get(side, {})
            row[f"{side} QB (champion)"] = names.get(a.get("qb_projected_id"), a.get("qb_projected_id"))
            row[f"{side} report"] = "verified" if a.get("inj_report_available") == 1 else "none"
        row["report_retrieved"] = (s.get("data_cutoff") or {}).get("official_injury_file_downloaded_at")
        rows.append(row)
    return pd.DataFrame(rows)
