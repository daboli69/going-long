"""Tails Amendment 3: does Kalshi or the sportsbook consensus lead the other, judged by the move to the close. Rule: docs/TAILS_PREREG.md."""
from __future__ import annotations

import glob
import json

import numpy as np
import pandas as pd

from . import kalshi as K
from . import tails, tails_ladder
from .ingest import normalize_team
from .tails import ROOT, RAW, rule

HOURS = (24, 3)
MAX_BOOK_AGE = pd.Timedelta(hours=6)
MAX_K_AGE = pd.Timedelta(hours=3)
MIN_BOOKS = 3
DECIDE_WEEKS, CONFIRM_WEEKS = (1, 4), (5, 8)
PLAUSIBLE = 0.15
MARKETS = ("winner", "spread", "total")
MARKET_DIR = RAW / "archive" / "market"


def _norm(t):
    try:
        return normalize_team(t)
    except Exception:
        return t


def games_frame() -> pd.DataFrame:
    from . import homewin_deep as h
    g, _ = h.load_games()
    return g[g["season"] == 2026].copy()


def book_quotes(games: pd.DataFrame) -> pd.DataFrame:
    """All raw timestamped sportsbook quotes (2026): the assembled parquet plus every archived snapshot, mapped to a game id."""
    q = pd.read_parquet(RAW / "market" / "going_quotes.parquet")
    q = q.rename(columns={"commence_time": "kick", "quote_time": "qt"})[["kick", "home", "away", "book", "market", "side", "price", "point", "qt"]]
    rows = []
    for f in sorted(glob.glob(str(MARKET_DIR / "going_*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for r in d.get("content", []):
            if r.get("period") not in (None, "FULL") or r.get("in_play"):
                continue
            rows.append((r["kickoff"], r["home"], r["away"], r["book"], r["market"], r["side"], r["price"], r.get("point"), r["quote_time"]))
    a = pd.DataFrame(rows, columns=["kick", "home", "away", "book", "market", "side", "price", "point", "qt"])
    Q = pd.concat([q, a], ignore_index=True)
    Q["kick"], Q["qt"] = pd.to_datetime(Q["kick"], utc=True), pd.to_datetime(Q["qt"], utc=True)
    Q["home"], Q["away"] = Q["home"].map(_norm), Q["away"].map(_norm)
    Q = Q.drop_duplicates(["book", "market", "side", "home", "away", "qt", "point", "price"])
    gk = games[["gid", "home", "away", "kickoff_utc"]]
    Q = Q.merge(gk, on=["home", "away"], how="inner")
    Q = Q[(Q["kick"] - Q["kickoff_utc"]).abs() <= pd.Timedelta(days=1)]
    return Q[Q["qt"] <= Q["kickoff_utc"]]


def _ip(p):
    p = np.asarray(p, float)
    return np.where(p < 0, -p / (100 - p), 100 / (100 + p))


def book_at(Q: pd.DataFrame, gid: str, T: pd.Timestamp) -> dict:
    """Consensus at T: newest quote per book at or before T and no older than 6 hours; median over at least 3 books."""
    x = Q[(Q["gid"] == gid) & (Q["qt"] <= T) & (Q["qt"] >= T - MAX_BOOK_AGE)]
    out = {}
    last = x.sort_values("qt").groupby(["book", "market", "side"]).tail(1)
    h = last[last["market"] == "h2h"].pivot(index="book", columns="side", values="price")
    if {"home", "away"} <= set(h.columns):
        h = h.dropna()
        if len(h) >= MIN_BOOKS:
            ph, pa = _ip(h["home"]), _ip(h["away"])
            out["winner"] = float(np.median(ph / (ph + pa)))
    s = last[(last["market"] == "spreads") & (last["side"] == "home")].dropna(subset=["point"])
    if len(s) >= MIN_BOOKS:
        out["spread"] = float(-np.median(s["point"]))
    t = last[(last["market"] == "totals") & (last["side"].str.lower() == "over")].dropna(subset=["point"])
    if len(t) >= MIN_BOOKS:
        out["total"] = float(np.median(t["point"]))
    used = last["qt"]
    out["age_h"] = float((T - used.median()).total_seconds() / 3600) if len(used) else np.nan
    out["books"] = int(last["book"].nunique())
    return out


def aligned() -> tuple[pd.DataFrame, dict]:
    """One row per (game, market, horizon): both prices at T, both closes, ages. Only games kicked off, weeks 1 to 8, 2026."""
    G = games_frame()
    now = pd.Timestamp.now(tz="UTC")
    G = G[(G["kickoff_utc"] < now) & (G["week"] <= CONFIRM_WEEKS[1])]
    cl = tails.load_games().set_index("game_id")[["spread_line", "total_line", "home_moneyline", "away_moneyline"]]
    Q = book_quotes(G)
    hist, krep = K.history(G, progress=lambda *_: None)
    fits = pd.read_parquet(ROOT / "data" / "cache" / "tails_ladder_fits.parquet")
    fits = fits[(fits["liq"] == "L1") & (fits["season"] == 2026)].set_index(["gid", "series", "horizon"])["mu"]
    rows = []
    for g in G.itertuples():
        c = cl.loc[g.gid] if g.gid in cl.index else None
        if c is None:
            continue
        ph, pa = _ip(c["home_moneyline"]), _ip(c["away_moneyline"])
        bclose = {"winner": float(ph / (ph + pa)) if pd.notna(ph) and pd.notna(pa) else np.nan, "spread": float(c["spread_line"]), "total": float(c["total_line"])}
        kc = K.probability(hist, g.gid, g.kickoff_utc, g.kickoff_utc)
        kclose = {"winner": kc["p_home"], "spread": fits.get((g.gid, "KXNFLSPREAD", 1), np.nan), "total": fits.get((g.gid, "KXNFLTOTAL", 1), np.nan)}
        for h in HOURS:
            T = g.kickoff_utc - pd.Timedelta(hours=h)
            b = book_at(Q, g.gid, T)
            kw = K.probability(hist, g.gid, T, g.kickoff_utc)
            kage = (T - pd.Timestamp(kw["quote_time"])).total_seconds() / 3600 if kw.get("quote_time") else np.nan
            kt = {"winner": kw["p_home"], "spread": fits.get((g.gid, "KXNFLSPREAD", h), np.nan), "total": fits.get((g.gid, "KXNFLTOTAL", h), np.nan)}
            for m in MARKETS:
                rows.append({"gid": g.gid, "week": int(g.week), "market": m, "h": h, "B_T": b.get(m, np.nan), "K_T": kt[m], "B_close": bclose[m], "K_close": kclose[m],
                             "B_age_h": b["age_h"] if m in b else np.nan, "K_age_h": kage if m == "winner" else np.nan, "books": b["books"]})
    t = pd.DataFrame(rows)
    t["stage"] = np.where(t["week"].between(*DECIDE_WEEKS), "decide", np.where(t["week"].between(*CONFIRM_WEEKS), "confirm", ""))
    t["gap"] = t["K_T"] - t["B_T"]
    t["dB"] = t["B_close"] - t["B_T"]
    t["dK"] = t["K_close"] - t["K_T"]
    t["usable"] = t[["B_T", "K_T", "B_close", "K_close"]].notna().all(axis=1)
    return t, {"kalshi_history": krep, "book_quote_rows": int(len(Q)), "book_quote_games": int(Q["gid"].nunique()),
               "book_quote_range": [str(Q["qt"].min()), str(Q["qt"].max())], "books": int(Q["book"].nunique())}


def slope(x: np.ndarray, y: np.ndarray) -> float:
    xc = x - x.mean()
    return float((xc * (y - y.mean())).sum() / (xc ** 2).sum()) if (xc ** 2).sum() > 0 else np.nan


def power_table(t: pd.DataFrame, rng, B: int = 2000) -> dict:
    """Smallest loading detectable at 80% power per setting, stage and direction (2.8 times the bootstrap standard error)."""
    out = {}
    for (m, h, stage), d in t[t["usable"] & (t["stage"] != "")].groupby(["market", "h", "stage"]):
        n = len(d)
        key = f"{m}_{h}h_{stage}"
        r = {"games": int(n)}
        if n < 8:
            out[key] = {**r, "note": "too few games", "informative": False}
            continue
        for name, x, y in (("a_B_kalshi_leads", d["gap"].to_numpy(), d["dB"].to_numpy()), ("a_K_book_leads", -d["gap"].to_numpy(), d["dK"].to_numpy())):
            bs = [slope(x[i], y[i]) for i in (rng.integers(0, n, n) for _ in range(B))]
            bs = np.array([v for v in bs if np.isfinite(v)])
            se = float(bs.std()) if len(bs) else np.nan
            r[name] = {"loading": slope(x, y), "se": se, "min_detectable": 2.8 * se, "informative": bool(2.8 * se <= PLAUSIBLE)}
        r["informative"] = bool(all(r[k]["informative"] for k in ("a_B_kalshi_leads", "a_K_book_leads")))
        out[key] = r
    return out


def counts(t: pd.DataFrame, rep: dict) -> dict:
    u = t[t["usable"]]
    both = {f"{m}_{h}h": int(u[(u["market"] == m) & (u["h"] == h)]["gid"].nunique()) for m in MARKETS for h in HOURS}
    quote_age = {f"{m}_{h}h": {"median_age_h": float(d["B_age_h"].median()), "share_over_3h": float((d["B_age_h"] > 3).mean())} for (m, h), d in t[t["B_T"].notna()].groupby(["market", "h"])}
    espn = sorted(glob.glob(str(MARKET_DIR / "espn_odds_*.json")))
    lad = tails_ladder.counts()
    return {"games_2026_weeks_1_to_8_played": int(t["gid"].nunique()), "games_with_both_sides_and_closes": both, "book_quote_age_at_horizon": quote_age, "sportsbook": rep,
            "going_archive_snapshots": len(glob.glob(str(MARKET_DIR / "going_*.json"))), "espn_draftkings_snapshots": len(espn),
            "kalshi_winner_games": rep["kalshi_history"]["games_matched"], "kalshi_winner_candles": rep["kalshi_history"]["candles"],
            "kalshi_ladders": {k: v for k, v in lad.items() if k.startswith("KX")}, "order_book_snapshots": lad.get("order_book_snapshots"),
            "trade_prints_center_rungs": int(tails_ladder.tape_check()["trade_prints"]),
            "note": "Raw sportsbook quotes exist only for 2026; there are none for 2025, so 2025 cannot be a decide stage on the book side."}


def qb_events(games: pd.DataFrame, Q: pd.DataFrame | None = None, hist: pd.DataFrame | None = None) -> dict:
    """Quarterback status changes between consecutive ESPN injury snapshots (timestamped from 2026-10-16) that sit within 72 hours before that team's game.
    Where both markets have a price, the change in the team's win probability from 1 hour before to 6 hours after the snapshot, in the book consensus and on Kalshi."""
    from .gamecenter_data import TEAM_NAMES
    abbr = {v: k for k, v in TEAM_NAMES.items()}
    last, ev, snaps = {}, [], 0
    for f in sorted(glob.glob(str(RAW / "archive" / "espn_injuries_*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        ts = pd.Timestamp(d.get("timestamp")) if d.get("timestamp") else None
        if ts is None:
            continue
        ts = ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")
        snaps += 1
        for tm in d.get("injuries", []):
            for e in tm.get("injuries", []):
                if ((e.get("athlete") or {}).get("position") or {}).get("abbreviation") != "QB":
                    continue
                key = (e["id"], tm["displayName"])
                st = e.get("status")
                if key in last and last[key] != st:
                    ev.append({"qb": (e.get("athlete") or {}).get("displayName"), "team": abbr.get(tm["displayName"]), "from": last[key], "to": st, "seen_at": ts})
                last[key] = st
    now = pd.Timestamp.now(tz="UTC")
    played = games[games["kickoff_utc"] < now]
    rows = []
    for e in ev:
        g = played[((played["home"] == e["team"]) | (played["away"] == e["team"])) & (played["kickoff_utc"] > e["seen_at"]) & (played["kickoff_utc"] <= e["seen_at"] + pd.Timedelta(hours=72))]
        if g.empty or e["team"] is None:
            continue
        g = g.iloc[0]
        r = {**{k: (str(v) if k == "seen_at" else v) for k, v in e.items()}, "gid": g["gid"]}
        if Q is not None and hist is not None:
            sign = 1 if g["home"] == e["team"] else -1
            t0, t1 = e["seen_at"] - pd.Timedelta(hours=1), e["seen_at"] + pd.Timedelta(hours=6)
            if t1 < g["kickoff_utc"]:
                b0, b1 = book_at(Q, g["gid"], t0).get("winner"), book_at(Q, g["gid"], t1).get("winner")
                k0, k1 = K.probability(hist, g["gid"], t0, g["kickoff_utc"])["p_home"], K.probability(hist, g["gid"], t1, g["kickoff_utc"])["p_home"]
                if None not in (b0, b1) and np.isfinite([k0, k1]).all():
                    s_ = 1 if sign == 1 else -1
                    r.update(d_book=float(s_ * (b1 - b0)), d_kalshi=float(s_ * (k1 - k0)))
        rows.append(r)
    both = [r for r in rows if "d_book" in r]
    out = {"snapshots": snaps, "qb_status_changes": len(ev), "before_that_teams_game_within_72h": len(rows), "with_both_markets_priced": len(both), "events": rows[:12],
           "study": "descriptive only" if len(both) < 8 else "run"}
    if both:
        out["median_change_book"] = float(np.median([r["d_book"] for r in both]))
        out["median_change_kalshi"] = float(np.median([r["d_kalshi"] for r in both]))
    return out


LEADLAG_DIR = tails.OUT / "leadlag"


def _canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)


def snapshot(week: int | None = None) -> dict:
    """Write-once, before kickoff: Kalshi winner price and the sportsbook consensus (winner, spread, total) with ages for every game of the week not yet started."""
    import hashlib
    from datetime import datetime, timezone
    G = games_frame()
    now = pd.Timestamp.now(tz="UTC")
    up = G[G["kickoff_utc"] > now]
    week = int(week or up["week"].min())
    path = LEADLAG_DIR / f"2026_w{week:02d}.json"
    if path.exists():
        return json.loads(path.read_text())
    G = up[up["week"] == week]
    Q = book_quotes(G.assign(kickoff_utc=G["kickoff_utc"]))
    Q = Q[Q["qt"] <= now]
    live = K.live_prices(G).set_index("gid")["p_home"].to_dict()
    rows = []
    for g in G.itertuples():
        b = book_at(Q, g.gid, now)
        rows.append({"gid": g.gid, "kickoff_utc": str(g.kickoff_utc), "kalshi_winner_p_home": None if pd.isna(live.get(g.gid, np.nan)) else float(live[g.gid]),
                     "book_winner_p_home": b.get("winner"), "book_spread_home_margin": b.get("spread"), "book_total": b.get("total"), "book_median_age_h": b.get("age_h"), "books": b.get("books")})
    body = {"observed_at": now.isoformat(), "week": week, "games": rows, "ladder_archive": f"ladders/2026_w{week:02d}.json"}
    body["sha256"] = hashlib.sha256(_canon(body).encode()).hexdigest()
    LEADLAG_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=1, default=str))
    with (tails.OUT / "ledger.jsonl").open("a") as f:
        f.write(json.dumps({"file": "leadlag/" + path.name, "sha256": body["sha256"], "created": body["observed_at"]}) + "\n")
    return body
