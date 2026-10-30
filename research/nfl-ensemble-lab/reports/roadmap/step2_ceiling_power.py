"""Step 2: ceilings and simulation-based power per target (PROTOCOL.md). Ceilings assume the market is the truth."""
from common import *

res = header("step2")
res["conditional_on_market_is_truth"] = ["all entropy and sigma/sqrt(pi) ceilings", "all power simulations (the market defines the baseline world)"]

# ---- 2a winners
W = winners_frame()
W = W[W.p_t90.notna()].copy()
y = W.y_home_win.to_numpy(float)
p = W.p_t90.to_numpy(float)
codes, k = cluster_index(W.wk.to_numpy())
gap = ll(p, y) - entropy(p)
m, lo, hi, _ = cluster_boot_mean(gap, codes, k)


def mz(X, yy, cod, kk, B=1000):
    b = logit_fit(X, yy)
    r = np.random.default_rng(SEED)
    bs = []
    members = [np.where(cod == j)[0] for j in range(kk)]
    for _ in range(B):
        ii = np.concatenate([members[j] for j in r.integers(0, kk, kk)])
        bs.append(logit_fit(X[ii], yy[ii]))
    return b, np.percentile(np.array(bs), [2.5, 97.5], axis=0)


b, ci = mz(np.column_stack([np.ones(len(p)), logit(p)]), y, codes, k)
res["winners"] = {
    "market_price": "last candle at or before kickoff - 90 min", "n_games": int(len(W)),
    "seasons": {int(a): int(c) for a, c in W.season.value_counts().sort_index().items()}, "week_clusters": k,
    "realized_log_loss": float(ll(p, y).mean()), "entropy_ceiling": float(entropy(p).mean()), "gap_mean": m, "gap_ci95": [lo, hi],
    "mz_intercept": float(b[0]), "mz_intercept_ci95": [float(ci[0, 0]), float(ci[1, 0])],
    "mz_slope": float(b[1]), "mz_slope_ci95": [float(ci[0, 1]), float(ci[1, 1])],
    "effective_sample": design_effect(gap, codes, k)}

# ---- 2b margin and total ladders
L = ladder_frame()
res["ladders"] = {}
for tgt in ("margin", "total"):
    d = L[L.target == tgt]
    cod, kk = cluster_index(d.wk.to_numpy())
    real = crps_normal(d.y.to_numpy(), d.mu.to_numpy(), d.sd.to_numpy())
    ceil = d.sd.to_numpy() / np.sqrt(np.pi)
    g = real - ceil
    mg, lg, hg, _ = cluster_boot_mean(g, cod, kk)
    tg = d.ladder_realized.to_numpy() - d.ladder_ceiling.to_numpy()
    mt, lt, ht, _ = cluster_boot_mean(tg, cod, kk)
    res["ladders"][tgt] = {
        "n_ladders": int(len(d)), "week_clusters": kk, "fit_ok_share": float(d.fit_ok.mean()), "sd_median": float(d.sd.median()),
        "normal_crps_ceiling_points": float(ceil.mean()), "normal_crps_realized_points": float(real.mean()), "gap_points": mg, "gap_ci95": [lg, hg],
        "threshold_score_ceiling": float(d.ladder_ceiling.mean()), "threshold_score_realized": float(d.ladder_realized.mean()),
        "threshold_gap": mt, "threshold_gap_ci95": [lt, ht], "effective_sample": design_effect(g, cod, kk)}

# ---- 2c props
T = pd.read_parquet(PK / "scored_thresholds.parquet")
T["lad"] = T.gid + "|" + T.pid.astype(str) + "|" + T.stat
T = T[T.p_market90.notna()]
rows = []
for lid, d in T.groupby("lad"):
    pm = d.p_market90.to_numpy(float)
    yes = d.y_home_win.to_numpy(float)
    ks = d.k.to_numpy(float)
    row = {"lad": lid, "stat": d.stat.iloc[0], "wk": f"{int(d.season.iloc[0])}_{int(d.week.iloc[0]):02d}", "n_thr": len(d),
           "ceil": float((pm * (1 - pm)).sum()), "real": float(((pm - yes) ** 2).sum())}
    if len(d) >= 3 and np.ptp(pm) > 0.02:
        mu_, sd_, ok = fit_normal(ks - 0.5, pm)
        row.update(mu=mu_, sd=sd_, fit_ok=ok)
    rows.append(row)
P = pd.DataFrame(rows)
if "sd" not in P:
    P["sd"] = np.nan
cod, kk = cluster_index(P.wk.to_numpy())
g = (P.real - P.ceil).to_numpy()
mg, lg, hg, _ = cluster_boot_mean(g, cod, kk)
res["props"] = {
    "n_ladders": int(len(P)), "week_clusters": kk, "threshold_score_ceiling": float(P.ceil.mean()), "threshold_score_realized": float(P.real.mean()),
    "gap": mg, "gap_ci95": [lg, hg], "effective_sample": design_effect(g, cod, kk),
    "normal_fit_sd_over_sqrt_pi_by_stat": {s: {"median": float((d.sd / np.sqrt(np.pi)).median()), "n_fitted": int(d.sd.notna().sum())} for s, d in P.groupby("stat")},
    "note": "outcome values were not loaded for props, so the normal ceiling is in stat units with no realized comparison"}

# ---- 2d simulation-based power (exchangeable null plus an improving forecaster)
B_BOOT = 500


def power_curve(sim_diff, cod, kk, sB_grid, n_sims):
    """sim_diff(sB, rng) gives per-unit loss difference (A minus B; positive means B is better)."""
    members = np.bincount(cod, minlength=kk).astype(float)
    out = []
    rr = np.random.default_rng(SEED + 1)
    idx = rr.integers(0, kk, (B_BOOT, kk))
    for sB in sB_grid:
        det, gains = [], []
        for _ in range(n_sims):
            d = sim_diff(sB, rr)
            gains.append(d.mean())
            s = np.bincount(cod, weights=d, minlength=kk)
            bs = s[idx].sum(1) / members[idx].sum(1)
            det.append(np.percentile(bs, 2.5) > 0)
        out.append({"sB": float(sB), "expected_gain": float(np.mean(gains)), "power_one_sided_2.5pct": float(np.mean(det))})
    return out


def mde(rows):
    pr = sorted((r["expected_gain"], r["power_one_sided_2.5pct"]) for r in rows if r["sB"] < 1.0)
    g = [a for a, _ in pr]
    pw = [b_ for _, b_ in pr]
    return float(np.interp(0.8, pw, g)) if max(pw) >= 0.8 else None


def make_w(L0, theta):
    def f(sB, r):
        n = len(L0)
        z = r.standard_normal(n)
        eA = r.standard_normal(n)
        eB = sB * r.standard_normal(n)
        yy = (r.random(n) < sigmoid(L0 + theta * z)).astype(float)
        return ll(sigmoid(L0 + theta * (z + eA)), yy) - ll(sigmoid(L0 + theta * (z + eB)), yy)
    return f


def make_ladder(df, theta):
    sd = df.sd.to_numpy(float)
    mu = df.mu.to_numpy(float)

    def f(sB, r):
        n = len(sd)
        z = r.standard_normal(n)
        eA = r.standard_normal(n)
        eB = sB * r.standard_normal(n)
        yy = mu + theta * sd * z + sd * r.standard_normal(n)
        return crps_normal(yy, mu + theta * sd * (z + eA), sd) - crps_normal(yy, mu + theta * sd * (z + eB), sd)
    return f


sgrid = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
res["power"] = {"design": "truth logit = L + theta*z; market and model are noisy copies of z with noise sd 1 and sB; sB=1 is an exchangeable null; "
                          "detection = one-sided 2.5% week-clustered bootstrap", "sims": 300, "boots": B_BOOT}
for theta in (0.3, 0.6):
    rows_w = power_curve(make_w(logit(p), theta), codes, k, sgrid, 300)
    res["power"][f"winners_theta{theta}"] = {"curve": rows_w, "false_positive_at_null": rows_w[0]["power_one_sided_2.5pct"],
                                             "min_detectable_gain_80pct_logloss": mde(rows_w), "n_games": int(len(p)), "week_clusters": k}
for tgt in ("margin", "total"):
    d = L[L.target == tgt]
    cod, kk = cluster_index(d.wk.to_numpy())
    for theta in (0.15, 0.3):
        rows_l = power_curve(make_ladder(d, theta), cod, kk, sgrid, 300)
        res["power"][f"{tgt}_theta{theta}"] = {"curve": rows_l, "false_positive_at_null": rows_l[0]["power_one_sided_2.5pct"],
                                               "min_detectable_gain_80pct_points": mde(rows_l), "mean_sd_points": float(d.sd.mean()),
                                               "n_ladders": int(len(d)), "week_clusters": kk}

Tg = {lid: d for lid, d in T.groupby("lad")}
PP = P[P.sd.notna()].reset_index(drop=True)
lads = []
for lid in PP.lad:
    d = Tg[lid].sort_values("k")
    lads.append((d.k.to_numpy(float), d.p_market90.to_numpy(float)))
sds = PP.sd.to_numpy(float)
cod_p, kk_p = cluster_index(PP.wk.to_numpy())


def make_props(theta):
    def f(sB, r):
        out = np.empty(len(lads))
        for i, (ks, S) in enumerate(lads):
            z, eA, eB, u = r.standard_normal(), r.standard_normal(), sB * r.standard_normal(), r.random()
            yes = (u <= np.interp(ks - theta * sds[i] * z, ks, S)).astype(float)
            Sa = np.interp(ks - theta * sds[i] * (z + eA), ks, S)
            Sb = np.interp(ks - theta * sds[i] * (z + eB), ks, S)
            out[i] = ((Sa - yes) ** 2).sum() - ((Sb - yes) ** 2).sum()
        return out
    return f


for theta in (0.15, 0.3):
    rows_p = power_curve(make_props(theta), cod_p, kk_p, [1.0, 0.5, 0.0], 100)
    res["power"][f"props_theta{theta}"] = {"curve": rows_p, "false_positive_at_null": rows_p[0]["power_one_sided_2.5pct"],
                                           "min_detectable_gain_80pct_threshold_score": mde(rows_p), "n_ladders": int(len(PP)), "week_clusters": kk_p, "sims": 100}

fps = {k_: v["false_positive_at_null"] for k_, v in res["power"].items() if isinstance(v, dict) and "false_positive_at_null" in v}
res["checks"] = {"a_winner_ceiling_computed": True,
                 "b_ladder_counts": {"margin": res["ladders"]["margin"]["n_ladders"], "total": res["ladders"]["total"]["n_ladders"], "props": res["props"]["n_ladders"]},
                 "b_ok": res["ladders"]["margin"]["n_ladders"] >= 100 and res["ladders"]["total"]["n_ladders"] >= 100 and res["props"]["n_ladders"] >= 500,
                 "c_false_positive_rates": fps, "c_ok": all(0.005 <= v <= 0.05 for v in fps.values()), "d_mde_reported": True}
res["PASS"] = bool(res["checks"]["b_ok"] and res["checks"]["c_ok"])
write("step2_ceiling_power.json", res)
print("PASS" if res["PASS"] else "FAIL")
print(json.dumps(res["checks"], indent=1))
