"""Amendment 2: does the game simulator already carry the quarterback to top-receiver link? python scripts/dependence_sim_check.py"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "artifacts" / "props"


def measure(c: pd.DataFrame, rng: np.random.Generator, b: int = 2000) -> dict:
    c = c.dropna(subset=["qb_act", "wr_act", "qb_sim", "wr_sim", "sim_corr"]).reset_index(drop=True)
    x, y, s = (c["qb_act"] - c["qb_sim"]).to_numpy(), (c["wr_act"] - c["wr_sim"]).to_numpy(), c["sim_corr"].to_numpy()
    d = np.corrcoef(x, y)[0, 1] - s.mean()
    ug, inv = np.unique(c["game_id"].to_numpy(), return_inverse=True)
    idx = [np.where(inv == i)[0] for i in range(len(ug))]
    ds = []
    for _ in range(b):
        k = np.concatenate([idx[i] for i in rng.integers(0, len(ug), len(ug))])
        ds.append(np.corrcoef(x[k], y[k])[0, 1] - s[k].mean())
    lo, hi = np.quantile(ds, [0.025, 0.975])
    verdict = "about right" if (lo > -0.10 and hi < 0.10) else "sim has too little" if lo > 0.10 else "sim has too much" if hi < -0.10 else "cannot say"
    return {"team_games": int(len(c)), "games": int(len(ug)), "actual_residual_corr": float(np.corrcoef(x, y)[0, 1]), "mean_sim_corr": float(s.mean()), "D": float(d), "ci95": [float(lo), float(hi)], "verdict": verdict}


if __name__ == "__main__":
    c = pd.concat([pd.read_parquet(P / "dev" / "correlation.parquet"), pd.read_parquet(P / "eval" / "correlation.parquet")], ignore_index=True)
    c["season"] = c["game_id"].str[:4].astype(int)
    rng = np.random.default_rng(20261106)
    out = {"primary_2022_2024": measure(c[c.season <= 2024], rng), "confirm_2025": measure(c[c.season == 2025], rng),
           "by_season_descriptive": {str(s): measure(c[c.season == s], rng) for s in (2022, 2023, 2024, 2025)}}
    (ROOT / "docs" / "dependence_sim_check.json").write_text(json.dumps(out, indent=1))
    for k in ("primary_2022_2024", "confirm_2025"):
        print(k, json.dumps({a: (round(b, 3) if isinstance(b, float) else b) for a, b in out[k].items() if a != "ci95"}), [round(v, 3) for v in out[k]["ci95"]])
    for s, v in out["by_season_descriptive"].items():
        print(s, round(v["actual_residual_corr"], 3), round(v["mean_sim_corr"], 3), round(v["D"], 3))
