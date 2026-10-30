"""Improvement protocol Step 1: detectability budget (PROTOCOL2.md). Reads saved outputs only."""
from common import *
from scipy.stats import norm, t as tdist

res = header("i1_detectability")
S3 = json.load(open(OUT / "real_step3.json"))
S5 = json.load(open(OUT / "real_step5.json"))
S2 = json.load(open(OUT / "real_step2.json"))
Z = 1.96 + 0.84
GAINS_LL = [0.005, 0.01, 0.02]
MKT_LL = S2["winners"]["realized_log_loss"]
MKT = {"winners": MKT_LL, "margin": S2["ladders"]["margin"]["normal_crps_realized"], "total": S2["ladders"]["total"]["normal_crps_realized"], "props": S2["props"]["threshold_score_realized"]}
GAMES_PER_SEASON = 272
PROPS_LADDERS_PER_SEASON = 150 * 18   # 2026 rate: 1,051 scored ladders in 7 weeks (scored_ladders.parquet)
KALSHI_SEASONS_LIMIT = 3

rows = []


def add(target, name, source, se, n_now, per_season, unit, score):
    r = {"target": target, "candidate": name, "se_source": source, "se": float(se), "n_now": int(n_now), "per_season": per_season}
    for g in GAINS_LL:
        g_unit = g / MKT_LL * score                      # same relative gain in the target's own unit
        n_req = n_now * (Z * se / g_unit) ** 2
        r[f"gain_ll_{g}"] = {"gain_in_unit": float(g_unit), "unit": unit, "games_needed": float(n_req), "seasons_needed": float(n_req / per_season),
                              "testable_on_kalshi_alone": bool(n_req / per_season <= KALSHI_SEASONS_LIMIT)}
    rows.append(r)


for v, d in S3["variants"].items():
    add("winners", v, "real_step3 vs market at decision time", d["vs_market_at_decision"]["se"], S3["n_complete"], GAMES_PER_SEASON, "log loss", 1.0 * MKT_LL)
    add("winners", v + " (close)", "real_step3 vs market at close", d["vs_market_at_close"]["se"], S3["n_complete"], GAMES_PER_SEASON, "log loss", 1.0 * MKT_LL)
for t_, vs in S3["ladders_at_t90_only"].items():
    for v, d in vs.items():
        add(t_, v, "real_step3 vs ladder at T-90", d["se"], d["n"], GAMES_PER_SEASON, "CRPS points", MKT[t_])
for a, d in S5["props"].items():
    lo, hi = d["equivalence"]["interval90"]
    k = S2["props"]["clusters"]
    se = (hi - lo) / (2 * tdist.ppf(0.95, k - 1))
    add("props", a, "real_step5 90% interval converted to SE", se, S2["props"]["n"], PROPS_LADDERS_PER_SEASON, "threshold score", MKT["props"])
res["rows"] = rows
res["settings"] = {"z_two_sided_5pct_80pct_power": Z, "games_per_season": GAMES_PER_SEASON, "props_ladders_per_season": PROPS_LADDERS_PER_SEASON,
                   "kalshi_alone_limit_seasons": KALSHI_SEASONS_LIMIT, "market_scores_2025": MKT,
                   "assumption": "CRPS and threshold-score gains are the same relative improvement as the log-loss gains (gain / 0.6121); a different mapping changes these rows"}

# formula check against the Step 2 power simulations (implied SE should be stable across grid points)
chk = {}
for k_ in ("winners_theta0.6", "margin_theta0.3", "total_theta0.3", "props_theta0.3"):
    pts = [(c["expected_gain"], c["power_one_sided_2.5pct"]) for c in S2["power"][k_]["curve"] if 0.2 <= c["power_one_sided_2.5pct"] <= 0.95]
    se_imp = [g / (1.96 + norm.ppf(p)) for g, p in pts if g > 0]
    chk[k_] = {"points_used": len(se_imp), "implied_se": se_imp, "cv": float(np.std(se_imp) / np.mean(se_imp)) if len(se_imp) >= 2 else None}
res["formula_check"] = chk
usable = {k_: v for k_, v in chk.items() if v["cv"] is not None}
res["checks"] = {"a_all_candidates_have_se": len(rows) == len(WIN_V := ["p_elo", "p_xgb_v1", "p_margin", "p_xgb_deep", "p_elo_platt", "p_xgb_v1_platt", "p_margin_platt", "p_xgb_deep_platt"]) * 2 + 3 + 2 + 5,
                 "b_all_gains_present": all(all(f"gain_ll_{g}" in r for g in GAINS_LL) for r in rows), "c_all_classified": all("testable_on_kalshi_alone" in r[f"gain_ll_{GAINS_LL[0]}"] for r in rows),
                 "d_formula_cv_le_0.25": bool(usable) and all(v["cv"] <= 0.25 for v in usable.values()), "d_designs_with_two_or_more_points": sorted(usable)}
res["PASS"] = bool(all(v for k_, v in res["checks"].items() if isinstance(v, bool)))
write("i1_detectability.json", res)
print("I1", "PASS" if res["PASS"] else "FAIL", json.dumps(res["checks"], default=str)); print({k_: (len(v["implied_se"]), v["cv"]) for k_, v in chk.items()})
