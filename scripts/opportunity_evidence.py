"""Descriptive current-season opportunity evidence for Picks; never a projection.

Two independent inputs, both public and free:

* ``situational_usage`` is counted directly from nflverse play-by-play: red-zone,
  inside-10, inside-5 and third-down targets/carries plus the team totals needed
  for shares. Only completed regular-season games of ``season`` are used.
* ``expected_vs_actual`` aggregates ffverse/ffopportunity weekly expected points
  (an xgboost model trained on earlier seasons) against the same games' actuals.

Expected-minus-actual is process evidence about how a player's production
compared with his opportunity.  It is not a forecast, a bounceback signal or a
bet recommendation, and nothing here changes a projection or the Champion.
Missing rows are unknown, never zero.
"""
from __future__ import annotations

from collections import defaultdict
import math

from pick_evidence import _number, _team, source_sha256

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}
EXCLUDED_FLAGS = ("no_play", "qb_kneel", "qb_spike", "play_deleted", "two_point_attempt")
SITUATIONS = {
    "red_zone": lambda r: _number(r.get("yardline_100")) and r["yardline_100"] <= 20,
    "inside_10": lambda r: _number(r.get("yardline_100")) and r["yardline_100"] <= 10,
    "inside_5": lambda r: _number(r.get("yardline_100")) and r["yardline_100"] <= 5,
    "third_down": lambda r: r.get("down") == 3,
}
# (label, expected column, actual column) summed per player-game.
COMPONENTS = {
    "fantasy_points": ("total_fantasy_points_exp", "total_fantasy_points"),
    "receptions": ("receptions_exp", "receptions"),
    "rec_yards": ("rec_yards_gained_exp", "rec_yards_gained"),
    "rec_tds": ("rec_touchdown_exp", "rec_touchdown"),
    "rush_yards": ("rush_yards_gained_exp", "rush_yards_gained"),
    "rush_tds": ("rush_touchdown_exp", "rush_touchdown"),
    "pass_yards": ("pass_yards_gained_exp", "pass_yards_gained"),
    "pass_tds": ("pass_touchdown_exp", "pass_touchdown"),
}

DEFINITIONS = {
    "situations": {
        "red_zone": "offense yardline_100 <= 20", "inside_10": "yardline_100 <= 10",
        "inside_5": "yardline_100 <= 5", "third_down": "down == 3",
        "plays": "Scrimmage pass targets and designed or scramble rushes in completed regular-season games; kneels, spikes, no-plays, deleted plays and two-point tries are excluded.",
        "share": "Player count divided by the team's targets (or carries) in the same situation.",
    },
    "expected_vs_actual": "Season-to-date and per-game sums over completed games present in the ffopportunity weekly file; delta = actual - expected. The expected model was fitted on earlier seasons and is not retrained in-season.",
}


def _int(value):
    """Integer from ints, finite floats or numeric strings (the ffopportunity parquet stores season as text and week as float); anything else is 0."""
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            return 0
    return int(value) if _number(value) else 0


def _complete_games(pbp_rows, season, final_game_ids=None):
    """Games with a final PBP marker and, when supplied, a final schedule score.

    ``game_seconds_remaining == 0`` also occurs at the end of regulation in a game
    that goes to overtime, so a schedule final is required whenever it is known.
    """
    done = {str(r.get("game_id")) for r in pbp_rows
            if _int(r.get("season")) == int(season)
            and (r.get("play_type") == "game_end" or r.get("game_seconds_remaining") == 0)}
    return done if final_game_ids is None else done & {str(g) for g in final_game_ids}


def situational_usage(season, pbp_rows, positions, final_game_ids=None):
    """Count situational targets/carries per team|player from completed games."""
    complete = _complete_games(pbp_rows, season, final_game_ids)
    zero = lambda: {k: {"targets": 0, "carries": 0} for k in SITUATIONS}
    players = defaultdict(zero)
    teams = defaultdict(zero)
    seen = defaultdict(set)
    for r in pbp_rows:
        if _int(r.get("season")) != int(season) or r.get("season_type") != "REG":
            continue
        gid = str(r.get("game_id") or "")
        team = _team(r.get("posteam"))
        if gid not in complete or not team or any(r.get(k) == 1 for k in EXCLUDED_FLAGS):
            continue
        events = []
        if r.get("play_type") == "pass" and r.get("receiver_player_id"):
            events.append((str(r["receiver_player_id"]), "targets"))
        if r.get("rush_attempt") == 1 and r.get("rusher_player_id"):
            events.append((str(r["rusher_player_id"]), "carries"))
        for pid, kind in events:
            seen[(team, pid)].add(gid)
            for name, test in SITUATIONS.items():
                if test(r):
                    players[(team, pid)][name][kind] += 1
                    teams[team][name][kind] += 1
    output = {}
    for (team, pid), counts in sorted(players.items()):
        position = positions.get(pid)
        if position not in SKILL_POSITIONS:
            continue
        row = {"team": team, "player_id": pid, "position": position, "games": len(seen[(team, pid)])}
        for name, c in counts.items():
            t = teams[team][name]
            row[name] = {
                "targets": c["targets"], "carries": c["carries"],
                "team_targets": t["targets"], "team_carries": t["carries"],
                "target_share": c["targets"] / t["targets"] if t["targets"] else None,
                "carry_share": c["carries"] / t["carries"] if t["carries"] else None,
            }
        output[f"{team}|{pid}"] = row
    return output, len(complete)


def expected_vs_actual(season, expected_rows, complete_games, positions, names, recent_games=6):
    """Aggregate ffopportunity weekly rows for completed games only."""
    logs = defaultdict(list)
    for r in expected_rows:
        pid, gid = str(r.get("player_id") or ""), str(r.get("game_id") or "")
        if _int(r.get("season")) != int(season) or gid not in complete_games:
            continue
        if positions.get(pid) not in SKILL_POSITIONS:
            continue
        if not all(_number(r.get(c)) for c in ("total_fantasy_points_exp", "total_fantasy_points")):
            continue
        entry = {"game_id": gid, "week": _int(r.get("week")), "team": _team(r.get("posteam")),
                 "targets": int(r["rec_attempt"]) if _number(r.get("rec_attempt")) else None,
                 "carries": int(r["rush_attempt"]) if _number(r.get("rush_attempt")) else None}
        for label, (exp_col, act_col) in COMPONENTS.items():
            entry[label + "_expected"] = float(r[exp_col]) if _number(r.get(exp_col)) else None
            entry[label + "_actual"] = float(r[act_col]) if _number(r.get(act_col)) else None
        logs[(entry["team"], pid)].append(entry)
    output = {}
    for (team, pid), rows in sorted(logs.items()):
        rows.sort(key=lambda x: (x["week"], x["game_id"]))
        totals = {}
        for label in COMPONENTS:
            exp = [x[label + "_expected"] for x in rows]
            act = [x[label + "_actual"] for x in rows]
            # A component is reported only when every game has both sides.
            if all(_number(v) for v in exp + act):
                totals[label] = {"expected": round(sum(exp), 3), "actual": round(sum(act), 3),
                                 "delta": round(sum(act) - sum(exp), 3)}
        output[f"{team}|{pid}"] = {
            "team": team, "player_id": pid, "name": names.get(pid), "position": positions.get(pid),
            "games": len(rows), "weeks": [x["week"] for x in rows], "totals": totals,
            "games_log": rows[-recent_games:],
        }
    return output


def build_opportunity_evidence(*, season, pbp_rows, expected_rows, roster_rows, generated_at,
                               source_meta=None, final_game_ids=None):
    meta = source_meta or {}
    positions, names = {}, {}
    for row in roster_rows:
        gsis = row.get("gsis_id")
        if not gsis or _int(row.get("season")) != int(season):
            continue
        positions.setdefault(str(gsis), str(row.get("position") or "").upper())
        names.setdefault(str(gsis), row.get("full_name"))
    pbp_ok = bool(pbp_rows) and meta.get("pbp", {}).get("status", "loaded") == "loaded"
    exp_ok = bool(expected_rows) and meta.get("expected_points", {}).get("status", "loaded") == "loaded"
    usage, complete_count = ({}, 0)
    complete = _complete_games(pbp_rows, season, final_game_ids) if pbp_ok else set()
    if pbp_ok:
        usage, complete_count = situational_usage(season, pbp_rows, positions, final_game_ids)
    comparison = expected_vs_actual(season, expected_rows, complete, positions, names) if exp_ok and pbp_ok else {}
    return {
        "schema_version": 1, "status": "research_only", "season": int(season), "generated_at": generated_at,
        "provenance": {
            "play_by_play": {"provider": "nflverse via nflreadpy", "status": "loaded" if pbp_ok else "unavailable",
                             "completed_games": complete_count, "rows_sha256": source_sha256(
                                 [{k: r.get(k) for k in ("game_id", "play_id")} for r in pbp_rows if _int(r.get("season")) == int(season)]) if pbp_ok else None},
            "expected_points": {
                "provider": "ffverse/ffopportunity weekly expected points (release v1.0.0-data)",
                "status": "loaded" if exp_ok else "unavailable",
                "rows": len(expected_rows) if exp_ok else 0,
                "latest_week": max((_int(r.get("week")) for r in expected_rows), default=0) if exp_ok else 0,
                "rows_sha256": source_sha256(expected_rows) if exp_ok else None,
                "model_note": "Expected values come from a model fitted on earlier seasons and not retrained in-season; ffopportunity has no stated data license beyond GPL-3 code, so credit is given.",
                "attribution": "Expected points: ffverse/ffopportunity; play-by-play: nflverse.",
            },
        },
        "definitions": DEFINITIONS,
        "situational_usage": usage,
        "expected_vs_actual": comparison,
        "limitations": [
            "Expected-minus-actual is descriptive process evidence, not a forecast, bounceback signal or recommendation.",
            "Four-game samples are noisy; touchdowns dominate the deltas.",
            "A player missing from either source is unknown, not zero.",
            "Situational counts include only completed regular-season games; they are not route or snap measures.",
        ],
    }


EXPECTED_URL = "https://github.com/ffverse/ffopportunity/releases/download/v1.0.0-data/ep_weekly_{season}.parquet"


def fetch_expected_points(season, timeout=60):
    """Download the public ffopportunity weekly file; failure is unknown, never zero."""
    try:
        import io
        import polars as pl
        import requests
        response = requests.get(EXPECTED_URL.format(season=season), timeout=timeout)
        response.raise_for_status()
        rows = pl.read_parquet(io.BytesIO(response.content)).to_dicts()
        return rows, {"status": "loaded", "rows": len(rows)}
    except Exception as exc:  # Network, format or schema failure must not block the nightly build.
        return [], {"status": "unavailable", "reason": type(exc).__name__}
