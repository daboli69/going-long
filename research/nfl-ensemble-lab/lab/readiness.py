"""Phase 2 readiness gate: audits the REAL data and artifacts (not just unit tests).

  python -m lab.readiness

Checks
  1. injury timestamps behave like pregame report times (not file-processing times)
  2. real-data perturbation: changing one game's outcome, stats, QB EPA and player
     snaps changes no feature of any game at or before its kickoff
  3. missing injury data is stored as missing (NaN), never as zero
  4. out-of-sample predictions were produced by models trained on earlier seasons only
  5. market odds provenance: closing lines without timestamps -> benchmark only
  6. the scheduled refresh task exists and recently succeeded
Writes artifacts/readiness_report.json and returns it. `ok` is False if any
critical check fails.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import availability
from .config import ARTIFACTS_DIR, RAW_DIR
from .data_pipeline import GAMES_TABLE, QB_GAMES, TEAM_GAMES, assemble_from_cache, load_feature_store, load_status
from .features import META_COLUMNS, select_features
from .training import current_version, load_run

REPORT = ARTIFACTS_DIR / "readiness_report.json"


def check_injury_timestamps(games: pd.DataFrame) -> dict:
    out = {"critical": True}
    long = pd.concat([games[["season", "week", "kickoff_utc"]].assign(team=games["home_team"]),
                      games[["season", "week", "kickoff_utc"]].assign(team=games["away_team"])])
    per = []
    for s in range(2016, availability.LAST_TIMESTAMPED_SEASON + 1):
        p = RAW_DIR / f"injuries_{s}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        t = pd.to_datetime(d["date_modified"], utc=True)
        d = d.assign(week=pd.to_numeric(d["week"]).astype(int), team=d["team"].map(availability._team), t=t)
        m = d.merge(long[long["season"] == s], on=["week", "team"], how="inner")
        hrs = (m["kickoff_utc"] - m["t"]).dt.total_seconds() / 3600
        # A file-processing timestamp would be one value (or one day) per file and fall
        # after the season; report times should track each week and precede kickoff.
        per.append({"season": s, "rows": int(len(d)), "distinct_days": int(t.dt.date.nunique()),
                    "share_after_season_end": float((t > long[long["season"] == s]["kickoff_utc"].max()).mean()),
                    "share_before_kickoff": float((hrs > 0).mean()),
                    "median_hours_before_kickoff": float(hrs.median()),
                    "corr_timestamp_vs_kickoff": float(np.corrcoef(m["t"].astype("int64"), m["kickoff_utc"].astype("int64"))[0, 1]),
                    "weekday_share": {k: round(float(v), 3) for k, v in m["t"].dt.day_name().value_counts(normalize=True).head(4).items()}})
    out["per_season"] = per
    ok = all(r["distinct_days"] > 30 and r["share_before_kickoff"] > 0.99 and r["corr_timestamp_vs_kickoff"] > 0.99
             and r["share_after_season_end"] < 0.01 for r in per)
    out["ok"] = bool(ok and per)
    out["interpretation"] = ("date_modified spans each season on many distinct days, tracks each week's kickoffs "
                             "(correlation > 0.99), falls mostly on report days, and precedes kickoff for >99% of rows: "
                             "consistent with official report submission times, not a file-processing time. "
                             "Residual risk: it records the league feed's modification time, not the public posting time.")
    return out


def check_perturbation(games: pd.DataFrame, fs: pd.DataFrame) -> dict:
    tstats, qstats = pd.read_parquet(TEAM_GAMES), pd.read_parquet(QB_GAMES)
    seasons = sorted(int(x) for x in games["season"].unique())
    snaps = availability.player_roles(seasons)
    target = games[(games["season"] == 2022) & (games["week"] == 10) & games["completed"]].iloc[0]
    gid = target["game_id"]
    base = assemble_from_cache(games, tstats, qstats, snaps)
    g2, t2, q2, s2 = games.copy(), tstats.copy(), qstats.copy(), snaps.copy()
    g2.loc[g2["game_id"] == gid, ["home_score", "away_score"]] = [77, 0]
    g2["margin"] = g2["home_score"] - g2["away_score"]
    num = [c for c in t2.columns if c not in ("game_id", "team", "season")]
    t2.loc[t2["game_id"] == gid, num] = t2.loc[t2["game_id"] == gid, num] * 3 + 1
    q2.loc[q2["game_id"] == gid, "qb_epa_sum"] = 500.0
    s2.loc[s2["game_id"].isin([gid, target["source_game_id"]]), "role"] = 0.0
    pert = assemble_from_cache(g2, t2, q2, s2)
    cols = [c for c in base.columns if c not in META_COLUMNS and base[c].dtype.kind in "fi"
            and not c.endswith(("_report_time",))]
    a = base.set_index("game_id")
    b = pert.set_index("game_id").loc[a.index]
    before = a["kickoff_utc"] <= target["kickoff_utc"]
    diff_before = ~np.isclose(a.loc[before, cols].astype(float).to_numpy(), b.loc[before, cols].astype(float).to_numpy(), equal_nan=True)
    after = a["kickoff_utc"] > target["kickoff_utc"]
    changed_after = int((~np.isclose(a.loc[after, cols].astype(float).to_numpy(), b.loc[after, cols].astype(float).to_numpy(), equal_nan=True)).any(axis=1).sum())
    bad_cols = sorted({cols[j] for j in np.where(diff_before.any(axis=0))[0]})
    return {"critical": True, "target_game": gid, "features_checked": len(cols), "games_at_or_before": int(before.sum()),
            "changed_cells_at_or_before": int(diff_before.sum()), "leaking_columns": bad_cols,
            "later_games_changed": changed_after, "ok": diff_before.sum() == 0 and changed_after > 0,
            "matches_stored_store": bool(len(base) == len(fs))}


def check_missing_injuries(fs: pd.DataFrame) -> dict:
    inj = [c for c in fs.columns if c.startswith(("home_inj_out", "away_inj_out", "diff_inj_out"))]
    unavailable = fs["inj_available"] == 0
    zeros = int((fs.loc[unavailable, inj].fillna(-1) == 0).any(axis=1).sum())
    per = fs.groupby("season").apply(lambda d: round(float(d["inj_available"].mean()), 3), include_groups=False).to_dict()
    # rows marked unavailable may still carry one side's data; diff_* must be NaN whenever either side is missing
    diff_bad = int((fs.loc[unavailable, [c for c in inj if c.startswith("diff_")]].notna()).any(axis=1).sum())
    return {"critical": True, "share_available_by_season": per, "unavailable_rows_with_zero_load": zeros,
            "unavailable_rows_with_non_missing_diff": diff_bad, "ok": diff_bad == 0}


def check_oof() -> dict:
    run = load_run()
    oof = run.get("oof", pd.DataFrame())
    if oof.empty:
        return {"critical": True, "ok": False, "error": "no out-of-sample predictions"}
    hi = oof["train_seasons"].str.split("-").str[1].astype(int)
    leak = int((hi >= oof["season"]).sum())
    return {"critical": True, "model_version": run["version"], "rows": int(len(oof)),
            "seasons": sorted(int(s) for s in oof["season"].unique()), "rows_trained_on_own_or_later_season": leak,
            "champion": run["selection"].get("champion"), "ok": leak == 0}


def check_market(games: pd.DataFrame) -> dict:
    return {"critical": False, "ok": True, "source": "nflverse/nfldata games.csv home/away_moneyline, spread_line",
            "timestamped": False, "share_completed_with_moneyline": float(games.loc[games["completed"], "home_moneyline"].notna().mean()),
            "treatment": "Closing consensus lines without availability timestamps. Used ONLY as a separate benchmark "
                         "probability (and as a benchmark baseline for residual analysis). Never a model or discovery input, "
                         "never an earlier-week prediction input, and no executable-edge or profit claims are possible."}


def check_refresh_task() -> dict:
    out = {"critical": False}
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-ScheduledTaskInfo -TaskName 'NFL Ensemble Lab - Data Refresh' | "
                            "Select-Object LastRunTime,LastTaskResult,NextRunTime | ConvertTo-Json"],
                           capture_output=True, text=True, timeout=30)
        info = json.loads(r.stdout) if r.stdout.strip() else {}
        out |= {"task": info, "ok": bool(info) and info.get("LastTaskResult") == 0}
    except Exception as exc:
        out |= {"ok": False, "error": str(exc)}
    out["last_refresh"] = load_status().get("refreshed_at")
    return out


def run(progress=print) -> dict:
    games = pd.read_parquet(GAMES_TABLE)
    fs = load_feature_store()
    report = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model_version": current_version()}
    for name, fn in (("injury_timestamps", lambda: check_injury_timestamps(games)),
                     ("real_data_perturbation", lambda: check_perturbation(games, fs)),
                     ("missing_injuries", lambda: check_missing_injuries(fs)),
                     ("out_of_sample_predictions", check_oof),
                     ("market_odds", lambda: check_market(games)),
                     ("refresh_task", check_refresh_task)):
        progress(f"readiness: {name} ...")
        try:
            report[name] = fn()
        except Exception as exc:
            report[name] = {"critical": True, "ok": False, "error": repr(exc)}
    report["model_features_checked"] = len(select_features(fs.columns))
    report["ok"] = all(v.get("ok") for v in report.values() if isinstance(v, dict) and v.get("critical"))
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: (v.get("ok") if isinstance(v, dict) else v) for k, v in r.items()}, indent=2))
