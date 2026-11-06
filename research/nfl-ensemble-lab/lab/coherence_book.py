"""Coherence Test C (docs/COHERENCE_PREREG.md, Amendment 3): do sportsbook player-prop consensus lines keep moving toward a game-line move already visible in an earlier snapshot?"""
from __future__ import annotations

import glob
import json

import numpy as np
import pandas as pd

from .config import CACHE_DIR, RAW_DIR
from .props import lines as L

ARCH = RAW_DIR / "archive"
OUT = CACHE_DIR / "coherence_book_design.parquet"
TARGETS = (40, 24, 15)
TOL = 4
MAX_AGE_H = 12
MIN_BOOKS = 3


def _t(x):
    return pd.to_datetime(x, utc=True, errors="coerce", format="mixed")


def game_state() -> pd.DataFrame:
    """Per snapshot and game: consensus home spread and total."""
    rows = []
    for f in sorted(glob.glob(str(ARCH / "market" / "going_*.json"))):
        d = json.load(open(f))
        snap = d.get("available_at")
        for r in d.get("content", []):
            if r.get("market") not in ("spreads", "totals") or r.get("period") not in (None, "FULL") or r.get("in_play") or r.get("point") is None:
                continue
            if r["market"] == "spreads" and r.get("side") != "home":
                continue
            if r["market"] == "totals" and str(r.get("side")).lower() != "over":
                continue
            rows.append((snap, r["kickoff"], r["home"], r["away"], r["book"], r["market"], float(r["point"]), r["quote_time"]))
    g = pd.DataFrame(rows, columns=["snap", "kick", "home", "away", "book", "market", "point", "qt"])
    for c in ("snap", "kick", "qt"):
        g[c] = _t(g[c])
    g = g[(g["qt"] <= g["snap"]) & (g["snap"] - g["qt"] <= pd.Timedelta(hours=MAX_AGE_H)) & (g["snap"] < g["kick"])]
    g = g.sort_values("qt").drop_duplicates(["snap", "home", "away", "book", "market"], keep="last")
    g["gk"] = g["home"] + "@" + g["away"] + g["kick"].dt.strftime("%Y-%m-%d")
    agg = g.groupby(["snap", "gk", "market"]).agg(med=("point", "median"), n=("book", "nunique"), kick=("kick", "min"), home=("home", "first"), away=("away", "first")).reset_index()
    agg = agg[agg["n"] >= MIN_BOOKS]
    w = agg.pivot_table(index=["snap", "gk", "kick", "home", "away"], columns="market", values="med").reset_index()
    return w.dropna(subset=["spreads", "totals"]).rename(columns={"spreads": "home_spread", "totals": "total"})


def prop_state() -> pd.DataFrame:
    d = L.archived_lines()
    d = d[(d["period"] == "FULL") & d["stat"].isin(["pass_yds", "rec_yds"]) & d["line"].notna() & d["gsis_id"].notna() & (~d["in_play"].fillna(False).astype(bool)) & (~d["dfs"].fillna(False).astype(bool))].copy()
    d["snap"], d["kick"], d["qt"] = _t(d["available_at"]), _t(d["kickoff"]), _t(d["quote_time"])
    d = d[(d["qt"] <= d["snap"]) & (d["snap"] - d["qt"] <= pd.Timedelta(hours=MAX_AGE_H)) & (d["snap"] < d["kick"])]
    d = d.sort_values("qt").drop_duplicates(["snap", "home", "away", "book", "gsis_id", "stat"], keep="last")
    d["gk"] = d["home"] + "@" + d["away"] + d["kick"].dt.strftime("%Y-%m-%d")
    agg = d.groupby(["snap", "gk", "gsis_id", "stat"]).agg(line=("line", "median"), n=("book", "nunique"), home=("home", "first"), away=("away", "first")).reset_index()
    return agg[agg["n"] >= MIN_BOOKS]


def roster_teams() -> dict:
    r = pd.read_parquet(RAW_DIR / "roster_weekly_2026.parquet", columns=["gsis_id", "team"]).dropna()
    return r.groupby("gsis_id")["team"].agg(lambda s: set(s)).to_dict()


def pick_snaps(gs: pd.DataFrame) -> pd.DataFrame:
    """For each game, the snapshot closest to each target within tolerance; all three distinct."""
    out = []
    for gk, g in gs.groupby("gk"):
        hrs = (g["kick"] - g["snap"]).dt.total_seconds() / 3600
        pick, ok = {}, True
        for t in TARGETS:
            diff = (hrs - t).abs()
            i = diff.idxmin()
            if diff[i] > TOL:
                ok = False
                break
            pick[t] = g.loc[i]
        if ok and len({pick[t]["snap"] for t in TARGETS}) == 3:
            out.append({"gk": gk, "home": pick[40]["home"], "away": pick[40]["away"], **{f"snap{t}": pick[t]["snap"] for t in TARGETS},
                        **{f"spread{t}": pick[t]["home_spread"] for t in TARGETS}, **{f"total{t}": pick[t]["total"] for t in TARGETS}})
    return pd.DataFrame(out)


def design() -> pd.DataFrame:
    gs, ps = game_state(), prop_state()
    games = pick_snaps(gs)
    rows = []
    for t in TARGETS:
        p = ps.merge(games[["gk", f"snap{t}"]].rename(columns={f"snap{t}": "snap"}), on=["gk", "snap"])
        rows.append(p.rename(columns={"line": f"line{t}"})[["gk", "gsis_id", "stat", f"line{t}"]])
    m = rows[0].merge(rows[1], on=["gk", "gsis_id", "stat"]).merge(rows[2], on=["gk", "gsis_id", "stat"])
    m = m.merge(games, on="gk")
    rt = roster_teams()
    def team_of(r):
        s = rt.get(r.gsis_id, set())
        h, a = r.home in s, r.away in s
        return r.home if h and not a else r.away if a and not h else None
    m["team"] = [team_of(r) for r in m.itertuples()]
    m = m[m["team"].notna()].copy()
    is_home = m["team"] == m["home"]
    sign = np.where(is_home, 1.0, -1.0)
    tp = lambda t: (m[f"total{t}"] + sign * (-m[f"spread{t}"])) / 2
    m["T40"], m["T24"] = tp(40), tp(24)
    m["gid"] = m["gk"]
    m["series"] = m["stat"]
    m["dG"] = m["T24"] - m["T40"]
    m["y_prev"] = m["line24"] - m["line40"]
    m["y_next"] = m["line15"] - m["line24"]
    return m[(is_home | (m["team"] == m["away"]))].reset_index(drop=True)
