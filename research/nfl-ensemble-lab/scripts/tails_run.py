"""Run the Tails tests from docs/tails_rule.json and write docs/tails_results.json. python scripts/tails_run.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import tails_tests  # noqa: E402

if __name__ == "__main__":
    res = tails_tests.run_all()
    (ROOT / "docs" / "tails_results.json").write_text(json.dumps(res, indent=1))
    print("passed:", res["tail_tests"]["passed"])
    for stage in ("discovery", "confirmation"):
        for k, v in res["tail_tests"][stage].items():
            print(stage, k, v["flagged_games"], round(v["observed_rate"], 3), round(v["priced_rate"], 3), round(v["ratio"], 2), round(v["p_holm"], 3))
    print(json.dumps(res["forecast_accuracy"]))
    print(json.dumps(res["range_models"]))
    print(json.dumps(res["favorite_longshot"]))
