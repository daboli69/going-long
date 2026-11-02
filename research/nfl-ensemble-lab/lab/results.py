"""How the app's saved pregame forecasts did against what happened, week by week.

Every number compared here was saved before the game: the win chance, expected margin and total from the saved forecast, and the player projections and
8-in-10 ranges from the Players tab. Actuals come from the official nflverse play-by-play, and for games it has not published yet, from the last stored
ESPN box score of the recorded game. A player with no recorded line counts as zero, which includes a player who did not play.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from . import gamesim as S
from . import ingame as G
from . import ingame_feed as F

STATS = {"Passing yards": ("pass", "yards"), "Rushing yards": ("rush", "yards"), "Receiving yards": ("rec", "yards"), "Receptions": ("rec", "catches")}
_LAST_REFRESH = [0.0]
_CACHE: dict = {}


def refresh_pbp(max_age_minutes: float = 30.0) -> None:
    """Pull the newest 2026 nflverse play-by-play (public, read-only, the same file the lab's normal refresh downloads), at most once per `max_age_minutes`."""
    if time.time() - _LAST_REFRESH[0] < max_age_minutes * 60:
        return
    _LAST_REFRESH[0] = time.time()
    try:
        from . import sources
        sources.download_pbp(D.SEASON, live=True, force=True, progress=lambda m: None)
    except Exception:
        pass


def _pbp_actuals(gids: list[str]) -> dict[str, pd.DataFrame]:
    path = G.RAW / f"play_by_play_{D.SEASON}.parquet"
    plays = pd.read_parquet(path, columns=G.PBP_COLS)
    plays = plays[plays["game_id"].isin(gids)]
    ev = G.events(plays)
    names = pd.read_parquet(G.RAW / "players.parquet", columns=["gsis_id", "display_name"]).dropna()
    nm = dict(zip(names["gsis_id"], names["display_name"]))
    out = {}
    for gid, g in ev.groupby("gid"):
        rows = []
        for fam in G.FAMILIES:
            r = G._fam_rows(g, fam)
            t = r.groupby(["team", "pid"]).agg(yards=("yards", "sum"), catches=("catch", "sum")).reset_index()
            t["fam"] = fam
            rows.append(t)
        a = pd.concat(rows, ignore_index=True)
        a["key"] = [S._norm(nm.get(p, "")) for p in a["pid"]]
        out[gid] = a
    return out


def _box_actuals(gid: str, home: str, away: str) -> pd.DataFrame | None:
    """The last stored ESPN box score of a recorded game, in the same shape as the play-by-play actuals."""
    idx = F.CAPTURE / "index.jsonl"
    if not idx.exists():
        return None
    eid = None
    for line in idx.read_text(encoding="utf-8").splitlines():
        import json
        r = json.loads(line)
        if F.normalize_team(r["teams"]["home"]) == home and F.normalize_team(r["teams"]["away"]) == away:
            eid = r["event"]
    snaps = F.snapshots(eid) if eid else []
    if not snaps:
        return None
    snap = F.parse(F.load(snaps[-1][1]))
    if snap["state"] != "post":
        return None
    rows = []
    for (team, name), pl in snap["players"].items():
        k = S._norm(name)
        if pl.get("pass_att") is not None:
            rows.append((team, k, "pass", pl.get("pass_yds") or 0.0, pl.get("pass_comp") or 0.0))
        if pl.get("rush_att") is not None:
            rows.append((team, k, "rush", pl.get("rush_yds") or 0.0, 0.0))
        if pl.get("targets") is not None:
            rows.append((team, k, "rec", pl.get("rec_yds") or 0.0, pl.get("rec") or 0.0))
    return pd.DataFrame(rows, columns=["team", "key", "fam", "yards", "catches"])


def week_results(week: int) -> dict:
    cached = _CACHE.get(week)
    if cached and time.time() - cached[0] < 60:
        return cached[1]
    games = D.games_table()
    g = games[(games["season"] == D.SEASON) & (games["week"] == week) & (games["game_type"] == "REG")]
    done = g[g["completed"].astype(bool)].sort_values("kickoff_utc")
    gids = list(done["game_id"])
    pbp_path = G.RAW / f"play_by_play_{D.SEASON}.parquet"
    have = set(pd.read_parquet(pbp_path, columns=["game_id"])["game_id"].unique()) if pbp_path.exists() else set()
    if any(x not in have for x in gids):
        refresh_pbp()
        have = set(pd.read_parquet(pbp_path, columns=["game_id"])["game_id"].unique())
    actual = _pbp_actuals([x for x in gids if x in have]) if gids else {}
    out_games, out_players, pending = [], [], []
    for r in done.itertuples():
        d = D.game_detail(r.game_id)
        if d is None or not d.get("has_forecast"):
            continue
        src = "official play-by-play"
        a = actual.get(r.game_id)
        if a is None:
            a = _box_actuals(r.game_id, d["home"], d["away"])
            src = "last stored ESPN box score"
        hs, as_ = float(d["home_score"]), float(d["away_score"])
        p_home = float(d["headline"]["p_home"])
        pick = d["home"] if p_home >= 0.5 else d["away"]
        winner = d["home"] if hs > as_ else d["away"] if as_ > hs else None
        e = d["expected"]
        out_games.append({"gid": r.game_id, "away": d["away"], "home": d["home"], "away_score": as_, "home_score": hs, "kickoff_label": d["kickoff_label"],
                          "pick": pick, "p_pick": max(p_home, 1 - p_home), "p_label": d["headline"].get("p_label"), "winner": winner, "correct": winner == pick if winner else None,
                          "exp_margin": e.get("margin"), "margin": hs - as_, "margin_error": None if e.get("margin") is None else (hs - as_) - e["margin"],
                          "exp_total": e.get("total"), "total": hs + as_, "total_error": None if e.get("total") is None else (hs + as_) - e["total"],
                          "sd_m": e.get("sd_m"), "sd_t": e.get("sd_t"), "actuals_from": src if a is not None else None})
        if a is None:
            pending.append(r.game_id)
            continue
        for p in d.get("props") or []:
            spec = STATS.get(p["stat"])
            if spec is None:
                continue
            fam, col = spec
            m = a[(a["fam"] == fam) & (a["team"] == p["team"]) & (a["key"] == S._norm(p["player"]))]
            actual_v = float(m[col].iloc[0]) if len(m) else 0.0
            lo, hi = p.get("range_low"), p.get("range_high")
            out_players.append({"gid": r.game_id, "player": p["player"], "team": p["team"], "opp": d["home"] if p["team"] == d["away"] else d["away"], "stat": p["stat"],
                                "projected": float(p["typical"]), "low": lo, "high": hi, "actual": actual_v, "error": actual_v - float(p["typical"]),
                                "inside": None if lo is None or hi is None else bool(lo <= actual_v <= hi), "no_line": len(m) == 0})
    gdf = pd.DataFrame(out_games)
    summary = {"games_played": int(len(g[g["completed"].astype(bool)])), "games_scored": int(len(gdf)), "pending_actuals": pending}
    if len(gdf):
        c = gdf["correct"].dropna()
        summary.update({"picked_right": int(c.sum()), "picked_wrong": int((~c.astype(bool)).sum()), "accuracy": float(c.mean()) if len(c) else None,
                        "avg_confidence": float(gdf["p_pick"].mean()), "mean_abs_margin_error": float(gdf["margin_error"].abs().mean()),
                        "mean_abs_total_error": float(gdf["total_error"].abs().mean()),
                        "margin_inside_80": float(np.mean([abs(x) <= 1.2816 * s for x, s in zip(gdf["margin_error"], gdf["sd_m"]) if x is not None and s])),
                        "total_inside_80": float(np.mean([abs(x) <= 1.2816 * s for x, s in zip(gdf["total_error"], gdf["sd_t"]) if x is not None and s]))})
    pdf = pd.DataFrame(out_players)
    pstats = {}
    if len(pdf):
        for stat, x in pdf.groupby("stat"):
            ins = x["inside"].dropna()
            pstats[stat] = {"n": int(len(x)), "mean_abs_error": float(x["error"].abs().mean()), "bias": float(x["error"].mean()),
                            "inside_range": float(ins.mean()) if len(ins) else None, "no_line": int(x["no_line"].sum())}
    res = {"week": week, "games": out_games, "players": out_players, "summary": summary, "player_summary": pstats}
    _CACHE[week] = (time.time(), res)
    return res
