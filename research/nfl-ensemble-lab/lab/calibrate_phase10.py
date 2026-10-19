"""B1: earlier-DEV-fold calibration of the saved combined champion probability."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from .config import ARTIFACTS_DIR, MODELS_DIR
from .longrun import DEV_FOLDS
from . import metrics
from .props.ensemble.data import OUT
from .props.ensemble.research import clustered_difference


def run():
    pointer = json.loads((MODELS_DIR / "CURRENT.json").read_text())
    version = pointer["version"]
    manifest = json.loads((MODELS_DIR / version / "manifest.json").read_text())
    champion = manifest["champion"]
    column = "p_" + champion
    path = ARTIFACTS_DIR / "runs" / version / "oof_predictions.parquet"
    # Do not load later outcome folds or any market-line column.
    data = pd.read_parquet(path, columns=["game_id", "season", "home_win", column],
                           filters=[("season", "in", list(DEV_FOLDS))]).dropna()
    if not set(data["season"].unique()) <= set(DEV_FOLDS):
        raise ValueError("Non-development fold in calibration experiment")
    data = data.sort_values(["season", "game_id"])
    data["reference"] = data[column]
    data["recalibrated"] = data[column]
    data["calibration_training_max_season"] = np.nan
    for season in DEV_FOLDS:
        history, target = data["season"] < season, data["season"] == season
        if history.sum() < 100:
            continue
        h = np.clip(data.loc[history, column].to_numpy(float), metrics.EPS, 1 - metrics.EPS)
        p = np.clip(data.loc[target, column].to_numpy(float), metrics.EPS, 1 - metrics.EPS)
        fit = LogisticRegression(C=1.0, max_iter=1000).fit(np.log(h / (1 - h))[:, None], data.loc[history, "home_win"])
        data.loc[target, "recalibrated"] = fit.predict_proba(np.log(p / (1 - p))[:, None])[:, 1]
        data.loc[target, "calibration_training_max_season"] = data.loc[history, "season"].max()
    y, p, q = (data[k].to_numpy(float) for k in ("home_win", "reference", "recalibrated"))
    lp, lq = np.clip(p, metrics.EPS, 1 - metrics.EPS), np.clip(q, metrics.EPS, 1 - metrics.EPS)
    delta_ll = -(y * np.log(lq) + (1 - y) * np.log(1 - lq)) + (y * np.log(lp) + (1 - y) * np.log(1 - lp))
    ll_ci = clustered_difference(data["game_id"], delta_ll)
    brier_ci = clustered_difference(data["game_id"], (q - y) ** 2 - (p - y) ** 2)
    passed = ll_ci["difference"] <= -.002 and ll_ci["ci95"][1] < 0 and metrics.brier(y, q) <= metrics.brier(y, p)
    result = {"experiment": "B1 combined-probability recalibration", "champion_version": version, "champion_method": champion,
        "folds": list(DEV_FOLDS), "n": len(data), "champion_log_loss": metrics.log_loss(y, p),
        "calibrated_log_loss": metrics.log_loss(y, q), "log_loss_paired_ci": ll_ci,
        "champion_brier": metrics.brier(y, p), "calibrated_brier": metrics.brier(y, q), "brier_paired_ci": brier_ci,
        "passes": bool(passed), "decision": "shadow candidate pending multiplicity correction" if passed else "Rejected",
        "note": "Saved champion DEV predictions only; earliest fold unchanged warm-up. No later fold scoring or promotion."}
    data.to_parquet(OUT / "game_recalibration_dev.parquet", index=False)
    (OUT / "game_recalibration.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
