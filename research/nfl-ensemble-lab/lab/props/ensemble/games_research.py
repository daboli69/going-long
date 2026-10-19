"""Independent game-anchor diagnostics on longrun DEV_FOLDS only."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ...data_pipeline import FEATURE_STORE
from ...config import ARTIFACTS_DIR, MODELS_DIR
from ...longrun import DEV_FOLDS
from ..independent import IndependentAnchor
from .data import OUT
from .research import clustered_difference


def run():
    frame = pd.read_parquet(FEATURE_STORE)
    rows = []
    levels = np.arange(1, 100) / 100
    for season in DEV_FOLDS:
        anchor = IndependentAnchor().fit(frame, min(season - 1, 2021))
        target = frame[(frame["season"] == season) & frame["home_score"].notna() & frame["game_type"].eq("REG")]
        pred = anchor.predict(target)
        prior = frame[(frame["season"] < season) & frame["home_score"].notna() & frame["game_type"].eq("REG")]
        for stat in ("margin", "total"):
            actual = (target["home_score"] - target["away_score"] if stat == "margin" else target["home_score"] + target["away_score"]).to_numpy()
            baseline = 0 if stat == "margin" else float((prior["home_score"] + prior["away_score"]).mean())
            prior_actual = (prior["home_score"] - prior["away_score"] if stat == "margin" else prior["home_score"] + prior["away_score"]).to_numpy()
            baseline_quantiles = baseline + np.quantile(prior_actual - prior_actual.mean(), levels)
            base_error = actual[:, None] - baseline_quantiles[None, :]
            baseline_crps = 2 * np.maximum(levels * base_error, (levels - 1) * base_error).mean(1)
            value = pred[stat].to_numpy()
            q = value[:, None] + np.quantile(anchor.residuals[stat], levels)[None, :]
            error = actual[:, None] - q
            crps = 2 * np.maximum(levels * error, (levels - 1) * error).mean(1)
            for i, gid in enumerate(target["game_id"]):
                rows.append({"game_id": gid, "season": season, "stat": stat, "actual": actual[i], "prediction": value[i],
                    "baseline": baseline, "absolute_error": abs(value[i] - actual[i]), "squared_error": (value[i] - actual[i]) ** 2,
                    "baseline_absolute_error": abs(baseline - actual[i]), "crps": crps[i], "baseline_crps": baseline_crps[i],
                    "coverage80": float(pred[f"{stat}_q10"].iloc[i] <= actual[i] <= pred[f"{stat}_q90"].iloc[i])})
    result = pd.DataFrame(rows)
    result.to_parquet(OUT / "game_dev_predictions.parquet", index=False)
    summaries = []
    for stat, d in result.groupby("stat"):
        ci = clustered_difference(d["game_id"], d["absolute_error"] - d["baseline_absolute_error"])
        crps_ci = clustered_difference(d["game_id"], d["crps"] - d["baseline_crps"])
        summaries.append({"experiment": "B2", "stat": stat, "n": len(d), "mae": float(d["absolute_error"].mean()),
            "rmse": float(np.sqrt(d["squared_error"].mean())), "bias": float((d["prediction"] - d["actual"]).mean()),
            "crps": float(d["crps"].mean()), "coverage80": float(d["coverage80"].mean()), "vs_baseline_mae": ci,
            "baseline_crps": float(d["baseline_crps"].mean()), "vs_baseline_crps": crps_ci,
            "baseline_thresholds_met": bool(ci["ci95"][1] < 0 and crps_ci["ci95"][1] < 0 and .75 <= d["coverage80"].mean() <= .85),
            "decision": "research only pending multiplicity adjustment; timestamp-eligible market comparison unavailable",
            "market_comparison": "blocked: authorized GOING history does not cover DEV_FOLDS; no closing-line fallback"})
    # Saved champion point margin, DEV rows/columns only. Never read market values.
    version = json.loads((MODELS_DIR / "CURRENT.json").read_text())["version"]
    champion = pd.read_parquet(ARTIFACTS_DIR / "runs" / version / "oof_predictions.parquet",
                               columns=["game_id", "margin_ensemble"], filters=[("season", "in", list(DEV_FOLDS))])
    margins = result[result["stat"] == "margin"].merge(champion, on="game_id").dropna(subset=["margin_ensemble"])
    for summary in summaries:
        if summary["stat"] == "margin":
            summary["vs_champion_margin_mae"] = clustered_difference(margins["game_id"], margins["absolute_error"] -
                                                                        abs(margins["margin_ensemble"] - margins["actual"]))
    (OUT / "game_research.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    return summaries


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
