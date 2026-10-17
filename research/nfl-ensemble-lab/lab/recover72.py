"""Phase 7.2: recovering timestamp-verifiable historical injury reports (2025 and early 2026).

Two routes, both with an EXTERNAL timestamp that proves the report existed before kickoff:
  1. Internet Archive captures of https://www.nfl.com/injuries/ (capture time = verifiable availability).
  2. GOING's git history of data/injury_context.json (read-only `git show`; availability = commit time of
     the CI bot's data refresh; GOING history begins 2026-08, so this route cannot reach 2025).
Our own retrieval time is never used as a publication time. Recovered rows are stored separately and are
NOT fed to any model: coverage is too sparse for training, and the champion stays frozen.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone

import pandas as pd

from . import extra_sources as X
from . import sources
from .config import CACHE_DIR, LAB_ROOT, RAW_DIR

WAYBACK_DIR = RAW_DIR / "archive" / "wayback"
OUT = CACHE_DIR / "recovered_injury_rows.parquet"
CDX = "https://web.archive.org/cdx/search/cdx?url=www.nfl.com/injuries/&from={y}0801&to={y2}0215&output=json&fl=timestamp,statuscode&filter=statuscode:200"
RAW = "https://web.archive.org/web/{ts}id_/https://www.nfl.com/injuries/"
GOING_ROOT = LAB_ROOT.parents[1]


def wayback_captures(season: int) -> list[str]:
    body, _ = sources._fetch(CDX.format(y=season, y2=season + 1), timeout=90)
    rows = json.loads(body)
    return [r[0] for r in rows[1:]]


def fetch_wayback(season: int, progress=print) -> pd.DataFrame:
    WAYBACK_DIR.mkdir(parents=True, exist_ok=True)
    parts = []
    for ts in wayback_captures(season):
        f = WAYBACK_DIR / f"nflcom_{ts}.html"
        if not f.exists():
            import gzip
            body, _ = sources._fetch(RAW.format(ts=ts), timeout=120)
            if body[:2] == b"\x1f\x8b":
                body = gzip.decompress(body)
            f.write_bytes(body)
            time.sleep(2)                         # polite to the archive
        rep, s, w = X.parse_nflcom(f.read_text(encoding="utf-8", errors="replace"))
        if rep.empty or s != season:
            continue
        at = pd.Timestamp(datetime.strptime(ts, "%Y%m%d%H%M%S"), tz="UTC")
        parts.append(rep.assign(available_at=at, source=f"Internet Archive capture {ts}"))
        progress(f"  capture {ts}: week {w}, {len(rep)} rows")
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def going_history(season: int = 2026) -> pd.DataFrame:
    """Every committed version of GOING's injury_context.json (read-only)."""
    log = subprocess.run(["git", "-C", str(GOING_ROOT), "log", "--all", "--format=%H %cI", "--", "data/injury_context.json"],
                         capture_output=True, text=True, check=True).stdout.split()
    parts = []
    for sha, when in zip(log[0::2], log[1::2]):
        raw = subprocess.run(["git", "-C", str(GOING_ROOT), "show", f"{sha}:data/injury_context.json"], capture_output=True, text=True)
        if raw.returncode:
            continue
        try:
            d = json.loads(raw.stdout)
        except json.JSONDecodeError:
            continue
        if d.get("season") != season:
            continue
        rows = [{"season": season, "week": r.get("week"), "team": r.get("team"), "gsis_id": r.get("gsis_id"), "full_name": r.get("name"),
                 "report_status": r.get("report_status"), "practice_status": r.get("practice_status")} for r in d.get("current_reports", {}).values()]
        parts.append(pd.DataFrame(rows).assign(available_at=pd.Timestamp(when).tz_convert("UTC"), source=f"GOING commit {sha[:10]}"))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def coverage(rec: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Per game: is there a recovered report for its week, with game statuses, captured before kickoff?"""
    if rec.empty:
        return pd.DataFrame()
    out = []
    for g in games.itertuples(index=False):
        r = rec[(rec["season"] == g.season) & (rec["week"] == g.week) & (rec["available_at"] < g.kickoff_utc)]
        fin = r[r["report_status"].isin(["Out", "Doubtful", "Questionable"])]
        out.append({"game_id": g.game_id, "season": g.season, "week": g.week, "kickoff_utc": g.kickoff_utc,
                    "recovered_before_kickoff": len(r) > 0, "with_game_statuses": len(fin) > 0,
                    "latest_source": r.sort_values("available_at")["source"].iloc[-1] if len(r) else None,
                    "hours_before_kickoff": round((g.kickoff_utc - r["available_at"].max()).total_seconds() / 3600, 1) if len(r) else None})
    return pd.DataFrame(out)


def run(progress=print) -> dict:
    from .data_pipeline import GAMES_TABLE
    games = pd.read_parquet(GAMES_TABLE)
    res = {}
    parts = []
    try:
        w = fetch_wayback(2025, progress)
        if len(w):
            w = X.map_gsis(w, X.weekly_rosters(2025))
            parts.append(w)
    except Exception as exc:
        res["wayback_error"] = repr(exc)[:200]
    try:
        gh = going_history(2026)
        if len(gh):
            parts.append(gh)
    except Exception as exc:
        res["going_error"] = repr(exc)[:200]
    rec = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if len(rec):
        rec.to_parquet(OUT, index=False)
    cov = coverage(rec, games[games["season"].isin([2025, 2026]) & (games["game_type"] == "REG")]) if len(rec) else pd.DataFrame()
    if len(cov):
        cov.to_csv(CACHE_DIR / "recovered_injury_coverage.csv", index=False)
        res["coverage"] = cov.groupby("season")[["recovered_before_kickoff", "with_game_statuses"]].mean().round(3).to_dict("index")
        res["games"] = cov.groupby("season").size().to_dict()
    res["rows"] = int(len(rec))
    res["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return res
