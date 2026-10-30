"""Experiments A (venue lag) and B (availability events) and the dense capture tool.
Protocol: docs/MARKET_NEWS_PREREGISTRATION.md (commit 396af66a). All local, read-only, no trading code.

  python scripts/market_news_study.py power      # standard errors / event counts only -> reports/market_news/power.json
  python scripts/market_news_study.py run        # A and B point estimates, placebos
  python scripts/market_news_study.py capture --hours 6 --interval 5    # dense manual capture before kickoffs
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import forecast_core as fc  # noqa: E402
from lab import homewin_deep as h  # noqa: E402
from lab import kalshi as K  # noqa: E402
from lab import props_kalshi as pk  # noqa: E402
from lab.config import CACHE_DIR, LAB_ROOT, RAW_DIR  # noqa: E402
from lab.ingest import normalize_team  # noqa: E402
from lab.market81 import NAME_TO_ABBR, american_to_prob  # noqa: E402

OUT = LAB_ROOT / "reports" / "market_news"
PK = CACHE_DIR / "props_kalshi"
GRID_BACK, HORIZON, NB, SEED = 48, 3, 1000, 0
STALE = pd.Timedelta(hours=24)
HOUR = 3_600_000_000_000


def log(m):
    print(m, flush=True)


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def asof(times_ns: np.ndarray, vals: np.ndarray, t_ns: int, cap_ns: int = int(STALE.value)) -> float:
    i = np.searchsorted(times_ns, t_ns, side="right") - 1
    if i < 0 or t_ns - times_ns[i] > cap_ns:
        return np.nan
    return float(vals[i])


# --------------------------------------------------------------------------- venue series

def going_series(G):
    gq = pd.read_parquet(h.CACHE / "going_quotes.parquet")
    gq = gq[gq["market"].isin(["h2h", "spreads", "totals"]) & gq["quote_time"].notna()].copy()
    g26 = G[G["season"] == 2026]
    idx = {}
    for r in g26.itertuples(index=False):
        idx.setdefault((r.home, r.away), []).append((r.kickoff_utc, r.gid))
    gq["gid"] = [next((gid for ko, gid in idx.get((hm, aw), []) if abs((ko - ct).total_seconds()) < 36 * 3600), None)
                 for hm, aw, ct in zip(gq["home"], gq["away"], gq["commence_time"])]
    gq = gq.dropna(subset=["gid"])
    series = {}   # (gid, target, venue) -> list of (times_ns, values) per book (venue P = one book, O = several)
    for (gid, book, market), d in gq.groupby(["gid", "book", "market"]):
        venue = "P" if book == "pinnacle" else "O"
        if market == "h2h":
            w = d.pivot_table(index="quote_time", columns="side", values="price", aggfunc="last").dropna()
            if not {"home", "away"} <= set(w.columns):
                continue
            ok = (w["home"].abs() >= 100) & (w["away"].abs() >= 100)
            w = w[ok]
            if w.empty:
                continue
            ph, pa = american_to_prob(w["home"].to_numpy()), american_to_prob(w["away"].to_numpy())
            t, v = w.index, logit(ph / (ph + pa))
            target = "winner"
        elif market == "spreads":
            x = d[d["side"] == "home"].dropna(subset=["point"]).drop_duplicates("quote_time").sort_values("quote_time")
            t, v, target = x["quote_time"], -x["point"].to_numpy(float), "spread"
        else:
            x = d[d["side"].str.lower() == "over"].dropna(subset=["point"]).drop_duplicates("quote_time").sort_values("quote_time")
            t, v, target = x["quote_time"], x["point"].to_numpy(float), "total"
        if len(t) == 0:
            continue
        series.setdefault((gid, target, venue), []).append((pd.DatetimeIndex(t).asi8, np.asarray(v, float)))
    return series


def kalshi_ladder_inputs(G):
    q = pd.read_parquet(PK / "quotes.parquet")
    q = q[q["series"].isin(["KXNFLSPREAD", "KXNFLTOTAL"])]
    gm = G.set_index("gid")[["home", "away"]]
    mk = {}
    for r in q.itertuples(index=False):
        if r.gid not in gm.index or pd.isna(r.strike):
            continue
        c = pk.candles(pd.Series({"ticker": r.ticker, "series": r.series, "historical": r.historical, "kickoff": r.kickoff,
                                  "open_time": pd.NaT, "close_time": pd.NaT, "status": "finalized"}))
        if c.empty:
            continue
        if r.series == "KXNFLTOTAL":
            tgt, c0, flip = "total", float(r.strike), False
        elif r.team == gm.at[r.gid, "home"]:
            tgt, c0, flip = "spread", float(r.strike), False
        elif r.team == gm.at[r.gid, "away"]:
            tgt, c0, flip = "spread", -float(r.strike), True
        else:
            continue
        mid = np.where(c["bid"].notna() & c["ask"].notna() & ((c["ask"] - c["bid"]) <= 0.10) & (c["bid"] > 0), (c["bid"] + c["ask"]) / 2, np.nan)
        mid = 1 - mid if flip else mid
        mk.setdefault((r.gid, tgt), []).append((c0, pd.DatetimeIndex(c["ts"]).asi8, mid))
    return mk


def kalshi_value(markets, wprice, t_ns):
    pts = []
    for c0, ts, mid in markets:
        i = np.searchsorted(ts, t_ns, side="right") - 1
        if i >= 0 and t_ns - ts[i] <= 3 * HOUR and not np.isnan(mid[i]):
            pts.append((c0, mid[i]))
    if wprice is not None:
        pw = asof(wprice[0], wprice[1], t_ns, 3 * HOUR)
        if not np.isnan(pw):
            pts.append((0.5, pw))
    if len(pts) < 5:
        return np.nan
    a = np.array(sorted(pts))
    iso = pk.isotonic_survival(a[:, 0], a[:, 1], np.ones(len(a)))
    return pk.median_from_cdf(a[:, 0], 1 - iso)


def build_panel(G):
    going = going_series(G)
    mk = kalshi_ladder_inputs(G)
    hist = pd.read_parquet(h.CACHE / "kalshi_history.parquet")
    wprice = {}
    for gid, d in hist.groupby("gid"):
        w = d.pivot_table(index="ts", columns="side", values="mid", aggfunc="last").sort_index()
        if {"home", "away"} <= set(w.columns):
            w = w.dropna()
            wprice[gid] = (w.index.asi8, logit(w["home"] / (w["home"] + w["away"])).to_numpy())
    gi = G.set_index("gid")
    rows = []
    gids = sorted({g for g, _, _ in going} & set(gi.index))
    for gid in gids:
        ko = gi.at[gid, "kickoff_utc"]
        t0 = (ko - pd.Timedelta(hours=GRID_BACK)).ceil("h")
        grid = pd.date_range(t0, (ko - pd.Timedelta(hours=1)).floor("h"), freq="h")
        for tgt in ("winner", "spread", "total"):
            P = going.get((gid, tgt, "P"))
            O = going.get((gid, tgt, "O"))
            if not P or not O or len(O) < 2:
                continue
            for t in grid:
                tn = t.value
                xP = asof(*P[0], tn)
                xO = np.nanmedian([asof(a, b, tn) for a, b in O]) if O else np.nan
                if tgt == "winner":
                    xK = asof(*wprice[gid], tn, 3 * HOUR) if gid in wprice else np.nan
                else:
                    xK = kalshi_value(mk.get((gid, tgt), []), wprice.get(gid) if tgt == "spread" else None, tn)
                rows.append((gid, tgt, int(gi.at[gid, "season"]), int(gi.at[gid, "week"]), int((ko - t).total_seconds() // 3600), xK, xP, xO))
    df = pd.DataFrame(rows, columns=["gid", "target", "season", "week", "k", "xK", "xP", "xO"])
    return df


# --------------------------------------------------------------------------- Experiment A

def prep(panel, venue):
    """dev and 3-hour change for one venue: panel sorted by game, target, descending k."""
    cols = {"K": ("xK", "xP", "xO"), "P": ("xP", "xK", "xO"), "O": ("xO", "xK", "xP")}[venue]
    p = panel.sort_values(["gid", "target", "k"], ascending=[True, True, False]).copy()
    own, a, b = (p[c] for c in cols)
    p["dev"] = own - (a + b) / 2
    p["dx"] = p.groupby(["gid", "target"])[cols[0]].shift(-HORIZON) - own
    return p.dropna(subset=["dev", "dx"])


def kappa_stats(x, y, game_codes, n_games):
    n = np.bincount(game_codes, minlength=n_games).astype(float)
    sx, sy = np.bincount(game_codes, x, n_games), np.bincount(game_codes, y, n_games)
    sxx, sxy = np.bincount(game_codes, x * x, n_games), np.bincount(game_codes, x * y, n_games)
    return n, sx, sy, sxx, sxy


def slope_from(stats, idx=None):
    n, sx, sy, sxx, sxy = (s if idx is None else s[idx] for s in stats)
    if idx is None:
        N, X, Y, XX, XY = n.sum(), sx.sum(), sy.sum(), sxx.sum(), sxy.sum()
    else:
        N, X, Y, XX, XY = (a.sum(1) for a in (n, sx, sy, sxx, sxy))
    return (N * XY - X * Y) / np.maximum(N * XX - X * X, 1e-12)


def kappa_boot(d, rng, nb=NB):
    codes, uniq = pd.factorize(d["gid"])
    stats = kappa_stats(d["dev"].to_numpy(), d["dx"].to_numpy(), codes, len(uniq))
    est = -float(slope_from(stats))
    idx = rng.integers(0, len(uniq), (nb, len(uniq)))
    boots = -slope_from(stats, idx)
    return est, boots, len(uniq)


def power_a(panel, rng):
    out = {}
    z = norm.ppf(1 - 0.05 / 3 / 2) + norm.ppf(0.8)
    weeks = int(panel[["season", "week"]].drop_duplicates().shape[0])
    for tgt in ("winner", "spread", "total"):
        d = prep(panel[panel["target"] == tgt], "K")
        if len(d) < 50:
            out[tgt] = {"rows": int(len(d))}
            continue
        _, boots, ng = kappa_boot(d, rng)
        se = float(np.std(boots))
        mde = z * se
        out[tgt] = {"rows": int(len(d)), "games": int(ng), "se_kappa_K": se, "mde": mde, "sesoi": 0.10, "available_weeks": weeks,
                    "decidable_now": bool(mde <= 0.10), "N_weeks": int(np.ceil(weeks * (mde / 0.10) ** 2)) if mde > 0.10 else weeks}
    return out


def run_a(panel, rng, gi):
    res = {}
    for tgt in ("winner", "spread", "total"):
        sub = panel[panel["target"] == tgt]
        r = {}
        for venue in ("K", "P", "O"):
            d = prep(sub, venue)
            if len(d) < 50:
                continue
            est, boots, ng = kappa_boot(d, rng)
            lo, hi = np.quantile(boots, [0.05 / 3 / 2, 1 - 0.05 / 3 / 2])
            hl = HORIZON * np.log(0.5) / np.log(1 - est) if 0 < est < 1 else None
            r[venue] = {"kappa": est, "ci": [float(lo), float(hi)], "half_life_hours": hl, "rows": int(len(d)), "games": int(ng)}
        # lead-lag on 1-hour changes
        p = sub.sort_values(["gid", "k"], ascending=[True, False]).copy()
        for v in ("xK", "xP"):
            p["d" + v] = p.groupby("gid")[v].diff()
        ll = {}
        for lag in range(-3, 4):
            q = p.copy()
            q["dP_shift"] = q.groupby("gid")["dxP"].shift(-lag)
            c = q[["dxK", "dP_shift"]].dropna()
            ll[str(lag)] = {"corr": float(c.corr().iloc[0, 1]), "n": int(len(c))} if len(c) > 30 else None
        r["lead_lag_hours_corr_K_with_P_at_lag"] = ll
        # lean / risk-coverage table for Kalshi
        d = prep(sub, "K")
        if len(d):
            sig = float(d["dev"].std())
            tab = []
            for thr in (0, 0.5, 1.0, 1.5, 2.0):
                m = d["dev"].abs() >= thr * sig
                if m.sum() >= 20:
                    conv = -np.sign(d.loc[m, "dev"]) * d.loc[m, "dx"]
                    tab.append({"threshold_sigma": thr, "coverage": float(m.mean()), "n": int(m.sum()), "share_moving_toward_consensus": float((conv > 0).mean()),
                                "mean_signed_convergence": float(conv.mean())})
            r["lean_table_kalshi"] = {"sigma": sig, "rows": tab}
        # placebo: permute dev_K across games within the same hours-to-kickoff slot
        if "K" in r:
            codes, uniq = pd.factorize(d["gid"])
            x, y, kk = d["dev"].to_numpy(), d["dx"].to_numpy(), d["k"].to_numpy()
            real = r["K"]["kappa"]
            plc = []
            for _ in range(200):
                xs = x.copy()
                for kval in np.unique(kk):
                    ix = np.flatnonzero(kk == kval)
                    xs[ix] = x[rng.permutation(ix)]
                plc.append(-float(slope_from(kappa_stats(xs, y, codes, len(uniq)))))
            plc = np.array(plc)
            r["placebo_K"] = {"real": real, "placebo_mean": float(plc.mean()), "placebo_p95": float(np.quantile(plc, 0.95)),
                              "permutation_p": float((1 + (plc >= real).sum()) / 201)}
        if tgt == "winner":
            from sklearn.linear_model import LogisticRegression
            rows = []
            for gid, g in sub.groupby("gid"):
                if not gi.at[gid, "played"] or gi.at[gid, "margin"] == 0:
                    continue
                kk = int(np.ceil(1.5))  # last grid hour at least 90 minutes before kickoff
                row = g[g["k"] >= kk].sort_values("k").head(1)
                if len(row) and row[["xK", "xP"]].notna().all(axis=1).iloc[0]:
                    rows.append((float(gi.at[gid, "margin"] > 0), row["xK"].iloc[0], row["xP"].iloc[0] - row["xK"].iloc[0]))
            if len(rows) > 30:
                a = np.array(rows)
                lr = LogisticRegression(C=1e6, max_iter=1000).fit(a[:, 1:], a[:, 0])
                bs = []
                for _ in range(500):
                    ix = rng.integers(0, len(a), len(a))
                    bs.append(LogisticRegression(C=1e6, max_iter=1000).fit(a[ix, 1:], a[ix, 0]).coef_[0][1])
                r["settlement_pinnacle_gap_coef"] = {"coef": float(lr.coef_[0][1]), "ci95": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))], "games": len(a)}
        res[tgt] = r
    return res


# --------------------------------------------------------------------------- Experiment B

def espn_events(G):
    files = sorted(glob.glob(str(RAW_DIR / "archive" / "espn_injuries_*.json")))
    UN = {"Out", "Doubtful", "Injured Reserve"}
    seen, events = {}, []
    snaps = pd.read_parquet(RAW_DIR / "snap_counts_2026.parquet", columns=["week", "player", "position", "team", "offense_snaps"])
    snaps["team"] = snaps["team"].map(lambda x: normalize_team(x) if isinstance(x, str) else None)
    snaps["key"] = snaps["player"].map(pk._norm_name)
    for f in files:
        c = json.loads(Path(f).read_text(encoding="utf-8"))
        ts = pd.Timestamp(c["timestamp"])
        first = f == files[0]
        for tm in c["injuries"]:
            for e in tm["injuries"]:
                a = e["athlete"]
                team = a.get("team", {}).get("abbreviation") if isinstance(a.get("team"), dict) else None
                try:
                    team = normalize_team(team) if team else NAME_TO_ABBR.get(tm["displayName"])
                except ValueError:
                    team = NAME_TO_ABBR.get(tm["displayName"])
                pos = (a.get("position") or {}).get("abbreviation") if isinstance(a.get("position"), dict) else None
                pid = (e["id"], a.get("displayName"))
                now_un = e["status"] in UN
                was = seen.get(pid, False)
                if now_un and not was and not first and team and pos in ("QB", "RB", "WR"):
                    events.append({"time": ts, "espn_date": e.get("date"), "team": team, "name": a.get("displayName"), "pos": pos, "status": e["status"]})
                seen[pid] = now_un
    ev_ = pd.DataFrame(events)
    if ev_.empty:
        return ev_
    # key player = top season-to-date offense snaps in the position group on that team (games before the event)
    keep = []
    for r in ev_.itertuples(index=False):
        nxt = G[(~G["played"]) & ((G["home"] == r.team) | (G["away"] == r.team)) & (G["kickoff_utc"] > r.time)].sort_values("kickoff_utc")
        if nxt.empty:
            continue
        wk = int(nxt["week"].iloc[0])
        s = snaps[(snaps["team"] == r.team) & (snaps["week"] < wk)]
        grp = {"QB": ["QB"], "RB": ["RB", "FB"], "WR": ["WR"]}[r.pos]
        top = s[s["position"].isin(grp)].groupby("key")["offense_snaps"].sum().sort_values(ascending=False)
        if len(top) and pk._norm_name(r.name) == top.index[0]:
            keep.append({**r._asdict(), "gid": nxt["gid"].iloc[0], "kickoff": nxt["kickoff_utc"].iloc[0], "affected_home": bool(nxt["home"].iloc[0] == r.team)})
    return pd.DataFrame(keep)


def winner_series():
    hist = pd.read_parquet(h.CACHE / "kalshi_history.parquet")
    out = {}
    for gid, d in hist.groupby("gid"):
        w = d.pivot_table(index="ts", columns="side", values="mid", aggfunc="last").sort_index().dropna()
        if {"home", "away"} <= set(w.columns):
            out[gid] = (w.index.asi8, logit(w["home"] / (w["home"] + w["away"])).to_numpy())
    return out


def reaction(ws, gid, t0, affected_home):
    if gid not in ws:
        return np.nan
    a = asof(*ws[gid], t0.floor("h").value, 3 * HOUR)
    b = asof(*ws[gid], (t0.floor("h") + pd.Timedelta(hours=6)).value, 3 * HOUR)
    if np.isnan(a) or np.isnan(b):
        return np.nan
    return (-(b - a)) if affected_home else (b - a)


def run_b(G, rng):
    ev_ = espn_events(G)
    ws = winner_series()
    if ev_.empty:
        return {"events": 0}
    ev_ = ev_[(ev_["kickoff"] - ev_["time"]) >= pd.Timedelta(hours=7)].copy()
    ev_["react"] = [reaction(ws, g, t, ah) for g, t, ah in zip(ev_["gid"], ev_["time"], ev_["affected_home"])]
    out = {"events_total": int(len(ev_)), "events_with_market_data": int(ev_["react"].notna().sum()), "by_type": {}, "weeks_covered": 2,
           "event_rate_per_week": float(len(ev_) / 2)}
    pvals = []
    for pos, g in ev_.dropna(subset=["react"]).groupby("pos"):
        n = len(g)
        up = int((g["react"] > 0).sum())
        sp = float(binomtest(up, n, 0.5, alternative="greater").pvalue) if n else None
        plc = []
        for _ in range(200):
            rr = []
            for r in g.itertuples(index=False):
                lo, hi = r.kickoff - pd.Timedelta(hours=GRID_BACK), r.kickoff - pd.Timedelta(hours=7)
                tt = lo + (hi - lo) * rng.random()
                rr.append(reaction(ws, r.gid, tt, r.affected_home))
            plc.append(np.nanmean(rr))
        plc = np.array(plc)
        obs = float(g["react"].mean())
        out["by_type"][pos] = {"events": int(n), "moved_expected_direction": up, "sign_test_p_one_sided": sp, "mean_signed_reaction_logit": obs,
                               "placebo_mean": float(np.nanmean(plc)), "placebo_p95": float(np.nanquantile(plc, 0.95)),
                               "placebo_p": float((1 + (plc >= obs).sum()) / 201)}
        pvals.append((pos, sp if sp is not None else 1.0))
    # Benjamini-Hochberg across the three types
    pvals.sort(key=lambda x: x[1])
    m = 3
    bh = {pos: bool(p <= 0.05 * (i + 1) / m) for i, (pos, p) in enumerate(pvals)}
    for pos in out["by_type"]:
        out["by_type"][pos]["bh_significant_q05"] = bh.get(pos, False)
    out["table"] = ev_[["time", "name", "pos", "status", "team", "gid", "react"]].astype(str).to_dict("records")
    return out


def power_b(G):
    ws = winner_series()
    ch = []
    for gid, (t, v) in ws.items():
        if gid not in G.set_index("gid").index:
            continue
        ko = G.set_index("gid").at[gid, "kickoff_utc"].value
        for tn in range(((ko - 48 * HOUR) // HOUR) * HOUR, ko - 7 * HOUR, HOUR):
            a, b = asof(t, v, tn, 3 * HOUR), asof(t, v, tn + 6 * HOUR, 3 * HOUR)
            if not np.isnan(a) and not np.isnan(b):
                ch.append(b - a)
    sd = float(np.std(ch))
    z = norm.ppf(0.975) + norm.ppf(0.8)
    n_need = int(np.ceil((z * sd / 0.05) ** 2))
    ev_ = espn_events(G)
    n_ev = int(len(ev_)) if len(ev_) else 0
    return {"sd_6h_winner_logit_change": sd, "sesoi_logit": 0.05, "events_needed_for_sesoi": n_need, "key_events_so_far": n_ev,
            "weeks_of_snapshots": 2, "events_per_week": n_ev / 2, "weeks_needed": float(n_need / max(n_ev / 2, 1e-9)),
            "mde_at_current_events": float(z * sd / np.sqrt(max(n_ev, 1)))}


# --------------------------------------------------------------------------- dense capture (manual long-running process)

def capture(args):
    from lab.archive10 import save
    games, _ = h.load_games()
    log(f"capture: every {args.interval} min for {args.hours} h; Ctrl+C to stop")
    end = time.time() + args.hours * 3600
    n = 0
    while time.time() < end:
        t0 = time.time()
        now = pd.Timestamp.now(tz="UTC")
        up = games[~games["played"] & (games["kickoff_utc"] > now) & (games["kickoff_utc"] <= now + pd.Timedelta(hours=args.window))]
        if not up.empty:
            m = pk.live_markets(games, list(pk.ENV))
            m = m[m["gid"].isin(up["gid"])]
            books, trades = [], []
            for r in m.itertuples(index=False):
                try:
                    books.append({"ticker": r.ticker, "gid": r.gid, "minutes_to_kickoff": round((r.kickoff - now).total_seconds() / 60, 1),
                                  "orderbook": K._get(f"/markets/{r.ticker}/orderbook").get("orderbook_fp", {})})
                    if r.vol24 > 0:
                        d = K._get(f"/markets/trades?ticker={r.ticker}&min_ts={int((now - pd.Timedelta(minutes=args.interval * 2)).timestamp())}&limit=1000")
                        if d.get("trades"):
                            trades.append({"ticker": r.ticker, "gid": r.gid, "trades": d["trades"]})
                except Exception as exc:
                    log(f"  warning: {r.ticker}: {str(exc)[:60]}")
            meta = {"prereg": "396af66a", "retrieved_at": now.isoformat(), "timestamp_class": "T1 observed (lab retrieval time)", "pass": n}
            save("dense_books", f"{now:%Y%m%dT%H%M}", books, meta, every_pull=True)
            save("dense_trades", f"{now:%Y%m%dT%H%M}", trades, meta, every_pull=True)
            log(f"{now:%H:%M} pass {n}: {len(books)} books, {sum(len(x['trades']) for x in trades)} trades, {len(up)} games in window")
        else:
            log(f"{now:%H:%M} no game kicks off within {args.window} h; waiting")
        try:
            from lab import availability
            availability.espn_latest()
            import urllib.request
            req = urllib.request.Request("https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries", headers={"User-Agent": "Mozilla/5.0"})
            body = json.load(urllib.request.urlopen(req, timeout=60))
            save("espn_injuries_dense", f"{now:%Y%m%dT%H%M}", body, {"retrieved_at": now.isoformat()}, every_pull=False)
        except Exception as exc:
            log(f"  injuries: {str(exc)[:60]}")
        n += 1
        time.sleep(max(1, args.interval * 60 - (time.time() - t0)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["power", "run", "capture"])
    ap.add_argument("--hours", type=float, default=6)
    ap.add_argument("--interval", type=float, default=5)
    ap.add_argument("--window", type=float, default=8, help="capture games kicking off within this many hours")
    args = ap.parse_args()
    if args.command == "capture":
        return capture(args)
    OUT.mkdir(parents=True, exist_ok=True)
    G = fc.games_frame()
    rng = np.random.default_rng(SEED)
    panel_path = OUT / "panel.parquet"
    if panel_path.exists():
        panel = pd.read_parquet(panel_path)
    else:
        panel = build_panel(G)
        panel.to_parquet(panel_path)
    log(f"panel rows {len(panel)}, games {panel['gid'].nunique()}, by target {panel.groupby('target').gid.nunique().to_dict()}, "
        f"non-missing K/P/O {panel[['xK', 'xP', 'xO']].notna().mean().round(2).to_dict()}")
    if args.command == "power":
        out = {"prereg": "396af66a", "A": power_a(panel, rng), "B": power_b(G)}
        body = json.dumps(out, indent=1, default=str)
        (OUT / "power.json").write_bytes(body.encode("utf-8"))
        log(json.dumps(out, default=str)[:1500])
        log(f"Wrote reports/market_news/power.json sha256 {hashlib.sha256(body.encode()).hexdigest()}")
        return
    pw = json.loads((OUT / "power.json").read_text(encoding="utf-8"))
    res = {"prereg": "396af66a", "label": "provisional; Codex has not reproduced earlier studies", "A": run_a(panel, rng, G.set_index("gid")), "B": run_b(G, rng), "power": pw}
    body = json.dumps(res, indent=1, default=str)
    (OUT / "results.json").write_bytes(body.encode("utf-8"))
    log(f"Wrote reports/market_news/results.json sha256 {hashlib.sha256(body.encode()).hexdigest()}")
    for tgt, r in res["A"].items():
        log(f"A {tgt}: " + "; ".join(f"{v} kappa {r[v]['kappa']:+.3f} [{r[v]['ci'][0]:+.3f},{r[v]['ci'][1]:+.3f}] hl {r[v]['half_life_hours']}" for v in ("K", "P", "O") if v in r))
    log(f"B: {json.dumps({k: v for k, v in res['B'].items() if k != 'table'}, default=str)[:1200]}")


if __name__ == "__main__":
    main()
