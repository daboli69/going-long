"""Main run and freeze for scripts/forecast_study.py (protocol docs/FORECAST_PREREGISTRATION.md, commits 94e455cc, db086e43)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

import forecast_study as FS
from lab import forecast_core as fc
from lab import homewin_deep as h
from lab import homewin_eval as ev
from lab import kalshi as K
from lab import props_kalshi as pk

log, write, CACHE, OUT = FS.log, FS.write, FS.CACHE, FS.OUT
A4, A3, SEED = 0.05 / 4, 0.05 / 3, 0


def clus(df):
    return (df["season"].astype(str) + "_" + df["week"].astype(str)).to_numpy()


def paired(df, d, alpha, sesoi=None, decidable=False):
    d = np.asarray(d, float)
    ci = ev.cluster_boot(d, clus(df), alpha)
    r = {"n": int(len(d)), "mean_diff": float(d.mean()), "ci": ci, "ci_level": 1 - alpha, "improves": bool(ci[1] < 0)}
    if sesoi is not None:
        r["sesoi"] = float(sesoi)
        r["material"] = bool(r["improves"] and d.mean() <= -sesoi)
    r["verdict_allowed"] = bool(decidable)
    return r


# --------------------------------------------------------------------------- Kalshi window rows

def window_rows(G, wf, lad, wp):
    gi = G.set_index("gid")
    m = wf.set_index("gid")
    rows = []
    for (gid, tgt), L in lad.items():
        if gid not in gi.index or gid not in m.index or not gi.at[gid, "played"]:
            continue
        muK = fc.ladder_median(L)
        if np.isnan(muK):
            continue
        r, p = gi.loc[gid], m.loc[gid]
        y_cont = float(r["margin"] if tgt == "margin" else r["total"])
        mu_m = float(p["mu_m"] if tgt == "margin" else p["mu_t"])
        sd_m = float(p["sd_m"] if tgt == "margin" else p["sd_t"])
        rows.append({"gid": gid, "tgt": tgt, "season": int(r["season"]), "week": int(r["week"]), "muK": muK, "mu_model": mu_m, "sd_model": sd_m,
                     "y": y_cont, "lad": L, "tie": bool(r["margin"] == 0)})
    return rows


def b_walk_forward(rows, tgt, shuffle_rng=None):
    """Per game: b fitted on earlier weeks of the window (min 100 games), lean z, corrected/base ladder CRPS. Returns DataFrame."""
    R = sorted([r for r in rows if r["tgt"] == tgt], key=lambda r: (r["season"], r["week"]))
    weeks = sorted({(r["season"], r["week"]) for r in R})
    if shuffle_rng is not None:  # placebo: permute the model's mu across games within each week
        for sw in weeks:
            idx = [i for i, r in enumerate(R) if (r["season"], r["week"]) == sw]
            perm = shuffle_rng.permutation(len(idx))
            vals = [(R[i]["mu_model"]) for i in idx]
            for j, i in enumerate(idx):
                R[i] = {**R[i], "mu_model": vals[perm[j]]}
    out = []
    for sw in weeks:
        before = [r for r in R if (r["season"], r["week"]) < sw]
        if len(before) < 100:
            continue
        d_tr = np.array([r["mu_model"] - r["muK"] for r in before])
        e_tr = np.array([r["y"] - r["muK"] for r in before])
        b, s = fc.fit_b(d_tr, e_tr), float(d_tr.std())
        for r in [r for r in R if (r["season"], r["week"]) == sw]:
            L = r["lad"]
            y = (r["y"] > L["c"].to_numpy()).astype(float)
            d = r["mu_model"] - r["muK"]
            delta = b * d
            z = d / s if s > 0 else 0.0
            p_base = L["p_iso"].to_numpy()
            p_cor = fc.shifted(L, delta)
            p_abs = p_base if abs(z) < 0.5 else p_cor
            p_mod = 1 - norm.cdf((L["c"].to_numpy() - r["mu_model"]) / r["sd_model"])
            row = {"gid": r["gid"], "season": r["season"], "week": r["week"], "b": b, "d": d, "z": z, "e": r["y"] - r["muK"], "muK": r["muK"],
                   "mu_model": r["mu_model"], "mu_corr": r["muK"] + delta, "y_cont": r["y"],
                   "c_base": fc.ladder_crps(p_base, y), "c_cor": fc.ladder_crps(p_cor, y), "c_abs": fc.ladder_crps(p_abs, y), "c_mod": fc.ladder_crps(p_mod, y)}
            if tgt == "margin" and not r["tie"]:
                yw = float(r["y"] > 0)
                row["ll_base"] = float(fc.log_loss_vec(np.array([float(fc.shifted(L, 0.0, np.array([0.5]))[0])]), yw)[0])
                row["ll_cor"] = float(fc.log_loss_vec(np.array([float(fc.shifted(L, delta, np.array([0.5]))[0])]), yw)[0])
            out.append(row)
    return pd.DataFrame(out)


def run(args):
    G = fc.games_frame()
    tun = json.loads((OUT / "tuning.json").read_text(encoding="utf-8"))
    wf = fc.walk_forward(G, tun["tau_n"], tun["tau_s"], range(2012, 2027))
    wf.to_parquet(CACHE.parent / "homewin_deep" / "forecast_wf.parquet")
    pw = json.loads((OUT / "power.json").read_text(encoding="utf-8"))["comparisons"]
    log(f"walk-forward: {len(wf)} games, {wf[['season', 'week']].drop_duplicates().shape[0]} weeks")
    res = {"prereg": fc.PREREG, "label": "history descriptive except L1; only prospective freezes can pass the K family; nothing promoted", "tau": {k: tun[k] for k in ("tau_n", "tau_s")}}

    # ---- family L (long history)
    mod_m, el_m = fc.crps_normal(wf["y_m"], wf["mu_m"], wf["sd_m"]), fc.crps_normal(wf["y_m"], wf["elo_mu"], fc.SD0)
    nv_m = fc.crps_normal(wf["y_m"], wf["naive_m_mu"], wf["naive_m_sd"])
    mod_t, nv_t = fc.crps_normal(wf["y_t"], wf["mu_t"], wf["sd_t"]), fc.crps_normal(wf["y_t"], wf["naive_t_mu"], wf["naive_t_sd"])
    nt = wf[~wf["tie"].astype(bool)]
    yw = (nt["y_m"] > 0).astype(float).to_numpy()
    L = {"L1_margin_vs_elo_normal": paired(wf, mod_m - el_m, A4, 0.01 * el_m.mean(), pw["L1_margin_vs_elo_normal"]["decidable_now"]),
         "L2_margin_vs_naive": paired(wf, mod_m - nv_m, A4, 0.01 * nv_m.mean(), pw["L2_margin_vs_naive"]["decidable_now"]),
         "L3_total_vs_naive": paired(wf, mod_t - nv_t, A4, 0.01 * nv_t.mean(), pw["L3_total_vs_naive"]["decidable_now"]),
         "L4_winner_logloss_vs_elo": paired(nt, fc.log_loss_vec(nt["p_win"].to_numpy(), yw) - fc.log_loss_vec(nt["p_elo"].to_numpy(), yw), A4, 0.005,
                                            pw["L4_winner_logloss_vs_elo"]["decidable_now"])}
    L["L1_margin_vs_elo_normal"]["seasons_better"] = int(((pd.Series(mod_m - el_m).groupby(wf["season"].to_numpy()).mean()) < 0).sum())
    L["L1_margin_vs_elo_normal"]["seasons"] = int(wf["season"].nunique())
    res["L"] = L
    res["L_means"] = {"margin_crps": {"model": float(mod_m.mean()), "elo_normal": float(el_m.mean()), "naive": float(nv_m.mean())},
                      "total_crps": {"model": float(mod_t.mean()), "naive": float(nv_t.mean())},
                      "winner_logloss": {"model": float(fc.log_loss_vec(nt["p_win"].to_numpy(), yw).mean()), "elo": float(fc.log_loss_vec(nt["p_elo"].to_numpy(), yw).mean())},
                      "rho_mean": float(wf["rho"].mean())}
    for k_, v in L.items():
        log(f"{k_}: diff {v['mean_diff']:+.4f} [{v['ci'][0]:+.4f},{v['ci'][1]:+.4f}] verdict_allowed={v['verdict_allowed']} improves={v['improves']}")

    # ---- conformal intervals for margin and total (80%)
    conf = {}
    for name, yv, mu, sd in (("margin", wf["y_m"], wf["mu_m"], wf["sd_m"]), ("total", wf["y_t"], wf["mu_t"], wf["sd_t"])):
        sc = (np.abs(yv.to_numpy() - mu.to_numpy()) / sd.to_numpy())
        keyw = list(zip(wf["season"], wf["week"]))
        hit_c, hit_r, n_c = [], [], 0
        order = sorted(set(keyw))
        for sw in order:
            idx = np.array([k_ == sw for k_ in keyw])
            before = np.array([k_ < sw for k_ in keyw])
            if before.sum() < 200:
                continue
            q = np.sort(sc[before])[min(int(np.ceil((before.sum() + 1) * 0.8)) - 1, before.sum() - 1)]
            hit_c += list(sc[idx] <= q)
            hit_r += list(sc[idx] <= norm.ppf(0.9))
            n_c += int(idx.sum())
        conf[name] = {"scored_games": n_c, "coverage_conformal": float(np.mean(hit_c)), "coverage_raw_normal": float(np.mean(hit_r)), "target": 0.8}
        log(f"conformal {name}: conformal {conf[name]['coverage_conformal']:.3f} raw {conf[name]['coverage_raw_normal']:.3f} (n={n_c})")
    res["conformal_margin_total"] = conf

    # ---- Kalshi window (family K)
    lad, wp = FS.kalshi_window(G)
    rows = window_rows(G, wf, lad, wp)
    K_ = {}
    desc = {}
    base_means = {}
    tables = {}
    for tgt, name, pwk in (("margin", "K1_margin_ladder_vs_kalshi", "K1_margin_ladder_vs_kalshi"), ("total", "K2_total_ladder_vs_kalshi", "K2_total_ladder_vs_kalshi")):
        T = b_walk_forward(rows, tgt)
        tables[tgt] = T
        base_means[tgt] = float(T["c_base"].mean())
        K_[name] = paired(T, (T["c_cor"] - T["c_base"]).to_numpy(), A3, 0.01 * T["c_base"].mean(), pw[pwk]["decidable_now"])
        K_[name]["weeks_scored"] = int(T[["season", "week"]].drop_duplicates().shape[0])
        K_[name]["b_mean"] = float(T["b"].mean())
        desc[tgt] = {"ladder_crps_base": float(T["c_base"].mean()), "ladder_crps_corrected": float(T["c_cor"].mean()),
                     "ladder_crps_model_alone": float(T["c_mod"].mean()), "ladder_crps_corrected_with_abstention": float(T["c_abs"].mean()),
                     "model_alone_vs_kalshi": paired(T, (T["c_mod"] - T["c_base"]).to_numpy(), A3)}
        log(f"{name}: corrected {T['c_cor'].mean():.3f} vs Kalshi {T['c_base'].mean():.3f} diff {K_[name]['mean_diff']:+.4f} "
            f"[{K_[name]['ci'][0]:+.4f},{K_[name]['ci'][1]:+.4f}] b mean {K_[name]['b_mean']:.3f} weeks {K_[name]['weeks_scored']}")
    Tm = tables["margin"].dropna(subset=["ll_base"])
    K_["K3_winner_logloss_vs_kalshi"] = paired(Tm, (Tm["ll_cor"] - Tm["ll_base"]).to_numpy(), A3, 0.005, pw["K3_winner_logloss_vs_kalshi"]["decidable_now"])
    res["K"], res["K_descriptive"] = K_, desc

    # placebo (shuffle model mu across games within each week)
    rng = np.random.default_rng(SEED)
    plc = {}
    for tgt, name in (("margin", "K1_margin_ladder_vs_kalshi"), ("total", "K2_total_ladder_vs_kalshi")):
        ds = []
        for _ in range(200):
            P = b_walk_forward(rows, tgt, shuffle_rng=rng)
            ds.append(float((P["c_cor"] - P["c_base"]).mean()))
        real = K_[name]["mean_diff"]
        ds = np.array(ds)
        plc[name] = {"real": real, "placebo_mean": float(ds.mean()), "placebo_p05": float(np.quantile(ds, 0.05)),
                     "permutation_p": float((1 + (ds <= real).sum()) / 201), "credible": bool(real < np.quantile(ds, 0.05))}
        log(f"placebo {name}: real {real:+.4f} placebo p05 {plc[name]['placebo_p05']:+.4f} p={plc[name]['permutation_p']:.3f}")
    res["placebo"] = plc

    # ---- leans
    leans = {}
    for tgt, T in tables.items():
        T = T.assign(az=T["z"].abs(), gain=T["c_base"] - T["c_cor"])
        bins = pd.cut(T["az"], [0, 0.5, 1.0, 1.5, 99], right=False, labels=["<0.5", "0.5-1", "1-1.5", "1.5+"])
        tab = []
        for lab_, g in T.groupby(bins, observed=True):
            sign = np.sign(g["d"])
            tab.append({"bin": str(lab_), "n": int(len(g)), "mean_lean_points": float(g["d"].abs().mean()),
                        "mean_realized_signed_deviation": float((g["e"] * sign).mean()), "mean_ladder_crps_gain": float(g["gain"].mean())})
        rho_s, _ = spearmanr(T["az"], T["gain"])
        rng2 = np.random.default_rng(SEED)
        wk_ids = clus(T)
        uw = np.unique(wk_ids)
        boots = []
        for _ in range(1000):
            pick = rng2.choice(uw, len(uw))
            sub = pd.concat([T[wk_ids == w] for w in pick])
            boots.append(spearmanr(sub["az"], sub["gain"])[0])
        leans[tgt] = {"table": tab, "spearman_lean_vs_gain": float(rho_s), "spearman_ci95": [float(np.nanquantile(boots, 0.025)), float(np.nanquantile(boots, 0.975))],
                      "abstain_below_z": 0.5, "share_abstained": float((T["az"] < 0.5).mean())}
        log(f"leans {tgt}: spearman {rho_s:+.3f} {leans[tgt]['spearman_ci95']}; table {[(t['bin'], t['n'], round(t['mean_ladder_crps_gain'], 3)) for t in tab]}")
    res["leans"] = leans

    # ---- Pinnacle (2026, descriptive): median forecasts vs outcomes
    gq = pd.read_parquet(h.CACHE / "going_quotes.parquet")
    pin = gq[(gq["book"] == "pinnacle") & gq["market"].isin(["spreads", "totals"])]
    gi = G.set_index("gid")
    pr = []
    for gid, g in gi[gi["played"] & (gi["season"] == 2026)].iterrows():
        P = g["kickoff_utc"] - pk.LEAD
        x = pin[(pin["home"] == g["home"]) & (pin["away"] == g["away"]) & ((pin["commence_time"] - g["kickoff_utc"]).abs() < pd.Timedelta(hours=36))
                & (pin["quote_time"] < P) & (pin["committed_at"] < P)]
        sp, to = x[(x["market"] == "spreads") & (x["side"] == "home")].sort_values("quote_time"), x[(x["market"] == "totals") & (x["side"].str.lower() == "over")].sort_values("quote_time")
        if len(sp) and len(to):
            pr.append({"gid": gid, "pin_margin": -float(sp["point"].iloc[-1]), "pin_total": float(to["point"].iloc[-1])})
    pr = pd.DataFrame(pr)
    mt, tt = tables["margin"].set_index("gid"), tables["total"].set_index("gid")
    j = pr.set_index("gid").join(mt[["muK", "mu_model", "mu_corr", "y_cont"]].rename(columns={"muK": "k_m", "mu_model": "m_m", "mu_corr": "c_m", "y_cont": "y_m"}), how="inner")
    j = j.join(tt[["muK", "mu_model", "mu_corr", "y_cont"]].rename(columns={"muK": "k_t", "mu_model": "m_t", "mu_corr": "c_t", "y_cont": "y_t"}), how="inner")
    if len(j):
        res["pinnacle_descriptive"] = {"games": int(len(j)),
                                       "margin_mae": {n: float((j["y_m"] - j[c]).abs().mean()) for n, c in (("pinnacle", "pin_margin"), ("kalshi", "k_m"), ("model", "m_m"), ("corrected", "c_m"))},
                                       "total_mae": {n: float((j["y_t"] - j[c]).abs().mean()) for n, c in (("pinnacle", "pin_total"), ("kalshi", "k_t"), ("model", "m_t"), ("corrected", "c_t"))},
                                       "pinnacle_vs_kalshi_median_gap": {"margin": float((j["pin_margin"] - j["k_m"]).abs().mean()), "total": float((j["pin_total"] - j["k_t"]).abs().mean())}}
        log(f"pinnacle descriptive: {res['pinnacle_descriptive']}")

    # ---- coherence: Kalshi winner price vs the spread ladder's implied P(home wins)
    q = pd.read_parquet(CACHE / "quotes.parquet")
    q = q[q["series"].isin(["KXNFLSPREAD"])]
    sp_only = fc.ladder_tables(q, G, {}, "90")
    gaps = []
    for (gid, tgt), Lm in sp_only.items():
        if tgt == "margin" and gid in wp and pd.notna(wp[gid]):
            gaps.append({"gid": gid, "gap": float(np.interp(0.5, Lm["c"], Lm["p_iso"]) - wp[gid])})
    gaps = pd.DataFrame(gaps)
    res["coherence"] = {"kalshi_winner_vs_spread_ladder": {"games": int(len(gaps)), "mean_gap": float(gaps["gap"].mean()),
                                                           "mean_abs_gap": float(gaps["gap"].abs().mean()), "share_abs_gap_over_0.02": float((gaps["gap"].abs() > 0.02).mean())},
                        "model_self": "P(win), spread and total are derived from one bivariate normal, so they agree by construction",
                        "not_run": ["team-total ladders (about 3,000 more candle pulls)", "Kalshi-normal comparator (omitted to save time)"]}
    log(f"coherence winner vs spread ladder: {res['coherence']['kalshi_winner_vs_spread_ladder']}")

    # ---- family T and prop interval coverage
    tf = FS.thin_frame()
    Tres, cov = {}, {}
    for grp, lab_ in (("thin", "T1_thin"), ("none", "T2_none"), ("liquid", "T3_liquid")):
        g = tf[tf["group"] == grp]
        if len(g) > 50:
            Tres[lab_] = paired(g, g["d_rel"].to_numpy(), A3, 0.01, False)
            Tres[lab_]["players_stats"] = int(len(g))
    res["T"] = Tres
    tf = tf.sort_values(["season", "week"]).reset_index(drop=True)
    tf["E"] = np.maximum(tf["q10"] - tf["y"], tf["y"] - tf["q90"])
    hit_raw = ((tf["y"] >= tf["q10"]) & (tf["y"] <= tf["q90"])).to_numpy()
    hit_conf = np.full(len(tf), np.nan)
    for st, g in tf.groupby("stat"):
        for sw in sorted(set(zip(g["season"], g["week"]))):
            cur = g[(g["season"] == sw[0]) & (g["week"] == sw[1])]
            prev = g[(g["season"] < sw[0]) | ((g["season"] == sw[0]) & (g["week"] < sw[1]))]
            if len(prev) < 200:
                continue
            qh = np.sort(prev["E"].to_numpy())[min(int(np.ceil((len(prev) + 1) * 0.8)) - 1, len(prev) - 1)]
            hit_conf[cur.index] = ((cur["y"] >= cur["q10"] - qh) & (cur["y"] <= cur["q90"] + qh)).to_numpy()
    tf["hit_raw"], tf["hit_conf"] = hit_raw, hit_conf
    for grp, g in tf.groupby("group"):
        gc = g.dropna(subset=["hit_conf"])
        cov[grp] = {"player_stats": int(len(g)), "raw_80_coverage": float(g["hit_raw"].mean()), "conformal_scored": int(len(gc)),
                    "conformal_80_coverage": float(gc["hit_conf"].mean()) if len(gc) else None,
                    "raw_coverage_same_rows": float(gc["hit_raw"].mean()) if len(gc) else None}
    res["prop_interval_coverage"] = cov
    log(f"prop coverage {cov}")
    write("results.json", res)


# --------------------------------------------------------------------------- weekly freeze (winners, spreads, totals)

def freeze(args):
    raise SystemExit("freeze is added after the main run is committed")
