"""What each defense gives up to each position, from FantasyPoints' fantasy-points-allowed tables, converted to actual stats.

Each table has one row per defense per week: the catches, yards, touchdowns, carries and fantasy points that defense allowed to a position
(quarterbacks, running backs, tight ends, wide receivers). The stats are used, not only the fantasy-point total: a defense that gives up
yards through the air but not on the ground shows that in the stats and is blurred in a single score. Only weeks before the game's week
feed a prediction.

Owner decision (Travis, 2026-11-01): the simulation applies these adjustments whether or not they beat the baseline in
`scripts/allowed_check.py`, which still tests them every Tuesday and refits the weights. The test result is shown next to the numbers.

The newest "Week N" folder in the FantasyPoints Inbox is read directly (never moved or edited) and laid over the imported cache, so a
fresh drop is used before the weekly import has run.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import fpds_usage as X
from .config import CACHE_DIR
from .ingest import normalize_team

WINDOW = 6
K_SHRINK = 4.0   # games of league-average play a defense is assumed to have before its own record counts for more
FILES = {"QB": "qb__working_usable", "RB": "rb__15f126a75b45__usable", "TE": "te__c0cc892bbcc3__usable", "WR": "wr__cb5b53e74409__usable"}
# stat the simulation predicts -> position -> column of the allowed table
STAT_COLS = {
    "rec_yds": {"WR": "receiving__yds", "TE": "receiving__yds", "RB": "receiving__yds"},
    "rec": {"WR": "receiving__rec", "TE": "receiving__rec", "RB": "receiving__rec"},
    "rush_yds": {"RB": "rushing__yds", "QB": "rushing__yds"},
}
FP_COL = "fp__fp"
RULE_PATH = CACHE_DIR / "allowed_rule.json"
MULT_CLIP = (0.8, 1.25)   # no matchup moves a player's number by more than this factor
LABEL = {"rec_yds": "receiving yards", "rec": "catches", "rush_yds": "rushing yards"}


def _inbox_root() -> Path:
    env = os.environ.get("GOING_FP_ROOT")
    return (Path(env) if env else Path(__file__).resolve().parents[3] / "FantasyPoints") / "Inbox"


def _week_folders(root: Path) -> list[tuple[int, Path]]:
    out = []
    if root.exists():
        for p in root.rglob("Week *"):
            m = re.fullmatch(r"Week (\d+)", p.name)
            if p.is_dir() and m and any(p.glob("fantasy-points-allowed-*.csv")):
                out.append((int(m.group(1)), p))
    return sorted(out)


def _parse_inbox_file(path: Path) -> pd.DataFrame | None:
    """One fantasy-points-allowed CSV (two header rows, an averages row and a footer) as rows in the cached table's layout."""
    try:
        t = pd.read_csv(path, header=[0, 1])
    except Exception:
        return None
    t.columns = [(str(a).strip().upper(), str(b).strip().upper()) for a, b in t.columns]
    need = [("TEAM DETAILS", "RANK"), ("TEAM DETAILS", "NAME"), ("TEAM DETAILS", "POS"), ("SPLITS", "WEEK"), ("FP", "FP")]
    if not all(c in t.columns for c in need):
        return None
    t = t[pd.to_numeric(t[("TEAM DETAILS", "RANK")], errors="coerce").notna()]
    if t.empty:
        return None
    pos = t[("TEAM DETAILS", "POS")].astype(str).str.replace("vs.", "", regex=False).str.strip().str.upper()
    out = pd.DataFrame({"season": 2026, "week": pd.to_numeric(t[("SPLITS", "WEEK")], errors="coerce"),
                        "team": t[("TEAM DETAILS", "NAME")].map(lambda s: normalize_team(s) if isinstance(s, str) else s),
                        "pos": pos.to_numpy(), "fp__fp": pd.to_numeric(t[("FP", "FP")], errors="coerce")})
    for col in sorted({c for cols in STAT_COLS.values() for c in cols.values()}):
        group, name = col.split("__")
        key = (group.upper(), name.upper())
        out[col] = pd.to_numeric(t[key], errors="coerce") if key in t.columns else np.nan
    out = out.dropna(subset=["week", "team"])
    out["week"] = out["week"].astype(int)
    return out


def inbox_weekly() -> pd.DataFrame:
    """The newest Inbox Week folder's tables. Where a position has several exports (wide receivers come split into slices), the one
    with the most fantasy points in total is the full set."""
    folders = _week_folders(_inbox_root())
    if not folders:
        return pd.DataFrame()
    best: dict = {}
    for _, folder in folders[-1:]:
        for f in sorted(folder.glob("fantasy-points-allowed-*.csv")):
            df = _parse_inbox_file(f)
            if df is None or df.empty:
                continue
            for pos, part in df.groupby("pos"):
                if pos in FILES and (pos not in best or part["fp__fp"].sum() > best[pos]["fp__fp"].sum()):
                    best[pos] = part
    return pd.concat(best.values(), ignore_index=True) if best else pd.DataFrame()


def _stamp() -> tuple:
    folders = _week_folders(_inbox_root())
    files = sorted(folders[-1][1].glob("fantasy-points-allowed-*.csv")) if folders else []
    return tuple((f.name, f.stat().st_mtime_ns) for f in files)


def allowed_weekly() -> pd.DataFrame:
    """One row per defense, week and position, with every stat that defense allowed to that position."""
    base = X._a6_dir()
    keep = sorted({c for cols in STAT_COLS.values() for c in cols.values()} | {FP_COL})
    frames = []
    for pos, f in FILES.items():
        t = pd.read_parquet(base / f"fantasy_points_allowed_{f}.parquet")
        out = t[["season", "week", "team"]].copy()
        for c in keep:
            out[c] = pd.to_numeric(t[c], errors="coerce") if c in t.columns else np.nan
        out["pos"] = pos
        frames.append(out)
    a = pd.concat(frames, ignore_index=True)
    a["team"] = a["team"].map(lambda s: normalize_team(s) if isinstance(s, str) else s)
    a = a.dropna(subset=["season", "week", "team"])
    a["season"], a["week"] = a["season"].astype(int), a["week"].astype(int)
    new = inbox_weekly()
    if len(new):
        a = pd.concat([a, new[a.columns]], ignore_index=True)
    return a.drop_duplicates(["season", "week", "team", "pos"], keep="last")


class Allowed:
    """Each defense's recent record against a position, as a shrunk relative gap to the league: 0.10 means 10% more than league average."""

    def __init__(self, table: pd.DataFrame | None = None):
        self.t = allowed_weekly() if table is None else table
        self._cache: dict = {}

    def gaps(self, season: int, week: int) -> pd.DataFrame:
        """Index (team, pos); one column per allowed stat. Defenses with fewer than two earlier weeks are left out."""
        key = (season, week)
        if key not in self._cache:
            s = self.t[(self.t["season"] == season) & (self.t["week"] < week)]
            weeks = sorted(s["week"].unique())[-WINDOW:]
            s = s[s["week"].isin(weeks)]
            cols = [c for c in s.columns if c not in ("season", "week", "team", "pos")]
            g = s.groupby(["team", "pos"])[cols].mean()
            n = s.groupby(["team", "pos"])["week"].nunique()
            league = g.groupby(level="pos").transform("mean")
            rel = (g / league.replace(0, np.nan) - 1.0).fillna(0.0)
            rel = rel.mul(n / (n + K_SHRINK), axis=0)
            self._cache[key] = rel[n >= 2]
        return self._cache[key]


def gap(allowed: Allowed, opp: dict, season: int, week: int, team: str, pos: str, col: str) -> float:
    """The opposing defense's relative gap to the league for one stat against one position (0 when unknown)."""
    o = opp.get((season, week, team))
    g = allowed.gaps(season, week)
    if o is None or (o, pos) not in g.index or col not in g.columns:
        return 0.0
    return float(g.loc[(o, pos), col])


# --------------------------------------------------------------------------- the rule the simulation reads

def load_rule(path: Path = RULE_PATH) -> dict:
    """Fitted weights from scripts/allowed_check.py: {"weights": {stat: {pos: weight}}, "passed": bool, "applied": bool}. Empty until it has run."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


_SINGLETON: dict = {}


def shared() -> Allowed:
    """The Allowed table for the current files, rebuilt when the cache or the Inbox drop changes."""
    key = (_stamp(), X._a6_stamp())
    if _SINGLETON.get("key") != key:
        _SINGLETON.update(key=key, obj=Allowed())
    return _SINGLETON["obj"]


def multipliers(defense: str, season: int, week: int, rule: dict | None = None, allowed: Allowed | None = None) -> dict:
    """{stat: {pos: factor}} for a team facing `defense`, plus the gaps they come from. Empty when the rule has no weights or the
    defense has fewer than two weeks on record. Factors stay inside MULT_CLIP."""
    rule = load_rule() if rule is None else rule
    if not rule.get("applied") or not rule.get("weights"):
        return {}
    g = (shared() if allowed is None else allowed).gaps(season, week)
    out: dict = {}
    for stat, by_pos in rule["weights"].items():
        for pos, w in by_pos.items():
            col = STAT_COLS.get(stat, {}).get(pos)
            if col is None or (defense, pos) not in g.index:
                continue
            gp = float(g.loc[(defense, pos), col])
            m = float(np.clip(1.0 + w * gp, *MULT_CLIP))
            out.setdefault(stat, {})[pos] = {"factor": m, "gap": gp}
    return out


def describe(mults: dict, defense: str) -> list[dict]:
    """Plain rows for the screen: what the defense allows to a position and how much that moves the number."""
    rows = []
    for stat in ("rec_yds", "rec", "rush_yds"):
        for pos, v in (mults.get(stat) or {}).items():
            rows.append({"defense": defense, "pos": pos, "stat": LABEL[stat], "gap": v["gap"], "factor": v["factor"]})
    return rows


# --------------------------------------------------------------------------- applying them

STAT_OF_ROW = {"Receiving yards": "rec_yds", "Receptions": "rec", "Rushing yards": "rush_yds"}


def apply_to_rows(rows: list[dict], pos_of: dict, mults: dict) -> dict:
    """Scale each player row (typical, expected, carries, range) by the factor for his position. Returns the team-wide factor for
    receiving yards (yardage-weighted) so the quarterback's passing yards can follow it."""
    if not mults:
        return {"rec_yds": 1.0}
    num = den = 0.0
    for r in rows:
        stat = STAT_OF_ROW.get(r["stat"])
        pos = pos_of.get(r["player"])
        m = (mults.get(stat) or {}).get(pos) if stat else None
        if m is None:
            continue
        f = m["factor"]
        if stat == "rec_yds":
            num += r["typical"] * f
            den += r["typical"]
        for k in ("typical", "expected", "range_low", "range_high", "carries"):
            if r.get(k) is not None:
                r[k] *= f
        r["allowed_factor"] = f
    return {"rec_yds": num / den if den > 0 else 1.0}


def apply_to_sampled(players: list[dict], mults: dict, rng: np.random.Generator) -> None:
    """Scale a sampled receiving game in place: each catch's yards follow the receiving-yards factor and the number of catches follows
    the catches factor (some catches become incompletions, some incompletions become catches) for that player's position."""
    for p in players:
        pos = p.get("group")
        fy = ((mults.get("rec_yds") or {}).get(pos) or {}).get("factor")
        fc = ((mults.get("rec") or {}).get(pos) or {}).get("factor")
        if fc is not None and fc != 1.0:
            rec, tgt = len(p["yards"]), int(p["tgt"])
            if fc < 1.0:
                keep = [y for y in p["yards"] if rng.random() < fc]
                p["yards"] = keep
            elif tgt > rec:
                extra = int(rng.binomial(tgt - rec, min(1.0, (fc - 1.0) * rec / max(tgt - rec, 1))))
                base = list(p["yards"]) or [9]
                p["yards"] = list(p["yards"]) + [int(rng.choice(base)) for _ in range(extra)]
            p["rec"] = len(p["yards"])
        if fy is not None and fy != 1.0:
            p["yards"] = [int(round(y * fy)) for y in p["yards"]]
