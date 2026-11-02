"""Does tracking speed add to the explosive-play model? Big Data Bowl 2026 data (2023 season, weeks 1 to 18, pass plays only) in data/raw/kaggle.

For each receiver, his top route speed is the 90th percentile of the fastest speed he reached on each play he ran a route before the ball was thrown, from
weeks 1 to 9. The test is out of sample: does that speed explain which of his targets in weeks 10 to 18 (that start more than 15 yards out) gain more than 15
yards, beyond his own earlier rate of such gains? One extra parameter, tested by likelihood ratio. Output: docs/kingzone_speed_check.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import kz2 as K  # noqa: E402

BDB = ROOT / "data" / "raw" / "kaggle" / "nfl-big-data-bowl-2026-analytics"
SPLIT = 9
MIN_ROUTES = 15


def top_speeds() -> pd.DataFrame:
    parts = []
    for w in range(1, SPLIT + 1):
        d = pd.read_csv(BDB / f"input_2023_w{w:02d}.csv", usecols=["game_id", "play_id", "nfl_id", "s", "player_role"])
        d = d[d["player_role"].isin(["Targeted Receiver", "Other Route Runner"])]
        parts.append(d.groupby(["game_id", "play_id", "nfl_id"])["s"].max().reset_index())
    d = pd.concat(parts)
    g = d.groupby("nfl_id")["s"].agg(routes="size", top=lambda s: float(np.percentile(s, 90))).reset_index()
    return g[g["routes"] >= MIN_ROUTES]


def logit_fit(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    def nll(b):
        z = X @ b
        return float(np.sum(np.logaddexp(0, z) - y * z))
    r = minimize(nll, np.zeros(X.shape[1]), method="BFGS")
    return r.x, -r.fun


def main() -> None:
    sp = top_speeds()
    pl = pd.read_parquet(ROOT / "data" / "raw" / "players.parquet", columns=["gsis_id", "nfl_id"]).dropna()
    pl["nfl_id"] = pl["nfl_id"].astype(float).astype(int)
    sp = sp.merge(pl, on="nfl_id")
    t = K.load()["touches"]
    t = t[(t["kind"] == 1) & t["risk"]]
    early = t[((t["season"] == 2022)) | ((t["season"] == 2023) & (t["week"] <= SPLIT))]
    late = t[(t["season"] == 2023) & (t["week"] > SPLIT)]
    prior = early.groupby("pid")["exc"].agg(k="sum", n="size")
    base = float(early["exc"].mean())
    late = late.merge(sp[["gsis_id", "top", "routes"]], left_on="pid", right_on="gsis_id").merge(prior, left_on="pid", right_index=True, how="left").fillna({"k": 0, "n": 0})
    late["prior"] = (late["k"] + 8 * base) / (late["n"] + 8)
    late["lp"] = np.log(late["prior"] / (1 - late["prior"]))
    late["z"] = (late["top"] - late.groupby("pg")["top"].transform("mean")) / late["top"].std()
    y = late["exc"].to_numpy(float)
    X0 = np.column_stack([np.ones(len(late)), late["lp"]])
    X1 = np.column_stack([X0, late["z"]])
    b0, ll0 = logit_fit(X0, y)
    b1, ll1 = logit_fit(X1, y)
    lr = 2 * (ll1 - ll0)
    out = {"season_covered": 2023, "weeks_for_speed": f"1 to {SPLIT}", "weeks_scored": f"{SPLIT + 1} to 18", "receivers_with_speed": int(late["pid"].nunique()), "targets_scored": int(len(late)),
           "exceedances": int(y.sum()), "coef_prior_logit": float(b1[1]), "coef_speed_per_sd": float(b1[2]), "lr_chi2": float(lr), "p_value": float(stats.chi2.sf(lr, 1)),
           "loglik_without": float(ll0), "loglik_with": float(ll1),
           "note": "Covers the 2023 season only (pass plays, speed before the throw). A speed feature cannot be used for the 2022, 2024 and 2025 test seasons, so it is reported here and left out of the tested model."}
    (ROOT / "docs" / "kingzone_speed_check.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
