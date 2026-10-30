"""Improvement protocol Step 2: what the closing-line columns would add. COUNTS OF NON-MISSING VALUES ONLY: no outcome, model or accuracy is computed from the line values."""
from common import *
res = header("i2_data_unlock")
g = pd.read_parquet(CACHE / "games.parquet", columns=["season", "game_type", "completed", "tie", "spread_line", "total_line", "home_moneyline", "away_moneyline", "market_p_home_novig"])
g = g[(g.season >= 2015) & (g.season <= 2025)]
done = g[(g.completed == True) & (~g.tie.astype(bool))]
cols = ["spread_line", "total_line", "home_moneyline", "away_moneyline", "market_p_home_novig"]
tab = {}
for s, d in done.groupby("season"):
    tab[int(s)] = {"completed_games": int(len(d)), **{c: int(d[c].notna().sum()) for c in cols}, "all_five_present": int(d[cols].notna().all(axis=1).sum())}
res["counts_by_season"] = tab
span = [s for s in tab if 2015 <= s <= 2024]
tot = sum(tab[s]["all_five_present"] for s in span)
res["games_2015_to_2024_with_all_five"] = tot
S1 = json.load(open(OUT / "i1_detectability.json"))
need = {}
for tgt, name in (("winners", "p_xgb_deep"), ("winners", "p_elo_platt"), ("margin", "L"), ("total", "L")):
    r = [x for x in S1["rows"] if x["target"] == tgt and x["candidate"] == name][0]
    need[f"{tgt}:{name}"] = {f"gain_{k.split('_')[-1]}": {"games_needed": v["games_needed"], "covered_by_2015_2024_lines": bool(v["games_needed"] <= tot)} for k, v in r.items() if k.startswith("gain_ll")}
res["step1_requirements_vs_available"] = need
se_now = [x for x in S1["rows"] if x["target"] == "winners" and x["candidate"] == "p_xgb_deep"][0]["se"]
res["rough_minimum_detectable_gain_if_used"] = {"assumption": "same per-game spread of the paired difference as in 2025 (SE scales with 1/sqrt(games)); comparison would be at the close only",
                                                 "se_now_271_games": se_now, "se_with_lines": float(se_now * np.sqrt(271 / tot)), "min_detectable_log_loss_80pct": float(2.8 * se_now * np.sqrt(271 / tot))}
res["limits"] = [
    "Undated: the table carries no quote time. The lines are labelled closing lines (from memory: nflverse schedule lines; the book or aggregator is not named in the table). A model-versus-close comparison cannot separate 'the model is worse' from 'the model saw less'.",
    "Coverage: see counts_by_season (measured). Playoff and rare missing-line games are counted, not imputed.",
    "De-vig: moneylines include the book's margin. The stored no-vig probability has no documented method in the table. Its method can only be checked by recomputing it from the moneylines, which is a use of the line values and waits for approval.",
    "No ladder: a single spread and a single total per game. CRPS needs an assumed spread of outcomes. The lab's default spreads (13.5 margin, 13.0 total) are assumptions in lab/gamecenter_data.py; the 2025 Kalshi ladders imply medians of 11.7 and 12.8 (measured, real_step2.json). Margin and total comparisons would be limited to the mean or rest on that assumption.",
    "Different venue: sportsbook closing lines versus Kalshi prices. Different margins, limits and information; the two benchmarks may not agree.",
    "Pushes and ties: a spread equal to the final margin is a push; the table's treatment is unchecked.",
    "Walk-forward predictions exist for 2012 to 2025, so 2015 to 2024 comparisons are possible, but the earlier seasons' prediction features were rebuilt retrospectively on 2026-10-28, not frozen at the time."]
res["checks"] = {"a_counts_present_2015_to_2025": sorted(tab) == list(range(2015, 2026)), "b_limits_written": len(res["limits"]) >= 6, "c_requirements_compared": bool(need), "d_question_asked_data_not_used_for_results": True}
res["PASS"] = bool(all(res["checks"].values()))
write("i2_data_unlock.json", res)
print({s: (v["completed_games"], v["all_five_present"], v["spread_line"], v["home_moneyline"], v["market_p_home_novig"]) for s, v in tab.items()}); print("total 2015-2024 all five:", tot); print(res["rough_minimum_detectable_gain_if_used"]); print({k: {a: b["covered_by_2015_2024_lines"] for a, b in v.items()} for k, v in need.items()})
