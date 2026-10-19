"""One fixed 2022 development analysis; paired game-cluster confidence intervals."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ... import metrics
from . import COUNTS, TARGETS, YARDS
from .combine import loss_rows
from .data import OUT


def paired_ci(frame, first, second, target="actual", stat=None, boot=2000):
    d = frame.dropna(subset=[first, second, target])
    if not len(d):
        return {"n": 0, "games": 0, "difference": None, "ci95": None}
    loss = loss_rows(stat, d[target], d[first]) - loss_rows(stat, d[target], d[second])
    return clustered_difference(d["game_id"], loss, boot)


def clustered_difference(game_ids, difference, boot=2000):
    d = pd.DataFrame({"game": np.asarray(game_ids), "difference": np.asarray(difference, float)}).dropna()
    group = d.groupby("game")["difference"].agg(["sum", "size"])
    if not len(group):
        return {"n": 0, "games": 0, "difference": None, "ci95": None}
    rng = np.random.default_rng(20261019)
    sampled = rng.integers(0, len(group), (boot, len(group)))
    means = group["sum"].to_numpy()[sampled].sum(1) / group["size"].to_numpy()[sampled].sum(1)
    ci = np.quantile(means, [.025, .975]).tolist()
    observed = float(d["difference"].mean())
    p = float((np.sum((means - observed) <= observed) + 1) / (boot + 1))
    return {"n": len(d), "games": len(group), "difference": observed, "ci95": ci,
            "p_improvement_one_sided": p}


def analyze():
    frame = pd.read_parquet(OUT / "dev_predictions.parquet")
    if set(frame["season"].unique()) != {2022}:
        raise ValueError("Phase 10 development analysis must contain 2022 only")
    results, diagnostics = [], {}
    for stat in TARGETS:
        d = frame[frame["stat"] == stat]
        methods = [m for m in ("equal", "weighted", "stacked", "logreg", "random_forest", "xgboost", "mlp",
                               "simulator_v1", "sim_independent", "recent_mean") if m in d and d[m].notna().any()]
        for method in methods:
            a = d.dropna(subset=[method, "actual"])
            row = {"experiment": "B3", "stat": stat, "method": method, "n": len(a), "games": a["game_id"].nunique(),
                   "metric": "Brier" if stat == "anytime_td" else "Poisson deviance" if stat in COUNTS else "MAE",
                   "loss": float(loss_rows(stat, a["actual"], a[method]).mean())}
            row["vs_recent_mean"] = paired_ci(a, method, "recent_mean", stat=stat)
            for baseline in ("simulator_v1", "sim_independent", "baseline_B"):
                if baseline in a and a[baseline].notna().any():
                    row["vs_" + baseline] = paired_ci(a, method, baseline, stat=stat)
            if stat == "anytime_td":
                row["log_loss"] = metrics.log_loss(a["actual"], a[method])
                diagnostics[stat + "/" + method] = metrics.calibration_table(a["actual"], a[method]).to_dict("records")
            if stat in YARDS:
                row["rmse"] = float(np.sqrt(np.mean((a["actual"] - a[method]) ** 2)))
            # No pass claim unless BOTH specified v1 and baseline B comparisons
            # exist and pass the pre-registered CI rule on >=100 games.
            comparisons = [row.get("vs_simulator_v1"), row.get("vs_baseline_B")]
            row["passes"] = bool(all(c and c["games"] >= 100 and c["ci95"][1] < 0 for c in comparisons))
            row["decision"] = "Challenger only" if row["passes"] else "research-only; primary acceptance not met"
            results.append(row)
        if stat in YARDS and all(k in d for k in ("q10", "q50", "q90")):
            a = d.dropna(subset=["q10", "q50", "q90", "actual"])
            pinball = {}
            for q in (10, 50, 90):
                error = a["actual"] - a[f"q{q}"]
                pinball[str(q)] = float(np.maximum(q / 100 * error, (q / 100 - 1) * error).mean())
            diagnostics[stat + "/quantile_head"] = {"n": len(a), "pinball": pinball,
                "coverage80": float(((a["actual"] >= a["q10"]) & (a["actual"] <= a["q90"])).mean()),
                "note": "Quantile-head intervals; not calibrated ensemble intervals"}
    td = frame[frame["stat"] == "anytime_td"]
    if "redzone_only" in td:
        comparison = paired_ci(td, "logreg", "redzone_only", stat="anytime_td")
        diagnostics["B4"] = comparison | {"passes": bool(comparison["games"] >= 100 and comparison["difference"] <= -.001
                                                     and comparison["ci95"][1] < 0)}
    result = {"split": "fit <=2021; walk-forward 2022 meta-learning", "results": results, "diagnostics": diagnostics,
              "status": "shadow only", "limitations": [
                  "GOING game/prop history starts in 2026: no authorized 2022 market anchors, v1 comparator blocked",
                  "recent_mean is a simple independent benchmark, not original market-scaled baseline B",
                  "2022 is reused development, not a new untouched holdout",
                  "historical prior-roster eligibility can miss offseason transactions",
                  "market-informed 2022 ablation blocked without timestamped 2022 quotes"]}
    (OUT / "research2022.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)} for r in results]).to_csv(OUT / "metrics2022.csv", index=False)
    return result


if __name__ == "__main__":
    r = analyze()
    print(pd.read_csv(OUT / "metrics2022.csv").to_string(index=False))
