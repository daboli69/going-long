"""Download -> normalize -> aggregate -> feature store, with incremental caching,
validation and coverage reporting."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import availability, features, ingest, sources
from .config import CACHE_DIR, CARRYOVER_SEASON, RAW_DIR

FEATURE_STORE = CACHE_DIR / "feature_store.parquet"
GAMES_TABLE = CACHE_DIR / "games.parquet"
TEAM_GAMES = CACHE_DIR / "team_game_stats.parquet"
QB_GAMES = CACHE_DIR / "qb_game_stats.parquet"
VALIDATION_REPORT = CACHE_DIR / "validation_report.json"
STATUS = CACHE_DIR / "data_status.json"
INJURY_VALID = CACHE_DIR / "injury_rows_pregame.parquet"
INJURY_COVERAGE = CACHE_DIR / "injury_coverage.csv"
# Bump when ingest aggregation logic changes so cached seasons are re-aggregated.
AGG_VERSION = "3"


def current_season(today: datetime | None = None) -> int:
    today = today or datetime.now(timezone.utc)
    return today.year if today.month >= 8 else today.year - 1


def refresh_data(force: bool = False, progress=print) -> dict:
    """Download/refresh all sources, aggregate play-by-play incrementally and rebuild
    the feature store. Completed seasons are downloaded once and reused."""
    live = current_season()
    progress("Step 1/5: schedule and results (nflverse/nfldata games.csv)")
    sources.download_games(force=force, progress=progress)
    games, warnings = ingest.load_games(RAW_DIR / "games.csv", CARRYOVER_SEASON)
    seasons = sorted(s for s in games["season"].unique() if s <= live)

    progress(f"Step 2/5: play-by-play for {seasons[0]}-{seasons[-1]} (nflverse-data pbp release)")
    manifest = sources.load_manifest()
    old = pd.read_parquet(TEAM_GAMES) if TEAM_GAMES.exists() else pd.DataFrame()
    old_qb = pd.read_parquet(QB_GAMES) if QB_GAMES.exists() else pd.DataFrame()
    agg_meta = manifest.get("_aggregated", {})
    tparts, qparts, missing = [], [], []
    for s in seasons:
        try:
            entry = sources.download_pbp(int(s), live=(s == live), force=force, progress=progress)
        except FileNotFoundError:
            missing.append(int(s))
            warnings.append(f"Play-by-play for {s} is not published yet.")
            continue
        sha = f'{entry["sha256"]}:{AGG_VERSION}'
        if agg_meta.get(str(s)) == sha and len(old) and (old["season"] == s).any():
            tparts.append(old[old["season"] == s])
            qparts.append(old_qb[old_qb["season"] == s])
            continue
        progress(f"  aggregating {s} play-by-play ...")
        pbp = pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=ingest.PBP_COLUMNS)
        t = ingest.team_game_stats(pbp)
        t["season"] = int(s)
        q = ingest.qb_game_stats(pbp)
        q["season"] = int(s)
        tparts.append(t)
        qparts.append(q)
        agg_meta[str(s)] = sha
    tstats = pd.concat(tparts, ignore_index=True)
    qstats = pd.concat(qparts, ignore_index=True)
    # Play-by-play game ids use the same nflverse convention; normalize relocated teams.
    id_map = dict(zip(games["source_game_id"], games["game_id"]))
    tstats["game_id"] = tstats["game_id"].map(lambda g: id_map.get(g, g))
    qstats["game_id"] = qstats["game_id"].map(lambda g: id_map.get(g, g))
    tstats.to_parquet(TEAM_GAMES, index=False)
    qstats.to_parquet(QB_GAMES, index=False)
    manifest = sources.load_manifest()
    manifest["_aggregated"] = agg_meta
    sources._save_manifest(manifest)

    progress("Step 3/5: injury reports, snap counts, depth charts (nflverse) + ESPN live injuries")
    avail = availability.refresh_sources([s for s in seasons], live, progress)
    warnings += avail["errors"]
    rows = availability.load_injury_rows([s for s in seasons if s >= 2016])
    valid = availability.pregame_injuries(rows, games)
    snaps = availability.player_roles(seasons)
    inj = availability.team_injury_features(games, valid, snaps, rows)
    from . import advanced
    warnings += advanced.refresh(seasons, live, progress)
    from . import players
    warnings += players.refresh_ftn(seasons, live, progress)
    valid.to_parquet(INJURY_VALID, index=False)
    injury_coverage(games, rows, valid, inj).to_csv(INJURY_COVERAGE, index=False)

    progress("Step 4/5: building pregame feature store (strictly pre-kickoff)")
    games.to_parquet(GAMES_TABLE, index=False)
    churn = availability.ol_churn(seasons, games)
    progress("  player model (RAPM per week, lineups, replacements, continuity, FTN) ...")
    p5 = players.build_team_player_features(games, valid, inj, seasons, progress=progress)
    churn = churn.merge(p5, on=["game_id", "team"], how="outer")
    progress("  snap-based player model (Phase 7 substitute for missing 2026 participation) ...")
    from . import snap_model
    churn = churn.merge(snap_model.build_features(games, tstats, valid, inj, seasons, progress=progress), on=["game_id", "team"], how="outer")
    fs = features.build_feature_store(games, tstats.drop(columns=["season"]), qstats.drop(columns=["season"]),
                                      inj, availability.report_status_lookup(valid), churn, advanced=True)
    fs.to_parquet(FEATURE_STORE, index=False)
    features.feature_catalog(fs.columns).to_csv(CACHE_DIR / "feature_catalog.csv", index=False)

    progress("Step 5/5: validating")
    report = validate(games, tstats, fs, warnings, cross_check=True, progress=progress)
    status = {"refreshed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "live_season": live, "seasons": [int(s) for s in seasons], "missing_pbp": missing,
              "games": int(len(games)), "completed_games": int(games["completed"].sum()),
              "feature_store_rows": int(len(fs)), "warnings": report["warnings"],
              "injury": {"latest_report_row_time": str(valid["available_at"].max()) if len(valid) else None,
                         "live_injury_file_downloaded_at": sources.load_manifest().get(f"nflverse_injuries_{live}", {}).get("downloaded_at"),
                         "espn_retrieved_at": avail.get("espn_retrieved_at"), "espn_records": avail.get("espn_records"),
                         "archived_snapshots": len(list(availability.ARCHIVE_DIR.glob("nflverse_injuries_*.parquet")))}}
    man_ = sources.load_manifest()
    status["model_inputs"] = {k: man_.get(k, {}).get("sha256") for k in ("nfldata_games", f"nflverse_injuries_{live}")} | \
        {"archives": len(list(availability.ARCHIVE_DIR.glob("nflverse_injuries_*.parquet")))}
    status["features_rebuilt_at"] = status["refreshed_at"]
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    progress(f"Done: {status['completed_games']} completed games, {len(fs)} feature rows.")
    return status


def assemble_from_cache(games: pd.DataFrame, tstats: pd.DataFrame, qstats: pd.DataFrame,
                        snaps: pd.DataFrame | None = None, advanced_transform=None, plays_transform=None) -> pd.DataFrame:
    """Rebuild the feature store from already-downloaded files (no network). Used by
    the readiness gate to re-run leakage checks on real data."""
    seasons = sorted(int(x) for x in games["season"].unique())
    rows = availability.load_injury_rows([x for x in seasons if x >= 2016])
    valid = availability.pregame_injuries(rows, games)
    snaps = availability.player_roles(seasons) if snaps is None else snaps
    inj = availability.team_injury_features(games, valid, snaps, rows)
    t = tstats.drop(columns=["season"], errors="ignore")
    q = qstats.drop(columns=["season"], errors="ignore")
    from . import players
    extra = availability.ol_churn(seasons, games).merge(
        players.build_team_player_features(games, valid, inj, seasons, progress=lambda m: None, plays_transform=plays_transform),
        on=["game_id", "team"], how="outer")
    from . import snap_model
    extra = extra.merge(snap_model.build_features(games, tstats, valid, inj, seasons, progress=lambda m: None),
                        on=["game_id", "team"], how="outer")
    return features.build_feature_store(games, t, q, inj, availability.report_status_lookup(valid),
                                        extra, advanced=True, advanced_transform=advanced_transform)


def injury_coverage(games: pd.DataFrame, rows: pd.DataFrame, valid: pd.DataFrame, inj: pd.DataFrame) -> pd.DataFrame:
    """Per season: injury rows downloaded, rows usable before kickoff, games covered (both teams)."""
    both = inj.groupby("game_id")["inj_report_available"].min()
    fs_cov = games.assign(c=games["game_id"].map(both)).groupby("season")["c"].sum()
    out = []
    for s, g in games[games["season"] >= 2016].groupby("season"):
        r, v = rows[rows["season"] == s], valid[valid["season"] == s]
        covered = int(fs_cov.get(int(s), 0))
        out.append({"season": int(s), "rows_downloaded": int(len(r)), "rows_with_timestamp": int(r["available_at"].notna().sum()),
                    "rows_usable_pre_kickoff": int(len(v)), "games": int(len(g)), "games_with_verified_report": covered,
                    "share_games_covered": round(covered / max(len(g), 1), 3),
                    "sources": ", ".join(sorted(set(v["source"]))) if len(v) else "none (no timestamps)"})
    return pd.DataFrame(out)


def validate(games: pd.DataFrame, tstats: pd.DataFrame, fs: pd.DataFrame, warnings: list[str] | None = None,
             cross_check: bool = False, progress=print) -> dict:
    warnings = list(warnings or [])
    errors: list[str] = []
    dups = ingest.find_duplicates(games)
    if len(dups):
        errors.append(f"{len(dups)} duplicate game rows remain")
    done = games[games["completed"]]
    have = set(tstats["game_id"])
    no_pbp = done[~done["game_id"].isin(have)]
    if len(no_pbp):
        warnings.append(f"{len(no_pbp)} completed games have no play-by-play aggregate "
                        f"(latest: {', '.join(no_pbp['game_id'].tail(3))}).")
    per_game = tstats.groupby("game_id").size()
    if (per_game != 2).any():
        errors.append(f"{int((per_game != 2).sum())} games do not have exactly two team rows in play-by-play")
    # Leakage guard: no feature row may reference a state at/after its own kickoff.
    if (fs["feature_cutoff_utc"] != fs["kickoff_utc"]).any():
        errors.append("feature cutoff differs from kickoff")
    cross = None
    if cross_check:
        cross = _cross_check_scores(games, progress)
        if cross.get("mismatches"):
            warnings.append(f"api.nfldata.org disagrees on {cross['mismatches']} final scores (see validation report)")
    by_season = []
    for s, d in games.groupby("season"):
        dd = d[d["completed"]]
        f = fs[fs["season"] == s]
        by_season.append({
            "season": int(s), "games": int(len(d)), "completed": int(len(dd)),
            "with_pbp": int(dd["game_id"].isin(have).sum()), "ties": int(dd["tie"].sum()),
            "with_moneyline": int(dd["market_p_home_novig"].notna().sum()),
            "with_spread": int(dd["spread_line"].notna().sum()),
            "with_starting_qb": int((d["home_qb_id"].notna() & d["away_qb_id"].notna()).sum()),
            "feature_missing_pct": round(float(f.filter(like="diff_blend_").isna().mean().mean() * 100), 2) if len(f) else None,
        })
    missing = fs.filter(regex=r"^(diff_|ctx_|mx_)").isna().mean().sort_values(ascending=False)
    report = {"validated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "errors": errors, "warnings": warnings, "coverage": by_season,
              "most_missing_features": {k: round(float(v), 4) for k, v in missing.head(15).items()},
              "cross_check": cross, "ok": not errors}
    VALIDATION_REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def _cross_check_scores(games: pd.DataFrame, progress) -> dict:
    """Compare final scores for the two most recent seasons with api.nfldata.org.
    Agreement is a transport check only: that API re-serves nflverse."""
    seasons = sorted(games.loc[games["completed"], "season"].unique())[-2:]
    try:
        rows = [r for s in seasons for r in sources.fetch_api_games(int(s), progress)]
    except Exception as exc:  # network failure must not block the pipeline
        return {"status": f"unavailable: {exc}"}
    api = pd.DataFrame(rows)
    if api.empty:
        return {"status": "no rows returned"}
    api = api.dropna(subset=["home_score"])
    m = games.merge(api[["game_id", "home_score", "away_score"]], left_on="source_game_id", right_on="game_id",
                    suffixes=("", "_api"))
    bad = m[(m["home_score"] != m["home_score_api"]) | (m["away_score"] != m["away_score_api"])]
    return {"status": "ok", "seasons": [int(s) for s in seasons], "compared": int(len(m)),
            "mismatches": int(len(bad)), "examples": bad["game_id"].head(5).tolist(),
            "note": "api.nfldata.org is derived from nflverse; agreement is not independent confirmation"}


def load_feature_store() -> pd.DataFrame:
    if not FEATURE_STORE.exists():
        raise FileNotFoundError("No feature store yet. Run 'Download / Update NFL Data' first.")
    return pd.read_parquet(FEATURE_STORE)


def load_status() -> dict:
    return json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}


def load_validation() -> dict:
    return json.loads(VALIDATION_REPORT.read_text(encoding="utf-8")) if VALIDATION_REPORT.exists() else {}


def numeric_matrix(fs: pd.DataFrame, cols: list[str]) -> np.ndarray:
    return fs[cols].astype(float).to_numpy()



def rebuild_features(progress=print) -> dict:
    """Light rebuild after a live refresh: re-read the (already downloaded) schedule and injury
    files and rebuild the feature store from cached aggregates. Skipped when no model input
    changed since the last build."""
    from . import sources as _src
    man = _src.load_manifest()
    live = current_season()
    inputs = {k: man.get(k, {}).get("sha256") for k in ("nfldata_games", f"nflverse_injuries_{live}")}
    inputs["archives"] = len(list(availability.ARCHIVE_DIR.glob("nflverse_injuries_*.parquet")))
    status = load_status()
    if status.get("model_inputs") == inputs and FEATURE_STORE.exists():
        return {"rebuilt": False, "reason": "no model input changed"}
    games, warnings = ingest.load_games(RAW_DIR / "games.csv", CARRYOVER_SEASON)
    tstats, qstats = pd.read_parquet(TEAM_GAMES), pd.read_parquet(QB_GAMES)
    seasons = sorted(int(s) for s in games["season"].unique() if s <= live)
    rows = availability.load_injury_rows([s for s in seasons if s >= 2016])
    valid = availability.pregame_injuries(rows, games)
    valid.to_parquet(INJURY_VALID, index=False)
    games.to_parquet(GAMES_TABLE, index=False)
    fs = assemble_from_cache(games, tstats, qstats)
    fs.to_parquet(FEATURE_STORE, index=False)
    status = load_status() | {"features_rebuilt_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model_inputs": inputs}
    STATUS.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
    progress("  feature store rebuilt (light)")
    return {"rebuilt": True}
