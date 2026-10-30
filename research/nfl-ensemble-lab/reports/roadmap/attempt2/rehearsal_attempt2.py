"""Rehearsal of Steps 2 to 7 on simulated seasons (conditions: GOVERNANCE.md and its amendments). Usage: python rehearsal.py <2|3|4|5|6|7>"""
import sys
from steps import *
from steps import _power_curve

STEP = sys.argv[1]
TEMPLATE = real_dataset(2025)
res = header(f"rehearsal_step{STEP}")
res["template"] = f"real season {TEMPLATE['season']} structure: {len(TEMPLATE['winners'])} games, {TEMPLATE['winners'].wk.nunique()} weeks, props ladders {len(TEMPLATE['props_lad'])}"
res["world_definitions"] = {k: {kk: vv for kk, vv in v.items()} for k, v in WORLDS.items()}
res["theta_default"] = THETA


def sims(world, n, offset=0):
    for i in range(n):
        yield sim_dataset(TEMPLATE, world, np.random.default_rng(1000 + offset + i))


def rate(hits, total):
    return float(hits / total) if total else float("nan")


if STEP == "2":
    ds = sim_dataset(TEMPLATE, "null", np.random.default_rng(1000))
    pw = step2_power(ds, n_sims=400, seed=1)
    fps = pw["false_positive_rates"]
    res["power_false_positive_rates"] = fps
    res["power_detail"] = {k: v for k, v in pw.items() if k != "false_positive_rates"}
    cover = {}
    for world in ("null", "planted"):
        tr = truth(TEMPLATE, world)["winners"]["gap_realized_minus_entropy"]
        hit = 0
        for d in sims(world, 100, 5000):
            g = step2_ceilings(d)["winners"]["gap"]
            hit += g["lo"] <= tr <= g["hi"]
        cover[world] = {"truth_gap": tr, "coverage": hit / 100}
    res["gap_interval_coverage"] = cover
    res["conditions"] = {"fp_in_band_0.5_to_5pct": all(0.005 <= v <= 0.05 for v in fps.values()), "gap_coverage_ge_90": all(v["coverage"] >= 0.90 for v in cover.values())}

elif STEP == "3":
    ok_id, cover = True, 0
    for world in ("exch", "planted"):
        tr = truth(TEMPLATE, world)["winners"]["news_term"]
        hit = 0
        for d in sims(world, 100, 6000):
            r = step3(d)
            ok_id &= r["identity_max_abs_error"] < 1e-9
            c = r["news_term_market_decision_minus_close"]
            hit += c["lo"] <= tr <= c["hi"]
        res[f"news_coverage_{world}"] = {"truth": tr, "coverage": hit / 100}
    res["identity_ok"] = bool(ok_id)
    res["conditions"] = {"identity_1e-9": bool(ok_id), "news_coverage_ge_90": all(res[f"news_coverage_{w}"]["coverage"] >= 0.90 for w in ("exch", "planted"))}

elif STEP == "4":
    rng = np.random.default_rng(7)
    n = 200
    dec = pd.Timestamp("2025-10-05 17:00", tz="UTC") + pd.to_timedelta(rng.integers(0, 500, n), unit="h")
    tab = pd.DataFrame({"decision_utc": dec, "known_utc": dec - pd.to_timedelta(rng.integers(1, 2000, n), unit="m")})
    clean_flags = knowledge_time_flags(tab)
    leaks = {}
    for name, delta in (("1h", pd.Timedelta(hours=1)), ("6h", pd.Timedelta(hours=6)), ("24h", pd.Timedelta(hours=24)), ("72h", pd.Timedelta(hours=72)), ("8d", pd.Timedelta(days=8))):
        t2 = tab.copy(); t2.loc[:49, "known_utc"] = t2.loc[:49, "decision_utc"] + delta
        leaks[name] = {"planted_rows": 50, "flagged": knowledge_time_flags(t2)}
    fp = tot = 0
    for d in sims("null", 400, 0):
        for v in WIN_VARIANTS:
            fp += beats_market_flag(d, v); tot += 1
    det = {}
    for beta in (0.1, 0.2, 0.5):
        h = 0
        for d in sims("null", 400, 20000):
            y = d["winners"].y_home_win.to_numpy(float)
            d["winners"]["p_leak"] = sigmoid(logit(d["winners"]["p_elo"].to_numpy(float)) + beta * (2 * y - 1))
            h += beats_market_flag(d, "p_leak")
        det[str(beta)] = h / 400
    res.update({"knowledge_time_clean_flags": clean_flags, "knowledge_time_planted": leaks, "beats_market_false_positive_rate": fp / tot, "beats_market_detection_by_leak_size_logit": det})
    res["conditions"] = {"clean_not_flagged": clean_flags == 0, "all_planted_ge_24h_flagged": all(leaks[k]["flagged"] == 50 for k in ("24h", "72h", "8d")),
                         "bmt_fp_le_5pct": fp / tot <= 0.05, "bmt_detects_ge_95pct_at_0.5": det["0.5"] >= 0.95}

elif STEP == "5":
    fam = {}
    def add(name, e):
        fam.setdefault(name, [0, 0, 0, 0]); fam[name][0] += e["p_t"] < 0.05; fam[name][1] += e["p_wild"] < 0.05; fam[name][2] += 1
    for i, d in enumerate(sims("null", 400, 0)):
        r = step5(d, np.random.default_rng(i))
        for v, e in r["winners"]["variants"].items(): add("winners", e["encompassing"])
        for tgt in ("margin", "total"):
            for v, e in r["ladders"][tgt]["variants"].items(): add(tgt, e["encompassing"])
        for a, e in r["props"].items(): add("props", e["encompassing"])
    res["null_false_positive_rates"] = {k: {"t_interval": v[0] / v[2], "wild_bootstrap": v[1] / v[2], "tests": v[2]} for k, v in fam.items()}
    tr = truth(TEMPLATE, "planted")
    hit = {"winners_xgb_deep": 0, "margin_L": 0, "total_L": 0}
    pw = 0
    for i, d in enumerate(sims("planted", 100, 3000)):
        r = step5(d, np.random.default_rng(i), wild=False)
        e = r["winners"]["variants"]["p_xgb_deep"]["encompassing"]; hit["winners_xgb_deep"] += e["lo"] <= tr["winners"]["lambda"]["p_xgb_deep"] <= e["hi"]; pw += e["p_t"] < 0.05
        for tgt in ("margin", "total"):
            e = r["ladders"][tgt]["variants"]["L"]["encompassing"]; hit[f"{tgt}_L"] += e["lo"] <= tr["ladders"]["lambda"]["L"] <= e["hi"]
    res["planted_interval_coverage"] = {k: v / 100 for k, v in hit.items()}
    res["planted_truth_lambda"] = {"winners_xgb_deep": tr["winners"]["lambda"]["p_xgb_deep"], "ladders_L": tr["ladders"]["lambda"]["L"]}
    res["planted_detection_rate_winners_xgb_deep"] = pw / 100
    res["conditions"] = {"fp_wild_in_1_to_9pct": all(0.01 <= v["wild_bootstrap"] <= 0.09 for v in res["null_false_positive_rates"].values()),
                         "planted_coverage_ge_90": all(v >= 0.90 for v in res["planted_interval_coverage"].values())}

elif STEP == "6":
    agg = {}
    for world in ("null", "planted"):
        a = np.zeros(8)
        for i, d in enumerate(sims(world, 100, 7000)):
            r = step6_placebos(d, np.random.default_rng(i), n_draw=25, n_shift=20, n_junk=20)
            a += np.array([*r["label_placebo_rejections"], *r["time_shift_rejections"], *r["time_shift_interval_covers_zero"], *r["junk_nominal_significant"]], float)[:8] if False else np.array([
                r["label_placebo_rejections"][0], r["label_placebo_rejections"][1], r["time_shift_rejections"][0], r["time_shift_rejections"][1],
                r["time_shift_interval_covers_zero"][0], r["junk_nominal_significant"][0], r["junk_nominal_significant"][1], r["junk_bh_discoveries"] == 0], float)
        agg[world] = {"label_placebo_rate": a[0] / a[1], "time_shift_rate": a[2] / a[3], "time_shift_cover_zero": a[4] / a[3], "junk_nominal_rate": a[5] / a[6], "no_bh_discovery_share": a[7] / 100}
    res["placebos"] = agg
    # planted-edge detection vs the Step 2 power design for the same gain
    tr = truth(TEMPLATE, "planted")["winners"]["gain_vs_market"]["p_xgb_deep"]
    ds0 = sim_dataset(TEMPLATE, "planted", np.random.default_rng(1))
    W0 = ds0["winners"]; codes0, k0 = codes_of(W0); L0 = logit(TEMPLATE["winners"].p_t90.to_numpy(float))
    def mk(sB, r):
        n = len(L0); z = r.standard_normal(n); yy = (r.random(n) < sigmoid(L0 + THETA * z)).astype(float)
        return ll(sigmoid(L0 + THETA * (z + r.standard_normal(n))), yy) - ll(sigmoid(L0 + THETA * (z + sB * r.standard_normal(n))), yy)
    cur = _power_curve(mk, *cluster_index(TEMPLATE["winners"].wk.to_numpy()), [0.4], 400, seed=2)[0]
    obs = 0
    for d in sims("planted", 100, 9000):
        W = d["winners"]; c, kk = codes_of(W); y = W.y_home_win.to_numpy(float)
        dd = ll(W.p_t90.to_numpy(), y) - ll(W.p_xgb_deep.to_numpy(), y); ci = cl_mean(dd, c, kk); obs += ci["lo"] > 0
    res["planted_edge"] = {"true_gain_per_game": tr, "step2_design_gain": cur["expected_gain"], "step2_predicted_power": cur["power_one_sided_2.5pct"], "observed_detection": obs / 100}
    n_ = agg["null"]
    res["conditions"] = {"label_fp_1_to_9": 0.01 <= n_["label_placebo_rate"] <= 0.09, "time_shift_fp_1_to_9": 0.01 <= n_["time_shift_rate"] <= 0.09,
                         "time_shift_cover_ge_90": n_["time_shift_cover_zero"] >= 0.90, "junk_2_to_9": 0.02 <= n_["junk_nominal_rate"] <= 0.09, "junk_no_bh_ge_90": n_["no_bh_discovery_share"] >= 0.90,
                         "planted_within_0.15": abs(res["planted_edge"]["observed_detection"] - cur["power_one_sided_2.5pct"]) <= 0.15}

elif STEP == "7":
    NULL_PBO = {"winners": 0.5, "margin": 2 / 3, "total": 0.5, "props": 0.6}  # exact null values for 8, 3, 2 and 5 variants (Amendment 6)
    fp = {}
    pbo_null = {}
    for i, d in enumerate(sims("exch", 400, 0)):
        r = step7(d, np.random.default_rng(i), B=500)
        for f, e in r["families"].items():
            fp.setdefault(f, [0, 0, 0]); fp[f][0] += e["p_spa"] < 0.05; fp[f][1] += e["p_rc"] < 0.05; fp[f][2] += 1
            if e["pbo"].get("valid"): pbo_null.setdefault(f, []).append(e["pbo"]["pbo"])
    res["exchangeable_false_positive_rates"] = {f: {"spa": v[0] / v[2], "reality_check": v[1] / v[2]} for f, v in fp.items()}
    res["exchangeable_pbo_mean"] = {f: float(np.mean(v)) for f, v in pbo_null.items()}
    rej, pbo_pl = {}, {}
    for i, d in enumerate(sims("planted", 100, 4000)):
        r = step7(d, np.random.default_rng(i), B=500)
        for f, e in r["families"].items():
            rej.setdefault(f, [0, 0]); rej[f][0] += e["p_spa"] < 0.05; rej[f][1] += 1
            if e["pbo"].get("valid"): pbo_pl.setdefault(f, []).append(e["pbo"]["pbo"])
    res["planted_rejection_rate"] = {f: v[0] / v[1] for f, v in rej.items()}
    res["planted_pbo_mean"] = {f: float(np.mean(v)) for f, v in pbo_pl.items()}
    res["null_pbo_exact"] = NULL_PBO
    res["conditions"] = {"spa_fp_1_to_9": all(0.01 <= v["spa"] <= 0.09 for v in res["exchangeable_false_positive_rates"].values()),
                         "pbo_null_within_0.10_of_exact": all(abs(v - NULL_PBO[f]) <= 0.10 for f, v in res["exchangeable_pbo_mean"].items()),
                         "planted_winners_rejects_ge_80": res["planted_rejection_rate"]["winners"] >= 0.80,
                         "planted_winners_pbo_lt_025": res["planted_pbo_mean"]["winners"] < 0.25}

res["PASS"] = bool(all(res["conditions"].values()))
write(f"rehearsal_step{STEP}.json", res)
print(f"REHEARSAL {STEP}:", "PASS" if res["PASS"] else "FAIL")
print(json.dumps({k: bool(v) for k, v in res["conditions"].items()}, indent=1))
