"""B3/B5 synthetic-line O/U diagnostics, strictly earlier-week calibration.

No market prices or betting returns are claimed. Real 2022 GOING lines do not exist.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import poisson

from ... import metrics
from . import COUNTS, YARDS
from .data import OUT
from .research import clustered_difference


def run():
    frame = pd.read_parquet(OUT / "dev_predictions.parquet")
    if set(frame["season"].unique()) != {2022}:
        raise ValueError("2022 diagnostics only")
    rows = []
    for stat, group in frame.groupby("stat"):
        if stat == "anytime_td":
            continue
        methods = [c for c in ("equal", "weighted", "stacked", "logreg", "random_forest", "xgboost", "mlp", "sim_independent", "recent_mean")
                   if c in group and group[c].notna().any()]
        for week, target in group.groupby("week"):
            history = group[group["week"] < week]
            # Identical finite samples for all reported methods; exclude warm-up
            # rather than calibrating yard distributions on later 2022 outcomes.
            valid = history.dropna(subset=methods + ["actual"])
            current = target.dropna(subset=methods + ["actual", "recent_mean"])
            if stat in YARDS and len(valid) < 100:
                continue
            line = np.floor(current["recent_mean"].to_numpy(float)) + .5
            actual = current["actual"].to_numpy(float) > line
            for method in methods:
                mean = current[method].to_numpy(float)
                if stat in COUNTS:
                    probability = poisson.sf(np.floor(line), np.maximum(mean, 1e-6))
                    source = "Poisson rate approximation, including structural mean; descriptive"
                else:
                    residual = valid["actual"].to_numpy(float) - valid[method].to_numpy(float)
                    residual -= residual.mean()
                    probability = (mean[:, None] + residual[None, :] > line[:, None]).mean(1)
                    source = "centered strictly earlier-week OOF residuals"
                for i, (_, row) in enumerate(current.iterrows()):
                    rows.append({"game_id": row["game_id"], "week": int(week), "pid": row["pid"], "stat": stat,
                                 "method": method, "line": float(line[i]), "over": int(actual[i]),
                                 "p_over": float(probability[i]), "source": source, "calibration_rows": len(valid)})
    data = pd.DataFrame(rows)
    data.to_parquet(OUT / "synthetic_ou2022.parquet", index=False)
    summaries = []
    for (stat, method), d in data.groupby(["stat", "method"]):
        row = {"stat": stat, "method": method, "n": len(d), "games": d["game_id"].nunique(),
               "brier": metrics.brier(d["over"], d["p_over"]), "log_loss": metrics.log_loss(d["over"], d["p_over"]),
               "reliability": metrics.calibration_table(d["over"], d["p_over"]).to_dict("records")}
        base = data[(data["stat"] == stat) & (data["method"] == "recent_mean")]
        paired = d.merge(base[["game_id", "pid", "p_over"]].rename(columns={"p_over": "base_probability"}), on=["game_id", "pid"])
        row["brier_vs_recent_mean"] = clustered_difference(paired["game_id"],
            (paired["p_over"] - paired["over"]) ** 2 - (paired["base_probability"] - paired["over"]) ** 2)
        summaries.append(row)
    result = {"experiment": "B3 synthetic over/under", "results": summaries,
              "line_definition": "floor(prior recent-mean baseline)+0.5; synthetic, not market",
              "status": "descriptive development only; cannot establish market edge"}
    (OUT / "synthetic_ou_research2022.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    r = run()
    print(json.dumps({"comparisons": len(r["results"]), "status": r["status"]}))
