"""Phase 8.1 market data (research + prospective archive). See docs/PHASE8_1_PREREGISTRATION.md for timestamp classes.

T1 timestamp-verified pregame: GOING nfl_betting.json git history (per-book last_update), lab stage snapshots,
   prospective ESPN/DraftKings archive (retrieval time).
T2 opening, time unrecorded: Sportsbook Review archive opening spread/total (2007-2021).
T3 closing, untimestamped: nfldata games.csv and SBR closing prices.
Market data never enters the frozen champion's inputs.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess

import numpy as np
import pandas as pd

from .config import ARTIFACTS_DIR, CACHE_DIR, LAB_ROOT, RAW_DIR

MKT_RAW = RAW_DIR / "market"
MKT_ARCHIVE = RAW_DIR / "archive" / "market"
OUT = ARTIFACTS_DIR / "phase81"
SBR_URL = "https://www.sportsbookreviewsonline.com/scoresoddsarchives/nfl-odds-{a}-{b}"
GOING_ROOT = LAB_ROOT.parents[1]

SBR_TEAMS = {"Arizona": "ARI", "Atlanta": "ATL", "Baltimore": "BAL", "Buffalo": "BUF", "Carolina": "CAR", "Chicago": "CHI",
             "Cincinnati": "CIN", "Cleveland": "CLE", "Dallas": "DAL", "Denver": "DEN", "Detroit": "DET", "GreenBay": "GB",
             "Houston": "HOU", "Indianapolis": "IND", "Jacksonville": "JAX", "KansasCity": "KC", "Kansas": "KC", "LVRaiders": "LV",
             "LasVegas": "LV", "Oakland": "LV", "LAChargers": "LAC", "SanDiego": "LAC", "LARams": "LA", "LosAngeles": "LA", "St.Louis": "LA",
             "Miami": "MIA", "Minnesota": "MIN", "NewEngland": "NE", "NewOrleans": "NO", "NYGiants": "NYG", "NYJets": "NYJ",
             "Philadelphia": "PHI", "Pittsburgh": "PIT", "SanFrancisco": "SF", "Seattle": "SEA", "TampaBay": "TB", "Tennessee": "TEN",
             "Washington": "WAS", "Washingtom": "WAS", "HoustonTexans": "HOU", "KCChiefs": "KC", "LosAngelesRams": "LA",
             "LosAngelesChargers": "LAC", "Tampa": "TB"}
NAME_TO_ABBR = {"Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
                "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
                "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
                "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
                "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA",
                "Minnesota Vikings": "MIN", "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
                "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
                "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS"}


# --------------------------------------------------------------------------- odds math

def american_to_prob(o):
    o = np.asarray(o, float)
    return np.where(o < 0, -o / (-o + 100), 100 / (o + 100))


def novig(p_home_raw, p_away_raw, method: str = "multiplicative"):
    """Remove bookmaker margin. multiplicative: p/sum; additive: subtract half the overround; power: p^k with sum 1."""
    h, a = np.asarray(p_home_raw, float), np.asarray(p_away_raw, float)
    if method == "multiplicative":
        return h / (h + a)
    if method == "additive":
        over = h + a - 1
        return np.clip(h - over / 2, 1e-4, 1 - 1e-4)
    if method == "power":
        out = np.full(h.shape, np.nan)
        for i, (x, y) in enumerate(zip(h.ravel(), a.ravel())):
            if not (np.isfinite(x) and np.isfinite(y)):
                continue
            lo, hi = 0.5, 3.0
            for _ in range(60):
                k = (lo + hi) / 2
                lo, hi = (k, hi) if x ** k + y ** k > 1 else (lo, k)
            out.ravel()[i] = x ** k
        return out
    raise ValueError(method)


# --------------------------------------------------------------------------- T2/T3: Sportsbook Review archive

def _sbr_page(season: int) -> str:
    MKT_RAW.mkdir(parents=True, exist_ok=True)
    p = MKT_RAW / f"sbr_{season}.html"
    if not p.exists():
        from . import sources
        body, _ = sources._fetch(SBR_URL.format(a=season, b=str(season + 1)[2:]), timeout=90)
        p.write_bytes(body)
    return p.read_text(encoding="utf-8", errors="replace")


def _num(x):
    x = str(x).strip().lower()
    if x in ("pk", "p", "pick"):
        return 0.0
    try:
        return float(x)
    except ValueError:
        return np.nan


def sbr_season(season: int, games: pd.DataFrame) -> pd.DataFrame:
    s = _sbr_page(season)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", s, flags=re.S)
    cells = [[html.unescape(re.sub("<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.S)] for r in rows]
    cells = [c for c in cells if len(c) >= 12 and c[0] != "Date"]
    out, unmapped = [], set()
    g = games[games["season"] == season]
    for v, h in zip(cells[0::2], cells[1::2]):
        if v[2] not in ("V", "N") or h[2] not in ("H", "N"):
            continue
        tv, th = SBR_TEAMS.get(v[3].replace(" ", "")), SBR_TEAMS.get(h[3].replace(" ", ""))
        if not tv or not th:
            unmapped |= {v[3], h[3]}
            continue
        mmdd = v[0].zfill(4)
        yr = season + (1 if int(mmdd[:2]) <= 3 else 0)
        date = pd.Timestamp(f"{yr}-{mmdd[:2]}-{mmdd[2:]}")
        ov, cv, oh, ch = map(_num, (v[9], v[10], h[9], h[10]))
        # the smaller number in each column is the spread (owned by that row's team), the larger the total
        def split(a, b):
            if np.isnan(a) or np.isnan(b):
                return np.nan, np.nan, None
            return (a, b, "V") if a < b else (b, a, "H")
        so, to, fav_o = split(ov, oh)
        sc, tc, fav_c = split(cv, ch)
        home_spread_open = np.nan if fav_o is None else (so if fav_o == "H" else -so)      # + = home favoured by this many
        home_spread_close = np.nan if fav_c is None else (sc if fav_c == "H" else -sc)
        cand = g[(g["home_team"] == th) & (g["away_team"] == tv) &
                 ((g["kickoff_utc"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None) - date).abs() <= pd.Timedelta(days=1))]
        if cand.empty:
            cand = g[(g["home_team"] == tv) & (g["away_team"] == th) &              # neutral-site listing swapped
                     ((g["kickoff_utc"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None) - date).abs() <= pd.Timedelta(days=1))]
            if len(cand):
                home_spread_open, home_spread_close = -home_spread_open, -home_spread_close
                v, h = h, v
        if cand.empty:
            continue
        out.append({"game_id": cand["game_id"].iloc[0], "season": season, "sbr_home_spread_open": home_spread_open,
                    "sbr_home_spread_close": home_spread_close, "sbr_total_open": to, "sbr_total_close": tc,
                    "sbr_home_ml_close": _num(h[11]), "sbr_away_ml_close": _num(v[11]),
                    "timestamp_class_open": "T2 opening (time unrecorded)", "timestamp_class_close": "T3 closing (untimestamped)"})
    df = pd.DataFrame(out)
    df.attrs["unmapped"] = sorted(unmapped)
    return df


def sbr(seasons=range(2016, 2022), games=None) -> pd.DataFrame:
    from .data_pipeline import GAMES_TABLE
    games = games if games is not None else pd.read_parquet(GAMES_TABLE)
    parts, unm = [], set()
    for s in seasons:
        d = sbr_season(s, games)
        unm |= set(d.attrs.get("unmapped", []))
        parts.append(d)
    out = pd.concat(parts, ignore_index=True).drop_duplicates("game_id")
    out.attrs["unmapped"] = sorted(unm)
    return out


# --------------------------------------------------------------------------- T1: GOING git history (read-only)

def going_quotes() -> pd.DataFrame:
    """Every bookmaker quote in every committed version of GOING data/nfl_betting.json (read-only git show)."""
    log = subprocess.run(["git", "-C", str(GOING_ROOT), "log", "--all", "--format=%H %cI", "--", "data/nfl_betting.json"],
                         capture_output=True, text=True, check=True).stdout.split()
    rows = []
    for sha, when in zip(log[0::2], log[1::2]):
        raw = subprocess.run(["git", "-C", str(GOING_ROOT), "show", f"{sha}:data/nfl_betting.json"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        if raw.returncode:
            continue
        try:
            d = json.loads(raw.stdout)
        except json.JSONDecodeError:
            continue
        for ev in d.get("games_raw") or []:
            h, a = NAME_TO_ABBR.get(ev.get("home_team")), NAME_TO_ABBR.get(ev.get("away_team"))
            if not h or not a:
                continue
            for bk in ev.get("bookmakers") or []:
                for m in bk.get("markets") or []:
                    for o in m.get("outcomes") or []:
                        side = "home" if o.get("name") == ev.get("home_team") else "away" if o.get("name") == ev.get("away_team") else o.get("name")
                        rows.append({"commit": sha[:10], "committed_at": when, "commence_time": ev.get("commence_time"), "home": h, "away": a,
                                     "book": bk.get("key"), "market": m.get("key"), "side": side, "price": o.get("price"),
                                     "point": o.get("point"), "quote_time": m.get("last_update") or bk.get("last_update")})
    q = pd.DataFrame(rows)
    if q.empty:
        return q
    for c in ("committed_at", "commence_time", "quote_time"):
        q[c] = pd.to_datetime(q[c], utc=True, errors="coerce")
    q = q[q["quote_time"] < q["commence_time"]]                      # pregame quotes only
    q = q.drop_duplicates(["home", "away", "commence_time", "book", "market", "side", "quote_time", "price", "point"])
    q["timestamp_class"] = "T1 timestamp-verified (book last_update, committed by GOING CI)"
    return q


def going_h2h_consensus(q: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Per game and quote time: multi-book no-vig consensus home probability (median across books)."""
    g = games[["game_id", "home_team", "away_team", "kickoff_utc"]]
    q2 = q.drop_duplicates(["home", "away", "commence_time"])[["home", "away", "commence_time"]]
    m = q2.merge(g, left_on=["home", "away"], right_on=["home_team", "away_team"])
    m = m[(m["kickoff_utc"] - m["commence_time"]).abs() < pd.Timedelta(hours=36)]
    lookup = dict(zip(zip(m["home"], m["away"], m["commence_time"]), m["game_id"]))
    out = []
    for (hh, aa, ct), d in q[q["market"] == "h2h"].groupby(["home", "away", "commence_time"]):
        gid = lookup.get((hh, aa, ct))
        if gid is None:
            continue
        w = d.pivot_table(index=["book", "quote_time"], columns="side", values="price", aggfunc="last").dropna()
        if w.empty or not {"home", "away"} <= set(w.columns):
            continue
        w["p"] = novig(american_to_prob(w["home"]), american_to_prob(w["away"]))
        w = w.reset_index().sort_values("quote_time")
        for t, x in w.groupby("quote_time"):
            latest = w[w["quote_time"] <= t].groupby("book").tail(1)            # each book's latest quote as of t
            out.append({"game_id": gid, "quote_time": t, "books": int(latest["book"].nunique()), "p_home_consensus": float(latest["p"].median())})
    return pd.DataFrame(out).drop_duplicates(["game_id", "quote_time"])


# --------------------------------------------------------------------------- T1 prospective: ESPN / DraftKings archive

def espn_odds_rows(scoreboard: dict) -> list[dict]:
    rows = []
    for ev in scoreboard.get("events", []):
        for comp in ev.get("competitions", []):
            teams = {c.get("homeAway"): c.get("team", {}).get("abbreviation") for c in comp.get("competitors", [])}
            for o in comp.get("odds") or []:
                ml = o.get("moneyline") or {}
                ps = o.get("pointSpread") or {}
                tot = o.get("total") or {}
                rec = {"event_id": ev.get("id"), "kickoff": ev.get("date"), "home": teams.get("home"), "away": teams.get("away"),
                       "provider": (o.get("provider") or {}).get("name"), "details": o.get("details"),
                       "spread_current": o.get("spread"), "total_current": o.get("overUnder")}
                for side in ("home", "away"):
                    for when in ("open", "close"):
                        rec[f"{side}_ml_{when}"] = ((ml.get(side) or {}).get(when) or {}).get("odds")
                        rec[f"{side}_spread_{when}"] = ((ps.get(side) or {}).get(when) or {}).get("line")
                for when in ("open", "close"):
                    rec[f"over_{when}"] = ((tot.get("over") or {}).get(when) or {}).get("line")
                rows.append(rec)
    return rows


ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"


def archive_espn_odds(scoreboard: dict | None = None) -> dict:
    """Append-only: one immutable file per distinct odds content, named by OUR retrieval time (the source gives no
    quote time). One small request with a short timeout, made only after official forecasts are saved. Never raises."""
    try:
        if scoreboard is None:
            from . import sources
            body, _ = sources._fetch(ESPN_SCOREBOARD, timeout=15, retries=1)
            scoreboard = json.loads(body)
            scoreboard["retrieved_at"] = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
        sb = scoreboard
        rows = espn_odds_rows(sb)
        if not rows:
            return {"ok": False, "reason": "no odds in scoreboard"}
        body = json.dumps({"retrieved_at": sb.get("retrieved_at"), "source": "ESPN scoreboard odds (provider as listed)",
                           "timestamp_class": "T1 retrieval-time (lab)", "rows": rows}, sort_keys=True).encode()
        h = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:12]
        MKT_ARCHIVE.mkdir(parents=True, exist_ok=True)
        if list(MKT_ARCHIVE.glob(f"espn_odds_*_{h}.json")):
            return {"ok": True, "new": False}
        stamp = pd.Timestamp(sb.get("retrieved_at") or pd.Timestamp.now(tz="UTC")).strftime("%Y%m%dT%H%M%SZ")
        f = MKT_ARCHIVE / f"espn_odds_{stamp}_{h}.json"
        f.write_bytes(body)
        import os
        import stat
        os.chmod(f, stat.S_IREAD)
        return {"ok": True, "new": True, "rows": len(rows), "file": f.name}
    except Exception as exc:                          # market collection must never affect forecasting
        return {"ok": False, "reason": repr(exc)[:200]}


def espn_archive() -> pd.DataFrame:
    rows = []
    for f in sorted(MKT_ARCHIVE.glob("espn_odds_*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for r in d["rows"]:
            rows.append(r | {"retrieved_at": d.get("retrieved_at"), "file": f.name})
    return pd.DataFrame(rows)


def snapshot_markets() -> pd.DataFrame:
    """Market lines recorded inside the lab's immutable stage snapshots (nfldata line at data refresh time)."""
    import os
    from .config import SNAPSHOTS_DIR
    from .prospective import load_ledger
    led = load_ledger()
    rows = []
    for r in led.itertuples(index=False):
        try:
            s = json.loads((SNAPSHOTS_DIR / str(r.path).replace("\\", os.sep)).read_text(encoding="utf-8"))
        except Exception:
            continue
        m = s.get("market_at_snapshot") or {}
        rows.append({"game_id": r.game_id, "stage": s.get("stage") or s.get("window"), "predicted_at": s.get("predicted_at"),
                     "data_refreshed_at": (s.get("data_cutoff") or {}).get("data_refreshed_at"), "p_champion": s.get("p_champion"),
                     "spread_line": m.get("spread_line"), "p_home_novig": m.get("p_home_novig"), "home_ml": m.get("home_moneyline"),
                     "away_ml": m.get("away_moneyline")})
    return pd.DataFrame(rows)
