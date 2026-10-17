"""Phase 7 additional free 2026 sources (monitoring only unless stated otherwise).

  * nflverse weekly rosters  - weekly status per player (ACT / RES / INA / DEV) and depth position.
  * Sleeper players feed     - injury status, practice participation, depth order, news timestamp.
  * NFL.com injury report    - official report as published on NFL.com (same content as the
                               nflverse injury file, usually available sooner).

Every fetch is archived with its retrieval time (a new file only when content changes) and logged
to data/source_health.jsonl. None of these feeds a model: they have no historical as-of archive.
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import re
from datetime import datetime, timezone

import pandas as pd

from . import sources
from .config import DATA_DIR, RAW_DIR

ARCHIVE = RAW_DIR / "archive" / "phase7"
HEALTH = DATA_DIR / "source_health.jsonl"
ROSTER_URL = "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_{season}.parquet"
SLEEPER_URL = "https://api.sleeper.app/v1/players/nfl"
NFLCOM_URL = "https://www.nfl.com/injuries/"
SLEEPER_MAX_AGE_H = 24          # Sleeper asks clients to call the players endpoint at most daily
SLEEPER_FIELDS = ["player_id", "gsis_id", "full_name", "team", "position", "status", "injury_status", "injury_body_part",
                  "practice_participation", "depth_chart_position", "depth_chart_order", "news_updated"]
NICK = {"Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR", "Bears": "CHI",
        "Bengals": "CIN", "Browns": "CLE", "Cowboys": "DAL", "Broncos": "DEN", "Lions": "DET", "Packers": "GB",
        "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX", "Chiefs": "KC", "Raiders": "LV", "Chargers": "LAC",
        "Rams": "LA", "Dolphins": "MIA", "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG",
        "Jets": "NYJ", "Eagles": "PHI", "Steelers": "PIT", "49ers": "SF", "Seahawks": "SEA", "Buccaneers": "TB",
        "Titans": "TEN", "Commanders": "WAS"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def log_health(source: str, ok: bool, rows: int = 0, error: str | None = None, **extra) -> dict:
    e = {"source": source, "ok": bool(ok), "rows": int(rows), "checked_at": _now().isoformat(timespec="seconds"),
         "error": (error or None) and str(error)[:300]} | extra
    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    with HEALTH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e) + "\n")
    return e


def source_health() -> pd.DataFrame:
    """Latest check and latest success per Phase 7 source."""
    if not HEALTH.exists():
        return pd.DataFrame(columns=["source", "last_check", "last_ok", "ok", "rows", "error", "failures_24h"])
    h = pd.DataFrame([json.loads(x) for x in HEALTH.read_text(encoding="utf-8").splitlines() if x.strip()])
    h["checked_at"] = pd.to_datetime(h["checked_at"], utc=True)
    out = []
    for s, d in h.groupby("source"):
        last, good = d.iloc[-1], d[d["ok"]]
        out.append({"source": s, "last_check": last["checked_at"], "last_ok": good["checked_at"].max() if len(good) else pd.NaT,
                    "ok": bool(last["ok"]), "rows": int(last["rows"]), "error": last.get("error"),
                    "failures_24h": int((~d["ok"] & (d["checked_at"] > _now() - pd.Timedelta(hours=24))).sum())})
    return pd.DataFrame(out)


def _archive(kind: str, body: bytes, ext: str) -> tuple[str, bool]:
    """Write body once per distinct content; returns (path, is_new)."""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(body).hexdigest()[:12]
    existing = list(ARCHIVE.glob(f"{kind}_*_{h}.{ext}"))
    if existing:
        return str(existing[0]), False
    p = ARCHIVE / f"{kind}_{_now().strftime('%Y%m%dT%H%M%SZ')}_{h}.{ext}"
    p.write_bytes(body)
    return str(p), True


def _latest(kind: str, ext: str):
    files = sorted(ARCHIVE.glob(f"{kind}_*.{ext}"))
    return files[-1] if files else None


def retrieved_at(path) -> pd.Timestamp:
    return pd.Timestamp(datetime.strptime(path.stem.split("_")[-2], "%Y%m%dT%H%M%SZ"), tz="UTC")


# --------------------------------------------------------------------------- weekly rosters

def fetch_weekly_rosters(season: int) -> dict:
    try:
        e = sources.download(f"nflverse_roster_weekly_{season}", ROSTER_URL.format(season=season),
                             RAW_DIR / f"roster_weekly_{season}.parquet", max_age_hours=6,
                             validate=sources._validate_parquet, progress=lambda m: None)
        d = pd.read_parquet(RAW_DIR / f"roster_weekly_{season}.parquet")
        return log_health("nflverse weekly rosters", True, len(d), latest_week=int(d["week"].max()), sha=e.get("sha256", "")[:12])
    except Exception as exc:
        return log_health("nflverse weekly rosters", False, error=repr(exc))


def weekly_rosters(season: int) -> pd.DataFrame:
    p = RAW_DIR / f"roster_weekly_{season}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


# --------------------------------------------------------------------------- Sleeper

def fetch_sleeper(force: bool = False) -> dict:
    last = _latest("sleeper_players", "parquet")
    if last is not None and not force and _now() - retrieved_at(last) < pd.Timedelta(hours=SLEEPER_MAX_AGE_H):
        return log_health("Sleeper players", True, len(pd.read_parquet(last)), note="cached (daily limit)")
    try:
        body, _ = sources._fetch(SLEEPER_URL, timeout=120)
        raw = json.loads(body)
        d = pd.DataFrame([{k: v.get(k) for k in SLEEPER_FIELDS} for v in raw.values() if v.get("team")])
        d = d[d["position"].isin(["QB", "RB", "WR", "TE", "K", "OL", "OT", "G", "C", "DL", "DE", "DT", "LB", "CB", "S", "DB"])]
        buf = io.BytesIO()
        d.sort_values("player_id").reset_index(drop=True).to_parquet(buf, index=False)
        path, new = _archive("sleeper_players", buf.getvalue(), "parquet")
        return log_health("Sleeper players", True, len(d), new_snapshot=new)
    except Exception as exc:
        return log_health("Sleeper players", False, error=repr(exc))


def sleeper_latest() -> tuple[pd.DataFrame, pd.Timestamp | None]:
    p = _latest("sleeper_players", "parquet")
    return (pd.read_parquet(p), retrieved_at(p)) if p is not None else (pd.DataFrame(columns=SLEEPER_FIELDS), None)


# --------------------------------------------------------------------------- NFL.com official report

_TAG = re.compile(r"<[^>]+>")


def parse_nflcom(text: str) -> tuple[pd.DataFrame, int | None, int | None]:
    """Team blocks: <div class="d3-o-section-sub-title"><span>Nickname</span></div> followed by a table."""
    m = re.search(r"Week (\d+) of the (\d{4}) Season", text)
    week, season = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    rows = []
    for nick, tbl in re.findall(r'd3-o-section-sub-title"\s*>\s*<span>\s*([^<]+?)\s*</span>.*?(<table.*?</table>)', text, flags=re.S):
        team = NICK.get(html.unescape(nick).strip())
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, flags=re.S)[1:]:
            c = [html.unescape(_TAG.sub("", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
            if len(c) >= 5:
                rows.append({"season": season, "week": week, "team": team, "full_name": c[0], "position": c[1],
                             "injury": c[2] or None, "practice_status": c[3] or None, "report_status": c[4] or None})
    return pd.DataFrame(rows), season, week


def _norm(n) -> str:
    n = re.sub(r"[^a-z ]", "", str(n).lower().replace("-", " "))
    return re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n).strip()


def map_gsis(rep: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    """Name + team -> gsis_id via the weekly roster (same week if present, else latest)."""
    if not len(rep) or not len(roster):
        return rep.assign(gsis_id=None)
    r = roster[roster["season"] == rep["season"].iloc[0]]
    r = r.sort_values("week").drop_duplicates(["team", "full_name"], keep="last")
    key = dict(zip(zip(r["team"], r["full_name"].map(_norm)), r["gsis_id"]))
    return rep.assign(gsis_id=[key.get((t, _norm(n))) for t, n in zip(rep["team"], rep["full_name"])])


def fetch_nflcom() -> dict:
    try:
        body, _ = sources._fetch(NFLCOM_URL, timeout=60)
        rep, season, week = parse_nflcom(body.decode("utf-8", "replace"))
        if not len(rep):
            raise ValueError("no report rows parsed (page layout may have changed)")
        rep = map_gsis(rep, weekly_rosters(season))
        buf = io.BytesIO()
        rep.to_parquet(buf, index=False)
        _, new = _archive("nflcom_injuries", buf.getvalue(), "parquet")
        return log_health("NFL.com injury report", True, len(rep), season=season, week=week, new_snapshot=new,
                          teams=int(rep["team"].nunique()), gsis_match_rate=round(float(rep["gsis_id"].notna().mean()), 3))
    except Exception as exc:
        return log_health("NFL.com injury report", False, error=repr(exc))


def nflcom_latest() -> tuple[pd.DataFrame, pd.Timestamp | None]:
    p = _latest("nflcom_injuries", "parquet")
    return (pd.read_parquet(p), retrieved_at(p)) if p is not None else (pd.DataFrame(), None)


# --------------------------------------------------------------------------- QB source agreement (monitoring)

def qb_sources(season: int, week: int) -> pd.DataFrame:
    """Per team, every available QB signal with its timestamp. Agreement is descriptive only."""
    rows = []
    ro = weekly_rosters(season)
    ro = ro[(ro["position"] == "QB")] if len(ro) else ro
    sl, sl_t = sleeper_latest()
    sl = sl[sl["position"] == "QB"] if len(sl) else sl
    nf, nf_t = nflcom_latest()
    nf = nf[(nf["position"] == "QB") & (nf["week"] == week)] if len(nf) else nf
    for team in sorted(NICK.values()):
        r = {"team": team}
        s1 = sl[(sl["team"] == team) & (sl["depth_chart_order"] == 1)] if len(sl) else sl
        r["sleeper_qb1"] = s1["full_name"].iloc[0] if len(s1) else None
        r["sleeper_qb1_injury"] = s1["injury_status"].iloc[0] if len(s1) else None
        r["sleeper_retrieved"] = sl_t
        out = nf[(nf["team"] == team) & nf["report_status"].isin(["Out", "Doubtful"])] if len(nf) else nf
        r["nflcom_qbs_out_doubtful"] = ", ".join(out["full_name"]) if len(out) else ""
        r["nflcom_retrieved"] = nf_t
        rw = ro[(ro["team"] == team)] if len(ro) else ro
        if len(rw):
            lw = rw[rw["week"] == rw["week"].max()]
            r["roster_week"] = int(lw["week"].iloc[0])
            r["roster_qbs_unavailable"] = ", ".join(lw[lw["status"].isin(["RES", "INA"])]["full_name"])
        rows.append(r)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- Phase 7.2: weekly timeline & source priority

SOURCE_PRIORITY = ("NFL.com official report", "nflverse official report", "weekly roster (reserve/inactive)", "ESPN injuries")
PRIORITY_NOTE = ("Game status: the newest official report wins (NFL.com and nflverse carry the same league report; the later "
                 "retrieval is used). Reserve/IR comes from the weekly roster or an ESPN 'Injured Reserve' status. A verified inactive "
                 "exists only once ESPN/rosters mark the player inactive (about 90 minutes before kickoff). A player missing from a "
                 "report that exists is listed as 'not on report'; a team with no report is 'unknown', never 'healthy'.")


def report_timeline(season: int, week: int) -> pd.DataFrame:
    """Every archived official-report version for one week (NFL.com and nflverse), one row per player and version."""
    from .availability import ARCHIVE_DIR
    parts = []
    for f in sorted(ARCHIVE.glob("nflcom_injuries_*.parquet")):
        d = pd.read_parquet(f)
        d = d[(d["season"] == season) & (d["week"] == week)]
        if len(d):
            parts.append(d.assign(source="NFL.com official report", retrieved_at=retrieved_at(f)))
    for f in sorted(ARCHIVE_DIR.glob(f"nflverse_injuries_*.parquet")):
        d = pd.read_parquet(f)
        if "season" not in d or "week" not in d:
            continue
        d = d[(pd.to_numeric(d["season"]) == season) & (pd.to_numeric(d["week"]) == week)]
        if len(d):
            ts = pd.Timestamp(datetime.strptime(f.stem.split("_")[2], "%Y%m%dT%H%M%SZ"), tz="UTC")
            parts.append(d[["team", "full_name", "position", "report_status", "practice_status"]].assign(
                source="nflverse official report", retrieved_at=ts))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def source_lag(season: int, week: int, min_statuses: int = 50) -> pd.DataFrame:
    """First retrieval at which each source carried the week's game statuses (>= min_statuses Out/Doubtful/Questionable)."""
    t = report_timeline(season, week)
    if t.empty:
        return t
    g = t.groupby(["source", "retrieved_at"])["report_status"].apply(lambda s: int(s.isin(["Out", "Doubtful", "Questionable"]).sum()))
    g = g.reset_index(name="game_statuses")
    first = g[g["game_statuses"] >= min_statuses].groupby("source")["retrieved_at"].min()
    return g.assign(first_with_statuses=g["source"].map(first))


def status_changes(season: int, week: int) -> pd.DataFrame:
    """Players whose game or practice status changed between consecutive versions of the same source."""
    t = report_timeline(season, week)
    if t.empty:
        return t
    rows = []
    for (src, team, name), d in t.sort_values("retrieved_at").groupby(["source", "team", "full_name"]):
        prev = None
        for r in d.itertuples(index=False):
            cur = (r.report_status, r.practice_status)
            if prev is not None and cur != prev:
                rows.append({"source": src, "team": team, "player": name, "at": r.retrieved_at, "from": " / ".join(map(str, prev)),
                             "to": " / ".join(map(str, cur))})
            prev = cur
    return pd.DataFrame(rows)
