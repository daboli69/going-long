"""Step functions shared by the rehearsal (simulated seasons) and the real runs. Definitions: GOVERNANCE.md and PROTOCOL.md."""
from datasets import *
from scipy.stats import t as tdist

SESOI_WIN = 0.005          # log loss; GOVERNANCE.md
SESOI_FRAC = 0.01          # margin, total, props: 1% of the mean market score
BOOT_WILD = 1999
LOOKS_TOTAL_WEEKS = 18


def codes_of(df, col="wk"):
    return cluster_index(df[col].to_numpy())


# ------------------------------------------------------------------ inference helpers
def cl_mean(x, codes, k, level=0.95) -> dict:
    """Mean with a cluster-robust t interval (clusters minus 1 degrees of freedom)."""
    x = np.asarray(x, float)
    n = len(x)
    m = x.mean()
    r = np.bincount(codes, weights=x - m, minlength=k)
    se = np.sqrt(k / (k - 1) * (r ** 2).sum()) / n
    c = tdist.ppf(0.5 + level / 2, k - 1)
    return {"mean": float(m), "se": float(se), "lo": float(m - c * se), "hi": float(m + c * se), "n": int(n), "clusters": int(k)}


def equivalence(d, codes, k, delta) -> dict:
    """d = model loss minus market loss. Equivalence rule from GOVERNANCE.md (90% interval against +-delta)."""
    c = cl_mean(d, codes, k, 0.90)
    if c["lo"] > delta:
        s = "worse_than_margin"
    elif c["hi"] < -delta:
        s = "better_than_margin"
    elif c["lo"] > -delta and c["hi"] < delta:
        s = "equivalent"
    else:
        s = "undetermined"
    return {"status": s, "interval90": [c["lo"], c["hi"]], "mean": c["mean"], "delta": float(delta)}


def fs_test(x, u, codes, k, rng=None, B=BOOT_WILD) -> dict:
    """Fair-Shiller encompassing regression u = lambda * x through the origin (u = outcome minus market, x = model minus market).
    Cluster-robust t interval (df = k - 1) and a null-imposed wild cluster bootstrap p-value (Rademacher)."""
    x = np.asarray(x, float); u = np.asarray(u, float)
    S = (x * x).sum()
    lam = (x * u).sum() / S
    e = u - lam * x
    sc = np.bincount(codes, weights=x * e, minlength=k)
    se = np.sqrt(k / (k - 1) * (sc ** 2).sum()) / S
    t = lam / se
    c = tdist.ppf(0.975, k - 1)
    out = {"lambda": float(lam), "se": float(se), "lo": float(lam - c * se), "hi": float(lam + c * se), "p_t": float(2 * tdist.sf(abs(t), k - 1)), "clusters": int(k), "n": int(len(x))}
    if rng is not None:
        a = np.bincount(codes, weights=x * u, minlength=k)
        s = np.bincount(codes, weights=x * x, minlength=k)
        w = rng.choice([-1.0, 1.0], size=(B, k))
        lb = (w * a).sum(1) / S
        num = w * a - lb[:, None] * s
        seb = np.sqrt(k / (k - 1) * (num ** 2).sum(1)) / S
        out["p_wild"] = float((np.abs(lb / seb) >= abs(t)).mean())
    return out


def mz_logit(p, y, codes, k) -> dict:
    """Mincer-Zarnowitz calibration: logistic regression of the outcome on the forecast's logit, cluster-robust t intervals."""
    X = np.column_stack([np.ones(len(p)), logit(p)])
    b = logit_fit(X, y)
    mu = sigmoid(X @ b)
    Hm = X.T @ (X * (mu * (1 - mu))[:, None])
    Hi = np.linalg.inv(Hm)
    sc = np.stack([np.bincount(codes, weights=X[:, j] * (y - mu), minlength=k) for j in range(2)], 1)
    V = k / (k - 1) * Hi @ (sc.T @ sc) @ Hi
    se = np.sqrt(np.diag(V))
    c = tdist.ppf(0.975, k - 1)
    return {"intercept": float(b[0]), "intercept_ci": [float(b[0] - c * se[0]), float(b[0] + c * se[0])], "slope": float(b[1]), "slope_ci": [float(b[1] - c * se[1]), float(b[1] + c * se[1])]}


def mz_ols(mu_f, y, codes, k) -> dict:
    X = np.column_stack([np.ones(len(mu_f)), mu_f])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    r = y - X @ b
    Hi = np.linalg.inv(X.T @ X)
    sc = np.stack([np.bincount(codes, weights=X[:, j] * r, minlength=k) for j in range(2)], 1)
    V = k / (k - 1) * Hi @ (sc.T @ sc) @ Hi
    se = np.sqrt(np.diag(V))
    c = tdist.ppf(0.975, k - 1)
    return {"intercept": float(b[0]), "intercept_ci": [float(b[0] - c * se[0]), float(b[0] + c * se[0])], "slope": float(b[1]), "slope_ci": [float(b[1] - c * se[1]), float(b[1] + c * se[1])]}


def ladder_view(ds, target):
    L = ds["ladders"]
    return L[L.target == target].reset_index(drop=True)


def ladder_losses(d, variant):
    suf = {"L": "L", "naive": "naive", "elo": "L"}[variant]
    mu_q = d["mu_elo"].to_numpy(float) if variant == "elo" else d[f"mu_{suf}"].to_numpy(float)
    sd_q = d[f"sd_{suf}"].to_numpy(float)
    return mu_q, sd_q


# ------------------------------------------------------------------ step 2
def step2_ceilings(ds) -> dict:
    W = ds["winners"]
    y, p = W.y_home_win.to_numpy(float), W.p_t90.to_numpy(float)
    codes, k = codes_of(W)
    gap = ll(p, y) - entropy(p)
    out = {"winners": {"n": int(len(W)), "clusters": k, "realized_log_loss": float(ll(p, y).mean()), "entropy_ceiling": float(entropy(p).mean()),
                       "gap": cl_mean(gap, codes, k), "calibration": mz_logit(p, y, codes, k), "effective_sample": design_effect(gap, codes, k)}, "ladders": {}}
    for tgt in ("margin", "total"):
        d = ladder_view(ds, tgt)
        cod, kk = codes_of(d)
        real = crps_normal(d.y.to_numpy(), d.mu.to_numpy(), d.sd.to_numpy())
        ceil = d.sd.to_numpy() / np.sqrt(np.pi)
        out["ladders"][tgt] = {"n": int(len(d)), "clusters": kk, "normal_crps_ceiling": float(ceil.mean()), "normal_crps_realized": float(real.mean()),
                               "gap_points": cl_mean(real - ceil, cod, kk), "threshold_gap": cl_mean(d.ladder_realized.to_numpy() - d.ladder_ceiling.to_numpy(), cod, kk),
                               "calibration": mz_ols(d.mu.to_numpy(), d.y.to_numpy(), cod, kk)}
    P = ds["props_lad"]
    cod, kk = codes_of(P)
    g = (P.real_market90 - P.ceil).to_numpy()
    out["props"] = {"n": int(len(P)), "clusters": kk, "threshold_score_ceiling": float(P.ceil.mean()), "threshold_score_realized": float(P.real_market90.mean()), "gap": cl_mean(g, cod, kk),
                    "normal_sd_over_sqrt_pi_by_stat": {s: float((d.sd / np.sqrt(np.pi)).median()) for s, d in P.groupby("stat") if d.sd.notna().any()}}
    return out


def wild_t_one_sided(d, cod, kk, w) -> bool:
    """Amendment 7: one-sided 2.5% test that the mean of d is above 0 using a null-imposed wild cluster bootstrap-t (Rademacher weights w, B x kk)."""
    n = len(d)
    S = np.bincount(cod, weights=d, minlength=kk)
    nc = np.bincount(cod, minlength=kk).astype(float)
    m = d.mean()
    se = np.sqrt(kk / (kk - 1) * ((S - nc * m) ** 2).sum()) / n
    ms = (w @ S) / n
    R = w * S - nc * ms[:, None]
    seb = np.sqrt(kk / (kk - 1) * (R ** 2).sum(1)) / n
    return float(((ms / seb) >= (m / se)).mean()) < 0.025


def _power_curve(sim_diff, cod, kk, grid, n_sims, seed, boots=499):
    rr = np.random.default_rng(seed)
    rows = []
    for sB in grid:
        det, gains = [], []
        for _ in range(n_sims):
            d = sim_diff(sB, rr)
            gains.append(d.mean())
            det.append(wild_t_one_sided(d, cod, kk, rr.choice([-1.0, 1.0], size=(boots, kk))))
        rows.append({"sB": float(sB), "expected_gain": float(np.mean(gains)), "power_one_sided_2.5pct": float(np.mean(det)), "fp_standard_error": float(np.sqrt(np.mean(det) * (1 - np.mean(det)) / n_sims))})
    return rows


def _mde(rows):
    pr = sorted((r["expected_gain"], r["power_one_sided_2.5pct"]) for r in rows if r["sB"] < 1.0)
    g, pw = [a for a, _ in pr], [b for _, b in pr]
    return float(np.interp(0.8, pw, g)) if max(pw) >= 0.8 else None


def step2_power(ds, n_sims=400, seed=1, theta_w=(0.3, 0.6), theta_l=(0.15, 0.3)) -> dict:
    """Simulation-based power with an exchangeable null (sB = 1). Detection: one-sided 2.5% week-clustered percentile bootstrap (protocol)."""
    grid = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0]
    out = {"design": "exchangeable null at sB=1; wild cluster bootstrap-t detection (Amendment 7); n_sims=%d" % n_sims}
    W = ds["winners"]
    codes, k = codes_of(W)
    L0 = logit(W.p_t90.to_numpy(float))

    def mk_w(theta):
        def f(sB, r):
            n = len(L0); z = r.standard_normal(n)
            yy = (r.random(n) < sigmoid(L0 + theta * z)).astype(float)
            return ll(sigmoid(L0 + theta * (z + r.standard_normal(n))), yy) - ll(sigmoid(L0 + theta * (z + sB * r.standard_normal(n))), yy)
        return f
    for th in theta_w:
        rows = _power_curve(mk_w(th), codes, k, grid, n_sims, seed)
        out[f"winners_theta{th}"] = {"curve": rows, "false_positive_at_null": rows[0]["power_one_sided_2.5pct"], "min_detectable_gain": _mde(rows), "n": int(len(W)), "clusters": k}
    for tgt in ("margin", "total"):
        d = ladder_view(ds, tgt)
        cod, kk = codes_of(d)
        sd, mu = d.sd.to_numpy(float), d.mu.to_numpy(float)

        def mk_l(theta, sd=sd, mu=mu):
            def f(sB, r):
                n = len(sd); z = r.standard_normal(n)
                yy = mu + theta * sd * z + sd * r.standard_normal(n)
                return crps_normal(yy, mu + theta * sd * (z + r.standard_normal(n)), sd) - crps_normal(yy, mu + theta * sd * (z + sB * r.standard_normal(n)), sd)
            return f
        for th in theta_l:
            rows = _power_curve(mk_l(th), cod, kk, grid, n_sims, seed)
            out[f"{tgt}_theta{th}"] = {"curve": rows, "false_positive_at_null": rows[0]["power_one_sided_2.5pct"], "min_detectable_gain_points": _mde(rows), "n": int(len(d)), "clusters": kk}
    T, P = ds["props_thr"], ds["props_lad"]
    P = P[P.sd.notna()].reset_index(drop=True)
    lads = [(g.sort_values("k").k.to_numpy(float), g.sort_values("k").p_market90.to_numpy(float)) for _, g in T[T.lad.isin(P.lad)].groupby("lad", sort=False)]
    order = [lid for lid, _ in T[T.lad.isin(P.lad)].groupby("lad", sort=False)]
    P = P.set_index("lad").loc[order].reset_index()
    sds = P.sd.to_numpy(float)
    cod, kk = codes_of(P)

    def mk_p(theta):
        def f(sB, r):
            o = np.empty(len(lads))
            for i, (ks, S) in enumerate(lads):
                z, eA, eB, u = r.standard_normal(), r.standard_normal(), sB * r.standard_normal(), r.random()
                yes = (u <= np.interp(ks - theta * sds[i] * z, ks, S)).astype(float)
                o[i] = ((np.interp(ks - theta * sds[i] * (z + eA), ks, S) - yes) ** 2).sum() - ((np.interp(ks - theta * sds[i] * (z + eB), ks, S) - yes) ** 2).sum()
            return o
        return f
    for th in theta_l:
        rows = _power_curve(mk_p(th), cod, kk, [1.0, 0.5, 0.0], n_sims, seed)
        out[f"props_theta{th}"] = {"curve": rows, "false_positive_at_null": rows[0]["power_one_sided_2.5pct"], "min_detectable_gain": _mde(rows), "n": int(len(P)), "clusters": kk}
    out["false_positive_rates"] = {k_: v["false_positive_at_null"] for k_, v in out.items() if isinstance(v, dict) and "false_positive_at_null" in v}
    return out


# ------------------------------------------------------------------ step 3
def step3(ds) -> dict:
    W = ds["winners"].dropna(subset=["p_dec", "p_t90", "p_close"]).reset_index(drop=True)
    y = W.y_home_win.to_numpy(float)
    codes, k = codes_of(W)
    news = ll(W.p_dec.to_numpy(), y) - ll(W.p_close.to_numpy(), y)
    t90_vs_close = ll(W.p_t90.to_numpy(), y) - ll(W.p_close.to_numpy(), y)
    out = {"n_complete": int(len(W)), "clusters": k, "news_term_market_decision_minus_close": cl_mean(news, codes, k), "market_t90_minus_close": cl_mean(t90_vs_close, codes, k), "variants": {}}
    worst = 0.0
    for v in WIN_VARIANTS:
        lq = ll(W[v].to_numpy(), y)
        d_dec = lq - ll(W.p_dec.to_numpy(), y)
        d_close = lq - ll(W.p_close.to_numpy(), y)
        worst = max(worst, float(np.abs(d_close - (d_dec + news)).max()))
        out["variants"][v] = {"vs_market_at_decision": cl_mean(d_dec, codes, k), "vs_market_at_close": cl_mean(d_close, codes, k)}
    out["identity_max_abs_error"] = worst
    out["ladders_at_t90_only"] = {}
    for tgt in ("margin", "total"):
        d = ladder_view(ds, tgt)
        cod, kk = codes_of(d)
        base = crps_normal(d.y.to_numpy(), d.mu.to_numpy(), d.sd.to_numpy())
        out["ladders_at_t90_only"][tgt] = {}
        for v in (MARGIN_VARIANTS if tgt == "margin" else TOTAL_VARIANTS):
            mu_q, sd_q = ladder_losses(d, v)
            out["ladders_at_t90_only"][tgt][v] = cl_mean(crps_normal(d.y.to_numpy(), mu_q, sd_q) - base, cod, kk)
    return out


# ------------------------------------------------------------------ step 4 detectors (rehearsal) and helpers
def beats_market_flag(ds, col) -> bool:
    """Flag a forecast column that is significantly better than the T-90 market (cluster t, two-sided 95%): too good to be clean."""
    W = ds["winners"]
    y = W.y_home_win.to_numpy(float)
    codes, k = codes_of(W)
    c = cl_mean(ll(W[col].to_numpy(), y) - ll(W.p_t90.to_numpy(), y), codes, k)
    return bool(c["hi"] < 0)


def knowledge_time_flags(table: pd.DataFrame, decision_col="decision_utc", known_col="known_utc") -> int:
    return int((pd.to_datetime(table[known_col], utc=True) > pd.to_datetime(table[decision_col], utc=True)).sum())


# ------------------------------------------------------------------ step 5
def step5(ds, rng=None, wild=True) -> dict:
    rng = rng if wild else None
    W = ds["winners"]
    y, p = W.y_home_win.to_numpy(float), W.p_t90.to_numpy(float)
    codes, k = codes_of(W)
    out = {"winners": {"market_calibration": mz_logit(p, y, codes, k), "variants": {}}, "ladders": {}, "props": {}}
    for v in WIN_VARIANTS:
        q = W[v].to_numpy(float)
        fs = fs_test(q - p, y - p, codes, k, rng)
        out["winners"]["variants"][v] = {"encompassing": fs, "equivalence": equivalence(ll(q, y) - ll(p, y), codes, k, SESOI_WIN), "model_calibration": mz_logit(q, y, codes, k)}
    for tgt in ("margin", "total"):
        d = ladder_view(ds, tgt)
        cod, kk = codes_of(d)
        yy, mu, sd = d.y.to_numpy(float), d.mu.to_numpy(float), d.sd.to_numpy(float)
        base = crps_normal(yy, mu, sd)
        out["ladders"][tgt] = {"market_calibration": mz_ols(mu, yy, cod, kk), "variants": {}}
        for v in (MARGIN_VARIANTS if tgt == "margin" else TOTAL_VARIANTS):
            mu_q, sd_q = ladder_losses(d, v)
            out["ladders"][tgt]["variants"][v] = {"encompassing": fs_test(mu_q - mu, yy - mu, cod, kk, rng),
                                                  "equivalence": equivalence(crps_normal(yy, mu_q, sd_q) - base, cod, kk, SESOI_FRAC * float(base.mean()))}
    T, P = ds["props_thr"], ds["props_lad"]
    for a in PROPS_ARMS:
        col = f"p_{a}"
        m = T[col].notna()
        Ta = T[m]
        cod, kk = codes_of(Ta)
        fs = fs_test(Ta[col].to_numpy(float) - Ta.p_market90.to_numpy(float), Ta.yes.to_numpy(float) - Ta.p_market90.to_numpy(float), cod, kk, rng)
        Pa = P[P[f"real_{a}"].notna()]
        cp, kp = codes_of(Pa)
        out["props"][a] = {"encompassing": fs, "equivalence": equivalence((Pa[f"real_{a}"] - Pa.real_market90).to_numpy(), cp, kp, SESOI_FRAC * float(P.real_market90.mean()))}
    return out


# ------------------------------------------------------------------ step 6
def _bh_discoveries(p, q=0.05) -> int:
    p = np.sort(np.asarray(p)); m = len(p)
    ok = np.where(p <= q * (np.arange(1, m + 1) / m))[0]
    return int(ok.max() + 1) if len(ok) else 0


def step6_placebos(ds, rng, n_draw=100, n_shift=20, n_junk=20) -> dict:
    """Amendment 5 definitions. (a) label placebo: outcomes redrawn from the T-90 market (the market is the truth, so the model weight is 0).
    (b) time-shift placebo: each game keeps its market and outcome but gets the model forecast of another game, shifted 9 to 28 places in
    (season, week, game) order. (c) junk placebo: pure-noise forecasts. All use the cluster-robust t test at 5%."""
    W = ds["winners"].sort_values(["season", "week", "gid"]).reset_index(drop=True)
    y, p = W.y_home_win.to_numpy(float), W.p_t90.to_numpy(float)
    codes, k = codes_of(W)
    lab, shf = [0, 0], [0, 0]
    shift_cover = []
    for v in WIN_VARIANTS:
        q = W[v].to_numpy(float)
        for _ in range(n_draw):
            yd = (rng.random(len(p)) < p).astype(float)
            lab[0] += fs_test(q - p, yd - p, codes, k, rng, 499)["p_wild"] < 0.05
            lab[1] += 1
        for s in range(n_shift):
            f = fs_test(np.roll(q, 9 + s) - p, y - p, codes, k, rng, 499)
            shf[0] += f["p_wild"] < 0.05
            shf[1] += 1
            shift_cover.append(bool(f["lo"] <= 0 <= f["hi"]))
    pj = [fs_test(sigmoid(logit(p) + 0.3 * rng.standard_normal(len(p))) - p, y - p, codes, k, rng, 499)["p_wild"] for _ in range(n_junk)]
    return {"label_placebo_rejections": lab, "time_shift_rejections": shf, "time_shift_interval_covers_zero": [int(sum(shift_cover)), len(shift_cover)],
            "junk_nominal_significant": [int(np.sum(np.array(pj) < 0.05)), n_junk], "junk_bh_discoveries": _bh_discoveries(pj)}


# ------------------------------------------------------------------ step 7
def spa_rc(D, codes, k, rng, B=1000) -> dict:
    """D: n x m, positive means the variant beats the benchmark. Amendment 7: Hansen SPA and White Reality Check with a studentized
    (bootstrap-t) wild cluster bootstrap: each draw is divided by its own cluster-robust standard error. From memory, check before use."""
    n, m = D.shape
    dbar = D.mean(0)
    S = np.stack([np.bincount(codes, weights=D[:, j], minlength=k) for j in range(m)], 1)       # k x m cluster sums
    nc = np.bincount(codes, minlength=k).astype(float)
    E = S - nc[:, None] * dbar                                                                  # centered cluster sums
    se = np.sqrt(k / (k - 1) * (E ** 2).sum(0)) / n
    se = np.where(se > 0, se, 1e-12)
    t_obs = dbar / se
    w = rng.choice([-1.0, 1.0], size=(B, k))
    dev = np.einsum("bk,km->bm", w, E) / n                                                      # B x m centered bootstrap means
    R = w[:, :, None] * E[None] - nc[None, :, None] * dev[:, None, :]                           # B x k x m
    seb = np.sqrt(k / (k - 1) * (R ** 2).sum(1)) / n
    seb = np.where(seb > 0, seb, 1e-12)
    T = max(float(t_obs.max()), 0.0)
    g = np.where(t_obs <= -np.sqrt(2 * np.log(np.log(n))), dbar, 0.0)
    Tb = np.maximum(((dev + g) / seb).max(1), 0.0)
    T_rc = float(t_obs.max())
    p_rc = float(((dev / seb).max(1) >= T_rc).mean())
    return {"p_rc": p_rc, "p_spa": float((Tb > T).mean()), "best_variant_index": int(np.argmax(dbar)), "best_mean_gain": float(dbar.max())}


def pbo(weekly: np.ndarray, S=8) -> dict:
    """Probability of backtest overfitting by combinatorially symmetric cross-validation. weekly: weeks x variants (higher is better)."""
    from itertools import combinations
    w, m = weekly.shape
    if w < S:
        return {"valid": False, "reason": f"{w} weeks is fewer than {S} blocks"}
    blocks = np.array([b.mean(0) for b in np.array_split(weekly, S)])
    lam = []
    for c in combinations(range(S), S // 2):
        ins = blocks[list(c)].mean(0)
        oos = blocks[[i for i in range(S) if i not in c]].mean(0)
        best = int(np.argmax(ins))
        rank = (oos < oos[best]).sum() + 1
        om = rank / (m + 1)
        lam.append(np.log(om / (1 - om)))
    return {"valid": True, "pbo": float(np.mean(np.array(lam) <= 0)), "blocks": S, "combinations": len(lam)}


def step7(ds, rng, B=1000) -> dict:
    out = {"variants_counted": 0, "families": {}}
    fam = {}
    W = ds["winners"]
    y, p = W.y_home_win.to_numpy(float), W.p_t90.to_numpy(float)
    fam["winners"] = (np.column_stack([ll(p, y) - ll(W[v].to_numpy(float), y) for v in WIN_VARIANTS]), W, WIN_VARIANTS)
    for tgt, vs in (("margin", MARGIN_VARIANTS), ("total", TOTAL_VARIANTS)):
        d = ladder_view(ds, tgt)
        base = crps_normal(d.y.to_numpy(), d.mu.to_numpy(), d.sd.to_numpy())
        cols = []
        for v in vs:
            mu_q, sd_q = ladder_losses(d, v)
            cols.append(base - crps_normal(d.y.to_numpy(), mu_q, sd_q))
        fam[tgt] = (np.column_stack(cols), d, vs)
    P = ds["props_lad"]
    Pc = P.dropna(subset=[f"real_{a}" for a in PROPS_ARMS]).reset_index(drop=True)
    fam["props"] = (np.column_stack([Pc.real_market90 - Pc[f"real_{a}"] for a in PROPS_ARMS]), Pc, PROPS_ARMS)
    for name, (D, frame, vs) in fam.items():
        codes, k = codes_of(frame)
        res = spa_rc(D, codes, k, rng, B)
        wk = pd.DataFrame(D, columns=vs).assign(wk=frame.wk.to_numpy()).groupby("wk").mean().sort_index()
        res.update({"variants": list(vs), "m": len(vs), "clusters": k, "valid": k >= 10, "pbo": pbo(wk.to_numpy())})
        out["families"][name] = res
        out["variants_counted"] += len(vs)
    return out
