"""Quarterback talent drift (Kalman local level). Rule: docs/QB_DRIFT_PREREG.md (committed before this ran).

    .venv/Scripts/python.exe scripts/qb_drift.py

Writes docs/qb_drift_results.json. Read-only otherwise; no network beyond the lab's normal game table load.
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
from lab.config import RAW_DIR  # noqa: E402

GRID = [0.0, 0.005, 0.01, 0.02, 0.04]
FIT = (2003, 2015)
TEST = (2016, 2025)
BOOT, SEED = 2000, 20261110
N0 = float(h.QB_N0)
WENTZ, MURRAY = "00-0032950", "00-0035228"


def league_var() -> float:
    v = []
    for s in range(FIT[0], FIT[1] + 1):
        p = pd.read_parquet(RAW_DIR / f"play_by_play_{s}.parquet", columns=["qb_dropback", "epa"])
        v.append(p.loc[(p["qb_dropback"] == 1) & p["epa"].notna(), "epa"].to_numpy())
    return float(np.var(np.concatenate(v), ddof=1))


def run_filter(g: pd.DataFrame, q: float, s2: float, pm: float):
    """g: one quarterback's games in time order. Returns per-game predictive mean/var (before the game) and the final state."""
    m, P = pm, s2 / N0
    pm_, pv_ = [], []
    for n, e in zip(g["n"].to_numpy(float), g["epa"].to_numpy(float)):
        Pp = P + q
        obs_var = s2 / n
        pm_.append(m)
        pv_.append(Pp + obs_var)
        K = Pp / (Pp + obs_var)
        m = m + K * (e / n - m)
        P = (1 - K) * Pp
    return np.array(pm_), np.array(pv_), m, P


def c2_pred(g: pd.DataFrame, pm: float) -> np.ndarray:
    seas, n, e = g["season"].to_numpy(float), g["n"].to_numpy(float), g["epa"].to_numpy(float)
    out = np.empty(len(g))
    for i in range(len(g)):
        w = 0.5 ** (seas[i] - seas[:i])
        out[i] = ((w * e[:i]).sum() + N0 * pm) / ((w * n[:i]).sum() + N0)
    return out


def main():
    data, _ = h.load_all(False)
    qg = data.qb_games.sort_values(["kickoff_utc", "gid"])
    pm = h.qb_prior_mean(qg[qg["season"] <= 2011])
    s2 = league_var()
    team_k = {}
    for r in data.games.itertuples(index=False):
        for t in (r.home, r.away):
            team_k.setdefault(t, []).append(r.kickoff_utc.value)
    team_k = {t: np.sort(np.array(v)) for t, v in team_k.items()}

    rows = {q: [] for q in GRID}
    meta = []
    for qb, g in qg.groupby("qb"):
        g = g.sort_values("kickoff_utc").reset_index(drop=True)
        runs = {q: run_filter(g, q, s2, pm) for q in GRID}
        c2 = c2_pred(g, pm)
        k = g["kickoff_utc"].map(lambda x: x.value).to_numpy()
        gap = np.zeros(len(g), int)
        for i in range(1, len(g)):
            ks = team_k.get(g.loc[i, "team"], np.array([]))
            gap[i] = int(((ks > k[i - 1]) & (ks < k[i])).sum()) if g.loc[i, "team"] == g.loc[i - 1, "team"] else 99
        ybar = g["epa"].to_numpy(float) / g["n"].to_numpy(float)
        base = pd.DataFrame({"qb": qb, "gid": g["gid"], "season": g["season"], "n": g["n"], "y": ybar, "c2": c2, "gap": gap})
        for q in GRID:
            rows[q].append(base.assign(mu=runs[q][0], var=runs[q][1]))
        meta.append((qb, {q: (runs[q][2], runs[q][3]) for q in GRID}))
    tabs = {q: pd.concat(rows[q], ignore_index=True) for q in GRID}

    def loglik(t):
        return float((norm.logpdf(t["y"], t["mu"], np.sqrt(t["var"]))).sum())

    fit = {q: loglik(tabs[q][tabs[q]["season"].between(*FIT)]) for q in GRID}
    q_star = max(fit, key=fit.get)
    print("fit loglik", fit, "q*", q_star)

    t0, tq = tabs[0.0], tabs[q_star]
    m = t0["season"].between(*TEST).to_numpy()
    w = t0.loc[m, "n"].to_numpy(float)
    se0 = (t0.loc[m, "y"] - t0.loc[m, "mu"]).to_numpy() ** 2
    seq = (tq.loc[m, "y"] - tq.loc[m, "mu"]).to_numpy() ** 2
    sec2 = (t0.loc[m, "y"] - t0.loc[m, "c2"]).to_numpy() ** 2
    ll0 = norm.logpdf(t0.loc[m, "y"], t0.loc[m, "mu"], np.sqrt(t0.loc[m, "var"]))
    llq = norm.logpdf(tq.loc[m, "y"], tq.loc[m, "mu"], np.sqrt(tq.loc[m, "var"]))
    rng = np.random.default_rng(SEED)

    def paired(a, b, mask=None):
        d = (a - b)
        ww = w
        if mask is not None:
            d, ww = d[mask], w[mask]
        if len(d) == 0:
            return None
        idx = [rng.integers(0, len(d), len(d)) for _ in range(BOOT)]
        bs = np.array([(d[i] * ww[i]).sum() / ww[i].sum() for i in idx])
        return {"games": int(len(d)), "delta_wmse": float((d * ww).sum() / ww.sum()), "ci95": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]}

    gap_m = (tq.loc[m, "gap"].to_numpy() >= 10)
    res = {"s2": s2, "prior_mean": pm, "fit_loglik": {str(k): v for k, v in fit.items()}, "q_star": q_star,
           "test": {"games": int(m.sum()), "wmse_q0": float((se0 * w).sum() / w.sum()), "wmse_qstar": float((seq * w).sum() / w.sum()), "wmse_c2": float((sec2 * w).sum() / w.sum()),
                    "qstar_vs_q0": paired(seq, se0), "qstar_vs_c2": paired(seq, sec2), "loglik_per_game_delta": float((llq - ll0).mean()),
                    "gap_or_team_change_qstar_vs_q0": paired(seq, se0, gap_m)}}
    t = res["test"]
    res["validation_pass"] = bool(q_star > 0 and t["qstar_vs_q0"]["ci95"][1] < 0 and t["loglik_per_game_delta"] > 0)

    state = dict(meta)
    qs = q_star
    pw = {"qb": "Carson Wentz", "id": WENTZ}, {"qb": "Kyler Murray", "id": MURRAY}
    reading = {}
    for d in pw:
        m_, P_ = state[d["id"]][qs]
        reading[d["qb"]] = {"talent": round(float(m_), 4), "sd": round(float(np.sqrt(P_)), 4)}
    dm = reading["Carson Wentz"]["talent"] - reading["Kyler Murray"]["talent"]
    dsd = float(np.hypot(reading["Carson Wentz"]["sd"], reading["Kyler Murray"]["sd"]))
    p = float(norm.cdf(dm / dsd))
    reading["difference"] = {"wentz_minus_murray": round(dm, 4), "lo80": round(dm - 1.2816 * dsd, 4), "hi80": round(dm + 1.2816 * dsd, 4), "p_wentz_higher": round(p, 3)}
    reading["verdict"] = ("supported" if p >= 0.9 else "contradicted" if p <= 0.1 else "not distinguishable") if res["validation_pass"] else "not used (validation failed)"
    paths = {}
    for d in pw:
        g = tabs[qs][tabs[qs]["qb"] == d["id"]]
        gg = qg[qg["qb"] == d["id"]].sort_values("kickoff_utc").reset_index(drop=True)
        mu_after = []
        _, _, _, _ = run_filter(gg, qs, s2, pm)
        mm, PP = pm, s2 / N0
        for n, e in zip(gg["n"].to_numpy(float), gg["epa"].to_numpy(float)):
            Pp = PP + qs
            K = Pp / (Pp + s2 / n)
            mm = mm + K * (e / n - mm)
            PP = (1 - K) * Pp
            mu_after.append((mm, PP))
        gg["mu"], gg["P"] = [a for a, _ in mu_after], [b for _, b in mu_after]
        last = gg.groupby("season").tail(1)
        paths[d["qb"]] = [{"season": int(r.season), "talent": round(float(r.mu), 3), "sd": round(float(np.sqrt(r.P)), 3)} for r in last.itertuples() if r.season >= 2018]
    res["wentz_murray"] = reading
    res["paths"] = paths
    (ROOT / "docs" / "qb_drift_results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
