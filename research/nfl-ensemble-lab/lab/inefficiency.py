"""Which football markets are most inefficient, net of cost (docs/INEFFICIENCY_PREREG.md)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, special, stats

from . import basket as BK
from .config import CACHE_DIR, RAW_DIR

SIZE = 0.03
PRIOR_SD = 0.2
MIN_BETS = 100
LINES_FILE = RAW_DIR / "market" / "aussportsbetting_nfl.xlsx"
KALSHI_FILE = CACHE_DIR / "props_kalshi" / "quotes.parquet"
KALSHI_SERIES = {"KXNFLSPREAD": "k_spread", "KXNFLTOTAL": "k_total", "KXNFLPASSYDS": "k_pass_yds", "KXNFLRECYDS": "k_rec_yds", "KXNFLREC": "k_receptions", "KXNFLRSHYDS": "k_rush_yds"}
GROUPS = {"g_spread": "lines", "g_total": "lines", "g_moneyline": "lines", "b_pass_yds": "books", "b_rec_yds": "books", **{v: "kalshi" for v in KALSHI_SERIES.values()}}
COLS = ["market", "era", "cluster", "p", "price_a", "price_b", "y"]


def _fair(pa, pb):
    return np.array([BK.power_fair(a, b) for a, b in zip(pa, pb)])


def _pack(market, era, cluster, price_a, price_b, y, p=None):
    price_a, price_b = np.asarray(price_a, float), np.asarray(price_b, float)
    p = _fair(price_a, price_b) if p is None else np.asarray(p, float)
    return pd.DataFrame({"market": market, "era": np.asarray(era), "cluster": np.asarray(cluster).astype(str), "p": p, "price_a": price_a, "price_b": price_b, "y": np.asarray(y, float)})


def game_lines() -> pd.DataFrame:
    d = pd.read_excel(LINES_FILE, sheet_name="Data", header=0)
    d["date"] = pd.to_datetime(d["Date"])
    d = d[d["Playoff Game?"].isna()].copy()
    d["season"] = np.where(d["date"].dt.month >= 8, d["date"].dt.year, d["date"].dt.year - 1)
    d["margin"] = d["Home Score"] - d["Away Score"]
    d["tot"] = d["Home Score"] + d["Away Score"]
    d["cluster"] = np.arange(len(d))
    era = lambda s: np.where(s.between(2006, 2015), "decide", np.where(s.between(2016, 2025), "confirm", "other"))
    out = []
    s = d.dropna(subset=["Home Line Close", "Home Line Odds Close", "Away Line Odds Close"])
    e = s["margin"] + s["Home Line Close"]
    s, e = s[e != 0], e[e != 0]
    out.append(_pack("g_spread", era(s["season"]), s["cluster"], 1 / s["Home Line Odds Close"], 1 / s["Away Line Odds Close"], (e > 0)))
    s = d.dropna(subset=["Total Score Close", "Total Score Over Close", "Total Score Under Close"])
    e = s["tot"] - s["Total Score Close"]
    s, e = s[e != 0], e[e != 0]
    out.append(_pack("g_total", era(s["season"]), s["cluster"], 1 / s["Total Score Over Close"], 1 / s["Total Score Under Close"], (e > 0)))
    s = d.dropna(subset=["Home Odds Close", "Away Odds Close"])
    s = s[s["margin"] != 0]
    out.append(_pack("g_moneyline", era(s["season"]), s["cluster"], 1 / s["Home Odds Close"], 1 / s["Away Odds Close"], (s["margin"] > 0)))
    r = pd.concat(out, ignore_index=True)
    return r[r["era"] != "other"].reset_index(drop=True)


def sportsbook_props() -> pd.DataFrame:
    lg = BK.legs()
    lg = lg.sort_values("snap").groupby(["book", "game_id", "gsis_id", "stat"], as_index=False).tail(1)
    rec, pas, done = BK.actuals()
    ros = pd.read_parquet(RAW_DIR / "roster_weekly_2026.parquet", columns=["gsis_id", "week", "status"])
    act = set(zip(ros.loc[ros["status"] == "ACT", "gsis_id"], ros.loc[ros["status"] == "ACT", "week"]))
    lg = lg[lg["game_id"].isin(done) & lg["week"].between(1, 8)]
    lg = lg.merge(rec, on=["game_id", "gsis_id"], how="left").merge(pas, on=["game_id", "gsis_id"], how="left")
    lg["actual"] = np.where(lg["stat"] == "pass_yds", lg["pas"], lg["rec"])
    ok = lg["actual"].notna() | pd.Series([(g, w) in act for g, w in zip(lg["gsis_id"], lg["week"])], index=lg.index)
    lg = lg[ok].copy()
    lg["actual"] = lg["actual"].fillna(0)
    lg = lg[lg["actual"] != lg["line"]]
    pa, pb = BK.american_p(lg["over_odds"]), BK.american_p(lg["under_odds"])
    era = np.where(lg["week"] <= 4, "decide", "confirm")
    out = [_pack("b_" + st, era[(lg["stat"] == st).to_numpy()], lg.loc[lg["stat"] == st, "game_id"], pa[(lg["stat"] == st).to_numpy()], pb[(lg["stat"] == st).to_numpy()], (lg.loc[lg["stat"] == st, "actual"] > lg.loc[lg["stat"] == st, "line"]).to_numpy()) for st in ("pass_yds", "rec_yds")]
    return pd.concat(out, ignore_index=True)


def kalshi_props() -> pd.DataFrame:
    q = pd.read_parquet(KALSHI_FILE)
    q = q[q["result"].isin(["yes", "no"]) & q["bid90"].notna() & q["ask90"].notna() & q["liquid90"].astype(bool) & ((q["ask90"] - q["bid90"]) <= 0.10) & (q["ask90"] <= 0.99) & (q["bid90"] >= 0.01)]
    q = q[q["series"].isin(KALSHI_SERIES) & q["season"].isin([2025, 2026])]
    mk = q["series"].map(KALSHI_SERIES)
    era = np.where(q["season"] == 2025, "decide", "confirm")
    return _pack(mk.to_numpy(), era, q["gid"].to_numpy(), q["ask90"], 1 - q["bid90"], (q["result"] == "yes"), p=((q["bid90"] + q["ask90"]) / 2).clip(0.01, 0.99))


def all_contracts() -> pd.DataFrame:
    return pd.concat([game_lines(), sportsbook_props(), kalshi_props()], ignore_index=True)


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def calib_fit(p, y, w=None, center=(1.0, 0.0), sd=None):
    """Logistic recalibration y ~ sigmoid(a * logit p + b); optional normal prior around `center`."""
    x, y = logit(p), np.asarray(y, float)
    w = np.ones_like(x) if w is None else np.asarray(w, float)

    def nll(th):
        z = th[0] * x + th[1]
        v = -np.sum(w * (y * special.log_expit(z) + (1 - y) * special.log_expit(-z)))
        if sd is not None:
            v += 0.5 * np.sum(((th - np.asarray(center)) / sd) ** 2)
        return v
    return optimize.minimize(nll, np.asarray(center, float), method="BFGS").x


def pooled_center(dec: pd.DataFrame) -> tuple:
    w = 1.0 / dec.groupby("market")["p"].transform("size")
    return tuple(calib_fit(dec["p"], dec["y"], w))


def fit_all(dec: pd.DataFrame) -> dict:
    ctr = pooled_center(dec)
    par = {m: calib_fit(g["p"], g["y"], center=ctr, sd=PRIOR_SD) for m, g in dec.groupby("market")}
    return {"pool": ctr, "par": par}


def choose(d: pd.DataFrame, par: np.ndarray) -> pd.DataFrame:
    q = special.expit(par[0] * logit(d["p"]) + par[1])
    ea, eb = q - d["price_a"], (1 - q) - d["price_b"]
    side_a = ea >= eb
    edge = np.where(side_a, ea, eb)
    price = np.where(side_a, d["price_a"], d["price_b"])
    won = np.where(side_a, d["y"], 1 - d["y"])
    return d.assign(side_a=side_a, edge=edge, price=price, won=won, bet=edge > 0)


def cluster_means(bets: pd.DataFrame, value: str) -> pd.Series:
    b = bets[bets["bet"]]
    return b.groupby("cluster").apply(lambda g: float((g[value] - g["price"]).mean()) if value == "won" else float(g[value].mean()))


def murphy(p, y, bins=10) -> dict:
    p, y = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4), np.asarray(y, float)
    ll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    base = float(y.mean())
    h = lambda r: float(-(r * np.log(r) + (1 - r) * np.log(1 - r))) if 0 < r < 1 else 0.0
    kl = lambda o, q: float(o * np.log(o / q) + (1 - o) * np.log((1 - o) / (1 - q))) if 0 < o < 1 else float(-np.log(1 - q) if o == 0 else -np.log(q))
    b = pd.qcut(p, bins, labels=False, duplicates="drop")
    rel = res = 0.0
    for k in np.unique(b):
        m = b == k
        o, q = float(y[m].mean()), float(p[m].mean())
        rel += m.mean() * kl(min(max(o, 1e-4), 1 - 1e-4), q)
        res += m.mean() * kl(min(max(o, 1e-4), 1 - 1e-4), min(max(base, 1e-4), 1 - 1e-4))
    return {"log_loss": ll, "uncertainty": h(base), "resolution": res, "reliability": rel}


def boot(M: np.ndarray, n=2000, seed=0):
    """M: clusters x markets of within-game mean net (NaN where no bet). Returns bootstrap means (n x markets)."""
    rng = np.random.default_rng(seed)
    ok = ~np.isnan(M)
    S, N = np.where(ok, M, 0.0), ok.astype(float)
    C = M.shape[0]
    out = np.empty((n, M.shape[1]))
    for i in range(n):
        idx = rng.integers(0, C, C)
        out[i] = S[idx].sum(0) / np.maximum(N[idx].sum(0), 1)
    return out


def dl_shrink(theta, se):
    theta, se = np.asarray(theta, float), np.asarray(se, float)
    w = 1 / se ** 2
    mu0 = (w * theta).sum() / w.sum()
    Q = (w * (theta - mu0) ** 2).sum()
    tau2 = max(0.0, (Q - (len(theta) - 1)) / (w.sum() - (w ** 2).sum() / w.sum()))
    wr = 1 / (se ** 2 + tau2)
    mu = (wr * theta).sum() / wr.sum()
    B = tau2 / (tau2 + se ** 2)
    post = mu + B * (theta - mu)
    psd = np.sqrt(B * se ** 2)
    return post, psd, tau2, mu


def romano_wolf(t_obs, t_star):
    """One-sided stepdown adjusted p-values. t_star is bootstrap draws x markets of centered statistics."""
    order = np.argsort(-t_obs)
    padj = np.empty(len(t_obs))
    prev = 0.0
    for j, k in enumerate(order):
        rest = order[j:]
        p = float(np.mean(t_star[:, rest].max(1) >= t_obs[k]))
        prev = max(prev, p)
        padj[k] = prev
    return padj


def bh(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    q = np.empty_like(p)
    m = len(p)
    run = 1.0
    for r, k in zip(range(m, 0, -1), o[::-1]):
        run = min(run, p[k] * m / r)
        q[k] = run
    return q


def gate_market(bets: pd.DataFrame, reps=200, seed=0) -> dict:
    """Plant a net edge of +SIZE on the sides the rule picks and see whether the estimate recovers it and has power."""
    b = bets[bets["bet"]]
    if b["cluster"].nunique() < 5:
        return {"n_bets": int(len(b)), "informative": False, "reason": "rule rarely fires"}
    rng = np.random.default_rng(seed)
    pw = np.clip(b["price"].to_numpy() + SIZE, 0.01, 0.99)
    cl = pd.factorize(b["cluster"])[0]
    C = cl.max() + 1
    cnt = np.bincount(cl)
    est, hit = [], 0
    for _ in range(reps):
        net = (rng.random(len(b)) < pw).astype(float) - b["price"].to_numpy()
        m = np.bincount(cl, weights=net) / cnt
        mean, se = m.mean(), m.std(ddof=1) / np.sqrt(C)
        est.append(mean)
        hit += (mean - 1.645 * se) > 0
    se_typ = float(np.std(est))
    return {"n_bets": int(len(b)), "n_games": int(C), "planted": SIZE, "recovered": float(np.mean(est)), "recovery_error": float(np.mean(est) - SIZE), "power": hit / reps,
            "smallest_detectable": 2.8 * se_typ, "informative": bool(abs(np.mean(est) - SIZE) <= 0.01 and hit / reps >= 0.80)}
