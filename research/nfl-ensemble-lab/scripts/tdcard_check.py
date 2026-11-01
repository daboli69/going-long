"""Does the touchdown card reproduce a third-party card? Javonte Williams (DAL) for 2026 weeks 3 to 7, against the numbers printed on a published card.

    .venv\Scripts\python.exe scripts\tdcard_check.py

The reference numbers were read off screenshots of Venom Analytics' card for the same player and games (Travis shared them on 2026-11-01): they are counts of
carries and targets by zone, touchdowns, touches and goal-line touches a game, his share of running-back red-zone touches, and the touchdowns Arizona allowed by
position over its last seven games. Counts must match exactly; the rest is printed beside the published figure. Needs the local 2026 play-by-play (not run in the
test suite, which uses a synthetic league). Writes docs/tdcard_check.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import gamesim as S  # noqa: E402
from lab import tdcard as T  # noqa: E402

REFERENCE_ZONES = {"Goal line (in 5)": (13, 0), "Red zone (6 to 20)": (12, 0), "Fringe (21 to 40)": (14, 4), "Open field": (47, 9)}
REFERENCE_ARI_TABLE = [(1, "LAC", 1, 1, 0, 0), (2, "SEA", 0, 3, 1, 0), (3, "SF", 1, 2, 2, 0), (4, "NYG", 0, 2, 1, 0), (5, "DET", 2, 2, 1, 1), (6, "LA", 1, 0, 1, 0), (7, "DEN", 2, 0, 0, 1)]


def main():
    pid = S._pid_by_norm()[S._norm("Javonte Williams")]
    c = T.card("DAL", pid, 8, "ARI", 7.0, 54.5)
    zones = {z["zone"]: (z["carries"], z["targets"]) for z in c["cheat"]["zones"]}
    table = [(r["week"], r["vs"], r["RB"], r["WR"], r["TE"], r["QB"]) for r in c["opportunity"]["table"]]
    checks = {
        "window is weeks 3 to 7 (five games)": list(map(int, c["window"]["weeks"])) == [3, 7] and c["window"]["games"] == 5,
        "zone counts match": zones == REFERENCE_ZONES,
        "7 touchdowns scored": c["cheat"]["scored"] == 7,
        "19.8 touches a game": abs(c["profile"]["touches_pg"] - 19.8) < 0.05,
        "2.6 goal-line touches a game": abs(c["profile"]["gl_pg"] - 2.6) < 0.05,
        "25 of 34 running-back red-zone touches": (c["profile"]["rz_claim"]["mine"], c["profile"]["rz_claim"]["group"]) == (25, 34),
        "6% target share": round(c["profile"]["target_share"], 2) == 0.06,
        "7% touchdown rate": round(c["profile"]["td_rate"], 2) == 0.07,
        "Arizona's seven games of touchdowns allowed, row by row": table == REFERENCE_ARI_TABLE,
        "Arizona totals RB 7, WR 10, TE 6, QB 2": c["opportunity"]["totals"] == {"RB": 7, "WR": 10, "TE": 6, "QB": 2},
        "matchup 1.00 TD a game": abs(c["opportunity"]["matchup_pg"] - 1.0) < 1e-9,
        "snap share about 75%": abs(c["opportunity"]["snap_share"] - 0.75) < 0.01,
        "0 games since a touchdown": c["opportunity"]["games_since_td"] == 0,
    }
    beside = {"expected touchdowns": (round(c["cheat"]["expected"], 2), 6.6), "red-zone role": (round(c["profile"]["rz_role"], 3), 0.34),
              "team red-zone trips a game": (round(c["profile"]["team_rz_trips_pg"], 1), 4.0), "team red-zone TD rate": (round(c["profile"]["team_rz_td_rate"], 2), 0.71),
              "Arizona red-zone TD rate allowed": (round(c["profile"]["opp_rz_td_rate_allowed"], 2), 0.65),
              "Arizona rank, touchdowns to RB / WR / TE / QB (1 = most)": ([c["opportunity"]["ranks"][k] for k in ("RB", "WR", "TE", "QB")], [10, 2, 5, 9])}
    out = {"matches_exactly": checks, "ours_vs_published": {k: {"ours": a, "published": b} for k, (a, b) in beside.items()}}
    (ROOT / "docs" / "tdcard_check.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps(out, indent=1, default=float))
    if not all(checks.values()):
        raise SystemExit("some counts do not match the published card")


if __name__ == "__main__":
    main()
