#!/usr/bin/env python3
"""
Builds the data the draft board reads.

  data/players.json          base player info, shared across every format
  data/formats/index.json    which formats are available
  data/formats/<id>.json     ADP + market values for one league format

Splitting it this way means adding a superflex league costs ~90KB, not a
second copy of every player's name and team. The browser loads the base file
once and then whichever format the active league needs.

Sources (all free, no keys):
  Sleeper       /v1/players/nfl        canonical IDs, team, position
  FFC           /api/v1/adp/<fmt>      consensus ADP + stdev + bye
  FantasyCalc   /values/current        market value, carries sleeperId

Formats are defined in FORMATS below, or overridden with a GRIDLINE_FORMATS
env var holding the same JSON shape.
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SEASON = int(os.environ.get("SEASON", "2026"))

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FORMAT_DIR = DATA / "formats"

KEEP_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
TEAM_FIXES = {"JAC": "JAX", "WSH": "WAS", "LAR": "LA", "OAK": "LV", "SD": "LAC", "STL": "LA"}

# id  -> what the two upstream sources need to be asked for.
# ffc:  standard | ppr | half-ppr | 2qb    (2qb is the closest public proxy
#       for superflex ADP — not identical, but it prices QBs correctly)
# ppr:  reception points, passed to FantasyCalc
# qbs:  1 = single QB, 2 = superflex / 2QB
FORMATS = [
    {"id": "ppr-12-1",  "label": "12-team PPR",            "ffc": "ppr",      "teams": 12, "ppr": 1,   "qbs": 1},
    {"id": "ppr-12-2",  "label": "12-team Superflex PPR",  "ffc": "2qb",      "teams": 12, "ppr": 1,   "qbs": 2},
    {"id": "half-12-1", "label": "12-team Half PPR",       "ffc": "half-ppr", "teams": 12, "ppr": 0.5, "qbs": 1},
    {"id": "half-12-2", "label": "12-team Superflex Half", "ffc": "2qb",      "teams": 12, "ppr": 0.5, "qbs": 2},
    {"id": "std-12-1",  "label": "12-team Standard",       "ffc": "standard", "teams": 12, "ppr": 0,   "qbs": 1},
    {"id": "ppr-10-1",  "label": "10-team PPR",            "ffc": "ppr",      "teams": 10, "ppr": 1,   "qbs": 1},
    {"id": "ppr-10-2",  "label": "10-team Superflex PPR",  "ffc": "2qb",      "teams": 10, "ppr": 1,   "qbs": 2},
    {"id": "ppr-14-1",  "label": "14-team PPR",            "ffc": "ppr",      "teams": 14, "ppr": 1,   "qbs": 1},
    {"id": "ppr-14-2",  "label": "14-team Superflex PPR",  "ffc": "2qb",      "teams": 14, "ppr": 1,   "qbs": 2},
]

if os.environ.get("GRIDLINE_FORMATS"):
    FORMATS = json.loads(os.environ["GRIDLINE_FORMATS"])


def get_json(url, tries=3, pause=2):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "goinglong-etl/2.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            last = exc
            if attempt < tries - 1:
                time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last}")


def normalize(name):
    """'A.J. Brown Jr.' -> 'ajbrown'. Must stay in sync with the JS copy."""
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().replace("'", "").replace("\u2019", "").replace(".", "").replace("-", " ")
    parts = [p for p in re.split(r"\s+", name) if p and p not in SUFFIXES]
    return re.sub(r"[^a-z0-9]", "", "".join(parts))


def fix_team(team):
    return TEAM_FIXES.get(team.upper(), team.upper()) if team else None


# ---------------------------------------------------------------- sources

def fetch_players():
    raw = get_json("https://api.sleeper.app/v1/players/nfl")
    players = {}
    for pid, p in raw.items():
        pos = p.get("position") or (p.get("fantasy_positions") or [None])[0]
        if pos not in KEEP_POSITIONS:
            continue
        if pos != "DEF" and not p.get("active"):
            continue
        name = p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        if not name:
            continue
        players[pid] = {
            "sleeper_id": pid,
            "name": name,
            "pos": pos,
            "team": fix_team(p.get("team")),
            "age": p.get("age"),
            "injury_status": p.get("injury_status"),
            "key": normalize(name),
        }
    print(f"sleeper: {len(players)} fantasy-relevant players")
    return players


_ADP_CACHE = {}
_VAL_CACHE = {}


def fetch_adp(ffc_format, teams):
    ck = (ffc_format, teams)
    if ck in _ADP_CACHE:
        return _ADP_CACHE[ck]
    url = (f"https://fantasyfootballcalculator.com/api/v1/adp/{ffc_format}"
           f"?teams={teams}&year={SEASON}&position=all")
    try:
        payload = get_json(url)
        rows = payload.get("players", []) if isinstance(payload, dict) else []
    except RuntimeError as exc:
        print(f"  ! ADP fetch failed ({ffc_format}/{teams}): {exc}")
        rows = []
    out = {}
    for r in rows:
        key = normalize(r.get("name"))
        if key:
            out[(key, (r.get("position") or "").upper())] = {
                "adp": r.get("adp"),
                "sd": r.get("stdev"),
                "bye": r.get("bye"),
                "n": r.get("times_drafted"),
                # earliest / latest he's actually gone. "hi" is his optimistic
                # market outcome, which the board uses for the guide's
                # "will this player burn me?" test.
                "hi": r.get("high"),
                "lo": r.get("low"),
            }
    _ADP_CACHE[ck] = out
    return out


def fetch_values(teams, ppr, qbs):
    ck = (teams, ppr, qbs)
    if ck in _VAL_CACHE:
        return _VAL_CACHE[ck]
    url = ("https://api.fantasycalc.com/values/current"
           f"?isDynasty=false&numQbs={qbs}&numTeams={teams}&ppr={ppr}")
    try:
        rows = get_json(url)
    except RuntimeError as exc:
        print(f"  ! value fetch failed ({teams}/{ppr}/{qbs}): {exc}")
        rows = []
    by_sleeper, by_key = {}, {}
    for r in rows:
        p = r.get("player") or {}
        rec = {
            "v": r.get("redraftValue") or r.get("value"),
            "vr": r.get("overallRank"),
            "pr": r.get("positionRank"),
            "t30": r.get("trend30Day"),
        }
        if p.get("sleeperId"):
            by_sleeper[str(p["sleeperId"])] = rec
        k = normalize(p.get("name"))
        if k:
            by_key[(k, (p.get("position") or "").upper())] = rec
    _VAL_CACHE[ck] = (by_sleeper, by_key)
    return _VAL_CACHE[ck]


# ---------------------------------------------------------------- build

def build_format(spec, players):
    adp = fetch_adp(spec["ffc"], spec["teams"])
    vs_sleeper, vs_key = fetch_values(spec["teams"], spec["ppr"], spec["qbs"])

    table, n_adp, n_val = {}, 0, 0
    for pid, p in players.items():
        lookup = (p["key"], p["pos"])
        rec = {}
        a = adp.get(lookup)
        if a:
            rec.update({k: v for k, v in a.items() if v is not None})
            n_adp += 1
        m = vs_sleeper.get(pid) or vs_key.get(lookup)
        if m:
            rec.update({k: v for k, v in m.items() if v is not None})
            n_val += 1
        if rec.get("adp") or rec.get("v"):
            table[pid] = rec

    payload = {
        "format": spec,
        "season": SEASON,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {"players": len(table), "adp": n_adp, "value": n_val},
        "players": table,
    }
    path = FORMAT_DIR / f"{spec['id']}.json"
    path.write_text(json.dumps(payload, separators=(",", ":")))
    kb = path.stat().st_size / 1024
    print(f"  {spec['id']:<12} {len(table):>4} players  adp {n_adp:>4}  val {n_val:>4}  {kb:>5.0f}KB")
    return len(table)


def build():
    FORMAT_DIR.mkdir(parents=True, exist_ok=True)
    players = fetch_players()

    base = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": SEASON,
        "players": list(players.values()),
    }
    (DATA / "players.json").write_text(json.dumps(base, separators=(",", ":")))
    print(f"wrote players.json — {(DATA/'players.json').stat().st_size/1024:.0f}KB\n")

    built = []
    for spec in FORMATS:
        try:
            count = build_format(spec, players)
            if count:
                built.append(spec)
            else:
                print(f"  ! {spec['id']} came back empty, leaving it out of the index")
        except Exception as exc:  # noqa: BLE001 — one bad format shouldn't kill the run
            print(f"  ! {spec['id']} failed: {exc}")
        time.sleep(1)

    (FORMAT_DIR / "index.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": SEASON,
        "formats": built,
    }, indent=1))
    print(f"\nindexed {len(built)} of {len(FORMATS)} formats")
    if not built:
        raise RuntimeError("no formats built — board would have nothing to load")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:  # noqa: BLE001
        print(f"ETL FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
