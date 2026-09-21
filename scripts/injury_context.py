"""Build no-auth NFL injury effects and current replacement-role evidence.

The historical model compares played-through injury weeks with each player's
own preceding healthy active weeks.  It is an association, not a medical or
causal claim.  Current roles use observed nflverse snap/opportunity shares and
timestamped depth charts; missing evidence remains missing.
"""
from __future__ import annotations

import json
import math
import os
import statistics as stats_lib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from build_pipeline import atomic_json, finite, normalize_name

ROOT = Path(__file__).resolve().parents[1]
POSITIONS = {"QB", "RB", "WR", "TE"}
MARKETS = {
    "QB": {"pass_yds": "passing_yards", "pass_tds": "passing_yards", "rush_yds": "rushing_yards"},
    "RB": {"rush_yds": "rushing_yards", "rec_yds": "receiving_yards", "receptions": "receptions",
           "rush_tds": "carries", "rec_tds": "targets", "atd": "opportunities", "first_td": "opportunities"},
    "WR": {"rec_yds": "receiving_yards", "receptions": "receptions", "rush_yds": "rushing_yards",
           "rec_tds": "targets", "rush_tds": "carries", "atd": "opportunities", "first_td": "opportunities"},
    "TE": {"rec_yds": "receiving_yards", "receptions": "receptions", "rec_tds": "targets",
           "atd": "targets", "first_td": "targets"},
}
DEFAULT_SCALE = {"questionable": .88, "probable": .98, "limited": .94, "practice_dnp": .88}
BODY_ALIASES = {
    "hamstring": ("hamstring",), "ankle": ("ankle",), "knee": ("knee",), "hip": ("hip",),
    "groin": ("groin",), "foot": ("foot",), "toe": ("toe",), "calf": ("calf",),
    "quad": ("quadricep", "quad"), "back": ("back",), "shoulder": ("shoulder",),
    "concussion": ("concussion", "head"), "chest_rib": ("rib", "chest", "sternum"),
    "hand_wrist": ("hand", "wrist", "finger", "thumb"), "elbow": ("elbow",),
    "achilles": ("achilles",), "neck": ("neck",),
}


def canonical_team(value):
    value = str(value or "").upper()
    return {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}.get(value, value)


def identity_name(value):
    """Compact identity key kept in sync with shared/football-injuries.js."""
    return normalize_name(value).replace(" ", "")


def body_group(value):
    text = str(value or "").strip().lower()
    if not text or "not injury" in text or text in {"rest", "illness", "personal"}:
        return None
    for group, terms in BODY_ALIASES.items():
        if any(term in text for term in terms):
            return group
    return "other"


def status_group(row):
    report = str(row.get("report_status") or "").lower()
    practice = str(row.get("practice_status") or "").lower()
    if "out" in report or "doubtful" in report:
        return None
    if "questionable" in report:
        return "questionable"
    if "probable" in report:
        return "probable"
    if "did not" in practice or practice in {"dnp", "did not participate"}:
        return "practice_dnp"
    if "limited" in practice:
        return "limited"
    return None


def metric_value(row, column):
    if column == "opportunities":
        return float(row.get("carries") or 0) + float(row.get("targets") or 0)
    value = row.get(column)
    return float(value) if finite(value) else 0.0


def build_effects(injuries, weekly_stats, snaps, rosters):
    """Return empirical-Bayes effects using only played-through historical weeks."""
    pfr_to_gsis = {row.get("pfr_id"): row.get("gsis_id") for row in rosters if row.get("pfr_id") and row.get("gsis_id")}
    snap_map = {}
    for row in snaps:
        pid = pfr_to_gsis.get(row.get("pfr_player_id"))
        key = (int(row.get("season") or 0), int(row.get("week") or 0), pid)
        if pid and row.get("game_type") == "REG":
            snap_map[key] = max(snap_map.get(key, 0), float(row.get("offense_pct") or 0))
    stat_map = {}
    for row in weekly_stats:
        if row.get("season_type") != "REG" or not row.get("player_id"):
            continue
        key = (int(row["season"]), int(row["week"]), row["player_id"])
        stat_map[key] = dict(row, offense_pct=snap_map.get(key, 0))
    for key, snap_pct in snap_map.items():
        stat_map.setdefault(key, {"season": key[0], "week": key[1], "player_id": key[2], "offense_pct": snap_pct})

    reports = {}
    for row in injuries:
        pid, pos = row.get("gsis_id"), str(row.get("position") or "").upper()
        body, state = body_group(row.get("report_primary_injury") or row.get("practice_primary_injury")), status_group(row)
        if not pid or pos not in POSITIONS or not body or not state or row.get("season_type") != "REG":
            continue
        key = (int(row["season"]), int(row["week"]), pid)
        candidate = dict(row, position=pos, body_group=body, status_group=state)
        # Prefer a game-status row over practice-only duplicates.
        if key not in reports or (candidate.get("report_status") and not reports[key].get("report_status")):
            reports[key] = candidate

    by_player = defaultdict(list)
    for key, row in stat_map.items():
        if row.get("offense_pct", 0) >= .10:
            by_player[key[2]].append((key, row))
    for rows in by_player.values():
        rows.sort(key=lambda item: item[0][:2])
    injury_keys = set(reports)
    samples = defaultdict(list)
    observations = 0
    for key, report in reports.items():
        current = stat_map.get(key)
        if not current or current.get("offense_pct", 0) < .10:
            continue
        history = [row for prior_key, row in by_player.get(key[2], []) if prior_key[:2] < key[:2]
                   and prior_key not in injury_keys and row.get("offense_pct", 0) >= .20][-4:]
        if len(history) < 3:
            continue
        pos, body, state = report["position"], report["body_group"], report["status_group"]
        for market, column in MARKETS.get(pos, {}).items():
            baseline = stats_lib.mean(metric_value(row, column) for row in history)
            minimum = 10 if column.endswith("yards") else 1
            if baseline < minimum:
                continue
            ratio = max(.25, min(1.15, metric_value(current, column) / baseline))
            samples[(pos, body, state, market)].append(ratio)
            samples[(pos, "*", state, market)].append(ratio)
            observations += 1

    output = {}
    fallback_medians = {key: stats_lib.median(values) for key, values in samples.items() if key[1] == "*"}
    for key, values in sorted(samples.items()):
        pos, body, state, market = key
        raw = stats_lib.median(values)
        prior = DEFAULT_SCALE[state] if body == "*" else fallback_medians.get((pos, "*", state, market), DEFAULT_SCALE[state])
        # Shrink rare body-part cohorts strongly; never turn an injury into a boost.
        scale = max(.65, min(1.0, (len(values) * raw + 25 * prior) / (len(values) + 25)))
        output["|".join(key)] = {
            "position": pos, "body_part": body, "status": state, "market": market,
            "sample": len(values), "raw_median_ratio": round(raw, 4), "scale": round(scale, 4),
            "confidence": "high" if len(values) >= 75 else "moderate" if len(values) >= 25 else "limited",
        }
    return output, {"played_through_market_observations": observations, "effect_cells": len(output)}


def offensive_position(row):
    direct = str(row.get("position") or row.get("pos_abb") or "").upper()
    name = str(row.get("pos_name") or "").lower()
    if direct in POSITIONS:
        return direct
    if "quarterback" in name:
        return "QB"
    if "running back" in name or "fullback" in name:
        return "RB"
    if "wide receiver" in name:
        return "WR"
    if "tight end" in name:
        return "TE"
    return None


def build_current(season, injury_rows, depth_rows, weekly_roster, context, pbp_rows, ftn_rows):
    latest_week = max((int(row.get("week") or 0) for row in weekly_roster if row.get("game_type") == "REG"), default=0)
    roster = {row.get("gsis_id"): row for row in weekly_roster
              if row.get("game_type") == "REG" and int(row.get("week") or 0) == latest_week and row.get("gsis_id")}
    latest_depth_at = max((str(row.get("dt") or "") for row in depth_rows), default="")
    depth = {row.get("gsis_id"): row for row in depth_rows if str(row.get("dt") or "") == latest_depth_at and row.get("gsis_id")}
    scope = context.get("scopes", {}).get(str(season), {})
    usage = scope.get("players", {})

    reports = {}
    report_week = max((int(row.get("week") or 0) for row in injury_rows if row.get("season_type") == "REG"), default=0)
    for row in injury_rows:
        if row.get("season_type") != "REG" or int(row.get("week") or 0) != report_week or not row.get("gsis_id"):
            continue
        body = body_group(row.get("report_primary_injury") or row.get("practice_primary_injury"))
        if not body:
            continue
        player = roster.get(row["gsis_id"], row)
        identity = canonical_team(row.get("team") or player.get("team")) + "|" + identity_name(row.get("full_name") or player.get("full_name"))
        candidate = {
            "gsis_id": row["gsis_id"], "name": row.get("full_name"), "team": canonical_team(row.get("team")),
            "position": offensive_position(row), "body_part": body,
            "report_status": row.get("report_status"), "practice_status": row.get("practice_status"),
            "primary_injury": row.get("report_primary_injury") or row.get("practice_primary_injury"), "week": report_week,
        }
        if identity not in reports or (candidate["report_status"] and not reports[identity].get("report_status")):
            reports[identity] = candidate

    current = {}
    groups = defaultdict(list)
    for pid, row in roster.items():
        pos = offensive_position(row)
        if pos not in POSITIONS or not row.get("full_name") or not row.get("team"):
            continue
        team = canonical_team(row["team"])
        d, u = depth.get(pid, {}), usage.get(pid, {})
        record = {
            "gsis_id": pid, "name": row["full_name"], "team": team, "position": pos, "roster_week": latest_week,
            "roster_status": row.get("status"), "depth_slot": d.get("pos_slot"), "depth_rank": d.get("pos_rank"),
            "depth_updated_at": latest_depth_at or None, "snap_share": u.get("share"), "snap_share_type": u.get("share_type"),
            "target_share": u.get("target_share"), "rush_share": u.get("rush_share"), "games": u.get("games", 0),
        }
        identity = team + "|" + identity_name(row["full_name"])
        current[identity] = record
        groups[(team, pos)].append((identity, record))
    for rows in groups.values():
        rows.sort(key=lambda item: (item[1].get("depth_rank") or 99, -(item[1].get("snap_share") or 0), item[1]["name"]))
        for order, (_, row) in enumerate(rows, 1):
            row["role_order"] = order

    positions = {pid: offensive_position(row) for pid, row in roster.items()}
    qb_counts = defaultdict(Counter)
    ftn = {(str(row.get("nflverse_game_id")), float(row.get("nflverse_play_id") or -1)): row for row in ftn_rows}
    defense = defaultdict(Counter)
    for row in pbp_rows:
        passer, receiver, team = row.get("passer_player_id"), row.get("receiver_player_id"), canonical_team(row.get("posteam"))
        if not passer or not team or row.get("play_type") != "pass" or row.get("qb_spike") == 1:
            continue
        chart = ftn.get((str(row.get("game_id")), float(row.get("play_id") or -1)))
        # FTN's n_blitzers is the count of additional blitzing defenders, not
        # total pass rushers. One or more is therefore the supported split.
        blitz = bool(chart and finite(chart.get("n_blitzers")) and chart["n_blitzers"] >= 1)
        split = "blitz" if blitz else "non_blitz"
        qb_counts[(team, passer)]["dropbacks"] += 1
        qb_counts[(team, passer)][split + "_dropbacks"] += 1
        if receiver:
            pos = positions.get(receiver)
            if pos in {"RB", "WR", "TE"}:
                qb_counts[(team, passer)]["targets"] += 1
                qb_counts[(team, passer)]["targets_" + pos] += 1
                qb_counts[(team, passer)][split + "_targets_" + pos] += 1
        if chart and row.get("defteam"):
            d = defense[canonical_team(row["defteam"])]
            d["charted_dropbacks"] += 1
            d["blitzes"] += int(blitz)

    qb_tendencies = {}
    for team in {key[0] for key in qb_counts}:
        (team_key, passer), counts = max(((key, value) for key, value in qb_counts.items() if key[0] == team), key=lambda item: item[1]["dropbacks"])
        name = roster.get(passer, {}).get("full_name")
        rates = {pos: counts["targets_" + pos] / counts["targets"] if counts["targets"] else None for pos in ("RB", "WR", "TE")}
        qb_tendencies[team] = {"qb_id": passer, "qb_name": name, "dropbacks": counts["dropbacks"], "targets": counts["targets"],
                               "target_rate_by_position": rates,
                               "targets_per_dropback_by_position": {pos: counts["targets_" + pos] / counts["dropbacks"] if counts["dropbacks"] else None for pos in ("RB", "WR", "TE")},
                               "blitz_splits": {split: {"dropbacks": counts[split + "_dropbacks"],
                                   "target_rate_by_position": {pos: counts[split + "_targets_" + pos] / counts[split + "_dropbacks"] if counts[split + "_dropbacks"] else None for pos in ("RB", "WR", "TE")}}
                                   for split in ("blitz", "non_blitz")},
                               "supported_for_model": counts["dropbacks"] >= 50}
    defense_scheme = {team: {"charted_dropbacks": value["charted_dropbacks"],
                              "blitz_rate": value["blitzes"] / value["charted_dropbacks"] if value["charted_dropbacks"] else None,
                              "supported_for_model": value["charted_dropbacks"] >= 50}
                      for team, value in defense.items()}
    return current, reports, qb_tendencies, defense_scheme, {
        "roster_week": latest_week, "injury_report_week": report_week, "depth_updated_at": latest_depth_at or None,
        "current_players": len(current), "current_reports": len(reports),
    }


def build():
    import nflreadpy as nfl

    season = int(os.getenv("SEASON", datetime.now().year))
    first = max(2009, season - int(os.getenv("INJURY_LOOKBACK_SEASONS", "5")))
    history_seasons = list(range(first, season))
    context_path = ROOT / "data" / "football_context.json"
    context = json.loads(context_path.read_text(encoding="utf-8")) if context_path.exists() else {}

    historical_injuries = nfl.load_injuries(history_seasons).to_dicts()
    historical_stats = nfl.load_player_stats(history_seasons, summary_level="week").to_dicts()
    historical_snaps = nfl.load_snap_counts(history_seasons).to_dicts()
    historical_rosters = nfl.load_rosters(history_seasons).to_dicts()
    effects, validation = build_effects(historical_injuries, historical_stats, historical_snaps, historical_rosters)

    current_injuries = nfl.load_injuries([season]).to_dicts()
    depth = nfl.load_depth_charts([season]).to_dicts()
    weekly_roster = nfl.load_rosters_weekly([season]).to_dicts()
    pbp = nfl.load_pbp([season]).to_dicts()
    ftn = nfl.load_ftn_charting([season]).to_dicts()
    players, reports, qb, defenses, current_meta = build_current(season, current_injuries, depth, weekly_roster, context, pbp, ftn)

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "schema_version": 1, "model_version": "injury-cohort-role-1", "generated_at": generated, "season": season,
        "historical_seasons": history_seasons, "effects": effects, "current_players": players,
        "current_reports": reports, "qb_tendencies": qb, "defense_scheme": defenses,
        "validation": {**validation, **current_meta},
        "sources": {
            "injuries": {"provider": "nflverse injury reports", "authentication": "none", "rows": len(historical_injuries) + len(current_injuries)},
            "depth_charts": {"provider": "nflverse timestamped depth charts", "authentication": "none", "rows": len(depth)},
            "weekly_rosters": {"provider": "nflverse weekly rosters", "authentication": "none", "rows": len(weekly_roster)},
            "snap_roles": {"provider": "GOING football_context from nflverse snap counts/PBP", "authentication": "none"},
            "qb_scheme": {"provider": "nflverse PBP + FTN charting", "authentication": "none", "pbp_rows": len(pbp), "ftn_rows": len(ftn)},
        },
        "method": {
            "injury_effect": "Median injured-week outcome divided by the same player's prior four healthy active weeks; minimum three baselines; ratios winsorized 0.25-1.15 and shrunk toward position/status priors with strength 25; positive injury boosts prohibited.",
            "playing_through": "At least 10% offensive snaps; Out and Doubtful excluded.",
            "replacement_role": "Current observed snap, target and rush shares plus timestamped depth evidence. The browser applies market-specific bounded transfer caps.",
            "scheme_limit": "Current blitz splits require 50 charted dropbacks. Current-season man/zone participation is unavailable in-season and is not inferred.",
            "causality": "Observed association only; not medical advice and not proof that injury caused the change.",
        },
    }
    atomic_json(ROOT / "data" / "injury_context.json", payload)
    print(f"[injury context] {len(effects)} effects; {len(players)} current players; {len(reports)} reports")


if __name__ == "__main__":
    build()
