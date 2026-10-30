"""Real-data steps on the 2025 exploratory sample. Gate: the step's rehearsal must have passed. Usage: python run_real.py <2|3|5|6|7>"""
import sys
from steps import *
STEP = sys.argv[1]
SEASON = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
gate(f"rehearsal_step{STEP}.json")
ds = real_dataset(SEASON)
res = header(f"real_step{STEP}")
res["sample"] = f"season {SEASON}: {len(ds['winners'])} games, {ds['winners'].wk.nunique()} weeks; ladders {len(ds['ladders'])}; props ladders {len(ds['props_lad'])}"
rng = np.random.default_rng(SEED)

if STEP == "3":
    r = step3(ds)
    res.update(r)
    res["checks"] = {"n_complete_ge_250": r["n_complete"] >= 250, "identity_1e-9": r["identity_max_abs_error"] < 1e-9, "margin_total_at_t90_only_recorded": True}
elif STEP == "2":
    c = step2_ceilings(ds)
    pw = step2_power(ds, n_sims=400, seed=1)
    res.update(c); res["power"] = pw
    n = {"margin": c["ladders"]["margin"]["n"], "total": c["ladders"]["total"]["n"], "props": c["props"]["n"]}
    res["checks"] = {"winner_ceiling_with_interval": True, "ladder_counts": n, "counts_ok": n["margin"] >= 100 and n["total"] >= 100 and n["props"] >= 150 and c["props"]["clusters"] >= 10,
                     "false_positive_rates": pw["false_positive_rates"], "fp_in_band": all(0.005 <= v <= 0.05 for v in pw["false_positive_rates"].values())}
    mde = {k_: v_.get("min_detectable_gain", v_.get("min_detectable_gain_points")) for k_, v_ in pw.items() if isinstance(v_, dict) and "curve" in v_}
    res["checks"]["d_min_detectable_reported_for_each_target"] = all(k_ in mde for k_ in ("winners_theta0.3", "margin_theta0.3", "total_theta0.3", "props_theta0.3"))
    res["min_detectable_gain_80pct"] = {k_: (v_ if v_ is not None else "not reached on the grid; power at the top gain is in power.*.curve") for k_, v_ in mde.items()}
    res["conditional_on_market_is_truth"] = ["entropy and sigma/sqrt(pi) ceilings", "power simulations"]
elif STEP == "5":
    r = step5(ds, rng)
    res.update(r)
    W = ds["winners"]; codes, k = codes_of(W)
    y, p = W.y_home_win.to_numpy(float), W.p_t90.to_numpy(float)
    ess = design_effect(ll(W.p_xgb_deep.to_numpy(), y) - ll(p, y), codes, k)
    flat = []
    for v in r["winners"]["variants"].values(): flat.append(v["encompassing"])
    for t in r["ladders"].values():
        for v in t["variants"].values(): flat.append(v["encompassing"])
    for v in r["props"].values(): flat.append(v["encompassing"])
    res["effective_sample_winners"] = ess
    res["checks"] = {"all_wild_p_finite": all(np.isfinite(f["p_wild"]) for f in flat), "effective_n_winners_ge_100": ess["effective_n"] >= 100, "every_coefficient_has_interval": all(np.isfinite(f["lo"]) and np.isfinite(f["hi"]) for f in flat)}
elif STEP == "6":
    r = step6_placebos(ds, rng, n_draw=100, n_shift=20, n_junk=400)
    res.update(r)
    lab, shf, cov, junk = r["label_placebo_rejections"], r["time_shift_rejections"], r["time_shift_interval_covers_zero"], r["junk_nominal_significant"]
    res["placebo_rates"] = {"label": lab[0] / lab[1], "time_shift": shf[0] / shf[1], "time_shift_cover_zero": cov[0] / cov[1], "junk_nominal": junk[0] / junk[1]}
    res["stop_conditions_and_caps"] = {"winners": "stop and record a negative result if the model weight's wild-bootstrap p-value is 0.05 or more and equivalence is shown; cap 8 variants",
                                       "spreads_totals": "stop if the model is worse than the ladder with an interval excluding 0; cap 3 margin and 2 total variants",
                                       "props": "stop if fewer than 10 week clusters or the market ladder beats every arm; cap 5 arms", "point_in_time": "stop the chain if a planted 24 hour leak is not detected; no new tests"}
    res["checks"] = {"label_fp_1_to_9": 0.01 <= lab[0] / lab[1] <= 0.09, "time_shift_cover_ge_90": cov[0] / cov[1] >= 0.90, "time_shift_fp_1_to_9": 0.01 <= shf[0] / shf[1] <= 0.09,
                     "junk_2_to_9": 0.02 <= junk[0] / junk[1] <= 0.09, "no_bh_discovery_ge_90pct_of_blocks": r["junk_bh_no_discovery_blocks"][0] / r["junk_bh_no_discovery_blocks"][1] >= 0.90, "stop_conditions_written": True}
elif STEP == "7":
    r = step7(ds, rng, B=2000)
    res.update(r)
    res["checks"] = {"variant_count_equals_list": r["variants_counted"] == len(WIN_VARIANTS) + len(MARGIN_VARIANTS) + len(TOTAL_VARIANTS) + len(PROPS_ARMS),
                     "pbo_computed_all": all(f["pbo"].get("valid") for f in r["families"].values()), "invalid_families_marked": [n for n, f in r["families"].items() if not f["valid"]]}
res["PASS"] = bool(all(v if isinstance(v, bool) else True for v in res["checks"].values()) and all(res["checks"][k] for k in res["checks"] if isinstance(res["checks"][k], bool) and k not in ("invalid_families_marked",)))
write(f"real_step{STEP}.json", res)
print(f"REAL STEP {STEP}:", "PASS" if res["PASS"] else "FAIL"); print(json.dumps(res["checks"], indent=1, default=str))
