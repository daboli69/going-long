"""Price-quality audit of the Kalshi data behind the 2025 exploratory sample. Descriptive only (not a protocol step)."""
import glob
from common import *

res = header("price_quality")
hist = pd.read_parquet(HW / "kalshi_history.parquet")
hist = hist[hist.gid.str[:4] == "2025"].copy()
hist["spread"] = hist.ask - hist.bid

# ---- A: winner candles, all hours and at the three cutoffs
res["winner_candles_all_hours"] = {
    "candles": int(len(hist)), "games": int(hist.gid.nunique()),
    "share_zero_volume": float((hist.volume == 0).mean()), "share_spread_gt_0.05": float((hist.spread > 0.05).mean()),
    "spread_quantiles": {str(q): float(hist.spread.quantile(q)) for q in (0.5, 0.75, 0.9, 0.99)}}
ko = hist.groupby("gid").kickoff_utc.first()
W = winners_frame()
W = W[W.season == 2025]
dec = W.set_index("gid").decision_utc
rows = []
for gid, d in hist.groupby("gid"):
    if gid not in dec.index:
        continue
    for name, cut in (("decision", pd.Timestamp(dec[gid])), ("t90", ko[gid] - LEAD), ("close", ko[gid])):
        x = d[(d.ts <= min(cut, ko[gid])) & d.mid.notna()]
        if x.empty:
            continue
        last = x.sort_values("ts").groupby("side").tail(1).set_index("side")
        if not {"home", "away"} <= set(last.index):
            continue
        traded = x[x.volume > 0]
        stale = (cut - traded.ts.max()).total_seconds() / 3600 if len(traded) else np.nan
        rows.append({"gid": gid, "cutoff": name, "vol_home": last.at["home", "volume"], "vol_away": last.at["away", "volume"],
                     "spr_home": last.at["home", "spread"], "spr_away": last.at["away", "spread"], "hours_since_any_traded_candle": stale,
                     "overround": float(last.at["home", "mid"] + last.at["away", "mid"] - 1)})
Q = pd.DataFrame(rows)
res["winner_prices_at_cutoffs"] = {}
for name, g in Q.groupby("cutoff"):
    res["winner_prices_at_cutoffs"][name] = {
        "games": int(len(g)), "share_zero_volume_both_sides": float(((g.vol_home == 0) & (g.vol_away == 0)).mean()),
        "share_zero_volume_either_side": float(((g.vol_home == 0) | (g.vol_away == 0)).mean()),
        "share_spread_gt_0.05_either_side": float(((g.spr_home > 0.05) | (g.spr_away > 0.05)).mean()),
        "spread_median": float(np.nanmedian(np.r_[g.spr_home, g.spr_away])),
        "hours_since_traded_candle_quantiles": {str(q): float(g.hours_since_any_traded_candle.quantile(q)) for q in (0.5, 0.75, 0.9)},
        "share_no_traded_candle_ever_before_cutoff": float(g.hours_since_any_traded_candle.isna().mean()),
        "overround_quantiles": {str(q): float(g.overround.quantile(q)) for q in (0.05, 0.5, 0.95)}}

# ---- B: ladder quotes (spread, total) at T-90
q = pd.read_parquet(PK / "quotes.parquet")
q = q[(q.season == 2025) & q.series.isin(["KXNFLSPREAD", "KXNFLTOTAL"]) & q.mid90.notna()]
sp = q.ask90 - q.bid90
res["ladder_quotes_t90"] = {"thresholds_with_mid": int(len(q)), "share_liquid90_flag": float(q.liquid90.astype(bool).mean()), "share_zero_24h_volume": float((q.vol2490 == 0).mean()),
                            "spread_quantiles": {str(a): float(sp.quantile(a)) for a in (0.5, 0.75, 0.9)}, "share_spread_gt_0.05": float((sp > 0.05).mean())}

# ---- C: trade archive coverage and a trade-based price against the candle mid
allq = pd.read_parquet(PK / "quotes.parquet")
allq = allq[(allq.season == 2025) & allq.mid90.notna()]
files = {Path(f).stem: f for f in glob.glob(str(PK / "trades" / "*.json"))}
have = allq.ticker.isin(files.keys())
res["trade_archive"] = {"trade_files_total": len(files), "tickers_2025_with_candle_mid90": int(allq.ticker.nunique()), "share_with_trade_file": float(have.mean())}
diffs, n_trades = [], []
for r in allq[have].itertuples(index=False):
    tr = json.load(open(files[r.ticker]))
    if not tr:
        continue
    t = pd.DataFrame(tr)
    t["ts"] = pd.to_datetime(t.created_time, utc=True)
    t["p"] = t.yes_price_dollars.astype(float)
    t["c"] = t.count_fp.astype(float)
    P = pd.Timestamp(r.kickoff) - LEAD
    w = t[(t.ts <= P) & (t.ts > P - pd.Timedelta(hours=3))]
    n_trades.append(len(w))
    if len(w) and w.c.sum() > 0:
        diffs.append({"ticker": r.ticker, "vwap": float((w.p * w.c).sum() / w.c.sum()), "mid90": float(r.mid90), "n": len(w)})
D = pd.DataFrame(diffs)
res["trade_vwap_vs_candle_mid"] = {"tickers_with_file": int(have.sum()), "tickers_with_a_trade_in_3h_before_t90": int(len(D)),
                                    "median_trades_in_window_given_any": float(D.n.median()) if len(D) else None,
                                    "median_abs_difference": float((D.vwap - D.mid90).abs().median()) if len(D) else None,
                                    "p90_abs_difference": float((D.vwap - D.mid90).abs().quantile(0.9)) if len(D) else None,
                                    "correlation": float(np.corrcoef(D.vwap, D.mid90)[0, 1]) if len(D) > 2 else None,
                                    "note": "winner markets (KXNFLGAME) have no trade files; trade-based prices exist only for spread, total and prop tickers"}

# ---- D: dense archives
dense = {}
for kind in ("dense_books", "dense_trades"):
    fs = sorted(glob.glob(str(ROOT / "data/raw/archive" / kind / "*.json")))
    dense[kind] = {"files": len(fs), "snapshots_times_utc": [json.load(open(f)).get("archived_at") for f in fs]}
res["dense_archives"] = dense
res["conclusion_inputs"] = "see values above; no pass or fail attached to this audit"
write("price_quality.json", res)
print(json.dumps({k: v for k, v in res.items() if k not in ("step", "git_head", "protocol_sha256")}, indent=1, default=float)[:6000])
