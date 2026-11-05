"""Run Tails Amendment 2 (Kalshi ladders) and write docs/tails_ladder_results.json. Run scripts/tails_ladder_fetch.py first.
python scripts/tails_ladder_run.py [recovery]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import tails_ladder  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "recovery":
        print(json.dumps(tails_ladder.recovery(), indent=1))
    else:
        res = tails_ladder.run_all()
        (ROOT / "docs" / "tails_ladder_results.json").write_text(json.dumps(res, indent=1, default=str))
        print(json.dumps({k: v for k, v in res.items() if k != "tests"}, indent=1, default=str)[:3500])
        if res.get("tests"):
            print("passed:", res["tests"]["passed"])
