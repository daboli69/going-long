"""Run the snap simulator for a game: python scripts/snapsim_run.py 2026_08_CHI_SEA [--freeze]. --freeze writes the write-once hashed pre-kickoff record."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import snapgame  # noqa: E402

if __name__ == "__main__":
    gid = sys.argv[1]
    res = snapgame.freeze(gid) if "--freeze" in sys.argv else snapgame.get(gid, refresh=True)
    home, away = res["home"], res["away"]
    print(f"{away} at {home}, {res['sims']} sims")
    print(f"win: {home} {res['win'][home]:.1%}, {away} {res['win'][away]:.1%}")
    print(f"cover (home {res['spread_home']:+}): {home} {res['cover'][home]:.1%}, {away} {res['cover'][away]:.1%}")
    print(f"total {res['total']}: over {res['over']:.1%}, under {res['under']:.1%}")
    print(f"leans (sim, matchup, game agree): {len(res['leans']['leans'])}; frozen={res['frozen']}")
    for l in res["leans"]["leans"]:
        print(f"  {l['player']} {l['stat']} {l['line']} {l['side']} (sim {l['sim_chance']:.0%} vs market {l['market_chance']:.0%})")
