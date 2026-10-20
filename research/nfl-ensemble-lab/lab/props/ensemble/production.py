"""Amendment 1: recent-data fit of a committed frozen shadow configuration."""
from __future__ import annotations

import argparse
import json

import joblib
import numpy as np
import pandas as pd

from ...data_pipeline import FEATURE_STORE
from ...players import SEASON_WEIGHTS
from . import TARGETS
from .data import OUT, prepare
from .features import FEATURES, eligible
from .frozen import load
from .members import Members


def completed_cutoff(games, now=None):
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    g = games[(games["season"] == 2026) & games["game_type"].eq("REG")]
    done = g.groupby("week").apply(lambda d: bool(d["completed"].all() and (d["kickoff_utc"] < now).all()), include_groups=False)
    # Only a continuous run of fully completed weeks counts. A moved game
    # keeps its week incomplete even if later weeks have already finished.
    week = 0
    while bool(done.get(week + 1, False)):
        week += 1
    if not week:
        raise ValueError("No fully completed 2026 week")
    training = g[g["week"] <= week]
    return {"training_max_season": 2026, "training_last_completed_week": week,
            "training_cutoff_date": str(training["gameday"].max()),
            "training_last_game_kickoff": training["kickoff_utc"].max().isoformat()}


def season_weight_map(seasons, reference_season=2026):
    """Reuse lab weights 1/.6/.35, retaining older seasons at the oldest weight.

    The floor (rather than silently discarding older seasons) is explicit in the
    frozen configuration. No weight is selected from recent outcomes.
    """
    return {int(s): SEASON_WEIGHTS[min(reference_season - int(s), max(SEASON_WEIGHTS))] for s in seasons}


def fit(threads=7, prepare_data=True, log=print, prospective_week=None):
    frozen = load()  # Must succeed before any 2023–25 player file can be read.
    games = pd.read_parquet(FEATURE_STORE)
    cutoff = completed_cutoff(games)
    week = cutoff["training_last_completed_week"]
    frame = prepare(production=True, completed_week=week, log=log, prospective_week=prospective_week) if prepare_data else pd.read_parquet(OUT / "features_production.parquet")
    tr = frame[(frame["season"] >= 2016) & ((frame["season"] < 2026) | (frame["week"] <= week))].sort_values(["season", "week", "game_id"])
    directory = OUT / f"members_production_2026_w{week:02d}"
    directory.mkdir(parents=True, exist_ok=True)
    status = cutoff | {"frozen_config_sha256": frozen["config_sha256"], "fit_started_at": pd.Timestamp.now(tz="UTC").isoformat(),
                       "season_weights": season_weight_map(tr["season"].unique()), "models": {}, "shadow_only": True}
    for stat in TARGETS:
        path = directory / f"{stat}.joblib"
        if path.exists():
            log(f"reuse recent fit {stat}")
            continue
        try:
            target = tr[eligible(tr, stat) & tr[stat].notna()]
            w = target["season"].map(status["season_weights"]).to_numpy(float)
            # Unit mean keeps regularization scale comparable to development.
            w /= w.mean()
            model = Members().fit(target, stat, FEATURES, threads, log, sample_weight=w, production=True)
            joblib.dump(model, path)
            status["models"][stat] = {"n": len(target), "members": list(model.models), "errors": model.errors}
        except Exception as exc:
            status["models"][stat] = {"error": repr(exc)}
            log(f"FAILED production fit {stat}: {exc}; skipped")
        (directory / "fit_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    status["fit_finished_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    (directory / "fit_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    # A local pointer only; this is not a champion/model-registry promotion.
    (OUT / "production_fit.json").write_text(json.dumps(status | {"directory": str(directory)}, indent=2), encoding="utf-8")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=7)
    parser.add_argument("--reuse-features", action="store_true")
    args = parser.parse_args()
    print(json.dumps(fit(args.threads, not args.reuse_features), indent=2))
