"""Kalshi player props: as-of historical replay of the lab props simulator, market ladders and scoring.

Protocol: docs/PROPS_KALSHI_PREREGISTRATION.md (steps 1-5, commit 31af0b08). Calls Codex's lab.props code without
editing it. Kalshi access is read-only public market data ($0, no trading code).
"""
from __future__ import annotations

import json
import re
import unicodedata
import zlib

import numpy as np
import pandas as pd

from . import kalshi as K
from .config import CACHE_DIR, LAB_ROOT, RAW_DIR
from .ingest import normalize_team

PREREG = "31af0b08"
CACHE = CACHE_DIR / "props_kalshi"
REPORT = LAB_ROOT / "reports" / "props_kalshi"
LADDERS = {"KXNFLPASSYDS": "pass_yds", "KXNFLRSHYDS": "rush_yds", "KXNFLRECYDS": "rec_yds", "KXNFLREC": "rec"}
ENV = ("KXNFLTOTAL", "KXNFLSPREAD")
LEAD = pd.Timedelta(minutes=90)
TZ = "America/New_York"
FILTER = {"bid_min": 0.02, "ask_max": 0.98, "spread_max": 0.05, "vol24_min": 500.0}


# --------------------------------------------------------------------------- market inventory and candles

def scope_markets(games: pd.DataFrame) -> pd.DataFrame:
    """Ladder and environment markets in regular-season games, with gid, kickoff, team, threshold and player name."""
    inv = pd.read_parquet(CACHE_DIR / "kalshi" / "player_inventory.parquet")
    gm = K.match_games(K.game_markets(), games)
    gm["raw"] = gm["ticker"].str.rsplit("-", n=1).str[-1]          # Kalshi's own team code (e.g. JAC)
    code = {}
    for e, d in gm.groupby("event"):
        code[e.split("-", 1)[1]] = (d["gid"].iloc[0], d["kickoff_utc"].iloc[0], dict(zip(d["raw"], d["team"])))
    inv = inv[inv["series"].isin(list(LADDERS) + list(ENV))].copy()
    inv["code"] = inv["event"].str.split("-", n=1).str[1]
    inv = inv[inv["code"].isin(code)]
    inv["gid"] = inv["code"].map(lambda c: code[c][0])
    inv["kickoff"] = inv["code"].map(lambda c: code[c][1])
    last = inv["ticker"].str.rsplit("-", n=1).str[-1]
    inv["threshold"] = np.where(inv["strike"].notna(), np.floor(inv["strike"].astype(float)) + 1,
                                pd.to_numeric(last.str.extract(r"^(\d+)$")[0], errors="coerce"))
    seg = inv["ticker"].str.split("-").str[2]  # e.g. TENTPOLLARD20 (team + player) or DEN6 (spread team + points)
    raw = inv["code"].map(lambda c: code[c][2])
    inv["team"] = [next((m[r] for r in sorted(m, key=len, reverse=True) if isinstance(x, str) and x.startswith(r)), None)
                   for x, m in zip(seg, raw)]
    inv["player"] = inv["yes_sub"].str.split(":").str[0].str.strip()
    inv["stat"] = inv["series"].map(LADDERS)
    # spread: "<TEAM><k>" = team wins by more than k - 0.5 ... strike is the authoritative threshold
    return inv.reset_index(drop=True)


def candles(m: pd.Series) -> pd.DataFrame:
    """Hourly candles from 7 days before kickoff to kickoff + 5h (cached; history is immutable after settlement)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "candles" / f"{m['ticker']}.json"
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        cs = json.loads(path.read_text(encoding="utf-8"))
    else:
        s, e = int((m["kickoff"] - pd.Timedelta(days=7)).timestamp()), int((m["kickoff"] + pd.Timedelta(hours=5)).timestamp())
        base = f"/historical/markets/{m['ticker']}" if m["historical"] else f"/series/{m['series']}/markets/{m['ticker']}"
        cs = K._get(f"{base}/candlesticks?start_ts={s}&end_ts={e}&period_interval=60").get("candlesticks", [])
        if m["kickoff"] + pd.Timedelta(hours=5) < pd.Timestamp.now(tz="UTC"):
            path.write_text(json.dumps(cs), encoding="utf-8")

    def cl(b):
        b = b or {}
        return K._f(b.get("close_dollars", b.get("close")))
    return pd.DataFrame([{"ts": pd.Timestamp(c["end_period_ts"], unit="s", tz="UTC"), "bid": cl(c.get("yes_bid")),
                          "ask": cl(c.get("yes_ask")), "last": cl(c.get("price")),
                          "volume": K._f(c.get("volume_fp", c.get("volume"))) or 0.0} for c in cs],
                        columns=["ts", "bid", "ask", "last", "volume"])


def quote_at(c: pd.DataFrame, P: pd.Timestamp) -> dict:
    """Latest candle ending at or before P, with the step-0 liquidity flag."""
    x = c[c["ts"] <= P]
    if x.empty:
        return {"mid": np.nan, "bid": np.nan, "ask": np.nan, "vol24": 0.0, "liquid": False}
    r = x.iloc[-1]
    vol = float(x["volume"].iloc[-24:].sum())
    ok_book = pd.notna(r["bid"]) and pd.notna(r["ask"]) and r["bid"] >= FILTER["bid_min"] and r["ask"] <= FILTER["ask_max"]
    liquid = bool(ok_book and (r["ask"] - r["bid"]) <= FILTER["spread_max"] and vol >= FILTER["vol24_min"])
    mid = (r["bid"] + r["ask"]) / 2 if ok_book else r["last"]
    return {"mid": float(mid) if pd.notna(mid) else np.nan, "bid": r["bid"], "ask": r["ask"], "vol24": vol, "liquid": liquid}


def trades(m: pd.Series, P: pd.Timestamp) -> list[dict]:
    """Trades in the 24h before P (raw prints) for a liquid market."""
    path = CACHE / "trades" / f"{m['ticker']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    out, cur = [], ""
    ep = "/historical/trades" if m["historical"] else "/markets/trades"
    while True:
        d = K._get(f"{ep}?ticker={m['ticker']}&min_ts={int((P - pd.Timedelta(hours=24)).timestamp())}&max_ts={int(P.timestamp())}"
                   f"&limit=1000" + (f"&cursor={cur}" if cur else ""))
        out += d.get("trades", [])
        cur = d.get("cursor")
        if not cur or not d.get("trades"):
            break
    path.write_text(json.dumps(out), encoding="utf-8")
    return out


# --------------------------------------------------------------------------- ladders -> distributions

def isotonic_survival(k: np.ndarray, p: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted isotonic fit of P(X >= k), non-increasing in k."""
    from sklearn.isotonic import IsotonicRegression
    o = np.argsort(k)
    fit = IsotonicRegression(increasing=False, y_min=0.0, y_max=1.0).fit(k[o], p[o], sample_weight=w[o])
    out = np.empty_like(p, dtype=float)
    out[o] = fit.predict(k[o])
    return out


def median_from_cdf(x: np.ndarray, F: np.ndarray) -> float:
    """Linear interpolation of the 0.5 crossing of a monotone CDF; NaN if 0.5 is not bracketed."""
    o = np.argsort(x)
    x, F = x[o], F[o]
    if F.min() > 0.5 or F.max() < 0.5:
        return np.nan
    i = int(np.searchsorted(F, 0.5))
    if i == 0:
        return float(x[0])
    x0, x1, f0, f1 = x[i - 1], x[i], F[i - 1], F[i]
    return float(x0 + (0.5 - f0) * (x1 - x0) / (f1 - f0)) if f1 > f0 else float(x0)


def game_environment(gm: pd.DataFrame, home: str, away: str, P: pd.Timestamp, winner_p: float) -> dict:
    """Kalshi median home margin and total at P from the spread, total and game-winner markets."""
    rows = []
    for m in gm[gm["series"] == "KXNFLSPREAD"].itertuples(index=False):
        q = quote_at(candles(pd.Series(m._asdict())), P)
        if np.isnan(q["mid"]) or pd.isna(m.strike):
            continue
        x = float(m.strike)
        # team wins by more than x: home -> P(M > x) so F(x) = 1 - p; away -> P(M < -x) so F(-x) = p
        if m.team == home:
            rows.append((x, 1 - q["mid"], 1 / max(q["ask"] - q["bid"], 0.01) if pd.notna(q["bid"]) else 1.0))
        elif m.team == away:
            rows.append((-x, q["mid"], 1 / max(q["ask"] - q["bid"], 0.01) if pd.notna(q["bid"]) else 1.0))
    if not np.isnan(winner_p):
        rows.append((0.0, 1 - winner_p, 20.0))
    tot = []
    for m in gm[gm["series"] == "KXNFLTOTAL"].itertuples(index=False):
        q = quote_at(candles(pd.Series(m._asdict())), P)
        if np.isnan(q["mid"]) or pd.isna(m.strike):
            continue
        tot.append((float(m.strike), 1 - q["mid"], 1 / max(q["ask"] - q["bid"], 0.01) if pd.notna(q["bid"]) else 1.0))
    out = {"margin": np.nan, "total": np.nan, "n_spread": len(rows), "n_total": len(tot)}
    for key, pts in (("margin", rows), ("total", tot)):
        if len(pts) >= 2:
            a = np.array(pts)
            F = 1 - isotonic_survival(a[:, 0], 1 - a[:, 1], a[:, 2])  # CDF via survival fit
            out[key] = median_from_cdf(a[:, 0], F)
    return out


# --------------------------------------------------------------------------- player matching

def _norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


def player_ids(markets: pd.DataFrame, season: int) -> pd.Series:
    ros = pd.read_parquet(RAW_DIR / f"roster_weekly_{season}.parquet", columns=["team", "gsis_id", "full_name"])
    ros["team"] = ros["team"].map(normalize_team)
    ros["key"] = ros["full_name"].map(_norm_name)
    look = ros.drop_duplicates(["team", "key"]).set_index(["team", "key"])["gsis_id"]
    keys = list(zip(markets["team"], markets["player"].map(_norm_name)))
    return pd.Series([look.get(k_) for k_ in keys], index=markets.index)


# --------------------------------------------------------------------------- simulator replay (as of each week)

class Replayer:
    """Runs lab.props' v1/v2/base for one season-week with as-of inputs and a supplied game environment."""

    def __init__(self, season: int, games_csv: pd.DataFrame, n_sims: int = 10_000):
        from .props import models as M, sim as S, v2 as V2
        self.season, self.n, self.games_csv = season, n_sims, games_csv
        self.T1 = M.fit(range(2016, season))
        S.calibrate_clock(self.T1)
        self.T2 = V2.prepare(self.T1)
        ros = pd.read_parquet(RAW_DIR / f"roster_weekly_{season}.parquet", columns=["week", "team", "gsis_id", "status", "position", "full_name"])
        self.ros = ros.rename(columns={"gsis_id": "pid", "team": "posteam"}).assign(posteam=lambda d: d["posteam"].map(normalize_team))
        self.names = self.ros.drop_duplicates("pid", keep="last").set_index("pid")["full_name"]
        self.pbp = M.load_pbp([season - 1, season])

    def week(self, week: int, games: pd.DataFrame, envs: dict, inj: pd.DataFrame, log=print) -> pd.DataFrame:
        """envs: gid -> {arm: (home_points, away_points)}. inj: injury rows already filtered to before each game's T-90."""
        from .props import evaluate as E, game as G, players as PL, sim as S, v2 as V2
        from .props.weekly import availability
        season = self.season
        p = self.pbp[(self.pbp["season"] < season) | (self.pbp["week"] < week)]
        pan = PL.panel(p, self.T1)
        a = PL.asof(pan, season, week)
        possd = E._pos_sd(pan, season)
        ps = p[p["season"] == season]
        first_qb = ps[ps["play_type"] == "pass"].dropna(subset=["passer_player_id"]).sort_values(["week", "game_id", "play_id"]) \
            .groupby(["game_id", "posteam"])["passer_player_id"].first().reset_index().merge(ps.drop_duplicates("game_id")[["game_id", "week"]])
        prev = p[p["season"] == season - 1]
        prev_qb = prev[prev["play_type"] == "pass"].dropna(subset=["passer_player_id"]).sort_values(["week", "game_id", "play_id"]) \
            .groupby(["game_id", "posteam"])["passer_player_id"].first().reset_index().merge(prev.drop_duplicates("game_id")[["game_id", "week"]])
        rows = []
        for g in games.itertuples(index=False):
            if g.game_id not in envs:
                continue
            sides = [g.home_team, g.away_team]
            avail, qbs, hist = {}, {}, {}
            for t in sides:
                avail[t], _ = availability(self.ros, inj, week, t)
                last = first_qb[first_qb["posteam"] == t].sort_values("week")
                if not len(last):
                    last = prev_qb[prev_qb["posteam"] == t].sort_values("week")
                qbs[t] = last["passer_player_id"].iloc[-1] if len(last) else None  # most recent previous starter (as of)
                tp = pan[pan["posteam"] == t]
                hist[t] = (tp[(tp["season"] == season) & (tp["week"] < week)].drop_duplicates("game_id"),
                           tp[tp["season"] == season - 1].drop_duplicates("game_id"))
            teams, pl, cols, info = G.build(a, avail, hist, week, qbs, sides)
            elig = G.eligible(info, a)
            seed = zlib.crc32(g.game_id.encode())
            for arm, imp in envs[g.game_id].items():
                imp = list(imp)
                rng = np.random.default_rng(seed)
                e1, _ = S.calibrate(self.T1, teams, pl, imp, rng)
                r1 = S.simulate(self.T1, teams, pl, self.n, e1, rng)
                rng2 = np.random.default_rng(seed + 1)
                e2, _ = S.calibrate_v2(self.T2, teams, pl, imp, rng2)
                r2 = S.simulate(self.T2, teams, pl, self.n, e2, rng2)
                for t, pid, k in elig:
                    si = sides.index(t)
                    base = {"gid": g.game_id, "season": season, "week": week, "arm": arm, "team": t, "pid": pid,
                            "name": self.names.get(pid, ""), "stat": k, "imp": imp[si]}
                    for v, r in (("v1", r1), ("v2", r2)):
                        x = r["stats"][k][:, cols[pid]]
                        if v == "v2":
                            x = V2.correct(x, k)
                        rows.append(base | {"version": v, "mean": float(x.mean()), **dict(zip(G.QCOLS, np.quantile(x, G.LEVELS)))})
                    ratio = float(np.clip(imp[si] / max(E._team_ppg(self.games_csv, season, week, t), 1.0), 0.6, 1.6))
                    b = G.baseline(a, pid, k, ratio, possd) if pid in a.index else None
                    if b is not None:
                        m_, q = G.baseline_quantiles(b)
                        rows.append(base | {"version": "base", "mean": float(m_), **dict(zip(G.QCOLS, np.asarray(q, float)))})
            log(f"    {g.game_id}: {len(elig)} player-stats x {len(envs[g.game_id])} arm(s)")
        return pd.DataFrame(rows)


def p_at_least(q: np.ndarray, k: float) -> float:
    """P(X >= k) from 99 quantiles (levels 0.01..0.99), interpolated at k - 0.5 for integer stats."""
    from .props.game import LEVELS
    F = np.interp(k - 0.5, q, LEVELS, left=0.0, right=1.0)
    return float(1.0 - F)
