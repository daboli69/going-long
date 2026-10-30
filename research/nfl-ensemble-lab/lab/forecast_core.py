"""Joint score model and Kalshi-ladder tools. Protocol: docs/FORECAST_PREREGISTRATION.md (commit 94e455cc).

Closed-form Gaussian conjugate posterior (what PyMC would sample for this model). Local, $0, no trading code.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import homewin_deep as h
from . import props_kalshi as pk

PREREG = "94e455cc"
SD0 = 13.5
HALF_LIFE = 365.0
R_LAG = pd.Timedelta(minutes=90) + pd.Timedelta(hours=4)
MIN_TRAIN_GAMES = 300
LV = np.arange(1, 100) / 100.0


# --------------------------------------------------------------------------- scoring primitives

def crps_normal(y, mu, sd):
    y, mu, sd = np.asarray(y, float), np.asarray(mu, float), np.asarray(sd, float)
    z = (y - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def p_win(mu, sd):
    a, b = norm.cdf((0.5 - mu) / sd), norm.cdf((-0.5 - mu) / sd)
    return 1 - a + 0.5 * (a - b)


def log_loss_vec(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def pin_crps(Q: np.ndarray, y: np.ndarray) -> np.ndarray:
    """2 * mean pinball loss over the 99 quantile levels (a CRPS approximation); Q is n x 99."""
    d = y[:, None] - Q
    return 2 * np.maximum(LV * d, (LV - 1) * d).mean(1)


def games_frame() -> pd.DataFrame:
    g, _ = h.load_games()
    g, _ = h._with_elo(g)
    g["total"] = g["score_home"] + g["score_away"]
    return g.sort_values("kickoff_utc").reset_index(drop=True)


# --------------------------------------------------------------------------- Gaussian team-strength model

def _design(df: pd.DataFrame, tix: dict, kind: str) -> np.ndarray:
    n, T = len(df), len(tix)
    X = np.zeros((n, 1 + T))
    r = np.arange(n)
    hi, ai = df["home"].map(tix).to_numpy(), df["away"].map(tix).to_numpy()
    if kind == "margin":
        X[:, 0] = 1 - df["neutral"].to_numpy(float)
        X[r, 1 + hi] += 1
        X[r, 1 + ai] -= 1
    else:
        X[:, 0] = 1
        X[r, 1 + hi] += 1
        X[r, 1 + ai] += 1
    return X


def _gauss(X, y, w, prior_prec):
    w = w / w.mean()
    sig2 = float(np.average((y - np.average(y, weights=w)) ** 2, weights=w))
    for _ in range(3):
        A = (X.T * w) @ X / sig2 + np.diag(prior_prec)
        Ainv = np.linalg.inv(A)
        beta = Ainv @ (X.T @ (w * y)) / sig2
        r = y - X @ beta
        dof = float(np.einsum("ij,jk,ik,i->", X, Ainv, X, w)) / sig2
        sig2 = float((w * r * r).sum() / max(len(y) - dof, 1.0))
    return beta, Ainv, sig2, r, w


def week_cutoff(wk: pd.DataFrame) -> pd.Timestamp:
    return wk["kickoff_utc"].min() - R_LAG


def predict_week(G: pd.DataFrame, wk: pd.DataFrame, tau_n: float, tau_s: float, tix: dict) -> pd.DataFrame | None:
    """Fit on games before the week's cutoff and predict every game in `wk` (played or not)."""
    s = int(wk["season"].iloc[0])
    R = week_cutoff(wk)
    tr = G[G["played"] & (G["kickoff_utc"] < R) & (G["season"] >= s - 2)]
    if len(tr) < MIN_TRAIN_GAMES:
        return None
    age = (R - tr["kickoff_utc"]).dt.total_seconds().to_numpy() / 86400
    w = 0.5 ** (age / HALF_LIFE)
    T = len(tix)
    out = {}
    res = {}
    for kind, tau, y in (("margin", tau_n, (tr["score_home"] - tr["score_away"]).to_numpy(float)),
                         ("total", tau_s, (tr["score_home"] + tr["score_away"]).to_numpy(float))):
        X = _design(tr, tix, kind)
        pp = np.r_[1e-6, np.full(T, 1 / tau ** 2)]
        beta, Ainv, sig2, r, wn = _gauss(X, y, w, pp)
        Xt = _design(wk, tix, kind)
        mu = Xt @ beta
        sd = np.sqrt(sig2 + np.einsum("ij,jk,ik->i", Xt, Ainv, Xt))
        out[kind] = (mu, sd)
        res[kind] = (r, wn, y)
    rm, rt, wn = res["margin"][0], res["total"][0], res["margin"][1]
    rho = float(np.average(rm * rt, weights=wn) / np.sqrt(np.average(rm ** 2, weights=wn) * np.average(rt ** 2, weights=wn)))
    mu_m, sd_m = out["margin"]
    mu_t, sd_t = out["total"]
    wsum = w / w.sum()
    ym, yt = res["margin"][2], res["total"][2]
    nm_mu = float((wsum * ym).sum())
    nm_sd = float(np.sqrt((wsum * (ym - nm_mu) ** 2).sum()))
    nt_mu = float((wsum * yt).sum())
    nt_sd = float(np.sqrt((wsum * (yt - nt_mu) ** 2).sum()))
    elo_mu = SD0 * norm.ppf(np.clip(wk["elo_prob_home"].to_numpy(float), 1e-4, 1 - 1e-4))
    return pd.DataFrame({"gid": wk["gid"].to_numpy(), "season": s, "week": int(wk["week"].iloc[0]), "kickoff_utc": wk["kickoff_utc"].to_numpy(),
                         "played": wk["played"].to_numpy(), "tie": wk["tie"].to_numpy(), "y_m": wk["margin"].to_numpy(float),
                         "y_t": wk["total"].to_numpy(float), "mu_m": mu_m, "sd_m": sd_m, "mu_t": mu_t, "sd_t": sd_t, "rho": rho,
                         "p_win": p_win(mu_m, sd_m), "p_elo": wk["elo_prob_home"].to_numpy(float), "elo_mu": elo_mu,
                         "naive_m_mu": nm_mu, "naive_m_sd": nm_sd, "naive_t_mu": nt_mu, "naive_t_sd": nt_sd})


def walk_forward(G: pd.DataFrame, tau_n: float, tau_s: float, seasons: range, include_unplayed: bool = False) -> pd.DataFrame:
    teams = sorted(set(G["home"]) | set(G["away"]))
    tix = {t: i for i, t in enumerate(teams)}
    parts = []
    for (s, w), wk in G[G["season"].isin(list(seasons))].groupby(["season", "week"]):
        if not include_unplayed and not wk["played"].any():
            continue
        p = predict_week(G, wk if include_unplayed else wk[wk["played"]], tau_n, tau_s, tix)
        if p is not None:
            parts.append(p)
    return pd.concat(parts, ignore_index=True)


def tune_tau(G: pd.DataFrame, seasons=range(2008, 2012), grid=(2.0, 3.0, 4.0, 5.0)) -> dict:
    """Choose tau_n (margin CRPS) and tau_s (total CRPS) once on development seasons; nothing later is used."""
    rows = {"margin": {}, "total": {}}
    for t in grid:
        wf = walk_forward(G, t, 3.0, seasons)
        rows["margin"][t] = float(crps_normal(wf["y_m"], wf["mu_m"], wf["sd_m"]).mean())
        wf = walk_forward(G, 3.0, t, seasons)
        rows["total"][t] = float(crps_normal(wf["y_t"], wf["mu_t"], wf["sd_t"]).mean())
    return {"tau_n": min(rows["margin"], key=rows["margin"].get), "tau_s": min(rows["total"], key=rows["total"].get), "grid": rows}


# --------------------------------------------------------------------------- Kalshi ladders (spread, total, winner)

def ladder_tables(q: pd.DataFrame, games: pd.DataFrame, winner_p: dict, point: str = "90") -> dict:
    """{(gid, 'margin'|'total'): DataFrame(c, p_raw, p_iso, w)} using thresholds liquid at `point` (plus the winner price at 0.5)."""
    mid, bid, ask, liq = f"mid{point}", f"bid{point}", f"ask{point}", f"liquid{point}"
    gm = games.set_index("gid")[["home", "away"]]
    e = q[q["series"].isin(["KXNFLSPREAD", "KXNFLTOTAL"]) & q[liq].astype(bool) & q[mid].notna() & q["strike"].notna()].copy()
    rows = []
    for r in e.itertuples(index=False):
        if r.gid not in gm.index:
            continue
        w = 1 / max(getattr(r, ask) - getattr(r, bid), 0.01) if pd.notna(getattr(r, bid)) and pd.notna(getattr(r, ask)) else 1.0
        m = getattr(r, mid)
        if r.series == "KXNFLTOTAL":
            rows.append((r.gid, "total", float(r.strike), m, w))
        elif r.team == gm.at[r.gid, "home"]:
            rows.append((r.gid, "margin", float(r.strike), m, w))
        elif r.team == gm.at[r.gid, "away"]:
            rows.append((r.gid, "margin", -float(r.strike), 1 - m, w))
    for gid, p in winner_p.items():
        if pd.notna(p):
            rows.append((gid, "margin", 0.5, float(p), 20.0))
    t = pd.DataFrame(rows, columns=["gid", "target", "c", "p_raw", "w"])
    out = {}
    for (gid, tgt), g in t.groupby(["gid", "target"]):
        g = g.groupby("c", as_index=False).agg(p_raw=("p_raw", "mean"), w=("w", "sum")).sort_values("c")
        if len(g) < 3:
            continue
        g["p_iso"] = pk.isotonic_survival(g["c"].to_numpy(), g["p_raw"].to_numpy(), g["w"].to_numpy())
        out[(gid, tgt)] = g.reset_index(drop=True)
    return out


def ladder_median(lad: pd.DataFrame) -> float:
    return pk.median_from_cdf(lad["c"].to_numpy(), 1 - lad["p_iso"].to_numpy())


def shifted(lad: pd.DataFrame, delta: float, at: np.ndarray | None = None) -> np.ndarray:
    """P'(Y > c) = S_K(c - delta), S_K linearly interpolated over the ladder and clamped at its ends."""
    c = lad["c"].to_numpy() if at is None else at
    return np.interp(c - delta, lad["c"].to_numpy(), lad["p_iso"].to_numpy())


def ladder_crps(p: np.ndarray, y: np.ndarray) -> float:
    return float(((p - y) ** 2).sum())


def fit_b(d: np.ndarray, e: np.ndarray, pseudo_games: float = 50.0) -> float:
    lam = pseudo_games * float(np.mean(d ** 2))
    return float(np.clip((d * e).sum() / ((d ** 2).sum() + lam), 0.0, 1.0)) if len(d) else 0.0
