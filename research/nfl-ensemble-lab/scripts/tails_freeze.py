"""Save this week's Tails flags before kickoff (write-once) or score saved weeks after the games.
python scripts/tails_freeze.py [WEEK]      save
python scripts/tails_freeze.py ladders [WEEK]   save spread and total ladders before kickoff
python scripts/tails_freeze.py leadlag [WEEK]   save Kalshi and sportsbook consensus prices before kickoff
python scripts/tails_freeze.py score       score saved weeks"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import leadlag, tails_ladder, tails_week  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ladders":
        b = tails_ladder.archive_ladders(int(sys.argv[2]) if len(sys.argv) > 2 else None)
        print(f"week {b['week']}: {len(b['rungs'])} rungs saved at {b['observed_at']}, sha {b['sha256'][:12]}")
    elif len(sys.argv) > 1 and sys.argv[1] == "leadlag":
        b = leadlag.snapshot(int(sys.argv[2]) if len(sys.argv) > 2 else None)
        print(f"week {b['week']}: {len(b['games'])} games saved at {b['observed_at']}, sha {b['sha256'][:12]}")
    elif len(sys.argv) > 1 and sys.argv[1] == "score":
        print(json.dumps(tails_week.score(), indent=1))
        print(json.dumps(tails_ladder.score_archived(), indent=1))
    else:
        body = tails_week.freeze(int(sys.argv[1]) if len(sys.argv) > 1 else None)
        f = body["forecast"]
        print(f"week {f['week']}: {len(f['games'])} games, flagged {sum(g['u_any'] for g in f['games'])}, sha {body['sha256'][:12]}")
        for g in f["games"]:
            print(g["away"], "at", g["home"], g["closing_spread_home"], "u_qb" if g["u_qb"] else "", "u_gap" if g["u_gap"] else "", [round(x, 1) for x in g["range_90"]])
