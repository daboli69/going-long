"""Single-week FantasyPoints drops -> the authority's game-log layout (Travis, 2026-10-29).

Inbox convention (data week): `<HISTORY_FOLDER>/Week N` holds the exports for 2026 **week N only**, downloaded the
Tuesday after week N, in FantasyPoints' season view (no SEASON/WEEK/OPP columns). They feed the **week N+1**
forecast.

`convert_all()` writes a private converted copy for each drop to
`data/raw/fpds/weekly_converted/<HISTORY_FOLDER>/Week N+1/` (forecast-week naming, which the existing importer and
its safety checks expect). Each copy uses the authority file's exact header rows:
- SEASON = 2026, WEEK = N;
- OPP comes from the lab schedule, in the authority's own team-code style;
- every column the season view lacks (one within-game share column per table, e.g. `SNAP %`, `DB %`) is left blank
  and listed in the conversion report.

The Inbox is read only: nothing there is moved, edited or deleted. A table whose `G` exceeds 1 is refused, because
that is a multi-week summary, not a single-week drop.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from .config import CACHE_DIR, RAW_DIR
from .fpds_sources import HISTORY_FOLDER
from .ingest import normalize_team

SEASON = 2026
ADAPTER_VERSION = 2  # bump to force reconversion
CONVERTED_ROOT = RAW_DIR / "fpds" / "weekly_converted"
FULL_NAMES = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN", "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


class ConversionError(ValueError):
    pass


def _rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def _two_headers(rows: list[list[str]]) -> bool:
    a, b = (rows + [[], []])[:2]
    return bool(b) and any(x.strip() for x in a) and not any(ch.isdigit() for ch in "".join(b[:3]))


def _qualified(group: list[str], names: list[str]) -> list[tuple]:
    seen, out, g = Counter(), [], ""
    for gr, n in zip(group, names):
        g = gr.strip() or g
        key = (g, n.strip().upper())
        seen[key] += 1
        out.append(key + (seen[key],))
    return out


def _team_code(value: str) -> str | None:
    v = (value or "").strip()
    if not v or v.lower() == "nan":
        return None
    if v in FULL_NAMES:
        return FULL_NAMES[v]
    try:
        return normalize_team(v)
    except ValueError:
        return None


def _authority(table: str, inbox: Path) -> Path:
    from .fpds_research.protocol import title
    best = None
    for p in (inbox / HISTORY_FOLDER).glob("*.csv"):
        t, marker = title(p)
        if t == table:
            rank = (marker or 6, p.stat().st_mtime_ns)
            if best is None or rank > best[0]:
                best = (rank, p)
    if best is None:
        raise ConversionError(f"No authority file for table {table}")
    return best[1]


def _opponents(week: int) -> dict:
    g = pd.read_parquet(CACHE_DIR / "games.parquet", columns=["season", "week", "home_team", "away_team"])
    g = g[(g["season"] == SEASON) & (g["week"] == week)]
    return {**dict(zip(g["home_team"], g["away_team"])), **dict(zip(g["away_team"], g["home_team"]))}


def convert_table(drop: Path, authority: Path, week: int, opp: dict) -> tuple[list[list[str]], dict]:
    a_rows, d_rows = _rows(authority), _rows(drop)
    a_two, d_two = _two_headers(a_rows), _two_headers(d_rows)
    a_group, a_head = (a_rows[0], a_rows[1]) if a_two else ([""] * len(a_rows[0]), a_rows[0])
    d_group, d_head = (d_rows[0], d_rows[1]) if d_two else ([""] * len(d_rows[0]), d_rows[0])
    body = d_rows[2:] if d_two else d_rows[1:]
    header_rows = [a_group, a_head] if a_two else [a_head]
    if d_head == a_head and d_group == a_group:  # already in the authority layout (e.g. injury reports)
        return header_rows + body, {"mode": "identical_copy", "rows": len(body), "blank_columns": []}

    A, D = _qualified(a_group, a_head), _qualified(d_group, d_head)
    d_index = {k: i for i, k in enumerate(D)}
    name_only = Counter(k[1] for k in D)
    by_name = {k[1]: i for i, k in enumerate(D) if name_only[k[1]] == 1}
    up = [h.strip().upper() for h in d_head]
    g_col = up.index("G") if "G" in up else None
    team_col = next((up.index(c) for c in ("TEAM",) if c in up), None)
    name_col = up.index("NAME") if "NAME" in up else None

    # authority OPP style (e.g. ARZ vs ARI): most common raw spelling per normalized code
    a_up = [h.strip().upper() for h in a_head]
    style = {}
    if "OPP" in a_up:
        oi = a_up.index("OPP")
        cnt = Counter(r[oi] for r in a_rows[len(header_rows):] if len(r) > oi and r[oi])
        for raw, _ in cnt.most_common():
            code = _team_code(raw)
            if code and code not in style:
                style[code] = raw

    mapping, blank = [], []
    for k in A:
        col = k[1]
        if k in d_index:
            mapping.append(("src", d_index[k]))
        elif col in ("SEASON", "SEA", "YEAR"):
            mapping.append(("const", str(SEASON)))
        elif col in ("WEEK", "WK"):
            mapping.append(("const", str(week)))
        elif col == "OPP":
            mapping.append(("opp", None))
        elif col in by_name:
            mapping.append(("src", by_name[col]))
        else:
            mapping.append(("blank", None))
            blank.append(col)
    out, multi, no_opp, dropped = [], 0, 0, 0
    for r in body:
        if not any(x.strip() for x in r):
            continue
        if g_col is not None and g_col < len(r):
            try:
                multi += float(r[g_col]) > 1
            except ValueError:
                pass
        team = None
        if team_col is not None and team_col < len(r):
            team = _team_code(r[team_col])
        if team is None and name_col is not None and name_col < len(r):
            team = _team_code(r[name_col])
        if team is None:  # "League Avg" summary and blank footer rows are not game-log rows
            dropped += 1
            continue
        row = []
        for kind, v in mapping:
            if kind == "src":
                row.append(r[v] if v < len(r) else "")
            elif kind == "const":
                row.append(v)
            elif kind == "opp":
                o = opp.get(team) if team else None
                no_opp += o is None
                row.append(style.get(o, o) if o else "")
            else:
                row.append("")
        out.append(row)
    if multi:
        raise ConversionError(f"{drop.name}: {multi} rows have G > 1; this is a multi-week summary, not a single-week drop")
    return header_rows + out, {"mode": "converted", "rows": len(out), "blank_columns": blank, "rows_without_opponent": no_opp,
                               "dropped_rows_without_team": dropped}


def convert_week(week: int, inbox: Path) -> dict | None:
    """Convert Inbox `Week {week}` (data week) into converted `Week {week + 1}` (forecast week). Idempotent."""
    from .fpds_research.protocol import title
    drop = inbox / HISTORY_FOLDER / f"Week {week}"
    files = sorted(drop.glob("*.csv")) if drop.exists() else []
    if not files:
        return None
    out = CONVERTED_ROOT / HISTORY_FOLDER / f"Week {week + 1}"
    digest = hashlib.sha256((f"v{ADAPTER_VERSION}|" + "".join(f"{p.name}:{p.stat().st_size}:{p.stat().st_mtime_ns}" for p in files)).encode()).hexdigest()
    report_path = CONVERTED_ROOT / f"REPORT_data_week_{week}.json"
    if report_path.exists() and json.loads(report_path.read_text(encoding="utf-8")).get("inputs") == digest:
        return json.loads(report_path.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.csv"):
        old.unlink()  # private converted copies only; the Inbox is never touched
    authority_tables = {title(p)[0] for p in (inbox / HISTORY_FOLDER).glob("*.csv")}
    opp = _opponents(week)
    report = {"data_week": week, "forecast_week": week + 1, "season": SEASON, "inputs": digest, "tables": {},
              "unregistered_skipped": [], "missing_tables": []}
    seen = set()
    for p in files:
        table = title(p)[0]
        if table not in authority_tables:
            report["unregistered_skipped"].append(p.name)
            continue
        rows, info = convert_table(p, _authority(table, inbox), week, opp)
        with (out / p.name).open("w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows(rows)
        report["tables"][table] = info
        seen.add(table)
    report["missing_tables"] = sorted(authority_tables - seen)
    report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def convert_all(inbox: Path | None = None) -> list[dict]:
    from .fpds_research.common import SOURCE
    inbox = Path(inbox or SOURCE)
    done = []
    for d in sorted((inbox / HISTORY_FOLDER).glob("Week *")):
        m = re.fullmatch(r"Week (\d+)", d.name, re.I)
        if m and 7 <= int(m[1]) <= 17:
            r = convert_week(int(m[1]), inbox)
            if r:
                done.append(r)
    return done
