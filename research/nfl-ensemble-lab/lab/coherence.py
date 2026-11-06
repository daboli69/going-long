"""Coherence (docs/COHERENCE_PREREG.md). Test A: estimated reconciliation of a quarterback's passing forecast with his listed receivers' forecasts."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import dependence as D

FIT = (2022, 2023, 2024)
TEST = 2025
K_BUCKETS = (1, 2, 3, 4, 5)
R2_PLANTED = 0.03
GATE_LEVEL = 0.05 / 2
GATE_POWER = 0.80


def _bucket(k):
    return np.minimum(np.asarray(k), 5)


def load_teamgames(col: str = "base_mean") -> tuple[pd.DataFrame, pd.DataFrame]:
    a = pd.concat([pd.read_parquet(D.PROPS / "dev" / "player_games.parquet"), pd.read_parquet(D.PROPS / "eval" / "player_games.parquet")], ignore_index=True)
    a["position"] = a["pid"].map(D.positions())
    qb = a[a["stat"] == "pass_yds"]
    one = qb.groupby(["game_id", "team"]).size()
    qb = qb.merge(one[one == 1].rename("n").reset_index()[["game_id", "team"]], on=["game_id", "team"])[["game_id", "season", "team", col, "actual"]].rename(columns={col: "fQ", "actual": "yQ"})
    r = a[(a["stat"] == "rec_yds") & a["position"].isin(["WR", "TE", "RB"])][["game_id", "team", "pid", col, "actual"]].rename(columns={col: "f", "actual": "y"})
    r = r.merge(qb[["game_id", "team"]], on=["game_id", "team"])
    g = r.groupby(["game_id", "team"]).agg(k=("f", "size"), Rf=("f", "sum"), Ry=("y", "sum")).reset_index()
    tg = qb.merge(g, on=["game_id", "team"])
    r = r.merge(tg[["game_id", "team", "season", "Rf"]], on=["game_id", "team"])
    return tg, r


def share_by_k(tg: pd.DataFrame) -> dict:
    f = tg[tg["season"].isin(FIT)]
    out = {}
    for k in K_BUCKETS:
        s = f[_bucket(f["k"]) == k]
        out[k] = float((s["yQ"] - s["Ry"]).sum() / s["yQ"].sum()) if len(s) else 0.0
    return out


def incoherence(tg: pd.DataFrame, share: dict) -> np.ndarray:
    return (tg["fQ"] - tg["Rf"] - tg["fQ"] * tg["k"].map(lambda k: share[int(_bucket(k))])).to_numpy()


def fit_slopes(tg: pd.DataFrame, r: pd.DataFrame, share: dict) -> dict:
    f = tg[tg["season"].isin(FIT)]
    c = pd.Series(incoherence(tg, share), index=tg.index)
    cq = c[f.index].to_numpy()
    eq = (f["yQ"] - f["fQ"]).to_numpy()
    bq = float((cq * eq).sum() / (cq * cq).sum())
    cmap = tg.assign(c=c).set_index(["game_id", "team"])["c"]
    fr = r[r["season"].isin(FIT)]
    x = fr.set_index(["game_id", "team"]).index.map(cmap).to_numpy() * (fr["f"] / fr["Rf"]).to_numpy()
    e = (fr["y"] - fr["f"]).to_numpy()
    br = float((x * e).sum() / (x * x).sum())
    return {"b_Q": bq, "b_R": br}


def reconcile_score(tg: pd.DataFrame, r: pd.DataFrame, share: dict, b: dict) -> dict:
    """Held-out squared-error differences (unreconciled minus reconciled), averaged within game."""
    t = tg[tg["season"] == TEST].copy()
    t["c"] = incoherence(t, share)
    dq = (t["yQ"] - t["fQ"]) ** 2 - (t["yQ"] - (t["fQ"] + b["b_Q"] * t["c"])) ** 2
    rr = r[r["season"] == TEST].merge(t[["game_id", "team", "c"]], on=["game_id", "team"])
    adj = b["b_R"] * rr["c"] * rr["f"] / rr["Rf"]
    dr = (rr["y"] - rr["f"]) ** 2 - (rr["y"] - rr["f"] - adj) ** 2
    return {"g_Q": D.game_means(dq.to_numpy(), t["game_id"].to_numpy()), "g_R": D.game_means(dr.to_numpy(), rr["game_id"].to_numpy()),
            "mse_Q": float(((t["yQ"] - t["fQ"]) ** 2).mean()), "mse_R": float(((rr["y"] - rr["f"]) ** 2).mean())}


def planted_data(tg: pd.DataFrame, r: pd.DataFrame, share: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Replace actuals with f + b c + noise so that c explains R2_PLANTED of each group's error variance. Uses forecast means and structure only."""
    tg, r = tg.copy(), r.copy()
    c = pd.Series(incoherence(tg, share), index=tg.index)
    sq = 0.30 * tg["fQ"]
    bq = np.sqrt(R2_PLANTED / (1 - R2_PLANTED)) * np.sqrt((sq ** 2).mean()) / np.sqrt((c ** 2).mean())
    tg["yQ"] = tg["fQ"] + bq * c + rng.standard_normal(len(tg)) * sq
    cmap = tg.assign(c=c).set_index(["game_id", "team"])["c"]
    r["c"] = r.set_index(["game_id", "team"]).index.map(cmap).to_numpy()
    w = r["f"] / r["Rf"]
    sr = 0.8 * r["f"] + 5
    br = np.sqrt(R2_PLANTED / (1 - R2_PLANTED)) * np.sqrt((sr ** 2).mean()) / np.sqrt(((r["c"] * w) ** 2).mean())
    r["y"] = r["f"] + br * r["c"] * w + rng.standard_normal(len(r)) * sr
    ry = r.groupby(["game_id", "team"])["y"].sum().rename("Ry_new").reset_index()
    tg = tg.merge(ry, on=["game_id", "team"]).drop(columns="Ry").rename(columns={"Ry_new": "Ry"})
    return tg, r.drop(columns="c"), {"b_Q": float(bq), "b_R": float(br)}


def gate(tg: pd.DataFrame, r: pd.DataFrame, rng: np.random.Generator, reps: int = 400, scan=(2, 3, 5)) -> dict:
    share = share_by_k(tg)  # structure only: shares are re-estimated from planted actuals inside each run
    res = {"Q": [], "R": []}
    est = {"b_Q": [], "b_R": []}
    planted = None
    for _ in range(reps):
        tg2, r2, planted = planted_data(tg, r, share, rng)
        sh = share_by_k(tg2)
        b = fit_slopes(tg2, r2, sh)
        s = reconcile_score(tg2, r2, sh, b)
        res["Q"].append(D.dm_p(s["g_Q"])[1]); res["R"].append(D.dm_p(s["g_R"])[1])
        est["b_Q"].append(b["b_Q"]); est["b_R"].append(b["b_R"])
    out = {"planted": planted, "mean_estimated": {k: float(np.mean(v)) for k, v in est.items()}}
    out["recovery_ok"] = {k: bool(abs(np.mean(est[k]) - planted[k]) <= 0.25 * abs(planted[k])) for k in planted}
    out["test_games"] = int(tg.loc[tg["season"] == TEST, "game_id"].nunique())
    out["power"] = {k: float(np.mean(np.array(v) < GATE_LEVEL)) for k, v in res.items()}
    out["informative"] = {"Q": bool(out["power"]["Q"] >= GATE_POWER and out["recovery_ok"]["b_Q"]), "R": bool(out["power"]["R"] >= GATE_POWER and out["recovery_ok"]["b_R"])}
    out["scan"] = {}
    for k in scan:
        tk, rk = _replicate_test(tg, r, k)
        pw = {"Q": [], "R": []}
        for _ in range(150):
            t2, r2, _p = planted_data(tk, rk, share, rng)
            sh = share_by_k(t2)
            sc = reconcile_score(t2, r2, sh, fit_slopes(t2, r2, sh))
            pw["Q"].append(D.dm_p(sc["g_Q"])[1]); pw["R"].append(D.dm_p(sc["g_R"])[1])
        out["scan"][str(k)] = {"games": out["test_games"] * k, **{g: float(np.mean(np.array(v) < GATE_LEVEL)) for g, v in pw.items()}}
    out["games_for_80pct_power"] = {g: next((v["games"] for v in out["scan"].values() if v[g] >= GATE_POWER), None) for g in ("Q", "R")}
    return out


def _replicate_test(tg: pd.DataFrame, r: pd.DataFrame, k: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    keep = tg["season"] != TEST
    t = tg[~keep]
    tg2 = pd.concat([tg[keep]] + [t.assign(game_id=t["game_id"] + f"#{i}") for i in range(k)], ignore_index=True)
    rt = r[r["season"] == TEST]
    r2 = pd.concat([r[r["season"] != TEST]] + [rt.assign(game_id=rt["game_id"] + f"#{i}") for i in range(k)], ignore_index=True)
    return tg2, r2
