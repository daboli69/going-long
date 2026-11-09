"""Matchup features against the closing line. Stages: gate. Rule: docs/MATCHUP_PREREG.md (Amendment 1).

    .venv\\Scripts\\python.exe scripts\\matchup_run.py gate

The gate never computes the real challenger-minus-champion difference. It runs the shuffled-feature (placebo) check and the planted-effect check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import matchup as M  # noqa: E402

DOCS = ROOT / "docs"
SEED = 20261108
RUNS = 200
PLANT = 0.004
MDE_MAX, POWER_MIN = 0.006, 0.80
HYP = {"H1": (M.H1, "net_eff"), "H2": (M.H2, "int_prod")}


def shuffled(df: pd.DataFrame, cols: list[str], rng: np.random.Generator) -> pd.DataFrame:
    """Permute the feature rows across games within the same season and week (the columns move together)."""
    d = df.copy()
    out = d[cols].to_numpy().copy()
    for _, idx in d.groupby(["season", "week"]).indices.items():
        out[idx] = out[rng.permutation(idx)]
    d[cols] = out
    return d


def pooled(oos: pd.DataFrame) -> float:
    return float(M.paired(oos)["dll"].mean())


def plant_b(df: pd.DataFrame, col: str) -> float:
    """b such that the true probability (champion log-odds plus b x the standardised feature) beats the champion by PLANT nats on average, 2022 to 2025."""
    t = df[(df["season"] >= M.FIRST_TEST) & (df["season"] <= M.LAST_TEST)]
    z = (t[col] - df[col].mean()) / df[col].std()
    pm = 1 / (1 + np.exp(-t["m"].to_numpy()))

    def kl(b):
        pt = 1 / (1 + np.exp(-(t["m"].to_numpy() + b * z.to_numpy())))
        return float(np.mean(pt * np.log(pt / pm) + (1 - pt) * np.log((1 - pt) / (1 - pm))))
    lo, hi = 0.0, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if kl(mid) < PLANT else (lo, mid)
    return (lo + hi) / 2


def gate():
    df = pd.read_parquet(ROOT / "data" / "cache" / "matchup_features.parquet") if (ROOT / "data" / "cache" / "matchup_features.parquet").exists() else M.build()
    n_test = int(((df["season"] >= M.FIRST_TEST) & (df["season"] <= M.LAST_TEST)).sum())
    out = {"games_total": int(len(df)), "games_test_2022_2025": n_test, "seed": SEED, "runs": RUNS, "planted_gain": PLANT}
    for h, (cols, first) in HYP.items():
        rng = np.random.default_rng(SEED + (0 if h == "H1" else 1))
        plc = np.array([pooled(M.walk(shuffled(df, cols, rng), cols)) for _ in range(RUNS)])
        sd = float(plc.std(ddof=1))
        mde = 2.8 * sd
        b = plant_b(df, first)
        z = (df[first] - df[first].mean()) / df[first].std()
        p_true = 1 / (1 + np.exp(-(df["m"] + b * z)))
        fired, gains = 0, []
        for _ in range(RUNS):
            d = df.assign(ysim=(rng.random(len(df)) < p_true.to_numpy()).astype(float))
            pr = M.paired(M.walk(d, cols, y_col="ysim"))
            fired += M.passes(pr)
            gains.append(-float(pr["dll"].mean()))
        power = fired / RUNS
        out[h] = {"features": cols, "placebo_mean": float(plc.mean()), "placebo_sd": sd, "smallest_detectable": float(mde), "planted_b": float(b),
                  "planted_recovered_gain": float(np.mean(gains)), "planted_power": power,
                  "testable": bool(mde <= MDE_MAX and power >= POWER_MIN)}
        print(h, {k: (round(v, 5) if isinstance(v, float) else v) for k, v in out[h].items()})
    (DOCS / "matchup_gate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def diagnostic():
    """Which part of the pass rule binds in the planted-effect runs, at planted gains of 0.004 and 0.008 (descriptive; the gate verdict does not use it)."""
    global PLANT
    df = pd.read_parquet(ROOT / "data" / "cache" / "matchup_features.parquet")
    res = {}
    for h, (cols, first) in HYP.items():
        for plant in (0.004, 0.008):
            PLANT = plant
            b = plant_b(df, first)
            z = (df[first] - df[first].mean()) / df[first].std()
            pt = 1 / (1 + np.exp(-(df["m"] + b * z)))
            rng = np.random.default_rng(7)
            c = {"gain": [], "interval": 0, "min_gain": 0, "three_of_four": 0, "brier": 0, "all": 0}
            for _ in range(RUNS):
                d = df.assign(ysim=(rng.random(len(df)) < pt.to_numpy()).astype(float))
                pr = M.paired(M.walk(d, cols, y_col="ysim"))
                mean, se = M.week_se(pr)
                a, m_, s_, b_ = mean + 1.96 * se < 0, mean <= -0.002, int((pr.groupby("season")["dll"].mean() < 0).sum()) >= 3, pr["dbr"].mean() <= 0
                c["gain"].append(-mean)
                c["interval"] += int(a); c["min_gain"] += int(m_); c["three_of_four"] += int(s_); c["brier"] += int(b_); c["all"] += int(a and m_ and s_ and b_)
            res[f"{h}_planted_{plant}"] = {"planted_b": round(b, 3), "mean_gain": round(float(np.mean(c["gain"])), 5), "sd_gain": round(float(np.std(c["gain"])), 5),
                                           **{k: v / RUNS for k, v in c.items() if k != "gain"}}
            print(h, plant, res[f"{h}_planted_{plant}"])
    (DOCS / "matchup_gate_diagnostic.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    {"gate": gate, "diagnostic": diagnostic}[sys.argv[1]]()
