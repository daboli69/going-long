"""Build additive, descriptive Picks evidence from public nflverse snapshots.

Nothing in this module changes a projection or recommendation.  Teammate
absence is accepted only from an explicit weekly ``Out`` report;
positive offensive snaps establish that a teammate played.  Missing rows are
unknown, never zero or an inferred absence.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
import math


SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _timestamp(value):
    """Parse only timestamps with an explicit timezone; naive times are unknown."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def source_sha256(rows):
    """Hash a deterministic representation of loaded source rows, not raw bytes."""
    encoded = sorted(_canonical_json(row) for row in rows)
    return hashlib.sha256(_canonical_json(encoded).encode("utf-8")).hexdigest()


def _team(value):
    value = str(value or "").upper()
    return {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV", "SD": "LAC", "STL": "LA"}.get(value, value)


def _game_time(game):
    value = game.get("kickoff") or game.get("gameday") or game.get("game_date")
    parsed = _timestamp(value)
    if parsed:
        return parsed
    # Schedules can use a date-only field. That is useful to order games, but
    # not precise enough to prove an injury report preceded kickoff.
    if isinstance(value, str) and len(value) == 10:
        try:
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _finite_mean(values):
    values = [float(x) for x in values if _number(x)]
    return sum(values) / len(values) if values else None


def _summarize(games):
    return {
        "games": len(games),
        "offense_snaps_per_game": _finite_mean([g["offense_snaps"] for g in games]),
        "offense_snap_share": _finite_mean([g["offense_pct"] for g in games]),
        "targets_per_game": _finite_mean([g["targets"] for g in games]),
        "target_share": _finite_mean([g["target_share"] for g in games]),
        "receiving_yards_per_game": _finite_mean([g["receiving_yards"] for g in games]),
        "carries_per_game": _finite_mean([g["carries"] for g in games]),
        "carry_share": _finite_mean([g["carry_share"] for g in games]),
        "rushing_yards_per_game": _finite_mean([g["rushing_yards"] for g in games]),
    }


def build_pick_evidence(*, season, games, pbp_rows, snap_rows, roster_rows,
                        injury_rows, weekly_roster_rows=(), as_of, generated_at, source_meta=None,
                        minimum_games=2, recent_games=6):
    """Return provenance, current roster/report inputs, trends and cautious splits.

    ``games`` are nflverse schedule rows; ``pbp_rows`` and ``snap_rows`` are
    nflreadpy rows for the season; ``roster_rows`` are season rosters, used only
    to map PFR snap IDs to stable GSIS IDs and positions. Injury-report OUT
    Undated weekly OUT reports establish retrospective descriptive cohorts,
    never historical decision-time availability. Dated reports cannot postdate
    kickoff. A final schedule and game-end PBP marker establish complete games.
    """
    now = _timestamp(generated_at)
    cutoff_date = str(as_of or (now.date().isoformat() if now else ""))[:10]
    sources = source_meta or {}
    provenance = {
        "provider": "nflverse public data via nflreadpy",
        "authentication": "none",
        "generated_at": generated_at,
        "as_of": cutoff_date,
        "source_updated_at": None,
        "inputs": {},
    }
    for name, rows in (("schedules", games), ("pbp", pbp_rows), ("snap_counts", snap_rows),
                       ("rosters", roster_rows), ("weekly_rosters", weekly_roster_rows),
                       ("injury_reports", injury_rows)):
        detail = dict(sources.get(name) or {})
        detail.setdefault("status", "loaded" if rows else "unavailable")
        detail.setdefault("rows", len(rows))
        detail.setdefault("loaded_at", generated_at)
        detail.setdefault("source_updated_at", None)
        detail.setdefault("loaded_rows_sha256", source_sha256(rows))
        provenance["inputs"][name] = detail

    schedule = {}
    for game in games:
        if int(game.get("season") or 0) != int(season) or game.get("game_type", "REG") != "REG":
            continue
        gid = game.get("game_id") or game.get("id")
        kickoff = _game_time(game)
        if not gid or not kickoff or (now and kickoff >= now) or not all(_number(game.get(k)) for k in ('home_score', 'away_score')):
            continue
        schedule[str(gid)] = {
            "game_id": str(gid), "week": int(game.get("week") or 0),
            "kickoff": kickoff, "date": kickoff.date().isoformat(),
            "home": _team(game.get("home_team") or game.get("home")),
            "away": _team(game.get("away_team") or game.get("away")),
        }

    pfr_to_gsis, positions = {}, {}
    for row in roster_rows:
        if int(row.get("season") or 0) != int(season):
            continue
        gsis, pfr = row.get("gsis_id"), row.get("pfr_id")
        if gsis and pfr:
            pfr_to_gsis[str(pfr)] = str(gsis)
        if gsis and str(row.get("position") or "").upper() in SKILL_POSITIONS:
            positions.setdefault(str(gsis), str(row["position"]).upper())

    complete_games = {str(r.get('game_id')) for r in pbp_rows if
                      r.get('play_type') == 'game_end' or r.get('game_seconds_remaining') == 0}
    schedule = {gid: game for gid, game in schedule.items() if gid in complete_games}
    # Zero opportunity requires positive snaps AND a complete game's PBP.
    appearances = {}
    latest_team_games = defaultdict(list)
    for row in snap_rows:
        if int(row.get("season") or 0) != int(season) or row.get("game_type", "REG") != "REG":
            continue
        gid = str(row.get("game_id") or "")
        game = schedule.get(gid)
        team = _team(row.get("team"))
        pid = pfr_to_gsis.get(str(row.get("pfr_player_id") or ""))
        snaps = row.get("offense_snaps")
        if not game or team not in (game["home"], game["away"]) or not pid or not _number(snaps) or snaps <= 0:
            continue
        key = (gid, team, pid)
        pos = positions.get(pid)
        if pos not in SKILL_POSITIONS:
            continue
        appearances[key] = {
            "game_id": gid, "week": game["week"], "date": game["date"], "kickoff": game["kickoff"].isoformat(),
            "team": team, "player_id": pid, "position": pos,
            "offense_snaps": float(snaps),
            "offense_pct": float(row["offense_pct"]) if _number(row.get("offense_pct")) else None,
            "targets": 0, "receiving_yards": 0.0, "carries": 0, "rushing_yards": 0.0,
        }
        latest_team_games[(team, game["week"])].append(gid)

    team_usage = defaultdict(lambda: {"targets": 0, "carries": 0})
    for row in pbp_rows:
        if int(row.get("season") or 0) != int(season) or row.get("season_type") != "REG":
            continue
        gid = str(row.get("game_id") or "")
        game = schedule.get(gid)
        team = _team(row.get("posteam"))
        if not game or team not in (game["home"], game["away"]):
            continue
        if any(row.get(k) == 1 for k in ("no_play", "qb_kneel", "qb_spike", "play_deleted")):
            continue
        if row.get("play_type") == "pass":
            receiver = row.get("receiver_player_id")
            if receiver:
                receiver = str(receiver)
                team_usage[(gid, team)]["targets"] += 1
                key = (gid, team, receiver)
                if key in appearances:
                    appearances[key]["targets"] += 1
                    if _number(row.get("receiving_yards")):
                        appearances[key]["receiving_yards"] += float(row["receiving_yards"])
        if row.get("rush_attempt") == 1 and not row.get("qb_kneel"):
            runner = row.get("rusher_player_id")
            if runner:
                runner = str(runner)
                team_usage[(gid, team)]["carries"] += 1
                key = (gid, team, runner)
                if key in appearances:
                    appearances[key]["carries"] += 1
                    if _number(row.get("rushing_yards")):
                        appearances[key]["rushing_yards"] += float(row["rushing_yards"])

    for key, appearance in appearances.items():
        totals = team_usage[(key[0], key[1])]
        appearance["target_share"] = appearance["targets"] / totals["targets"] if totals["targets"] else None
        appearance["carry_share"] = appearance["carries"] / totals["carries"] if totals["carries"] else None

    # Choose the latest report row known by kickoff for each exact team/week/GSIS.
    reports = defaultdict(list)
    unverified_report_times = 0
    for row in injury_rows:
        if int(row.get("season") or 0) != int(season) or row.get("season_type") != "REG" or not row.get("gsis_id"):
            continue
        team, week = _team(row.get("team")), int(row.get("week") or 0)
        changed = _timestamp(row.get("date_modified"))
        if changed is None:
            if row.get("report_status"):
                unverified_report_times += 1
            else:
                continue
        if now and changed and changed > now:
            continue
        key = (team, week, str(row["gsis_id"]))
        reports[key].append({"date_modified": changed, "row": row})
    for rows in reports.values():
        rows.sort(key=lambda item: item["date_modified"] or datetime.min.replace(tzinfo=timezone.utc))

    # Pair skill-position teammates, including cross-position redistribution.
    # OUT requires an explicit weekly report; WITH requires positive
    # observed snaps. Other states, including missing rows, stay unknown.
    pair_games = defaultdict(lambda: {"with": [], "without": []})
    observed_by_game = defaultdict(dict)
    reported_by_team = defaultdict(set)
    for (gid, team, pid), appearance in appearances.items():
        observed_by_game[(gid, team)][pid] = appearance
    for team, week, pid in reports:
        if positions.get(pid) in SKILL_POSITIONS:
            reported_by_team[team].add(pid)
    for (gid, team, focal_id), focal in appearances.items():
        game = schedule[gid]
        for teammate_id in sorted(set(observed_by_game[(gid, team)]) | reported_by_team[team]):
            if teammate_id == focal_id:
                continue
            teammate = observed_by_game[(gid, team)].get(teammate_id)
            candidates = reports.get((team, game["week"], teammate_id), ())
            eligible_reports = [item for item in candidates if item["date_modified"] is None or item["date_modified"] <= game["kickoff"]]
            r = eligible_reports[-1] if eligible_reports else None
            condition = None
            if r and str(r["row"].get("report_status") or "").strip().casefold() == "out":
                # An observed snap contradicts the reported OUT; leave unknown.
                condition = None if teammate else "without"
            elif teammate and teammate["offense_snaps"] > 0:
                condition = "with"
            if condition:
                pair_games[(team, focal_id, teammate_id)][condition].append(focal)

    splits = {}
    for (team, focal_id, teammate_id), groups in sorted(pair_games.items()):
        n_with, n_without = len(groups["with"]), len(groups["without"])
        if not n_without:
            continue  # No observed absence cohort to compare; do not ship empty pairs.
        enough = n_with >= minimum_games and n_without >= minimum_games
        id_row = next((r for r in roster_rows if str(r.get("gsis_id")) == teammate_id), {})
        focal_row = next((r for r in roster_rows if str(r.get("gsis_id")) == focal_id), {})
        key = f"{team}|{focal_id}|{teammate_id}"
        splits[key] = {
            "team": team, "player_id": focal_id, "position": positions.get(focal_id),
            "teammate_id": teammate_id, "teammate_name": id_row.get("full_name"),
            "player_name": focal_row.get("full_name"), "minimum_games_per_condition": minimum_games,
            "with_n": n_with, "without_n": n_without,
            "with": _summarize(groups["with"]) if enough else None,
            "without": _summarize(groups["without"]) if enough else None,
            "status": "descriptive_observed" if enough else "insufficient_games",
            "interpretation": "Observed association only; usage shares/counts are not causal and do not alter projections.",
            "season": int(season),
            "report_timing": "Weekly refreshed reports may lack publication timestamps; descriptive cohorts cannot establish historical pregame availability.",
        }

    recent = sorted(appearances.values(), key=lambda x: (x["team"], x["player_id"], x["date"], x["game_id"]))
    by_team_player = defaultdict(list)
    for appearance in recent:
        by_team_player[(appearance["team"], appearance["player_id"])].append(appearance)
    trends = {}
    for (team, pid), rows in sorted(by_team_player.items()):
        rows = rows[-recent_games:]
        trends[f"{team}|{pid}"] = {
            "team": team, "player_id": pid, "position": positions.get(pid),
            "games": len(rows), "minimum_games": 2,
            "status": "descriptive_observed" if len(rows) >= 2 else "insufficient_games",
            "games_log": rows,
            "interpretation": "Only games with positive observed offensive snaps are listed; an omitted player-game is unknown, not zero or inactive.",
        }

    current_roster_week = max((int(r.get("week") or 0) for r in weekly_roster_rows
                               if int(r.get("season") or 0) == int(season)
                               and r.get("game_type") == "REG"), default=0)
    # Current roster input can be passed as weekly rows (marked by week and
    # status); keep exact source codes for the consumer, including RES and INA.
    current_roster = []
    status_codes = set()
    for row in weekly_roster_rows:
        if int(row.get("season") or 0) != int(season) or int(row.get("week") or 0) != current_roster_week:
            continue
        if row.get("game_type") not in (None, "REG"):
            continue
        status = str(row.get("status") or "")
        if status:
            status_codes.add(status)
        current_roster.append({
            "player_id": str(row.get("gsis_id") or ""), "team": _team(row.get("team")),
            "name": row.get("full_name"), "position": str(row.get("position") or "").upper(),
            "status": status or None, "week": current_roster_week,
        })

    current_report_week = max((int(r.get("week") or 0) for r in injury_rows
                               if int(r.get("season") or 0) == int(season)
                               and r.get("season_type") == "REG"), default=0)
    current_reports = {}
    for (team, week, pid), candidates in reports.items():
        if week != current_report_week:
            continue
        eligible = [item for item in candidates if not now or item["date_modified"] is None or item["date_modified"] <= now]
        if not eligible:
            continue
        row = eligible[-1]["row"]
        current_reports[f"{team}|{pid}"] = {
            "player_id": pid, "team": team, "week": week,
            "report_status": row.get("report_status"), "practice_status": row.get("practice_status"),
            "primary_injury": row.get("report_primary_injury") or row.get("practice_primary_injury"),
            "reported_at": eligible[-1]["date_modified"].isoformat() if eligible[-1]["date_modified"] else None,
        }

    source_status = {name: str(provenance["inputs"][name].get("status", "unknown"))
                     for name in ("pbp", "snap_counts", "rosters", "weekly_rosters", "injury_reports")}
    with_without_ready = all(source_status[name] == "loaded" for name in
                             ("pbp", "snap_counts", "rosters", "injury_reports"))

    return {
        "schema_version": 1, "status": "research_only",
        "season": int(season), "as_of": cutoff_date, "generated_at": generated_at,
        "provenance": provenance,
        "current_roster": {
            "status": "loaded" if source_status["weekly_rosters"] == "loaded" else "unavailable",
            "week": current_roster_week, "status_codes": sorted(status_codes),
            "players": current_roster,
        },
        "current_injury_reports": {
            "status": "loaded" if source_status["injury_reports"] == "loaded" else "unavailable",
            "week": current_report_week, "players": current_reports,
        },
        "with_without_status": "ready_for_descriptive_counts" if with_without_ready else "source_unavailable",
        "report_time_audit": {
            "eligible_dated_rows": sum(item['date_modified'] is not None for items in reports.values() for item in items), "report_rows_with_unknown_timezone": unverified_report_times,
            "rule": "Exact weekly OUT plus no observed offensive snaps establishes a descriptive absence. Undated reports cannot establish pregame knowledge; contradictory snaps remain unknown.",
        },
        "minimum_games_per_condition": minimum_games,
        "recent_games_per_player": recent_games,
        "recent_player_games": trends if all(source_status[name] == 'loaded' for name in ('pbp','snap_counts','rosters')) else {},
        "teammate_out_splits": splits if with_without_ready else {},
        "limitations": [
            "Public nflverse injury and snap data are refreshed snapshots, not immutable decision-time archives.",
            "A missing injury or snap row is unknown. Positive offensive snaps are required to establish WITH.",
            "Undated weekly OUT reports support retrospective descriptive cohorts only, never a decision-time backtest.",
            "Small samples are descriptive context only; no projection, probability, recommendation, or stake is changed.",
            "Routes are not measured by this evidence. Offensive snap share is not route share.",
        ],
    }
