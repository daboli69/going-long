"""Improvement protocol Step 4: shrink-to-market blend (definition and conditions in PROTOCOL2.md). Usage: python i4_blend.py rehearsal | real"""
import sys
from steps import *

MODE = sys.argv[1]
res = header(f"i4_{MODE}", ("i4_blend.py",))
import os
K_PRIOR_GAMES = int(os.environ.get("I4_K", "50"))
FIRST_WEEKS = 3


def blend_weights(x, u, order):
    """Weight for each game from completed earlier weeks only. order: integer rank of the game's week (0, 1, 2 ...).
    w = clip(sum(x u) / (sum(x^2) + K), 0, 1) with K = 20 x mean(x^2) over the games of the first 3 weeks (forecast gaps, no outcomes)."""
    x = np.asarray(x, float); u = np.asarray(u, float); order = np.asarray(order)
    K = K_PRIOR_GAMES * float(np.mean(x[order < FIRST_WEEKS] ** 2))
    w = np.zeros(len(x)); sxu = sxx = 0.0
    for wk in np.unique(order):
        m = order == wk
        w[m] = float(np.clip(sxu / (sxx + K), 0.0, 1.0)) if wk > 0 else 0.0
        sxu += float((x[m] * u[m]).sum()); sxx += float((x[m] ** 2).sum())
    return w


def week_rank(wk):
    codes = pd.factorize(pd.Series(sorted(set(wk))))[0]
    m = dict(zip(sorted(set(wk)), codes))
    return np.array([m[v] for v in wk])


def winners_blend(df, variant):
    d = df.sort_values(["wk", "gid"]).reset_index(drop=True)
    y, p, q = d.y_home_win.to_numpy(float), d.p_t90.to_numpy(float), d[variant].to_numpy(float)
    order = week_rank(d.wk.to_numpy())
    w = blend_weights(q - p, y - p, order)
    f = np.clip(p + w * (q - p), 0.01, 0.99)
    codes, k = codes_of(d)
    return {"w": w, "loss_blend": ll(f, y), "loss_model": ll(q, y), "loss_market": ll(p, y), "codes": codes, "k": k, "order": order}


def ladder_blend(d, variant):
    d = d.sort_values(["wk", "gid"]).reset_index(drop=True)
    y, mu = d.y.to_numpy(float), d.mu.to_numpy(float)
    mu_q, sd_q = ladder_losses(d, variant)
    sd = d.sd.to_numpy(float)
    order = week_rank(d.wk.to_numpy())
    w = blend_weights(mu_q - mu, y - mu, order)
    codes, k = codes_of(d)
    return {"w": w, "loss_blend": crps_normal(y, mu + w * (mu_q - mu), sd), "loss_model": crps_normal(y, mu_q, sd_q), "loss_market": crps_normal(y, mu, sd), "codes": codes, "k": k, "order": order}


def summarize(r, delta):
    return {"mean_w": float(r["w"].mean()), "final_w": float(r["w"][r["order"] == r["order"].max()].mean()),
            "blend_minus_model": cl_mean(r["loss_blend"] - r["loss_model"], r["codes"], r["k"]),
            "blend_minus_market": cl_mean(r["loss_blend"] - r["loss_market"], r["codes"], r["k"]),
            "equivalence_vs_market": equivalence(r["loss_blend"] - r["loss_market"], r["codes"], r["k"], delta)}


if MODE == "rehearsal":
    T = real_dataset(2025)
    out = {"null": {"mean_w": [], "within_0.005": [], "ladder_mean_w": [], "ladder_within": []}, "planted_strong": {"mean_w": [], "below_market": [], "ladder_mean_w": [], "ladder_below": []}}
    for world, var_w, var_l in (("null", "p_xgb_v1", "L"), ("planted_strong", "p_xgb_deep", "L")):
        for i in range(200):
            d = sim_dataset(T, world, np.random.default_rng(3000 + i))
            r = winners_blend(d["winners"], var_w)
            out[world]["mean_w"].append(float(r["w"].mean()))
            diff = float((r["loss_blend"] - r["loss_market"]).mean())
            out[world]["within_0.005" if world == "null" else "below_market"].append(abs(diff) <= 0.005 if world == "null" else diff < 0)
            tl = ladder_view(d, "margin"); rl = ladder_blend(tl, var_l)
            out[world]["ladder_mean_w"].append(float(rl["w"].mean()))
            dl = float((rl["loss_blend"] - rl["loss_market"]).mean())
            out[world]["ladder_within" if world == "null" else "ladder_below"].append(abs(dl) <= 0.07 if world == "null" else dl < 0)
    n, p_ = out["null"], out["planted_strong"]
    res["null"] = {"mean_w_winners": float(np.mean(n["mean_w"])), "share_within_0.005": float(np.mean(n["within_0.005"])), "mean_w_margin": float(np.mean(n["ladder_mean_w"])), "share_within_margin": float(np.mean(n["ladder_within"]))}
    res["planted_strong"] = {"mean_w_winners": float(np.mean(p_["mean_w"])), "share_blend_below_market": float(np.mean(p_["below_market"])), "mean_w_margin": float(np.mean(p_["ladder_mean_w"])), "share_ladder_blend_below_market": float(np.mean(p_["ladder_below"]))}
    res["conditions"] = {"null_mean_w_le_0.15": res["null"]["mean_w_winners"] <= 0.15 and res["null"]["mean_w_margin"] <= 0.15, "null_within_margin_ge_90": res["null"]["share_within_0.005"] >= 0.9 and res["null"]["share_within_margin"] >= 0.9,
                         "planted_mean_w_ge_0.5": res["planted_strong"]["mean_w_winners"] >= 0.5 and res["planted_strong"]["mean_w_margin"] >= 0.5,
                         "planted_below_market_ge_90": res["planted_strong"]["share_blend_below_market"] >= 0.9 and res["planted_strong"]["share_ladder_blend_below_market"] >= 0.9}
    res["PASS"] = bool(all(res["conditions"].values()))
    write("i4_rehearsal.json", res); print("I4 REHEARSAL", "PASS" if res["PASS"] else "FAIL", json.dumps(res["null"]), json.dumps(res["planted_strong"]), json.dumps({k: bool(v) for k, v in res["conditions"].items()}))
else:
    gate("i4_rehearsal.json", ("i4_blend.py",))
    ds = real_dataset(2025)
    W = ds["winners"]; res["sample"] = f"2025: {len(W)} games"
    res["winners"] = {v: summarize(winners_blend(W, v), SESOI_WIN) for v in WIN_VARIANTS}
    res["ladders"] = {}
    for t, vs in (("margin", MARGIN_VARIANTS), ("total", TOTAL_VARIANTS)):
        d = ladder_view(ds, t); base = crps_normal(d.y.to_numpy(), d.mu.to_numpy(), d.sd.to_numpy())
        res["ladders"][t] = {v: summarize(ladder_blend(d, v), SESOI_FRAC * float(base.mean())) for v in vs}
    # leak check: the week-5 weight must not change when everything after week 4 is removed
    d = W.sort_values(["wk", "gid"]).reset_index(drop=True); y, p, q = d.y_home_win.to_numpy(float), d.p_t90.to_numpy(float), d["p_xgb_v1"].to_numpy(float)
    order = week_rank(d.wk.to_numpy()); wfull = blend_weights(q - p, y - p, order)
    keep = order <= 4; wcut = blend_weights((q - p)[keep], (y - p)[keep], order[keep])
    res["leak_check"] = {"week_index_5_weight_full": float(wfull[order == 4][0]), "week_index_5_weight_cut": float(wcut[order[keep] == 4][0]), "equal": bool(np.isclose(wfull[order == 4][0], wcut[order[keep] == 4][0]))}
    prim = {"winners:p_xgb_v1": res["winners"]["p_xgb_v1"], "margin:L": res["ladders"]["margin"]["L"], "total:L": res["ladders"]["total"]["L"]}
    res["primary"] = prim
    res["stop_rule"] = {k: (v["equivalence_vs_market"]["status"] == "worse_than_margin") for k, v in prim.items()}
    res["checks"] = {"weights_from_earlier_weeks_only": res["leak_check"]["equal"], "intervals_and_equivalence_reported": all("blend_minus_model" in v for v in prim.values()), "stop_rule_evaluated": True}
    res["PASS"] = bool(all(res["checks"].values()))
    write("i4_blend.json", res); print("I4 REAL", "PASS" if res["PASS"] else "FAIL", json.dumps(res["checks"]), "stop rule fired:", res["stop_rule"])
