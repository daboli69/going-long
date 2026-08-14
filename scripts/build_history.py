#!/usr/bin/env python3
"""
Builds data/history.json — real production history for every player, keyed by
Sleeper ID so it joins straight onto the draft board.

Sources (free, no keys, both on GitHub):
  nflverse-data   stats_player_week_<season>.csv   weekly player stats
  nflverse-data   nextgen_stats/ngs_*              NGS season aggregates (via nflreadpy)
  DynastyProcess  db_playerids.csv                 gsis_id <-> sleeper_id

Why weekly rather than season totals: the guide's metrics are per-game, need a
games-played filter, and drop the final week of the season as meaningless. You
can only do that from week-level rows.

nflreadpy is an optional dependency, used only for Next Gen Stats — nflverse
serves those as Parquet with no guessable public URL, and nflreadpy is the only
thing that knows the real path. If it isn't installed, the script still runs
and just skips the NGS fields (has_ngs: false in the output).

What comes out, per player per season:
  g            games with a snap (REG, weeks 1..17)
  ppr / half / std      fantasy points per game
  rush_fp      rushing fantasy points per game   (QB mobility)
  td_rate      passing TDs / attempts            (QB regression)
  fp_db        fantasy points per dropback       (late QB)
  rec_fp       receiving fantasy points per game (RB pass-game role)
  rush10       share of carries gaining 10+      (late RB)
  adot         average depth of target           (late WR)
  td_pg        total TDs per game                (TE regression)
  wopr / racr / pacr / cpoe / *_epa_pg   nflverse's own advanced rate stats
  tgt_share, tgt_pg, car_pg, att
  weekly       [week, PPR points] pairs for the qualifying season (sparkline)

n1 additionally carries an "ngs" block when available:
  separation, cushion, yac_oe     receiving — route-running proxy, since real
                                   routes-run charting has no free source
  ryoe_pa, box8_rate              rushing — production over expectation, and
                                   how stacked the box was
  aggressiveness, time_to_throw,
  air_to_sticks, cpoe_ngs         passing — QB tendency profile
"""

import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "history.json"

SEASON = int(os.environ.get("SEASON", "2026"))
N_SEASONS = int(os.environ.get("HISTORY_SEASONS", "3"))
# The guide drops the final week of every season — it's mostly rested starters.
LAST_WEEK = int(os.environ.get("HISTORY_LAST_WEEK", "17"))

NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"
PLAYER_IDS = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
KEEP_POS = {"QB", "RB", "WR", "TE"}


def fetch_csv(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "going-long-etl/1.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            return list(csv.DictReader(io.StringIO(text)))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last = exc
    raise RuntimeError(f"failed to fetch {url}: {last}")


def num(row, key):
    v = row.get(key)
    if v in (None, "", "NA", "NaN"):
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


def id_map():
    """gsis_id -> sleeper_id, plus sleeper_id -> draft year for career-year rules"""
    rows = fetch_csv(PLAYER_IDS)
    out, drafted = {}, {}
    for r in rows:
        g, s = (r.get("gsis_id") or "").strip(), (r.get("sleeper_id") or "").strip()
        if g and s:
            out[g] = s
        if s:
            try:
                dy = int(float(r.get("draft_year") or 0))
                if 1980 < dy < 2100:
                    drafted[s] = dy
            except ValueError:
                pass
    print(f"id crosswalk: {len(out)} gsis->sleeper pairs, {len(drafted)} with draft year")
    return out, drafted


def fantasy_points(r, rec_pts):
    """Standard scoring with a configurable point-per-reception."""
    fumbles_lost = (num(r, "sack_fumbles_lost") + num(r, "rushing_fumbles_lost")
                    + num(r, "receiving_fumbles_lost"))
    passing = (0.04 * num(r, "passing_yards") + 4 * num(r, "passing_tds")
               - 2 * num(r, "passing_interceptions") + 2 * num(r, "passing_2pt_conversions"))
    rushing = (0.1 * num(r, "rushing_yards") + 6 * num(r, "rushing_tds")
               + 2 * num(r, "rushing_2pt_conversions"))
    receiving = (0.1 * num(r, "receiving_yards") + 6 * num(r, "receiving_tds")
                 + rec_pts * num(r, "receptions") + 2 * num(r, "receiving_2pt_conversions"))
    return passing + rushing + receiving - 2 * fumbles_lost


def rushing_points(r):
    """Rushing fantasy points only — the quarterback separator in the guide."""
    return (0.1 * num(r, "rushing_yards") + 6 * num(r, "rushing_tds")
            + 2 * num(r, "rushing_2pt_conversions"))


try:
    import nflreadpy as _nfl
    HAVE_NFLREADPY = True
except ImportError:
    HAVE_NFLREADPY = False


def fetch_ngs(season):
    """
    Next Gen Stats season aggregates (week=0, season_type=REG rows), keyed by
    gsis_id. Separate from the weekly CSV pull above because it needs
    nflreadpy to resolve — nflverse serves these as Parquet with no
    guessable filename, only nflreadpy's own downloader knows the path.

    Gives real substitutes for charting stats that aren't free anywhere:
    avg_separation and YAC-over-expected stand in for route-running
    efficiency; rush_yards_over_expected stands in for the "is this back's
    production his blocking or his own legs" question; aggressiveness and
    time-to-throw profile a quarterback's tendencies beyond raw rushing.
    """
    if not HAVE_NFLREADPY:
        return {}
    out = {}
    for stat_type in ("rushing", "receiving", "passing"):
        try:
            df = _nfl.load_nextgen_stats(stat_type=stat_type, seasons=[season])
        except Exception as exc:  # noqa: BLE001
            print(f"  ! NGS {stat_type} {season} unavailable: {exc}")
            continue
        df = df.filter((df["week"] == 0) & (df["season_type"] == "REG"))
        for row in df.iter_rows(named=True):
            gid = row.get("player_gsis_id")
            if not gid:
                continue
            rec = out.setdefault(gid, {})
            if stat_type == "rushing":
                rec["ryoe_pa"] = row.get("rush_yards_over_expected_per_att")
                rec["box8_rate"] = row.get("percent_attempts_gte_eight_defenders")
            elif stat_type == "receiving":
                rec["separation"] = row.get("avg_separation")
                rec["cushion"] = row.get("avg_cushion")
                rec["yac_oe"] = row.get("avg_yac_above_expectation")
            elif stat_type == "passing":
                rec["aggressiveness"] = row.get("aggressiveness")
                rec["time_to_throw"] = row.get("avg_time_to_throw")
                rec["air_to_sticks"] = row.get("avg_air_yards_to_sticks")
                rec["cpoe_ngs"] = row.get("completion_percentage_above_expectation")
    return out


def build_season(season, gsis_to_sleeper):
    url = f"{NFLVERSE}/stats_player/stats_player_week_{season}.csv"
    try:
        rows = fetch_csv(url)
    except RuntimeError as exc:
        print(f"  ! {season}: {exc}")
        return {}
    agg = {}
    kept = 0
    for r in rows:
        if (r.get("season_type") or "").upper() != "REG":
            continue
        try:
            week = int(float(r.get("week") or 0))
        except ValueError:
            continue
        if week < 1 or week > LAST_WEEK:
            continue
        pos = (r.get("position") or "").upper()
        if pos not in KEEP_POS:
            continue
        sid = gsis_to_sleeper.get((r.get("player_id") or "").strip())
        if not sid:
            continue

        a = agg.setdefault(sid, {
            "pos": pos, "name": r.get("player_display_name") or r.get("player_name"),
            "g": 0, "ppr": 0.0, "half": 0.0, "std": 0.0, "rush_fp": 0.0,
            "tgt": 0.0, "car": 0.0, "rec": 0.0, "rec_yds": 0.0, "rush_yds": 0.0,
            "tgt_share": 0.0, "ay_share": 0.0, "share_n": 0,
            "att": 0.0, "pass_td": 0.0, "sacks": 0.0, "air_yds": 0.0,
            "rush10": 0.0, "rec_td": 0.0, "rush_td": 0.0,
            # already computed by nflverse — just sum and average like everything else.
            "wopr": 0.0, "wopr_n": 0, "racr": 0.0, "racr_n": 0,
            "pacr": 0.0, "pacr_n": 0, "cpoe": 0.0, "cpoe_n": 0,
            "pass_epa": 0.0, "rush_epa": 0.0, "rec_epa": 0.0,
            "weekly": [],   # (week, ppr-points) — sparkline source, last season only
        })
        a["g"] += 1
        kept += 1
        a["ppr"]     += fantasy_points(r, 1.0)
        a["half"]    += fantasy_points(r, 0.5)
        a["std"]     += fantasy_points(r, 0.0)
        a["rush_fp"] += rushing_points(r)
        a["tgt"]     += num(r, "targets")
        a["car"]     += num(r, "carries")
        a["rec"]     += num(r, "receptions")
        a["rec_yds"] += num(r, "receiving_yards")
        a["rush_yds"] += num(r, "rushing_yards")
        a["att"]     += num(r, "attempts")
        a["pass_td"] += num(r, "passing_tds")
        a["sacks"]   += num(r, "sacks_suffered")
        a["air_yds"] += num(r, "receiving_air_yards")
        a["rush10"]  += num(r, "rushing_10")
        a["rec_td"]  += num(r, "receiving_tds")
        a["rush_td"] += num(r, "rushing_tds")
        a["pass_epa"] += num(r, "passing_epa")
        a["rush_epa"] += num(r, "rushing_epa")
        a["rec_epa"]  += num(r, "receiving_epa")
        a["weekly"].append([week, round(fantasy_points(r, 1.0), 1)])
        if num(r, "targets") > 0:
            a["wopr"] += num(r, "wopr"); a["wopr_n"] += 1
            a["racr"] += num(r, "racr"); a["racr_n"] += 1
        if num(r, "attempts") >= 10:
            a["pacr"] += num(r, "pacr"); a["pacr_n"] += 1
            a["cpoe"] += num(r, "passing_cpoe"); a["cpoe_n"] += 1
        ts = num(r, "target_share")
        if ts:
            a["tgt_share"] += ts
            a["ay_share"] += num(r, "air_yards_share")
            a["share_n"] += 1

    out = {}
    for sid, a in agg.items():
        g = a["g"]
        if g < 1:
            continue
        sn = max(a["share_n"], 1)
        r2 = lambda v: round(v, 2)
        dropbacks = a["att"] + a["sacks"]
        rec_fp = 0.1 * a["rec_yds"] + 6 * a["rec_td"] + 1.0 * a["rec"]
        out[sid] = {
            "pos": a["pos"], "g": g,
            "ppr": r2(a["ppr"] / g), "half": r2(a["half"] / g), "std": r2(a["std"] / g),
            "rush_fp": r2(a["rush_fp"] / g),
            "tgt_pg": r2(a["tgt"] / g), "car_pg": r2(a["car"] / g),
            "rec_pg": r2(a["rec"] / g),
            "att": int(a["att"]), "car": int(a["car"]),
            # QB: touchdown rate regresses hard; points per dropback is the
            # late-round separator. Both need volume to mean anything.
            "td_rate": round(a["pass_td"] / a["att"], 4) if a["att"] >= 100 else None,
            "fp_db": round(a["ppr"] / dropbacks, 3) if dropbacks >= 100 else None,
            # RB: receiving role early, explosiveness late.
            "rec_fp": r2(rec_fp / g),
            "rush10": round(a["rush10"] / a["car"], 3) if a["car"] >= 30 else None,
            # WR/TE: how they were deployed, and touchdown dependence.
            "adot": round(a["air_yds"] / a["tgt"], 2) if a["tgt"] >= 20 else None,
            "td_pg": r2((a["rec_td"] + a["rush_td"]) / g),
            "tgt_share": round(a["tgt_share"] / sn, 3) if a["share_n"] else None,
            "ay_share": round(a["ay_share"] / sn, 3) if a["share_n"] else None,
            # Already computed by nflverse — no reason to re-derive them.
            "wopr": round(a["wopr"] / a["wopr_n"], 3) if a["wopr_n"] else None,
            "racr": round(a["racr"] / a["racr_n"], 3) if a["racr_n"] else None,
            "pacr": round(a["pacr"] / a["pacr_n"], 3) if a["pacr_n"] else None,
            "cpoe": round(a["cpoe"] / a["cpoe_n"], 2) if a["cpoe_n"] else None,
            "pass_epa_pg": r2(a["pass_epa"] / g), "rush_epa_pg": r2(a["rush_epa"] / g),
            "rec_epa_pg": r2(a["rec_epa"] / g),
            # trimmed sparkline source — filled in only for the most recent
            # season by build(), to keep history.json from ballooning.
            "weekly": sorted(a["weekly"]),
        }
    print(f"  {season}: {len(out)} players from {kept} player-weeks")
    return out


def build():
    gsis_to_sleeper, draft_year = id_map()
    sleeper_to_gsis = {v: k for k, v in gsis_to_sleeper.items()}
    seasons = [SEASON - i for i in range(1, N_SEASONS + 1)]  # 2025, 2024, 2023
    by_season = {}
    for s in seasons:
        by_season[s] = build_season(s, gsis_to_sleeper)

    print("\nNext Gen Stats enrichment" + ("" if HAVE_NFLREADPY else " — skipped (nflreadpy not installed)"))
    ngs_by_season = {}
    if HAVE_NFLREADPY:
        for s in seasons:
            ngs_by_season[s] = fetch_ngs(s)
            print(f"  {s}: {len(ngs_by_season[s])} players")

    players = {}
    for s in seasons:
        for sid, rec in by_season[s].items():
            players.setdefault(sid, {})[str(s)] = rec

    # n1 = most recent season with 8+ games, which is the guide's qualifying bar
    payload_players = {}
    for sid, hist in players.items():
        n1 = None
        for s in seasons:
            rec = hist.get(str(s))
            if rec and rec["g"] >= 8:
                n1 = {"season": s, **rec}
                gid = sleeper_to_gsis.get(sid)
                ngs = ngs_by_season.get(s, {}).get(gid) if gid else None
                if ngs:
                    n1["ngs"] = {k: (round(v, 3) if isinstance(v, float) else v)
                                 for k, v in ngs.items() if v is not None}
                break
        dy = draft_year.get(sid)
        # The weekly sparkline is only useful for the qualifying season —
        # strip it from every other season so the file doesn't balloon.
        for s_key, rec in hist.items():
            if not n1 or s_key != str(n1["season"]):
                rec.pop("weekly", None)
        payload_players[sid] = {
            "seasons": hist, "n1": n1,
            "draft_year": dy,
            # career year 1 = rookie season. The guide's Year 2 QB finding
            # and the rookie WR buckets both key off this.
            "career_year": (SEASON - dy + 1) if dy else None,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seasons": seasons,
        "last_week": LAST_WEEK,
        "has_ngs": HAVE_NFLREADPY,
        "source": "nflverse-data stats_player + nextgen_stats, ids via DynastyProcess",
        "players": payload_players,
    }, separators=(",", ":")))
    kb = OUT.stat().st_size / 1024
    qualified = sum(1 for p in payload_players.values() if p["n1"])
    print(f"\nwrote {OUT} — {len(payload_players)} players, {qualified} with a "
          f"qualifying N-1 season, {kb:.0f}KB")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:  # noqa: BLE001
        print(f"HISTORY ETL FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
