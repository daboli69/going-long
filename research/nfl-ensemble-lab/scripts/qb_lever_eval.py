"""Quarterback lever challengers C1-C4 against the champion. Rule: docs/QB_LEVER_PREREG.md (committed before this ran).

    .venv/Scripts/python.exe scripts/qb_lever_eval.py build     # slow: rebuilds the quarterback input for every week 2004-2025
    .venv/Scripts/python.exe scripts/qb_lever_eval.py eval      # development and holdout; writes docs/qb_lever_results.json

Read-only apart from data/cache/qb_lever and the results json. 2026 is excluded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import homewin_deep as h  # noqa: E402

OUT = ROOT / "data" / "cache" / "qb_lever"
FIRST, LAST = 2004, 2025
DEV = (2012, 2021)
HOLD = (2022, 2025)
BOOT, SEED = 2000, 20261110
HALF_LIFE_SEASONS = 1.0
VARIANTS = ["champion", "C1", "C2", "C3"]


def _allowed(qg: pd.DataFrame) -> pd.DataFrame:
    """Per game, what each defense allowed: the opposing offense's total dropbacks and EPA."""
    t = qg.groupby(["gid", "team", "season", "kickoff_utc"])[["n", "epa"]].sum().reset_index()
    t["opp"] = [g.split("_")[2] if g.split("_")[3] == tm else g.split("_")[3] for g, tm in zip(t["gid"], t["team"])]
    return t.rename(columns={"opp": "defense", "n": "n_allowed", "epa": "epa_allowed"})[["gid", "defense", "season", "kickoff_utc", "n_allowed", "epa_allowed"]]


def values_for(variant: str, qg_all: pd.DataFrame, allowed_all: pd.DataFrame, T: pd.Timestamp, season: int, prior_mean: float) -> pd.Series:
    rows = qg_all[qg_all["kickoff_utc"] < T].copy()
    if variant in ("C1", "C3"):
        al = allowed_all[allowed_all["kickoff_utc"] < T]
        league = al["epa_allowed"].sum() / al["n_allowed"].sum()
        ss = al.groupby(["season", "defense"])[["n_allowed", "epa_allowed"]].sum().rename(columns={"n_allowed": "N", "epa_allowed": "S"})
        rows["opp"] = [g.split("_")[2] if g.split("_")[3] == tm else g.split("_")[3] for g, tm in zip(rows["gid"], rows["team"])]
        rows = rows.join(ss, on=["season", "opp"])
        g_allowed = al.set_index(["gid", "defense"])[["n_allowed", "epa_allowed"]]
        j = rows.join(g_allowed, on=["gid", "opp"])
        nrest = j["N"] - j["n_allowed"]
        mean_excl = np.where(nrest > 0, (j["S"] - j["epa_allowed"]) / nrest.replace(0, np.nan), league)
        rows["epa"] = rows["epa"] - rows["n"] * (np.nan_to_num(mean_excl, nan=league) - league)
    w = 0.5 ** ((season - rows["season"]) / HALF_LIFE_SEASONS) if variant in ("C2", "C3") else 1.0
    rows["wn"], rows["we"] = rows["n"] * w, rows["epa"] * w
    agg = rows.groupby("qb")[["wn", "we"]].sum()
    return (agg["we"] + h.QB_N0 * prior_mean) / (agg["wn"] + h.QB_N0)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    data, _ = h.load_all(False)
    qg = data.qb_games
    allowed = _allowed(qg)
    pm = h.qb_prior_mean(qg[qg["season"] <= 2011])
    games = data.games
    recs = []
    for (s, w), g in games[(games["season"] >= FIRST) & (games["season"] <= LAST)].groupby(["season", "week"]):
        T = h.week_cutoff(data, s, w)
        vals = {v: values_for(v, qg, allowed, T, s, pm) for v in VARIANTS}
        for r in g.itertuples(index=False):
            row = {"gid": r.gid}
            for side, team in (("home", r.home), ("away", r.away)):
                for v in VARIANTS:
                    st = h.team_qb_state(data, team, s, w, T, vals[v], pm)
                    row[f"{v}_{side}"] = st["qb_delta"]
                    if v == "champion":
                        row[f"change_{side}"] = st["qb_change"]
            recs.append(row)
        print(s, w, flush=True) if w == 1 else None
    pd.DataFrame(recs).to_parquet(OUT / "variant_qb.parquet")
    print("built", len(recs))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def calib_slope(p, y):
    from sklearn.linear_model import LogisticRegression
    return float(LogisticRegression(C=1e6).fit(logit(p)[:, None], y).coef_[0][0])


def evaluate():
    feats = pd.read_parquet(h.CACHE / "features.parquet")
    vq = pd.read_parquet(OUT / "variant_qb.parquet")
    f = feats.merge(vq, on="gid", how="inner", suffixes=("", "_v"))
    f = f[f["played"] & ~f["tie"] & f["season"].between(FIRST, LAST)].copy()
    chk = float((f["champion_home"] - f["champion_away"] - f["qb_delta_diff"]).abs().max())
    print("champion rebuild max abs diff vs cached qb_delta_diff:", chk)
    assert chk < 1e-9, "rebuilt champion input does not match the production feature"
    base = [c for c in h.MARGIN_X if c != "qb_delta_diff"]
    f["change_diff"] = f["change_home"] - f["change_away"]
    specs = {"champion": base + ["champion"], "C1": base + ["C1"], "C2": base + ["C2"], "C3": base + ["C3"], "C4": base + ["champion", "change_diff"]}
    for v in VARIANTS:
        f[v] = f[f"{v}_home"] - f[f"{v}_away"]
    preds = {k: np.full(len(f), np.nan) for k in specs}
    sigmas = {k: np.full(len(f), np.nan) for k in specs}
    for s in range(DEV[0], HOLD[1] + 1):
        tr = (f["season"] < s) & (f["season"] >= h.MARGIN_TRAIN_START)
        te = (f["season"] == s).to_numpy()
        for k, cols in specs.items():
            X, y = f.loc[tr, cols].to_numpy(float), f.loc[tr, "margin"].to_numpy(float)
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            resid = y - X @ beta
            preds[k][te] = f.loc[te, cols].to_numpy(float) @ beta
            sigmas[k][te] = np.sqrt(resid @ resid / (len(y) - X.shape[1]))
    f = f[f["season"] >= DEV[0]].reset_index(drop=True)
    for k in specs:
        preds[k] = preds[k][-len(f):]
        sigmas[k] = sigmas[k][-len(f):]
    y_margin, y_win = f["margin"].to_numpy(float), f["y_home_win"].astype(int).to_numpy()
    se = {k: (y_margin - preds[k]) ** 2 for k in specs}
    prob = {k: norm.cdf(preds[k] / sigmas[k]) for k in specs}
    ll = {k: -(y_win * np.log(np.clip(prob[k], 1e-9, 1)) + (1 - y_win) * np.log(np.clip(1 - prob[k], 1e-9, 1))) for k in specs}
    rng = np.random.default_rng(SEED)
    out = {"champion_rebuild_max_abs_diff": chk, "slices": {}}
    swap = ((f["change_home"] == 1) | (f["change_away"] == 1)).to_numpy()
    for name, (a, b) in (("dev", DEV), ("holdout", HOLD)):
        m = f["season"].between(a, b).to_numpy()
        idx = np.where(m)[0]
        draws = [rng.integers(0, len(idx), len(idx)) for _ in range(BOOT)]
        res = {}
        for k in specs:
            if k == "champion":
                res[k] = {"n": int(m.sum()), "mse": float(se[k][m].mean()), "logloss": float(ll[k][m].mean()), "calib_slope": calib_slope(prob[k][m], y_win[m])}
                continue
            d_se, d_ll = se[k][m] - se["champion"][m], ll[k][m] - ll["champion"][m]
            bs = np.array([d_se[d].mean() for d in draws])
            res[k] = {"mse": float(se[k][m].mean()), "mse_delta": float(d_se.mean()), "mse_delta_ci95": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))],
                      "p_one_sided": float((bs >= 0).mean()), "logloss_delta": float(d_ll.mean()), "calib_slope": calib_slope(prob[k][m], y_win[m]),
                      "swap_games": int((swap & m).sum()), "swap_mse_delta": float(((se[k] - se["champion"])[m & swap]).mean()) if (swap & m).any() else None}
        out["slices"][name] = res
    ps = sorted((out["slices"]["holdout"][k]["p_one_sided"], k) for k in ("C1", "C2", "C3", "C4"))
    holm = {}
    for i, (p, k) in enumerate(ps):
        holm[k] = {"p": p, "alpha_i": 0.025 / (4 - i)}
    for i, (p, k) in enumerate(ps):
        passed_prev = all(holm[kk]["p"] <= holm[kk]["alpha_i"] for _, kk in ps[:i])
        holm[k]["holm_significant"] = bool(passed_prev and p <= holm[k]["alpha_i"])
    for k in ("C1", "C2", "C3", "C4"):
        r, dv = out["slices"]["holdout"][k], out["slices"]["dev"][k]
        r["holm"] = holm[k]
        r["passes_gate"] = bool(holm[k]["holm_significant"] and r["mse_delta_ci95"][1] < 0 and r["logloss_delta"] <= 0 and 0.9 <= r["calib_slope"] <= 1.1 and dv["mse_delta"] <= 0)
    (ROOT / "docs" / "qb_lever_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"build": build, "eval": evaluate}[sys.argv[1]]()
