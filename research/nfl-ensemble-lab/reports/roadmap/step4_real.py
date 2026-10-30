"""Step 4 on real data: the lab's perturbation audit, planted late-cutoff leaks, planted Kalshi-candle leak, and a status for each input.
Gate: rehearsal step 4 must have passed. PROTOCOL.md Step 4 pass condition; GOVERNANCE.md."""
import sys
from common import *
sys.path.insert(0, str(ROOT))
from lab import homewin_deep as h, homewin_eval as ev, kalshi as K

gate("rehearsal_step4.json")
res = header("step4_real")
data, _ = h.load_all(refresh=False)
pm = h.qb_prior_mean(data.qb_games[data.qb_games["season"] <= 2011])

# (a) the lab's existing perturbation audit with its own negative control
audit = ev.leakage_check(data)  # raises DataCheckError on a leak
res["lab_perturbation_audit"] = {"weeks": {k: v for k, v in audit.items() if k != "negative_control_detected"}, "negative_control_detected": bool(audit["negative_control_detected"])}

# (b) planted leaks: build week features with a cutoff late by delta, on data vs data corrupted after the true cutoff
season, week = 2025, 10
T = h.week_cutoff(data, season, week)
bad = h.perturb_after(data, T, season, week)
base = h.week_features(data, season, week, prior_mean=pm)
num = base.select_dtypes("number").columns
clean_again = h.week_features(bad, season, week, prior_mean=pm)
res["clean_run_unchanged"] = bool(np.allclose(base[num].to_numpy(float), clean_again[num].to_numpy(float), equal_nan=True))
res["planted_late_cutoff"] = {}
for name, delta in (("1h", pd.Timedelta(hours=1)), ("6h", pd.Timedelta(hours=6)), ("24h", pd.Timedelta(hours=24)), ("72h", pd.Timedelta(hours=72)), ("8d", pd.Timedelta(days=8))):
    a = h.week_features(data, season, week, cutoff=T + delta, prior_mean=pm)
    b = h.week_features(bad, season, week, cutoff=T + delta, prior_mean=pm)
    moved = ~np.isclose(a[num].to_numpy(float), b[num].to_numpy(float), equal_nan=True)
    res["planted_late_cutoff"][name] = {"detected": bool(moved.any()), "columns_that_moved": [c for c, m in zip(num, moved.any(0)) if m]}

# (c) planted leak in the Kalshi hourly candles: corrupt candles stamped after T, then read the price at T and at T plus 1 hour
hist = pd.read_parquet(HW / "kalshi_history.parquet")
hist = hist[(hist.gid.str[:7] == "2025_10")].copy()
rng = np.random.default_rng(3)
bad_h = hist.copy()
mask = bad_h.ts > T
bad_h.loc[mask, "mid"] = rng.uniform(0.05, 0.95, int(mask.sum()))
same_at_T = changed_at_T1 = n = 0
for gid, d in hist.groupby("gid"):
    ko = d.kickoff_utc.iloc[0]
    a0 = K.probability(d, gid, T, ko)["p_home"]; b0 = K.probability(bad_h[bad_h.gid == gid], gid, T, ko)["p_home"]
    a1 = K.probability(d, gid, T + pd.Timedelta(hours=1), ko)["p_home"]; b1 = K.probability(bad_h[bad_h.gid == gid], gid, T + pd.Timedelta(hours=1), ko)["p_home"]
    if np.isnan(a0) or np.isnan(b0):
        continue
    n += 1; same_at_T += (a0 == b0); changed_at_T1 += (a1 != b1)
res["planted_candle_leak"] = {"games": n, "price_unchanged_at_true_cutoff": int(same_at_T), "price_changed_with_cutoff_plus_1h": int(changed_at_T1)}

# (d) status per input
res["input_status"] = {
    "Elo": "tested clean for data flow: scores after the cutoff were corrupted and the Elo-based features did not move (lab perturbation audit, four weeks plus 2025 week 10). Not tested: whether the Elo constants were tuned on outcomes that include later games.",
    "EPA aggregates": "tested clean for data flow: play aggregates after the cutoff were replaced with noise and the EPA edges did not move. Not tested: the play-value model behind EPA is trained on many seasons at once (from memory, small but real).",
    "ESPN FPI": "not testable here: FPI is fetched live at freeze time (homewin_eval.fpi_projection) and no historical snapshots exist, so a past-week value cannot be checked for revision. Treat any FPI value not archived at the time as unusable for backtests.",
    "FantasyPoints files": "not tested in this protocol: they feed the props pipeline (FPDS), not the winner, spread or total features this audit covers. The adapter note says files describe the previous week; that week mapping needs its own file-level check.",
    "hourly Kalshi candles": "tested: candle ts is Kalshi's end_period_ts (lab/kalshi.py lines 155 to 167), corrupting candles after the cutoff left the price at the cutoff unchanged, and corrupting up to cutoff plus 1 hour changed it (planted_candle_leak).",
    "ESPN injury snapshots": "tested in part: the lab's injury table (available_at) was corrupted after the cutoff without moving features. The raw ESPN snapshot files under data/raw/archive were not separately perturbed; their file names carry a UTC time but a later snapshot can rewrite statuses, so only the snapshot at or before the cutoff may be used."}
req = res["planted_late_cutoff"]
res["checks"] = {"lab_audit_passed": True, "negative_control_fired": res["lab_perturbation_audit"]["negative_control_detected"], "clean_run_unchanged": res["clean_run_unchanged"],
                 "planted_24h_72h_8d_detected": all(req[k]["detected"] for k in ("24h", "72h", "8d")),
                 "candle_leak_detected": res["planted_candle_leak"]["price_changed_with_cutoff_plus_1h"] > 0 and res["planted_candle_leak"]["price_unchanged_at_true_cutoff"] == res["planted_candle_leak"]["games"],
                 "every_input_has_a_status": len(res["input_status"]) == 6}
res["PASS"] = bool(all(res["checks"].values()))
write("step4_real.json", res)
print("PASS" if res["PASS"] else "FAIL"); print(json.dumps(res["checks"], indent=1)); print({k: v["detected"] for k, v in req.items()}); print(res["planted_candle_leak"])
