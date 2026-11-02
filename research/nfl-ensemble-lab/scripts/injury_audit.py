"""Is every player who is ruled out missing from everything the Game Center shows? Run before each slate and again after inactive lists post.

    .venv\\Scripts\\python.exe scripts\\injury_audit.py [week]

For each team still to play in the week it builds the set of players not expected to play from the latest ESPN injury list (Out, Doubtful, Injured Reserve,
Suspension), the team roster statuses and Friday's official report, then checks that none of them appears in: the simulated game's projections, the Players tab,
the week's player rankings (every prop) and the Market value tab. It also reports:
  - how old the injury feed is, and for each game starting within 100 minutes whether the official inactive list has posted (ESPN "inactive" notes);
  - skill-position players the lab cannot match to a player id by name (they could slip past name matching).
Writes docs/injury_audit.json (names are public; no keys or private data) and exits with status 1 if any ruled-out player is still shown. Reads local files;
the Market value check uses the prices already saved or fetched by the tab (read-only Kalshi data) and is skipped with --no-market.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import gamecenter_data as D  # noqa: E402
from lab import gamesim as S  # noqa: E402
from lab import rankings as R  # noqa: E402

SKILL = {"QB", "RB", "WR", "TE"}
OUT_STATUS = {"Out", "Doubtful", "Injured Reserve", "Suspension", "Physically Unable to Perform"}


def key(name: str) -> str:
    return S._norm(name)


_pl = pd.read_parquet(ROOT / "data" / "raw" / "players.parquet", columns=["display_name", "position"])
QB_NAMES = {S._norm(n) for n, q in zip(_pl["display_name"], _pl["position"]) if q == "QB"}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    week = int(args[0]) if args else S.current_week()
    inj, stamp = D.injuries_now()
    G = D.games_table()
    g = G[(G["season"] == D.SEASON) & (G["week"] == week) & (G["game_type"] == "REG") & ~G["completed"].astype(bool)].sort_values("kickoff_utc")
    now = pd.Timestamp.now(tz="UTC")
    pid_by = S._pid_by_norm()
    report = {"week": week, "feed_stamp": stamp, "games": [], "leaks": [], "unmatched_skill_names": []}
    if stamp:
        fed = pd.Timestamp(stamp[:4] + "-" + stamp[4:6] + "-" + stamp[6:8] + "T" + stamp[9:11] + ":" + stamp[11:13] + ":00Z")
        report["feed_age_minutes"] = round((now - fed).total_seconds() / 60)
    teams_out: dict[str, dict] = {}
    for r in g.itertuples():
        mins = (pd.Timestamp(r.kickoff_utc) - now).total_seconds() / 60
        row = {"gid": r.game_id, "minutes_to_kickoff": round(mins)}
        for t in (r.home_team, r.away_team):
            out_t, _ = S.unavailable(t, week)
            teams_out[t] = out_t
            posted = S.inactives_final(t, week)
            row[t] = {"ruled_out": len(out_t), "inactive_list_posted": posted}
            if mins <= 100 and not posted:
                report["leaks"].append({"where": "feed", "team": t, "player": None, "why": f"kickoff in {round(mins)} minutes and no official inactive list in the feed yet"})
            for p, pos in zip(inj.loc[(inj["team"] == t) & inj["status"].isin(OUT_STATUS), "player"], inj.loc[(inj["team"] == t) & inj["status"].isin(OUT_STATUS), "pos"]):
                if pos in SKILL and key(p) not in pid_by:
                    report["unmatched_skill_names"].append({"team": t, "player": p, "pos": pos})
        report["games"].append(row)

    def check(where: str, team: str, player: str):
        hit = teams_out.get(team, {}).get(key(player))
        if hit:
            report["leaks"].append({"where": where, "team": team, "player": player, "status": hit[1]})

    shown = {"sim": 0, "players_tab": 0, "rankings": 0, "market": 0}
    for r in g.itertuples():
        sim = S.simulate(r.game_id, "typical", 0)
        passers = {p["player"] for p in sim["players"] if p["stat"] == "Passing yards"}
        for p in sim["players"]:
            shown["sim"] += 1
            check("simulated game", p["team"], p["player"])
            if key(p["player"]) in QB_NAMES and p["player"] not in passers and p["stat"] != "Passing yards":
                report["leaks"].append({"where": "simulated game", "team": p["team"], "player": p["player"], "why": "a quarterback who is not the starter has rushes or catches"})
        det = S.game_detail_adjusted(r.game_id, with_props=True)
        report.setdefault("adjustments", {})[r.game_id] = None if not det.get("injury_adjustment") else {"margin": round(det["injury_adjustment"]["margin"], 2), "total": round(det["injury_adjustment"]["total"], 2)}
        for p in det["props"]:
            shown["players_tab"] += 1
            check("Players tab", p["team"], p["player"])
    rk = R.week_rankings(week)
    for stat, v in rk["stats"].items():
        for p in v["rows"]:
            shown["rankings"] += 1
            check(f"rankings: {v['label']}", p["team"], p["player"])
    for p in rk.get("all_td", []):
        check("rankings: anytime touchdown (all players)", p["team"], p["player"])
    if "--no-market" not in sys.argv:
        from lab import tdmarket as M
        try:
            mk = M.week_market(week)
            for p in mk["rows"] + mk["unpriced"]:
                shown["market"] += 1
                check("Market value tab", p["team"], p["player"])
        except Exception as exc:  # Kalshi unreachable: say so, do not fail the audit on it
            report["market_skipped"] = type(exc).__name__
    report["rows_checked"] = shown
    report["ruled_out_by_team"] = {t: len(o) for t, o in teams_out.items()}
    (ROOT / "docs" / "injury_audit.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("week", "feed_stamp", "feed_age_minutes", "rows_checked", "leaks", "unmatched_skill_names")}, indent=1))
    if report["leaks"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
