"""Real (2025 or 2026) and simulated datasets with one schema, so rehearsal and real runs use the same step functions."""
from common import *

WIN_VARIANTS = ["p_elo", "p_xgb_v1", "p_margin", "p_xgb_deep", "p_elo_platt", "p_xgb_v1_platt", "p_margin_platt", "p_xgb_deep_platt"]
MARGIN_VARIANTS = ["L", "naive", "elo"]
TOTAL_VARIANTS = ["L", "naive"]
PROPS_ARMS = ["K", "A", "base", "K_v1", "A_v1"]
THETA = 0.8

# world: sA = market noise at T-90 (0 means the market is the truth); s_dec/s_close = market noise at the other times;
# s_var = noise of each model variant (default 1.0). Noise is in units of theta (see datasets.py sim_*).
WORLDS = {
    "null": dict(sA=0.0, s_dec=0.6, s_close=0.0, s_var={}, planted=None),                    # market equals the truth
    "exch": dict(sA=1.0, s_dec=1.5, s_close=0.7, s_var={}, planted=None),                    # market and variants exchangeable
    "planted": dict(sA=1.0, s_dec=1.5, s_close=0.7, s_var={"p_xgb_deep": 0.4, "L": 0.4, "K": 0.4}, planted="p_xgb_deep"),
    # Amendment 7: a stronger planted edge for the Step 7 power condition (Step 2 design predicts about 97% power at this gain)
    "planted_strong": dict(theta=1.2, sA=1.0, s_dec=1.5, s_close=0.7, s_var={"p_xgb_deep": 0.2, "L": 0.2, "K": 0.2}, planted="p_xgb_deep"),
}
WORLDS["planted"]["theta"] = 0.8


# ------------------------------------------------------------------ real data
def real_dataset(season: int = 2025) -> dict:
    W = winners_frame()
    W = W[(W.season == season) & W.p_t90.notna()].reset_index(drop=True)
    L = ladder_frame()
    L = L[L.season == season].reset_index(drop=True)
    wf = pd.read_parquet(HW / "forecast_wf.parquet").set_index("gid")
    for col in ("mu_L", "sd_L", "mu_naive", "sd_naive", "mu_elo"):
        L[col] = np.nan
    for i, r in L.iterrows():
        w = wf.loc[r.gid]
        if r.target == "margin":
            L.loc[i, ["mu_L", "sd_L", "mu_naive", "sd_naive", "mu_elo"]] = [w.mu_m, w.sd_m, w.naive_m_mu, w.naive_m_sd, w.elo_mu]
        else:
            L.loc[i, ["mu_L", "sd_L", "mu_naive", "sd_naive"]] = [w.mu_t, w.sd_t, w.naive_t_mu, w.naive_t_sd]
    T = pd.read_parquet(PK / "scored_thresholds.parquet")
    T = T[(T.season == season) & T.p_market90.notna()].copy()
    T["lad"] = T.gid + "|" + T.pid.astype(str) + "|" + T.stat
    T["wk"] = T.season.astype(str) + "_" + T.week.astype(int).astype(str).str.zfill(2)
    T = T.rename(columns={"y_home_win": "yes"})
    return {"winners": W, "ladders": L, "props_thr": T, "props_lad": props_ladders(T), "season": season}


def props_ladders(T: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for lid, d in T.groupby("lad"):
        d = d.sort_values("k")
        pm = d.p_market90.to_numpy(float)
        yes = d.yes.to_numpy(float)
        row = {"lad": lid, "wk": d.wk.iloc[0], "stat": d.stat.iloc[0], "n_thr": len(d), "ceil": float((pm * (1 - pm)).sum()), "real_market90": float(((pm - yes) ** 2).sum())}
        for a in PROPS_ARMS:
            p = d[f"p_{a}"].to_numpy(float) if f"p_{a}" in d else np.full(len(d), np.nan)
            row[f"real_{a}"] = float(((p - yes) ** 2).sum()) if not np.isnan(p).any() else np.nan
        if len(d) >= 3 and np.ptp(pm) > 0.02:
            row["mu"], row["sd"], _ = fit_normal(d.k.to_numpy(float) - 0.5, pm)
        else:
            row["mu"] = row["sd"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ simulation
def _noisy_logit(L0, z, s, rng, th=THETA):
    return sigmoid(L0 + th * (z + s * rng.standard_normal(len(L0))))


def sim_dataset(template: dict, world: str, rng) -> dict:
    w = WORLDS[world]
    TH = w.get("theta", THETA)
    sv = lambda v: w["s_var"].get(v, 1.0)
    W0 = template["winners"]
    L0 = logit(W0.p_t90.to_numpy(float))
    n = len(L0)
    z = rng.standard_normal(n)
    W = W0[["gid", "season", "week", "wk"]].copy()
    W["y_home_win"] = (rng.random(n) < sigmoid(L0 + TH * z)).astype(float)
    W["p_t90"] = _noisy_logit(L0, z, w["sA"], rng, TH)
    W["p_dec"] = _noisy_logit(L0, z, w["s_dec"], rng, TH)
    W["p_close"] = _noisy_logit(L0, z, w["s_close"], rng, TH)
    for v in WIN_VARIANTS:
        W[v] = _noisy_logit(L0, z, sv(v), rng, TH)
    # ladders
    L = template["ladders"][["gid", "target", "season", "week", "wk", "c", "mu", "sd"]].copy().reset_index(drop=True)
    cols = {k: [] for k in ("y", "mu_m", "p_iso", "mu_L", "sd_L", "mu_naive", "sd_naive", "mu_elo", "ladder_ceiling", "ladder_realized")}
    for r in L.itertuples(index=False):
        zz = rng.standard_normal()
        sd = r.sd
        y = r.mu + TH * sd * zz + sd * rng.standard_normal()
        mm = r.mu + TH * sd * (zz + w["sA"] * rng.standard_normal())
        p = 1 - norm.cdf((r.c - mm) / sd)
        yes = (y > r.c).astype(float)
        cols["y"].append(y); cols["mu_m"].append(mm); cols["p_iso"].append(p)
        cols["ladder_ceiling"].append(float((p * (1 - p)).sum())); cols["ladder_realized"].append(float(((p - yes) ** 2).sum()))
        cols["mu_L"].append(r.mu + TH * sd * (zz + sv("L") * rng.standard_normal())); cols["sd_L"].append(sd)
        cols["mu_naive"].append(r.mu + TH * sd * (zz + sv("naive") * rng.standard_normal())); cols["sd_naive"].append(sd)
        cols["mu_elo"].append(r.mu + TH * sd * (zz + sv("elo") * rng.standard_normal()) if r.target == "margin" else np.nan)
    for k_, v in cols.items():
        L[k_] = v
    L["mu"] = L["mu_m"]  # market normal fit, as in the real frame
    # props
    T0, rows, ladrows = template["props_thr"], [], []
    for lid, d in T0.groupby("lad"):
        d = d.sort_values("k")
        ks = d.k.to_numpy(float); S = d.p_market90.to_numpy(float)
        lrow = template["props_lad"].set_index("lad").loc[lid]
        sd = lrow.sd if not np.isnan(lrow.sd) else 1.0
        zz, u = rng.standard_normal(), rng.random()
        yes = (u <= np.interp(ks - TH * sd * zz, ks, S)).astype(float)
        P = {}
        for a in PROPS_ARMS:
            P[a] = np.interp(ks - TH * sd * (zz + sv(a) * rng.standard_normal()), ks, S)
        P["market90"] = np.interp(ks - TH * sd * (zz + w["sA"] * rng.standard_normal()), ks, S)
        rec = {"lad": lid, "wk": d.wk.iloc[0], "stat": d.stat.iloc[0], "n_thr": len(d), "yes": yes, "k": ks, "p_market90": P["market90"]}
        for a in PROPS_ARMS:
            rec[f"p_{a}"] = P[a]
        rows.append(rec)
        pm = P["market90"]
        lr = {"lad": lid, "wk": rec["wk"], "stat": rec["stat"], "n_thr": len(d), "ceil": float((pm * (1 - pm)).sum()), "real_market90": float(((pm - yes) ** 2).sum()), "sd": sd}
        for a in PROPS_ARMS:
            lr[f"real_{a}"] = float(((P[a] - yes) ** 2).sum())
        ladrows.append(lr)
    thr = pd.DataFrame({c: np.concatenate([np.atleast_1d(r[c]) if c not in ("lad", "wk", "stat") else np.repeat(r[c], r["n_thr"]) for r in rows])
                        for c in ["lad", "wk", "stat", "yes", "k", "p_market90"] + [f"p_{a}" for a in PROPS_ARMS]})
    return {"winners": W, "ladders": L, "props_thr": thr, "props_lad": pd.DataFrame(ladrows), "season": template["season"], "world": world}


def truth(template: dict, world: str, n_mc: int = 400_000, seed: int = 99) -> dict:
    """Large-sample population values for the simulated world (used only by the rehearsal)."""
    w = WORLDS[world]
    TH = w.get("theta", THETA)
    sv = lambda v: w["s_var"].get(v, 1.0)
    rng = np.random.default_rng(seed)
    L0 = rng.choice(logit(template["winners"].p_t90.to_numpy(float)), n_mc)
    z = rng.standard_normal(n_mc)
    t = sigmoid(L0 + TH * z)
    nz = lambda s: sigmoid(L0 + TH * (z + s * rng.standard_normal(n_mc)))
    p, pdec, pcl = nz(w["sA"]), nz(w["s_dec"]), nz(w["s_close"])
    Ell = lambda f: float((-(t * np.log(np.clip(f, 1e-6, 1)) + (1 - t) * np.log(np.clip(1 - f, 1e-6, 1)))).mean())
    out = {"winners": {"gap_realized_minus_entropy": Ell(p) - float(entropy(p).mean()), "news_term": Ell(pdec) - Ell(pcl), "lambda": {}, "gain_vs_market": {}}}
    for v in WIN_VARIANTS:
        q = nz(sv(v))
        out["winners"]["lambda"][v] = float(((t - p) * (q - p)).mean() / ((q - p) ** 2).mean())
        out["winners"]["gain_vs_market"][v] = Ell(p) - Ell(q)
    sA = w["sA"]
    out["ladders"] = {"lambda": {v: sA ** 2 / (sA ** 2 + sv(v) ** 2) for v in ("L", "naive", "elo")}}
    out["props"] = {"lambda_note": "threshold-level coefficients are not closed form; the rehearsal checks only the winners and ladder coefficients"}
    return out
