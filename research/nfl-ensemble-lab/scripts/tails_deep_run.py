"""Run Tails Amendment 1 checks and write docs/tails_deep_results.json. python scripts/tails_deep_run.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import tails_deep  # noqa: E402

if __name__ == "__main__":
    res = tails_deep.run_all()
    (ROOT / "docs" / "tails_deep_results.json").write_text(json.dumps(res, indent=1))
    print("starters", res["starter_agreement"], "\nsbr", res["sbr_rederive"], "\nkalshi", res["kalshi_history"])
    print("passed:", res["same_season_control"]["passed"], "dose:", res["dose_response"]["passed"])
    for s in ("discovery", "confirmation"):
        for k, v in res["same_season_control"][s].items():
            print(s, k, round(v["observed_rate"], 3), round(v["ratio"], 2), "old", round(res["original_ratios"][s].get(k, float("nan")), 2), "p", round(v["p_holm"], 3), "plc", round(v["placebo_percentile"], 2))
    print(json.dumps(res["positive_controls"]))
    print(json.dumps(res["dose_response"]))
    print(json.dumps(res["rung3_reported_only"]))
