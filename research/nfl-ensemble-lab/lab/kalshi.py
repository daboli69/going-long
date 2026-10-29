"""Kalshi NFL game-winner prices (series KXNFLGAME): read-only public market data, $0.

- No trading or account endpoints exist in this module. Market data needs no authentication. The key ID lives
  in data/private/kalshi.env (git-ignored) and is only sent if a private key is configured for signed calls.
- History: hourly candlesticks per team market, each stamped by Kalshi's own `end_period_ts`
  ("T1-exchange"). Settled markets are cached once; open markets refresh. Every live pull is archived write-once.
- A price is usable at time t only if its candle ended at or before t. Home probability = home mid /
  (home mid + away mid), with mid = (yes bid + yes ask) / 2, falling back to the last trade.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import CACHE_DIR, DATA_DIR
from .ingest import normalize_team

BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = "KXNFLGAME"
CACHE = CACHE_DIR / "kalshi"
TIMESTAMP_CLASS = "T1-exchange (Kalshi candle end_period_ts)"
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
_last_call = [0.0]


def key_id() -> str | None:
    """Kalshi API key ID from the environment or data/private/kalshi.env (never committed)."""
    if os.environ.get("KALSHI_API_KEY_ID"):
        return os.environ["KALSHI_API_KEY_ID"].strip()
    p = DATA_DIR / "private" / "kalshi.env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("KALSHI_API_KEY_ID="):
                return line.split("=", 1)[1].strip() or None
    return None


def _get(path: str, retries: int = 4) -> dict:
    """Public GET with polite pacing (at most ~8 requests a second) and backoff on 429/5xx."""
    for attempt in range(retries):
        wait = 0.125 - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        req = urllib.request.Request(BASE + path, headers={"User-Agent": "nfl-ensemble-lab (read-only research)",
                                                           "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
        time.sleep(2 ** attempt)
    raise ConnectionError(path)


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


# --------------------------------------------------------------------------- markets

def game_markets(status: str | None = None) -> pd.DataFrame:
    """Every KXNFLGAME team market: current ones from /markets, older ones from Kalshi's /historical/markets archive.

    `status="open"` returns only currently open markets (used for live prices)."""
    rows = []
    sources = [("/markets", False)] if status else [("/markets", False), ("/historical/markets", True)]
    for path, hist in sources:
        cur = ""
        while True:
            q = f"{path}?series_ticker={SERIES}&limit=1000" + (f"&status={status}" if status else "") + (f"&cursor={cur}" if cur else "")
            d = _get(q)
            for m in d.get("markets", []):
                team = m["ticker"].rsplit("-", 1)[-1]
                try:
                    team = normalize_team(team)
                except ValueError:
                    continue
                ev = m.get("event_ticker") or m["ticker"].rsplit("-", 1)[0]
                rows.append({"event": ev, "ticker": m["ticker"], "team": team, "date": _event_date(ev), "historical": hist,
                             "open_time": m.get("open_time"), "close_time": m.get("close_time"),
                             "occurrence": m.get("occurrence_datetime") or m.get("expected_expiration_time"),
                             "status": m.get("status"), "result": m.get("result"),
                             "yes_bid": _f(m.get("yes_bid_dollars")), "yes_ask": _f(m.get("yes_ask_dollars")),
                             "last": _f(m.get("last_price_dollars")), "volume": _f(m.get("volume_fp"))})
            cur = d.get("cursor")
            if not cur or not d.get("markets"):
                break
    df = pd.DataFrame(rows).drop_duplicates("ticker")
    for c in ("open_time", "close_time", "occurrence"):
        df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
    return df


def _event_date(event_ticker: str) -> pd.Timestamp | None:
    code = event_ticker.split("-")[1][:7]  # e.g. 26OCT29
    try:
        return pd.Timestamp(2000 + int(code[:2]), MONTHS[code[2:5]], int(code[5:7]))
    except (KeyError, ValueError):
        return None


def match_games(markets: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Attach the lab's canonical gid and home/away side to each team market (regular season only)."""
    ev = markets.groupby("event").agg(teams=("team", lambda s: frozenset(s)), date=("date", "first")).reset_index()
    g = games.assign(local_date=games["kickoff_utc"].dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize())
    by = {}
    for r in g.itertuples(index=False):
        by.setdefault(frozenset((r.home, r.away)), []).append(r)
    link = {}
    for e in ev.itertuples(index=False):
        if e.date is None or len(e.teams) != 2:
            continue
        hit = [r for r in by.get(e.teams, []) if abs((r.local_date - e.date).days) <= 1]
        if len(hit) == 1:
            link[e.event] = hit[0]
    m = markets[markets["event"].isin(link)].copy()
    m["gid"] = m["event"].map(lambda x: link[x].gid)
    m["side"] = [("home" if t == link[e].home else "away") for e, t in zip(m["event"], m["team"])]
    m["kickoff_utc"] = m["event"].map(lambda x: link[x].kickoff_utc)
    return m


# --------------------------------------------------------------------------- history

def candles(market: pd.Series, refresh: bool = False) -> pd.DataFrame:
    """Hourly candles over the market's life. Settled markets are cached permanently."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{market['ticker']}.json"
    final = market["status"] in ("settled", "finalized", "closed") or bool(market.get("historical"))
    if path.exists() and final and not refresh:
        cs = json.loads(path.read_text(encoding="utf-8"))
    else:
        start = int(market["open_time"].timestamp()) if pd.notna(market["open_time"]) else int(time.time()) - 30 * 86400
        end = int(min(time.time(), market["close_time"].timestamp() if pd.notna(market["close_time"]) else time.time()))
        base = (f"/historical/markets/{market['ticker']}" if market.get("historical")
                else f"/series/{SERIES}/markets/{market['ticker']}")
        cs, s = [], start
        while s < end:  # chunks of ~200 days of hourly candles
            e = min(end, s + 4800 * 3600)
            d = _get(f"{base}/candlesticks?start_ts={s}&end_ts={e}&period_interval=60")
            cs += d.get("candlesticks", [])
            s = e
        path.write_text(json.dumps({"retrieved_at": datetime.now(timezone.utc).isoformat(), "candlesticks": cs}), encoding="utf-8")
        cs = {"candlesticks": cs}
    def close(block):  # live API: close_dollars; historical archive: close
        block = block or {}
        return _f(block.get("close_dollars", block.get("close")))

    rows = [{"ts": pd.Timestamp(c["end_period_ts"], unit="s", tz="UTC"), "bid": close(c.get("yes_bid")),
             "ask": close(c.get("yes_ask")), "last": close(c.get("price")), "volume": _f(c.get("volume_fp", c.get("volume")))}
            for c in cs["candlesticks"]]
    return pd.DataFrame(rows, columns=["ts", "bid", "ask", "last", "volume"])


def history(games: pd.DataFrame, refresh: bool = False, progress=print) -> tuple[pd.DataFrame, dict]:
    """Long table of timestamped Kalshi prices per (gid, side), plus a coverage report."""
    m = match_games(game_markets(), games)
    parts = []
    for i, r in enumerate(m.itertuples(index=False)):
        c = candles(pd.Series(r._asdict()), refresh)
        if len(c):
            parts.append(c.assign(gid=r.gid, side=r.side, ticker=r.ticker, kickoff_utc=r.kickoff_utc))
        if i and i % 100 == 0:
            progress(f"  kalshi candles: {i}/{len(m)} markets")
    hist = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["ts", "bid", "ask", "last", "volume", "gid", "side", "ticker", "kickoff_utc"])
    hist["mid"] = np.where(hist["bid"].notna() & hist["ask"].notna() & (hist["ask"] >= hist["bid"]) & (hist["bid"] > 0),
                           (hist["bid"] + hist["ask"]) / 2, hist["last"])
    seasons = games.set_index("gid")["season"]
    both = hist.groupby("gid")["side"].nunique()
    report = {"timestamp_class": TIMESTAMP_CLASS, "team_markets_matched": int(len(m)), "games_matched": int(m["gid"].nunique()),
              "games_with_both_sides": int((both == 2).sum()),
              "by_season": {int(k): int(v) for k, v in seasons.reindex(both[both == 2].index).value_counts().sort_index().items()},
              "candles": int(len(hist))}
    return hist, report


def probability(hist: pd.DataFrame, gid: str, cutoff: pd.Timestamp, kickoff: pd.Timestamp | None = None) -> dict:
    """De-vigged home probability from the latest candles that ended at or before min(cutoff, kickoff)."""
    t = cutoff if kickoff is None else min(cutoff, kickoff)
    x = hist[(hist["gid"] == gid) & (hist["ts"] <= t) & hist["mid"].notna()]
    if x.empty:
        return {"p_home": np.nan, "quote_time": None}
    last = x.sort_values("ts").groupby("side").tail(1).set_index("side")
    if not {"home", "away"} <= set(last.index):
        return {"p_home": np.nan, "quote_time": None}
    ph, pa = last.at["home", "mid"], last.at["away", "mid"]
    if ph + pa <= 0:
        return {"p_home": np.nan, "quote_time": None}
    return {"p_home": float(ph / (ph + pa)), "quote_time": str(last["ts"].max()), "overround": float(ph + pa)}


def consensus_frame(hist: pd.DataFrame) -> pd.DataFrame:
    """Drop-in shape of the lab's GOING consensus (game_id, quote_time, books, p_home_consensus), one row per hour."""
    w = hist.pivot_table(index=["gid", "ts"], columns="side", values="mid", aggfunc="last").sort_index()
    w = w.groupby(level=0).ffill().dropna()
    if w.empty or not {"home", "away"} <= set(w.columns):
        return pd.DataFrame(columns=["game_id", "quote_time", "books", "p_home_consensus"])
    out = (w["home"] / (w["home"] + w["away"])).rename("p_home_consensus").reset_index()
    return out.rename(columns={"gid": "game_id", "ts": "quote_time"}).assign(books=1)


def live_prices(games: pd.DataFrame) -> pd.DataFrame:
    """Current top-of-book for open NFL game markets, archived write-once with the observation time."""
    from .archive10 import save
    now = pd.Timestamp.now(tz="UTC")
    m = match_games(game_markets("open"), games)
    if m.empty:
        return pd.DataFrame()
    m["mid"] = np.where(m["yes_bid"].notna() & m["yes_ask"].notna() & (m["yes_bid"] > 0), (m["yes_bid"] + m["yes_ask"]) / 2, m["last"])
    w = m.pivot_table(index=["gid", "kickoff_utc"], columns="side", values="mid", aggfunc="last").dropna().reset_index()
    w["p_home"] = w["home"] / (w["home"] + w["away"])
    w["overround"] = w["home"] + w["away"]
    w["observed_at"] = now
    save("kalshi", f"live_{now:%Y%m%d}", m.drop(columns=["kickoff_utc"]).astype(str).to_dict("records"),
         {"source": BASE, "series": SERIES, "retrieved_at": now.isoformat(), "timestamp_class": "T1 observed (lab retrieval time)"})
    return w
