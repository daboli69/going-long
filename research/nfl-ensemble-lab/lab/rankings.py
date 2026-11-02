"""Weekly player rankings for the Game Center: every player in the week's games, ranked by a 0 to 100 score for one prop at a time.

Inputs are the numbers the simulated game already uses (lab/gamesim.py): the projection after injuries, the opposing defense's record against
the position (lab/allowed_usage.py) and FantasyPoints usage (lab/fpds_usage.py). Nothing here is a new model and nothing is a betting
recommendation: the score orders players, it does not say a prop will win. Local files only, read-only, deterministic.

Score = weighted percentile blend, each part ranked among the players on that week's list for the prop:
    projection 50%   the player's projected number
    matchup    25%   how much the opposing defense moves that number (its record against the position)
    usage      25%   target share (receiving) or carry share (rushing), from FantasyPoints
A part with no data is left out and the others are re-weighted. Passing yards have no usage part.
Anytime touchdown: chance = 1 - exp(-expected touchdowns), where the team's expected offensive touchdowns come from its expected points
(0.1193 per point minus 0.407, measured on 2020 to 2026 regular-season games) and are split between receiving and rushing by the team's
recent rush share, then among players by the same weights the simulated game uses to pick scorers.
"""
from __future__ import annotations

import re
import time

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from . import gamecenter_data as D
from . import fpds_usage as X
from . import gamesim as S

TD_PER_POINT, TD_INTERCEPT, TD_FLOOR = 0.1193, -0.407, 0.3
WEIGHTS = {"projection": 0.5, "matchup": 0.25, "usage": 0.25}
TOP = 60
STATS = {
    "rec_yds": {"label": "Receiving yards", "row": "Receiving yards", "min": 12.0, "usage": "tgt_pct", "unit": "yds"},
    "rec": {"label": "Catches", "row": "Receptions", "min": 1.2, "usage": "tgt_pct", "unit": "rec"},
    "rush_yds": {"label": "Rushing yards", "row": "Rushing yards", "min": 12.0, "usage": "att_pct", "unit": "yds"},
    "pass_yds": {"label": "Passing yards", "row": "Passing yards", "min": 100.0, "usage": None, "unit": "yds"},
    "td": {"label": "Anytime touchdown", "row": None, "min": 0.03, "usage": "both", "unit": "chance"},
    "first_td": {"label": "First touchdown", "row": None, "min": 0.01, "usage": "both", "unit": "chance"},
}
ABOVE, BELOW = 1.10, 0.90   # projection against the market line, for the Above line / Below line tags


def pct_rank(x: np.ndarray) -> np.ndarray:
    """0 to 100 percentile among the values (ties share a rank); a single value scores 50."""
    x = np.asarray(x, float)
    if len(x) <= 1:
        return np.full(len(x), 50.0)
    return (rankdata(x, method="average") - 1) / (len(x) - 1) * 100.0


def blend(parts: dict) -> float | None:
    """Weighted mean of the available parts (0 to 100), re-weighting around any that are missing."""
    w = {k: WEIGHTS[k] for k, v in parts.items() if v is not None}
    if not w:
        return None
    return float(sum(WEIGHTS[k] * parts[k] for k in w) / sum(w.values()))


def td_chances(sim: dict) -> dict:
    """(player, team) -> {chance, exp_td, first} for anytime and first touchdown, from the simulated game's touchdown inputs and player rows.

    First touchdown treats each scorer's touchdowns as a Poisson stream: the game has a first touchdown with chance 1 - exp(-L), where L is both teams' expected
    touchdowns, and it is his with probability his expected touchdowns over L. Touchdowns by players not listed (defense, special teams, deep reserves) are in L."""
    out = {}
    exp_by_team = {t: max(TD_FLOOR, TD_PER_POINT * m["exp_points"] + TD_INTERCEPT) for t, m in (sim.get("td_model") or {}).items()}
    total = sum(exp_by_team.values())
    any_td = 1 - np.exp(-total) if total > 0 else 0.0
    for team, m in (sim.get("td_model") or {}).items():
        exp_td = exp_by_team[team]
        rs = float(m["rush_share"])
        rush = {r["player"]: max(r["typical"], 0.0) for r in sim["players"] if r["team"] == team and r["stat"] == "Rushing yards"}
        tot_rush = sum(rush.values())
        names = set(m["rec_weights"]) | set(rush)
        for n in names:
            lam = exp_td * ((1 - rs) * m["rec_weights"].get(n, 0.0) + (rs * rush.get(n, 0.0) / tot_rush if tot_rush > 0 else 0.0))
            if lam > 0:
                out[(n, team)] = {"chance": float(1 - np.exp(-lam)), "exp_td": float(lam), "first": float(any_td * lam / total) if total > 0 else 0.0}
    return out


def fpds_of(rows_by_stat: dict) -> dict:
    """FantasyPoints usage metrics for a player: the simulated game attaches them to one of his rows, so take whichever has them."""
    return next((r["fpds"] for r in rows_by_stat.values() if r.get("fpds")), {})


_RZ: dict = {}


def red_zone(name: str, team: str, week: int) -> dict | None:
    """FantasyPoints red-zone usage for a player over the last six weeks before `week`: end-zone and inside-20 targets a game, and the share of his carries
    from inside the 5. None when the table has nothing for him. Receiving touchdown shares use the targets (see docs/FPDS_USAGE_CHECK.md); carries from
    inside the 5 did not improve the rushing split in testing, so they are shown and not used."""
    key = (team, week)
    if key not in _RZ:
        try:
            _RZ[key] = X.features_asof(D.SEASON, team, week)
        except Exception:
            _RZ[key] = None
    f = _RZ[key]
    pid = S._pid_by_norm().get(S._norm(name))
    if f is None or pid is None or pid not in f.index:
        return None
    r = f.loc[pid]
    get = lambda c: float(r[c]) if c in r.index and pd.notna(r[c]) else None
    out = {"ez_tgt": get("eztgt"), "i20_tgt": get("i20_tgt"), "i5_carry_share": get("i5_pct"), "weeks": int(r.get("fp_weeks", 0) or 0)}
    return out if any(out[k] is not None for k in ("ez_tgt", "i20_tgt", "i5_carry_share")) else None


def _tags(row: dict, sim: dict, team: str) -> list[str]:
    tags = []
    ml, v = row.get("market_line"), row.get("projection")
    if ml and v is not None and row["stat"] != "td":
        if v >= ABOVE * ml:
            tags.append("Above the line")
        elif v <= BELOW * ml:
            tags.append("Below the line")
    q = next((x for x in sim.get("questionable", []) if x["player"] == row["player"] and x["team"] == team), None)
    if q:
        tags.append("Questionable")
    for m in sim.get("injury_moves", []):
        if m.get("team") == team and re.search(rf"{re.escape(row['player'])} \+\d", m.get("text", "")):
            tags.append("Gets a teammate's share")
            break
    return tags


def build_week(week: int) -> dict:
    """Rankings for every stat in `STATS`, across all games of `week`."""
    games = D.games_table()
    games = games[(games["season"] == D.SEASON) & (games["week"] == week) & (games["game_type"] == "REG")].sort_values("kickoff_utc")
    if (~games["completed"].astype(bool)).any():  # a week in progress ranks the games still to play; a finished week ranks them all
        games = games[~games["completed"].astype(bool)]
    cand: dict[str, list[dict]] = {k: [] for k in STATS}
    for g in games.itertuples():
        sim = S.simulate(g.game_id, "typical", 0)
        if not sim or not sim.get("ok"):
            continue
        tdc = td_chances(sim)
        by_pt = {}
        for r in sim["players"]:
            by_pt.setdefault((r["player"], r["team"]), {})[r["stat"]] = r
        common = {"gid": g.game_id, "kickoff_utc": str(g.kickoff_utc)}
        for (name, team), rs in by_pt.items():
            opp, home = (g.away_team, True) if team == g.home_team else (g.home_team, False)
            if team not in (g.home_team, g.away_team):
                continue
            base = {**common, "player": name, "team": team, "opp": opp, "home": home}
            for key, cfg in STATS.items():
                if key in ("td", "first_td"):
                    t = tdc.get((name, team))
                    if not t:
                        continue
                    anyrow = next(iter(rs.values()))
                    fp = fpds_of(rs)
                    tgt, att = fp.get("tgt_pct"), fp.get("att_pct")
                    rec_f = (rs.get("Receiving yards") or {}).get("allowed_factor")
                    rush_f = (rs.get("Rushing yards") or {}).get("allowed_factor")
                    factors = [f for f in (rec_f, rush_f) if f is not None]
                    use = [v for v in (tgt, att) if v is not None]
                    row = {**base, "stat": key, "pos": anyrow.get("pos"), "projection": t["chance"] if key == "td" else t["first"], "exp_td": t["exp_td"], "market_line": None, "market_chance": None,
                           "range_low": None, "range_high": None, "matchup_raw": float(np.mean(factors)) if factors else None, "usage_raw": float(max(use)) if use else None}
                else:
                    r = rs.get(cfg["row"])
                    if not r or r["typical"] < cfg["min"]:
                        continue
                    fp = fpds_of(rs)
                    row = {**base, "stat": key, "pos": r.get("pos"), "projection": float(r["typical"]), "range_low": r.get("range_low"), "range_high": r.get("range_high"),
                           "market_line": r.get("market_line"), "market_chance": r.get("market_chance"), "our_chance": r.get("our_chance"),
                           "matchup_raw": r.get("allowed_factor"), "usage_raw": fp.get(cfg["usage"]) if cfg["usage"] else None, "carries": r.get("carries")}
                if key in ("td", "first_td"):
                    row["red_zone"] = red_zone(name, team, int(g.week))
                row["tags"] = _tags(row, sim, team)
                cand[key].append(row)
    out = {}
    for key, rows in cand.items():
        if not rows:
            out[key] = {"label": STATS[key]["label"], "unit": STATS[key]["unit"], "rows": []}
            continue
        proj = pct_rank(np.array([r["projection"] for r in rows]))
        mu = np.array([np.nan if r["matchup_raw"] is None else r["matchup_raw"] for r in rows])
        us = np.array([np.nan if r["usage_raw"] is None else r["usage_raw"] for r in rows])
        mp = np.full(len(rows), np.nan)
        up = np.full(len(rows), np.nan)
        if np.isfinite(mu).sum() > 1:
            mp[np.isfinite(mu)] = pct_rank(mu[np.isfinite(mu)])
        if np.isfinite(us).sum() > 1:
            up[np.isfinite(us)] = pct_rank(us[np.isfinite(us)])
        for i, r in enumerate(rows):
            parts = {"projection": float(proj[i]), "matchup": None if np.isnan(mp[i]) else float(mp[i]), "usage": None if np.isnan(up[i]) else float(up[i])}
            r["parts"] = parts
            r["score"] = blend(parts)
        rows.sort(key=lambda r: (-r["score"], -r["projection"], r["player"]))
        for i, r in enumerate(rows[:TOP], 1):
            r["rank"] = i
        out[key] = {"label": STATS[key]["label"], "unit": STATS[key]["unit"], "rows": rows[:TOP], "players": len(rows)}
    return {"week": week, "weights": WEIGHTS, "stats": out, "all_td": cand["td"], "built_at": time.time()}


_CACHE: dict = {}


def week_rankings(week: int, ttl: float = 600.0) -> dict:
    hit = _CACHE.get(week)
    if hit and time.time() - hit["built_at"] < ttl:
        return hit
    _CACHE[week] = build_week(week)
    return _CACHE[week]


def public(payload: dict) -> dict:
    """The rankings as the screen reads them (without the full touchdown list used by the market tab)."""
    return {k: v for k, v in payload.items() if k != "all_td"}


def td_card(gid: str, team: str, player: str) -> dict | None:
    """The touchdown card for one player in one game, with his chance and score from the week's rankings."""
    from . import tdcard as T
    g = D.games_table()
    row = g[g["game_id"] == gid]
    if row.empty or team not in (row.iloc[0]["home_team"], row.iloc[0]["away_team"]):
        return None
    row = row.iloc[0]
    week = int(row["week"])
    opp = row["away_team"] if team == row["home_team"] else row["home_team"]
    e = (S.game_detail_adjusted(gid) or {}).get("expected") or {}
    margin, total = e.get("margin"), e.get("total")
    favored = None if margin is None else float(margin if team == row["home_team"] else -margin)
    pid = S._pid_by_norm().get(S._norm(player))
    if pid is None:
        return None
    ranked = next((r for r in week_rankings(week).get("all_td", []) if r["gid"] == gid and r["player"] == player), None)
    c = T.card(team, pid, week, opp, favored, total, tdp=None if ranked is None else ranked["projection"])
    if c is None:
        return None
    c["player"] = player
    c["score"] = None if ranked is None else ranked["score"]
    c["exp_td"] = None if ranked is None else ranked.get("exp_td")
    return c
