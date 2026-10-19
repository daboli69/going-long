"""Offline Phase 10 feature preparation. No spent-holdout player files are read."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ...config import ARTIFACTS_DIR, RAW_DIR
from ...data_pipeline import FEATURE_STORE
from ...ingest import normalize_team
from ..independent import chronological_context
from . import features as F

OUT = ARTIFACTS_DIR / "props" / "phase10"


def load_rosters(seasons, production=False):
    if production:
        from .frozen import load
        load()
    if not production and any(int(s) not in F.ALLOWED_SEASONS for s in seasons):
        raise ValueError("Forbidden player seasons")
    parts = []
    for s in seasons:
        path = RAW_DIR / f"roster_weekly_{s}.parquet"
        if path.exists():
            parts.append(pd.read_parquet(path, columns=["season", "week", "team", "gsis_id", "status", "position", "full_name"]))
    if not parts:
        raise ValueError("No permitted roster data")
    ros = pd.concat(parts, ignore_index=True).dropna(subset=["gsis_id"])
    ros["team"] = ros["team"].map(normalize_team)
    return ros.drop_duplicates(["season", "week", "team", "gsis_id"])


def candidates(games, rosters, now=None):
    """Use the latest strictly earlier roster, not actual target-week active players.

    For a live forecast a locally retrieved, current-week roster may be used only
    if its file mtime predates the decision and the game is still unstarted.
    """
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    rows = []
    for g in games.to_dict("records"):
        for side, other in (("home", "away"), ("away", "home")):
            team = g[side + "_team"]
            prior = rosters[(rosters["team"] == team) & ((rosters["season"] < g["season"]) |
                     ((rosters["season"] == g["season"]) & (rosters["week"] < g["week"])))]
            rule = "latest strictly earlier roster ACT; offseason changes may be missing"
            if g["season"] == 2026 and pd.Timestamp(g["kickoff_utc"]) > now:
                current = rosters[(rosters["season"] == 2026) & (rosters["week"] == g["week"]) & (rosters["team"] == team)]
                path = RAW_DIR / "roster_weekly_2026.parquet"
                if len(current) and path.exists() and pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC") <= now:
                    prior = current
                    rule = "local current-week ACT roster retrieved before decision"
            if not len(prior):
                continue
            latest = prior.sort_values(["season", "week"]).iloc[-1]
            selected = prior[(prior["season"] == latest["season"]) & (prior["week"] == latest["week"]) & (prior["status"] == "ACT")]
            for r in selected.to_dict("records"):
                rows.append({"game_id": g["game_id"], "season": g["season"], "week": g["week"],
                    "pid": r["gsis_id"], "name": r["full_name"], "team": team, "opponent": g[other + "_team"],
                    "position": r["position"], "home": int(side == "home"),
                    "rest": g.get(side + "_rest_days"), "dome": int(g.get("roof_type") == "dome"),
                    "projected_qb": g.get(side + "_qb_projected_id"), "qb_quality": g.get(side + "_qb_eff"),
                    "qb_out": g.get(side + "_qb_projected_out"), "backup_qb": g.get(side + "_qb_change"),
                    "ind_team_margin": g["ind_margin"] * (1 if side == "home" else -1), "ind_total": g["ind_total"],
                    "roster_rule": rule, "roster_source_season": int(latest["season"]), "roster_source_week": int(latest["week"]),
                    "kickoff_utc": g["kickoff_utc"], "decision_time": min(pd.Timestamp(g["kickoff_utc"]), now).isoformat()})
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    # A trade can leave a player on the older roster of the opponent. Resolve
    # only by strictly newer roster evidence; equal-time conflicting teams are
    # ambiguous and excluded rather than assigned by guesswork.
    result["roster_order"] = result["roster_source_season"] * 100 + result["roster_source_week"]
    newest = result.groupby(["game_id", "pid"])["roster_order"].transform("max")
    result = result[result["roster_order"] == newest]
    ambiguous = result.duplicated(["game_id", "pid"], keep=False)
    result = result[~ambiguous].drop(columns="roster_order")
    return result


def prepare(prospective_week=None, log=print, production=False, completed_week=None):
    source_games = None
    feature_week_limit = prospective_week
    if production:
        from .frozen import load
        load()
        if completed_week is None or completed_week < 1:
            raise ValueError("A verified last completed 2026 week is required")
        source_games = pd.read_parquet(FEATURE_STORE)
        now = pd.Timestamp.now(tz="UTC")
        upcoming = source_games[(source_games["season"] == 2026) & (source_games["kickoff_utc"] > now)
                                & (source_games["kickoff_utc"] <= now + pd.Timedelta(days=9))]
        feature_week_limit = max(int(upcoming["week"].max()) if len(upcoming) else completed_week + 1, completed_week + 1)
    seasons = list(range(2015, 2027)) if production else list(range(2015, 2023)) + ([2026] if prospective_week is not None else [])
    log("load permitted play-by-play only: " + str(seasons))
    plays = F.load_plays(seasons, feature_week_limit, production=production)
    if production:
        known = source_games[(source_games["season"] == 2026) & source_games["completed"] & (source_games["kickoff_utc"] < now)]
        plays = plays[(plays["season"] < 2026) | plays["game_id"].isin(known["game_id"])]
    rosters = load_rosters(seasons, production=production)
    history = F.aggregate(plays, rosters)
    del plays
    # Snap shares are completed-game observations; join to history before shifting.
    try:
        from ...availability import player_roles
        snaps = player_roles([s for s in seasons if s >= 2016])
        history = history.drop(columns="snap_share").merge(snaps.rename(columns={"gsis_id": "pid", "role": "snap_share"}),
                                                          on=["game_id", "pid"], how="left")
    except Exception as exc:
        log(f"snap shares unavailable: {exc}")
    games = source_games if source_games is not None else pd.read_parquet(FEATURE_STORE)
    if production:
        now = pd.Timestamp.now(tz="UTC")
        train = (games["season"] <= 2025) | ((games["season"] == 2026) & (games["week"] <= completed_week))
        future = (games["season"] == 2026) & (games["kickoff_utc"] > now) & (games["kickoff_utc"] <= now + pd.Timedelta(days=9))
        games = games[train | future].copy()
    else:
        games = games[(games["season"] <= 2022) | ((games["season"] == 2026) & (games["week"] == prospective_week))].copy()
    games = games[games["game_type"] == "REG"]
    log("build chronological football-only game context")
    context = chronological_context(games)
    games = games.merge(context, on="game_id", validate="one_to_one")
    candidate = candidates(games, rosters)
    log(f"build strictly earlier-week features for {len(candidate)} candidates")
    frame = F.earlier_features(history, candidate)
    target_cols = ["pass_yds", "pass_tds", "rec", "rec_yds", "rush_yds", "anytime_td"]
    observed = history[["game_id", "pid"] + target_cols].copy()
    # Prospective outcomes never enter the training/development result frame.
    if not production:
        observed = observed[~observed["game_id"].str.startswith("2026_")]
    frame = frame.merge(observed, on=["game_id", "pid"], how="left", validate="one_to_one")
    # Verified injury rows: exclude Out candidates only when publication predates
    # this decision. Current untimestamped injuries files are never read here.
    from ...data_pipeline import INJURY_VALID
    if INJURY_VALID.exists():
        inj = pd.read_parquet(INJURY_VALID)
        if len(inj):
            injuries = inj[["game_id", "gsis_id", "report_status", "available_at"]].rename(columns={"gsis_id": "pid"})
            injuries["available_at"] = pd.to_datetime(injuries["available_at"], utc=True, format="mixed")
            injuries = injuries.sort_values("available_at").drop_duplicates(["game_id", "pid"], keep="last")
            frame = frame.merge(injuries, on=["game_id", "pid"], how="left", validate="one_to_one")
            valid_out = frame["report_status"].eq("Out") & (frame["available_at"] < pd.to_datetime(frame["decision_time"], utc=True, format="mixed"))
            frame = frame[~valid_out]
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(OUT / ("features_production.parquet" if production else "features.parquet"), index=False)
    history.to_parquet(OUT / ("observations_production.parquet" if production else "observations_allowed.parquet"), index=False)
    metadata = {"loaded_player_seasons": seasons, "rows": len(frame), "columns": F.FEATURES,
                "missing_fraction": {c: float(frame[c].isna().mean()) for c in F.FEATURES},
                "formulas": {"hist_*": "mean over last 8 completed eligible player-games, strictly earlier weeks",
                    "shares": "player events divided by team events in a prior game; rolling mean",
                    "adot": "hist_air_yards / hist_targets", "yac_rate": "hist_yac / hist_rec",
                    "deep_target_rate": "hist_deep_targets / hist_targets; deep >=20 air yards",
                    "outside_rz_td_rate": "prior TDs from field position >20 / prior targets+carries",
                    "long_td_rate": "prior rushing/receiving TDs gaining >=40 yards / prior targets+carries",
                    "explosive_rate": "prior catches+runs gaining >=20 / prior targets+carries",
                    "opp_adjustment": "prior opponent position yards allowed / prior league position mean",
                    "context": "lab feature store as-of QB, rest, dome; earlier-season independent ridge margin/total"},
                "excluded_features": ["routes/participation (timestamp-consistent feature pipeline unavailable)",
                    "weather (no historical forecast archive)", "market implied points (no timestamped 2022 history)"]}
    metadata |= {"production_refit": production, "training_last_completed_week": completed_week,
                 "feature_history_max_week_exclusive": feature_week_limit,
                 "feature_cutoff_rule": "completed prior games in strictly earlier weeks; recent partial-week observations may inform later-week forecasts, never same-week forecasts or training after the fit cutoff"}
    (OUT / ("feature_provenance_production.json" if production else "feature_provenance.json")).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    log(f"prepared {len(frame)} rows")
    return frame
