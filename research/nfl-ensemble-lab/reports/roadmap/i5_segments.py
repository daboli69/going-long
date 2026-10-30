"""Improvement protocol Step 5: where does the model depart from the market, and is the market slower there? 2025 sample, descriptive only."""
from steps import *

res = header("i5_segments")
VAR = "p_xgb_v1"
ds = real_dataset(2025)
W = ds["winners"].dropna(subset=["p_dec", "p_t90", "p_close"]).reset_index(drop=True)
g = pd.read_parquet(CACHE / "games.parquet", columns=["game_id", "roof", "div_game"]).rename(columns={"game_id": "gid"})
f = pd.read_parquet(HW / "features.parquet", columns=["gid", "qb_change_home", "qb_change_away", "rest_home", "rest_away"])
W = W.merge(g, on="gid", how="left").merge(f, on="gid", how="left")
# substitutes (recorded in the output): qb_change_* in features.parquet is zero in every 2025 row and injury_rows_pregame.parquet has no 2025 rows
FIX = {"LA": "LAR", "WSH": "WAS", "JAC": "JAX"}
fx = lambda t: FIX.get(t, t)
gm = pd.read_parquet(CACHE / "games.parquet", columns=["game_id", "season", "kickoff_utc", "home_team", "away_team", "home_qb_id", "away_qb_id"])
gm = gm[gm.season.isin([2024, 2025])]
long = pd.concat([gm.rename(columns={"home_team": "team", "home_qb_id": "qb"})[["game_id", "season", "kickoff_utc", "team", "qb"]], gm.rename(columns={"away_team": "team", "away_qb_id": "qb"})[["game_id", "season", "kickoff_utc", "team", "qb"]]]).sort_values(["team", "kickoff_utc"])
long["qb_change"] = long.groupby("team").qb.shift(1).ne(long.qb) & long.groupby("team").qb.shift(1).notna()
qbc = long.groupby("game_id").qb_change.any()
W["qb_change_substitute"] = W.gid.map(qbc).fillna(False).astype(bool)
inj = pd.read_parquet(CACHE / "recovered_injury_rows.parquet", columns=["season", "week", "team", "report_status", "available_at"])
inj = inj[(inj.season == 2025) & inj.report_status.isin(["Out", "Doubtful"]) & inj.available_at.notna()].copy()
inj["available_at"] = pd.to_datetime(inj.available_at, utc=True); inj["team"] = inj.team.map(fx)
dec = W.set_index("gid").decision_utc
def heavy(r):
    n = 0
    for team in (fx(r.gid.split("_")[2]), fx(r.gid.split("_")[3])):
        d = inj[(inj.week == r.week) & (inj.team == team) & (inj.available_at < pd.Timestamp(dec[r.gid]))]
        n = max(n, len(d))
    return n
W["max_out_doubtful_one_team"] = [heavy(r) for r in W.itertuples()]
res["missing_values"] = {c: int(W[c].isna().sum()) for c in ("roof", "div_game", "rest_home", "rest_away")}
res["substitutions"] = ["qb_change: starting quarterback id differs from the team's previous game (games table, 2024 to 2025). It is a hindsight flag: the starter is not known at the decision time, so it shows where departures concentrate, not where the model could act.", "injuries: recovered_injury_rows.parquet (2025 rows) because injury_rows_pregame.parquet has no 2025 rows; the segment is a team with 3 or more players listed Out or Doubtful before the decision time"]
seg = {
    "qb_change": W.qb_change_substitute.to_numpy(),
    "short_rest": (np.minimum(W.rest_home.fillna(7), W.rest_away.fillna(7)) < 7).to_numpy(),
    "roof_closed_or_dome": W.roof.isin(["dome", "closed"]).to_numpy(),
    "divisional": (W.div_game.fillna(0) == 1).to_numpy(),
    "heavy_injuries_3plus_one_team": (W.max_out_doubtful_one_team >= 3).to_numpy()}
y = W.y_home_win.to_numpy(float); p90, pd_, pc, q = W.p_t90.to_numpy(float), W.p_dec.to_numpy(float), W.p_close.to_numpy(float), W[VAR].to_numpy(float)
metrics = {"departure_abs_model_minus_market": np.abs(q - p90), "model_minus_market_log_loss": ll(q, y) - ll(p90, y), "news_term_market_decision_minus_close": ll(pd_, y) - ll(pc, y)}
codes, k = codes_of(W)


def diff_in_means(d, ind):
    if ind.sum() == 0 or ind.all():
        return {"difference_segment_minus_rest": None, "lo": None, "hi": None, "p": 1.0}
    X = np.column_stack([np.ones(len(d)), ind.astype(float)])
    b = np.linalg.lstsq(X, d, rcond=None)[0]; r = d - X @ b; Hi = np.linalg.inv(X.T @ X)
    sc = np.stack([np.bincount(codes, weights=X[:, j] * r, minlength=k) for j in range(2)], 1)
    se = np.sqrt(np.diag(k / (k - 1) * Hi @ (sc.T @ sc) @ Hi))[1]
    c = tdist.ppf(0.975, k - 1)
    return {"difference_segment_minus_rest": float(b[1]), "lo": float(b[1] - c * se), "hi": float(b[1] + c * se), "p": float(2 * tdist.sf(abs(b[1] / se), k - 1))}


def holm(p):
    p = np.asarray(p); o = np.argsort(p); m = len(p); adj = np.empty(m); run = 0.0
    for r_, i in enumerate(o):
        run = max(run, (m - r_) * p[i]); adj[i] = min(run, 1.0)
    return adj


out = {}
for name, ind in seg.items():
    row = {"games_in_segment": int(ind.sum()), "games_rest": int((~ind).sum()), "weeks_in_segment": int(len(set(W.wk[ind]))), "flag_under_30_games": bool(ind.sum() < 30), "metrics": {}}
    for m_name, d in metrics.items():
        a = codes_of(W[ind])
        seg_c = cl_mean(d[ind], a[0], a[1]) if ind.sum() >= 5 and a[1] >= 2 else None
        b_ = codes_of(W[~ind]); rest_c = cl_mean(d[~ind], b_[0], b_[1])
        row["metrics"][m_name] = {"segment": seg_c, "rest": rest_c, **diff_in_means(d, ind)}
    out[name] = row
for m_name in metrics:
    adj = holm([out[s]["metrics"][m_name]["p"] for s in out])
    for s, a_ in zip(out, adj):
        out[s]["metrics"][m_name]["p_holm"] = float(a_)
res["variant"] = VAR; res["sample"] = f"2025: {len(W)} games with prices at all three cutoffs, {k} weeks"; res["segments"] = out
res["tests_counted"] = {"segments": len(seg), "metrics": len(metrics), "tests": len(seg) * len(metrics), "holm_family_size_per_metric": len(seg)}
res["checks"] = {"all_five_segments_computed": len(out) == 5, "intervals_present": all(out[s]["metrics"][m]["lo"] is not None for s in out for m in metrics), "tests_counted_recorded": True}
res["PASS"] = bool(all(res["checks"].values()))
write("i5_segments.json", res)
print("I5", "PASS" if res["PASS"] else "FAIL", res["missing_values"])
for s, r in out.items():
    print(f"{s:30s} n={r['games_in_segment']:3d} weeks={r['weeks_in_segment']:2d} " + " | ".join(f"{m.split('_')[0]}: diff {v['difference_segment_minus_rest']:+.4f} [{v['lo']:+.4f},{v['hi']:+.4f}] holm {v['p_holm']:.2f}" for m, v in r["metrics"].items()))
