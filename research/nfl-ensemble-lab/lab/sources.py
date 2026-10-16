"""Verified free data sources, cached downloads and provenance tracking.

Source audit (verified 2026-10-16, see docs/DATA_SOURCES.md):
  * nflverse/nfldata games.csv: schedule, scores, rest, starting QBs, roof,
    closing-consensus spread / moneyline / total. Primary schedule source.
  * nflverse-data release `pbp`: play_by_play_{season}.parquet (nflfastR
    EPA / success / WP). Primary statistics source.
  * api.nfldata.org: public read-only FastAPI that re-serves the nflverse
    "gold layer". It is a DERIVATIVE of nflverse, so it is used only as an
    independent-transport cross-check of final scores, never as a second
    source of evidence.
  * thadhutch/nfl-data-pipeline (now sports-quant): scrapes PFF grades
    (subscription) and Pro-Football-Reference pages. Not integrated: paid
    inputs and scraping, and its PFR data duplicates nflverse.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import RAW_DIR

USER_AGENT = "GOING-nfl-ensemble-lab/1.0 (research; local)"
GAMES_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
NFLDATA_API = "https://api.nfldata.org/v1"
MANIFEST = RAW_DIR / "manifest.json"
# The schedule and the live season's play-by-play change; refresh them after this age.
LIVE_MAX_AGE_HOURS = 6

Progress = Callable[[str], None]


@dataclass(frozen=True)
class SourceInfo:
    key: str
    name: str
    url: str
    role: str
    independent: bool
    integrated: bool
    notes: str


SOURCES = (
    SourceInfo("nfldata_games", "nflverse/nfldata games.csv", GAMES_URL,
               "schedule, results, rest, starting QBs, closing lines", True, True,
               "Lines are closing consensus without timestamps: benchmark only, never a model input."),
    SourceInfo("nflverse_pbp", "nflverse-data pbp release", PBP_URL.format(season="{season}"),
               "play-by-play EPA, success, yardage, turnovers", True, True,
               "nflfastR EPA model is fit on historical data; treated as a pregame-safe derived stat "
               "because only games before kickoff are aggregated."),
    SourceInfo("nfldata_api", "api.nfldata.org", NFLDATA_API,
               "cross-check of final scores", False, True,
               "Re-serves nflverse; agreement is a transport check, not independent confirmation."),
    SourceInfo("nflverse_injuries", "nflverse-data injuries release", "https://github.com/nflverse/nflverse-data/releases/tag/injuries",
               "weekly injury reports", True, False,
               "Excluded: report rows carry modification dates that can postdate kickoff."),
    SourceInfo("nflverse_ftn", "nflverse-data ftn_charting release", "https://github.com/nflverse/nflverse-data/releases/tag/ftn_charting",
               "charting incl. pressure", True, False,
               "Excluded in Phase 1: coverage starts 2022 only, so pressure rate cannot span 2016+."),
    SourceInfo("thadhutch", "thadhutch/nfl-data-pipeline (sports-quant)", "https://github.com/thadhutch/nfl-data-pipeline",
               "PFF grades + PFR scraping", False, False,
               "Not integrated: PFF requires a subscription; PFR data duplicates nflverse."),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def _save_manifest(manifest: dict) -> None:
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(MANIFEST)


def _fetch(url: str, timeout: int = 120, retries: int = 3) -> tuple[bytes, dict]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return resp.read(), headers
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise FileNotFoundError(f"Source returned 404: {url}") from exc
            last = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
        time.sleep(2 * (attempt + 1))
    raise ConnectionError(f"Download failed after {retries} attempts: {url} ({last})")


def _is_fresh(entry: dict | None, max_age_hours: float | None) -> bool:
    if not entry:
        return False
    if max_age_hours is None:
        return True
    age = datetime.now(timezone.utc) - datetime.fromisoformat(entry["downloaded_at"])
    return age.total_seconds() < max_age_hours * 3600


def download(key: str, url: str, dest: Path, *, max_age_hours: float | None,
             force: bool = False, validate: Callable[[bytes], None] | None = None,
             progress: Progress = print) -> dict:
    """Download url to dest unless a fresh cached copy exists; record provenance."""
    manifest = load_manifest()
    entry = manifest.get(key)
    if not force and dest.exists() and _is_fresh(entry, max_age_hours):
        return entry | {"cached": True}
    progress(f"Downloading {key} ...")
    body, headers = _fetch(url)
    if validate:
        validate(body)
    sha = hashlib.sha256(body).hexdigest()
    changed = not entry or entry.get("sha256") != sha
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    entry = {
        "key": key, "url": url, "path": dest.name, "bytes": len(body), "sha256": sha,
        "downloaded_at": _now(), "last_modified": headers.get("last-modified"),
        "etag": headers.get("etag"), "changed_since_previous": changed,
    }
    manifest[key] = entry
    _save_manifest(manifest)
    progress(f"  {key}: {len(body)/1e6:.1f} MB ({'updated' if changed else 'unchanged'})")
    return entry | {"cached": False}


def _validate_games_csv(body: bytes) -> None:
    head = body[:600].decode("utf-8", "replace").splitlines()[0]
    for col in ("game_id", "season", "home_team", "away_team", "home_score", "spread_line"):
        if col not in head.split(","):
            raise ValueError(f"games.csv schema changed: missing {col}")


def _validate_parquet(body: bytes) -> None:
    if body[:4] != b"PAR1" or body[-4:] != b"PAR1":
        raise ValueError("Downloaded play-by-play file is not a parquet file")


def download_games(force: bool = False, progress: Progress = print) -> dict:
    return download("nfldata_games", GAMES_URL, RAW_DIR / "games.csv",
                    max_age_hours=LIVE_MAX_AGE_HOURS, force=force,
                    validate=_validate_games_csv, progress=progress)


def download_pbp(season: int, live: bool, force: bool = False, progress: Progress = print) -> dict:
    """Completed seasons are cached permanently; the live season refreshes."""
    return download(f"nflverse_pbp_{season}", PBP_URL.format(season=season),
                    RAW_DIR / f"play_by_play_{season}.parquet",
                    max_age_hours=LIVE_MAX_AGE_HOURS if live else None, force=force,
                    validate=_validate_parquet, progress=progress)


def fetch_api_games(season: int, progress: Progress = print) -> list[dict]:
    """Page through api.nfldata.org /v1/games for one season (cross-check only)."""
    rows: list[dict] = []
    offset = 0
    while True:
        body, _ = _fetch(f"{NFLDATA_API}/games?season={season}&limit=500&offset={offset}", timeout=60)
        page = json.loads(body)
        rows.extend(page.get("data", []))
        offset += page.get("limit", 500)
        if offset >= page.get("total", 0) or not page.get("data"):
            return rows
