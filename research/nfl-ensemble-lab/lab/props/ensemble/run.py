"""Fit fixed development members and emit chronological 2022 shadow predictions.

python -m lab.props.ensemble.run fit --threads 7
python -m lab.props.ensemble.run develop
"""
from __future__ import annotations

import argparse
import json

import joblib
import numpy as np
import pandas as pd

from . import TARGETS
from .combine import combine
from .data import OUT
from .features import FEATURES, eligible
from .members import Members, make_member

META_COLS = ["game_id", "season", "week", "team", "pid", "name", "kickoff_utc", "decision_time"]


def fit(threads=7, log=print):
    frame = pd.read_parquet(OUT / "features.parquet")
    frame = frame[(frame["season"] >= 2016) & (frame["season"] <= 2021)].sort_values(["season", "week", "game_id"])
    directory = OUT / "members_dev"
    directory.mkdir(parents=True, exist_ok=True)
    status = {}
    for stat in TARGETS:
        path = directory / f"{stat}.joblib"
        if path.exists():
            log(f"reuse {stat}: fitted development artifact exists")
            continue
        try:
            target = frame[eligible(frame, stat) & frame[stat].notna()]
            member = Members().fit(target, stat, FEATURES, threads, log)
            joblib.dump(member, path)
            status[stat] = {"rows": len(target), "members": list(member.models), "errors": member.errors}
        except Exception as exc:
            status[stat] = {"error": repr(exc)}
            log(f"FAILED {stat}: {exc}; skipped")
        (directory / "fit_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    # Fixed B4 red-zone-only comparator; same training rows/model penalty.
    try:
        stat = "anytime_td"
        target = frame[eligible(frame, stat) & frame[stat].notna()]
        columns = ["hist_target_share", "hist_carry_share", "hist_rz_target_share", "hist_gl_target_share",
                   "hist_rz_carry_share", "hist_gl_carry_share", "hist_games", "is_qb", "is_rb", "is_wr", "is_te",
                   "home", "rest", "dome", "ind_team_margin", "ind_total", "qb_quality", "opp_position_td"]
        if not (directory / "redzone_only.joblib").exists():
            model = make_member(stat, "logreg", threads).fit(target[columns].to_numpy(float), target[stat].to_numpy())
            joblib.dump({"model": model, "columns": columns}, directory / "redzone_only.joblib")
    except Exception as exc:
        log(f"FAILED B4 comparator: {exc}; skipped")
    return status


def structural_rows(season):
    directory = OUT / ("structural_dev2022" if season == 2022 else "structural_prospective2026")
    files = sorted(directory.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)


def learned_predictions(frame, directory, log=print):
    rows = []
    for stat in TARGETS:
        path = directory / f"{stat}.joblib"
        if not path.exists():
            log(f"skip {stat}: member fit missing")
            continue
        model = joblib.load(path)
        target = frame[eligible(frame, stat)].copy()
        if not len(target):
            continue
        pred = model.predict(target)
        result = target[META_COLS].copy()
        result["stat"] = stat
        result["actual"] = target[stat] if stat in target else np.nan
        for key, value in pred.items():
            result[key] = value
        # Transparent simple independent baseline. It is NOT represented as
        # simulator baseline B, which needs matched eligible structural inputs.
        result["recent_mean"] = target["hist_" + ("off_td" if stat == "anytime_td" else stat)]
        if stat == "anytime_td":
            result["recent_mean"] = np.clip(result["recent_mean"], 0, 1)
            redzone = directory / "redzone_only.joblib"
            if redzone.exists():
                rz = joblib.load(redzone)
                result["redzone_only"] = rz["model"].predict_proba(target[rz["columns"]].to_numpy(float))[:, 1]
        rows.append(result)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def merge_structural(wide, structural):
    if structural.empty:
        return wide
    means = structural.pivot_table(index=["game_id", "pid", "stat"], columns="member", values="mean", aggfunc="first").reset_index()
    return wide.merge(means, on=["game_id", "pid", "stat"], how="left", validate="one_to_one")


def chronological_combinations(wide, previous=None, variant="independent"):
    if variant not in ("independent", "market-informed"):
        raise ValueError(variant)
    completed = []
    previous = pd.DataFrame() if previous is None else previous
    for (season, week, stat), current in wide.groupby(["season", "week", "stat"], sort=True):
        keys = ("logreg", "random_forest", "xgboost", "mlp", "sim_independent")
        if variant == "market-informed":
            keys += ("simulator_v1",)
        candidates = [k for k in keys if k in current]
        # Different availability patterns are explicit; missing members never
        # acquire invented values or silently receive a model's name.
        patterns = current[candidates].notna().apply(lambda r: tuple(k for k in candidates if r[k]), axis=1)
        history = pd.concat([previous] + completed, ignore_index=True) if completed or len(previous) else pd.DataFrame()
        if len(history):
            history = history[history["stat"] == stat]
        for pattern in dict.fromkeys(patterns):
            selected = current.loc[patterns.map(lambda p: p == pattern)].copy()
            if not pattern:
                continue
            values, raw, state = combine(stat, {k: selected[k].to_numpy(float) for k in pattern}, history, int(week), int(season))
            for key, value in values.items():
                selected[key] = value
                selected["raw_" + key] = raw[key]
            selected["members"] = ",".join(pattern)
            selected["member_min"] = selected[list(pattern)].min(axis=1)
            selected["member_max"] = selected[list(pattern)].max(axis=1)
            selected["meta_rows"] = state["history_rows"]
            selected["meta_max_week"] = state["meta_max_week"]
            selected["calibration"] = json.dumps(state["calibration"])
            selected["weights"] = json.dumps(state["weights"])
            selected["variant"] = variant
            completed.append(selected)
    return pd.concat(completed, ignore_index=True) if completed else pd.DataFrame()


def develop(log=print):
    frame = pd.read_parquet(OUT / "features.parquet")
    frame = frame[frame["season"] == 2022]
    wide = learned_predictions(frame, OUT / "members_dev", log)
    wide = wide[wide["actual"].notna()]
    wide = merge_structural(wide, structural_rows(2022))
    wide = chronological_combinations(wide)
    wide.to_parquet(OUT / "dev_predictions.parquet", index=False)
    log(f"2022 predictions: {len(wide)} rows, {wide['game_id'].nunique()} games")
    return wide


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("fit", "develop"))
    parser.add_argument("--threads", type=int, default=7)
    args = parser.parse_args()
    if args.command == "fit":
        fit(args.threads)
    else:
        develop()
