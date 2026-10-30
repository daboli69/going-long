"""Label audit for the 2025 sample: reconcile outcomes and prop labels across the sources that exist locally. Lists every disagreement."""
from common import *
res = header("label_audit")
FIX = {"LA": "LAR", "WSH": "WAS", "JAC": "JAX", "OAK": "LV", "SD": "LAC", "STL": "LAR"}
fx = lambda t: FIX.get(t, t)

# 1. nflverse games table vs ESPN events vs the lab's walk-forward labels
g = pd.read_parquet(CACHE / "games.parquet")
g = g[(g.season == 2025) & (g.completed == True)].copy()
g["home"] = g.home_team.map(fx); g["away"] = g.away_team.map(fx); g["day"] = pd.to_datetime(g.kickoff_utc, utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
ev = pd.DataFrame(json.load(open(HW / "espn_events_2025.json")))
ev = ev[ev.completed == True].copy()
ev["home"] = ev.home.map(fx); ev["away"] = ev.away.map(fx); ev["day"] = pd.to_datetime(ev.kickoff, utc=True).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
m = g.merge(ev[["home", "away", "day", "home_score", "away_score"]], on=["home", "away", "day"], how="left", suffixes=("", "_espn"))
unmatched = m[m.home_score_espn.isna()]
mm = m.dropna(subset=["home_score_espn"])
score_diff = mm[(mm.home_score != mm.home_score_espn) | (mm.away_score != mm.away_score_espn)]
res["nflverse_vs_espn_scores"] = {"nflverse_games": int(len(g)), "matched_to_espn": int(len(mm)), "unmatched": unmatched[["game_id", "home", "away", "day"]].to_dict("records"),
                                  "score_disagreements": score_diff[["game_id", "home_score", "home_score_espn", "away_score", "away_score_espn"]].to_dict("records")}
wf = pd.read_parquet(HW / "forecast_wf.parquet"); wf = wf[wf.season == 2025]
w2 = pd.read_parquet(HW / "walk_forward.parquet"); w2 = w2[w2.season == 2025]
gg = g.set_index("game_id")
bad_margin = [(r.gid, r.y_m, gg.at[r.gid, "margin"]) for r in wf.itertuples() if r.gid in gg.index and r.played and r.y_m != gg.at[r.gid, "margin"]]
bad_total = [(r.gid, r.y_t, gg.at[r.gid, "home_score"] + gg.at[r.gid, "away_score"]) for r in wf.itertuples() if r.gid in gg.index and r.played and r.y_t != gg.at[r.gid, "home_score"] + gg.at[r.gid, "away_score"]]
bad_win = [(r.gid, r.y_home_win, gg.at[r.gid, "home_win"]) for r in w2.itertuples() if r.gid in gg.index and not gg.at[r.gid, "tie"] and r.y_home_win != gg.at[r.gid, "home_win"]]
res["lab_labels_vs_nflverse"] = {"forecast_wf_margin_checked": int(wf.played.sum()), "margin_disagreements": bad_margin, "total_disagreements": bad_total, "walk_forward_winner_checked": int(len(w2)), "winner_disagreements": bad_win,
                                 "missing_from_games_table": [x for x in w2.gid if x not in gg.index][:20]}

# 2. exchange-side check of winners: price after the game is over should sit near 0 or 1 on the winning side
h = pd.read_parquet(HW / "kalshi_history.parquet"); h = h[h.gid.str[:4] == "2025"]
fin = h[h.ts >= h.kickoff_utc + pd.Timedelta(hours=5)].sort_values("ts").groupby(["gid", "side"]).tail(1)
fin = fin.pivot(index="gid", columns="side", values="mid").dropna()
W = winners_frame(); W = W[W.season == 2025].set_index("gid")
rows = []
for gid, r in fin.iterrows():
    if gid in W.index:
        implied = 1.0 if r.home > 0.9 and r.away < 0.1 else (0.0 if r.home < 0.1 and r.away > 0.9 else np.nan)
        rows.append((gid, implied, W.at[gid, "y_home_win"], float(r.home), float(r.away)))
F = pd.DataFrame(rows, columns=["gid", "implied", "label", "home_mid", "away_mid"])
res["kalshi_post_game_price_vs_label"] = {"games_checked": int(len(F)), "price_not_decisive_yet": int(F.implied.isna().sum()),
                                           "disagreements": F[(F.implied.notna()) & (F.implied != F.label)].to_dict("records"),
                                           "note": "a proxy for settlement (final candle at least 5 h after kickoff), not the settlement record"}

# 3. prop labels: scored thresholds vs Kalshi's own result field
T = pd.read_parquet(PK / "scored_thresholds.parquet"); T = T[T.season == 2025]
q = pd.read_parquet(PK / "quotes.parquet"); q = q[(q.season == 2025) & q.result.isin(["yes", "no"])]
J = T.merge(q[["gid", "pid", "stat", "threshold", "result"]].drop_duplicates(["gid", "pid", "stat", "threshold"]), left_on=["gid", "pid", "stat", "k"], right_on=["gid", "pid", "stat", "threshold"], how="left")
chk = J.dropna(subset=["result"])
dis = chk[(chk.result == "yes").astype(int) != chk.y_home_win]
res["prop_labels_vs_kalshi_result"] = {"thresholds": int(len(T)), "matched_to_a_kalshi_result": int(len(chk)), "unmatched": int(J.result.isna().sum()),
                                        "disagreements": int(len(dis)), "disagreement_rate": float(len(dis) / max(len(chk), 1)), "examples": dis[["gid", "pid", "stat", "k", "y_home_win", "result"]].head(10).to_dict("records")}
res["not_done"] = ["prop labels against official play-by-play: lab.props actual_stats needs the nflverse play-by-play loader, which may download data; not run to keep this local",
                   "Kalshi's own settlement record for winner markets is not stored locally; the post-game price is a proxy"]
n_labels = len(g) + len(w2) * 0 + len(chk)
n_bad = len(score_diff) + len(bad_margin) + len(bad_total) + len(bad_win) + len(res["kalshi_post_game_price_vs_label"]["disagreements"]) + len(dis)
res["total_disagreements"] = int(n_bad)
res["disagreement_share_of_checked_labels"] = float(n_bad / max(n_labels, 1))
res["PASS_condition_le_0.5pct"] = bool(res["disagreement_share_of_checked_labels"] <= 0.005)
write("label_audit.json", res)
print(json.dumps({k: (v if not isinstance(v, dict) else {a: (b if not isinstance(b, list) else f"{len(b)} items") for a, b in v.items()}) for k, v in res.items() if k not in ("step", "git_head", "protocol_sha256")}, indent=1, default=str)[:3500])
