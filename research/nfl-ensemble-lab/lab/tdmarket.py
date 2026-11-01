"""Our anytime-touchdown chance against Kalshi's anytime-touchdown price (series KXNFLTD, "Player: 1+ touchdowns"), for the Market value tab.

Kalshi access is read-only public market data ($0, no trading). Prices are fetched live, kept 60 seconds, and each fetch (at most one every
ten minutes) is appended to data/cache/props_kalshi/td_snapshots.jsonl with our chance beside it, so that after the games the picks can be
scored (scripts/td_value_check.py). No touchdown prices were archived before this, so nothing here has been checked against results yet.

Edge is for buying YES at the ask: our chance minus the ask minus Kalshi's fee, taken as 7% x ask x (1 - ask) per contract (the published
formula before rounding up to the cent). A positive edge means OUR number is higher than the market's, not that the bet wins.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime, timezone

from . import gamecenter_data as D
from . import kalshi as K
from . import rankings as R
from .config import CACHE_DIR
from .ingest import normalize_team

SERIES = "KXNFLTD"
SNAP = CACHE_DIR / "props_kalshi" / "td_snapshots.jsonl"
FEE = 0.07
MAX_SPREAD = 0.06          # a wider bid-ask gap is treated as no real price
VALUE_EDGE, MIN_CHANCE = 0.04, 0.12
SNAP_EVERY = 600.0
SUFFIX = {"jr", "sr", "ii", "iii", "iv", "v"}
_LIVE: dict = {}


def name_key(name: str) -> tuple[str, str]:
    """(first initial, last name) in plain lowercase letters, suffixes dropped."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    parts = [p for p in re.sub(r"[^a-z ]", " ", s).split() if p not in SUFFIX]
    return (parts[0][:1], parts[-1]) if parts else ("", "")


def _team(code: str) -> str | None:
    try:
        return normalize_team(code)
    except Exception:
        return None


def player_team(event: str, who: str) -> str | None:
    """The player's team in our convention from Kalshi's event ('26NOV01ATLTB': two team codes run together, away first) and the player part
    of the ticker ('ATLBROBINSON7': his team code, first initial, last name, number). Only splits where both halves are real teams count."""
    codes = re.sub(r"^\d{2}[A-Z]{3}\d{2}", "", event)
    for i in range(2, len(codes) - 1):
        a, b = codes[:i], codes[i:]
        if _team(a) and _team(b):
            for c in sorted((a, b), key=len, reverse=True):
                if who.startswith(c):
                    return _team(c)
    return None


def fee(ask: float) -> float:
    return FEE * ask * (1 - ask)


def read_markets() -> list[dict]:
    """Open anytime-touchdown (1+) markets: player name, team code in our convention, bid, ask, last, 24-hour volume. Cached 60 seconds."""
    hit = _LIVE.get("m")
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    d = K._get(f"/markets?series_ticker={SERIES}&status=open&limit=1000")
    out = []
    for m in d.get("markets", []):
        t = m["ticker"].split("-")
        if len(t) != 4 or t[3] != "1":
            continue
        name = (m.get("yes_sub_title") or m.get("title") or "").split(":")[0].strip()
        team = player_team(t[1], t[2])
        bid, ask = K._f(m.get("yes_bid_dollars")), K._f(m.get("yes_ask_dollars"))
        out.append({"ticker": m["ticker"], "player": name, "team": team, "bid": bid, "ask": ask, "last": K._f(m.get("last_price_dollars")),
                    "vol24": K._f(m.get("volume_24h_fp")) or 0.0})
    _LIVE["m"] = (time.time(), out)
    return out


def verdict(ours: float, bid: float | None, ask: float | None) -> dict:
    """Edge and a plain label for one player."""
    if ask is None or ask <= 0 or ask >= 1 or (bid is not None and ask - bid > MAX_SPREAD) or bid is None:
        return {"edge": None, "edge_after_fee": None, "label": "No real price", "mid": None if bid is None or ask is None else (bid + ask) / 2}
    gross = ours - ask
    net = gross - fee(ask)
    if net >= VALUE_EDGE and ours >= MIN_CHANCE:
        label = "Our number is well above the price"
    elif net > 0:
        label = "Slightly above the price"
    elif net > -VALUE_EDGE:
        label = "About fair"
    else:
        label = "Price is above our number"
    return {"edge": gross, "edge_after_fee": net, "label": label, "mid": (bid + ask) / 2, "value": bool(net >= VALUE_EDGE and ours >= MIN_CHANCE)}


def week_market(week: int) -> dict:
    """Every player in the week's remaining games with our chance, the Kalshi bid and ask, and the edge; sorted by edge after fees."""
    rk = R.week_rankings(week)
    mk = read_markets()
    by = {}
    for m in mk:
        k = (m["team"], *name_key(m["player"]))
        by.setdefault(k, []).append(m)
    rows, matched = [], 0
    for r in rk.get("all_td", []):
        k = (r["team"], *name_key(r["player"]))
        ms = by.get(k)
        if not ms or len(ms) > 1:
            rows.append({**_pick(r), "market": None})
            continue
        m = ms[0]
        matched += 1
        rows.append({**_pick(r), "market": {k2: m[k2] for k2 in ("ticker", "bid", "ask", "last", "vol24")}, **verdict(r["projection"], m["bid"], m["ask"])})
    priced = [r for r in rows if r.get("edge_after_fee") is not None]
    priced.sort(key=lambda r: -r["edge_after_fee"])
    unpriced = [r for r in rows if r.get("edge_after_fee") is None and r["projection"] >= 0.15]
    unpriced.sort(key=lambda r: -r["projection"])
    _snapshot(week, rows)
    return {"week": week, "fee_rate": FEE, "value_edge": VALUE_EDGE, "min_chance": MIN_CHANCE, "markets_open": len(mk), "players": len(rows), "matched": matched,
            "rows": priced, "unpriced": unpriced[:40], "built_at": time.time()}


def _pick(r: dict) -> dict:
    return {"player": r["player"], "team": r["team"], "opp": r["opp"], "home": r["home"], "gid": r["gid"], "kickoff_utc": r["kickoff_utc"], "pos": r.get("pos"),
            "projection": r["projection"], "score": r["score"], "tags": r.get("tags", [])}


def _snapshot(week: int, rows: list[dict]) -> None:
    """Append what was shown, at most once every ten minutes, so the picks can be scored after the games."""
    try:
        SNAP.parent.mkdir(parents=True, exist_ok=True)
        if SNAP.exists() and time.time() - SNAP.stat().st_mtime < SNAP_EVERY:
            return
        keep = [{"ticker": r["market"]["ticker"], "player": r["player"], "team": r["team"], "gid": r["gid"], "ours": round(r["projection"], 4),
                 "bid": r["market"]["bid"], "ask": r["market"]["ask"], "last": r["market"]["last"], "vol24": r["market"]["vol24"]} for r in rows if r.get("market")]
        with SNAP.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": datetime.now(timezone.utc).isoformat(), "week": week, "rows": keep}) + "\n")
    except OSError:
        pass
