"""Apply the pre-registered Holm rule without changing any forecast setting."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import TARGETS
from .data import OUT
from .research import clustered_difference


def run():
    tests = []
    recal = pd.read_parquet(OUT / "game_recalibration_dev.parquet")
    y, p, q = (recal[c].to_numpy(float) for c in ("home_win", "reference", "recalibrated"))
    p, q = np.clip(p, 1e-6, 1-1e-6), np.clip(q, 1e-6, 1-1e-6)
    delta = -(y*np.log(q)+(1-y)*np.log(1-q)) + (y*np.log(p)+(1-y)*np.log(1-p))
    c = clustered_difference(recal["game_id"], delta)
    tests.append({"id": "B1_combined_calibration", "p": c["p_improvement_one_sided"]})
    games = json.loads((OUT / "game_research.json").read_text())
    for row in games:
        for metric in ("mae", "crps"):
            tests.append({"id": f"B2_{row['stat']}_{metric}", "p": row[f"vs_baseline_{metric}"]["p_improvement_one_sided"]})
    props = json.loads((OUT / "research2022.json").read_text())
    lookup = {(r["stat"], r["method"]): r for r in props["results"]}
    for variant in ("independent", "market-informed"):
        for stat in TARGETS:
            for method in ("equal", "weighted", "stacked"):
                for benchmark in ("simulator_v1", "baseline_B"):
                    result = lookup.get((stat, method), {}).get("vs_" + benchmark) if variant == "independent" else None
                    tests.append({"id": f"B3_{variant}_{stat}_{method}_vs_{benchmark}",
                                  "p": result["p_improvement_one_sided"] if result else 1.,
                                  "status": "computed" if result else "blocked comparator; conservative p=1 for family accounting"})
    td = props["diagnostics"]["B4"]
    tests.append({"id": "B4_full_vs_redzone_TD", "p": td["p_improvement_one_sided"]})
    ordered = sorted(range(len(tests)), key=lambda i: tests[i]["p"])
    maximum = 0.
    for rank, index in enumerate(ordered):
        maximum = max(maximum, min(1., tests[index]["p"] * (len(tests) - rank)))
        tests[index]["holm_p"] = maximum
        tests[index]["reject_null_at_05"] = maximum < .05
    result = {"family_size": len(tests), "family_definition": "B1 LL; B2 margin/total MAE+CRPS; B3 six targets x three combinations x two variants x two benchmarks; B4 anytime-TD ablation. Missing comparisons conservatively p=1.",
              "tests": tests, "retained_qualified_challengers": [],
              "decision": "No fully benchmark-validated new configuration retained. Independent game anchor clears league baselines but does not improve saved champion margin; market comparison unavailable. Props equal reference is unpromoted and frozen for the requested prospective sheet."}
    (OUT / "multiplicity_and_retention.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = run()
    print(json.dumps({"family_size": result["family_size"], "B4": next(t for t in result["tests"] if t["id"].startswith("B4")),
                      "retained_qualified_challengers": result["retained_qualified_challengers"]}, indent=2))
