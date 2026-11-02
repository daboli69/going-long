"""Version 2.1 against version 2 under the rule in docs/INGAME_PREREG_V21.md.

    .venv\\Scripts\\python.exe scripts\\ingame_compare21.py

Reads the per-row scores both runs saved (scripts/ingame_eval2.py --tag v2rows, and --tag v21 --definition espn), pairs them on game, stat, checkpoint and player,
leaves quarterback rushing rows out, and writes docs/ingame_eval_v21.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import ingame_eval as E  # noqa: E402
import ingame_eval2 as E2  # noqa: E402
from lab import ingame as G  # noqa: E402


def main():
    old = pd.read_parquet(ROOT / "data" / "cache" / "ingame_rows_v2_v2rows_test.parquet")
    new = pd.read_parquet(ROOT / "data" / "cache" / "ingame_rows_v2_v21_test.parquet")
    key = ["gid", "fam", "t", "pid"]
    both = old.merge(new, on=key, suffixes=("_v2", "_v21"))
    both = both[~((both["fam"] == "rush") & (both["pos_v2"] == "QB"))]
    out = {"rows_v2": int(len(old)), "rows_v21": int(len(new)), "rows_paired": int(len(both)), "families": {}}
    raw = {}
    for fam in G.FAMILIES:
        x = both[both["fam"] == fam].copy()
        x["gain"] = x["crps_v2_v2"] - x["crps_v2_v21"]
        m, lo, hi = E.block_ci(x, "gain")
        dm = E2.dm_test(x.groupby("gid")["gain"].mean())
        out["families"][fam] = {"n": int(len(x)), "games": int(x["gid"].nunique()), "crps_v2": round(float(x["crps_v2_v2"].mean()), 3), "crps_v21": round(float(x["crps_v2_v21"].mean()), 3),
                                "gain": round(m, 3), "ci95": [round(lo, 3), round(hi, 3)], "dm_p": dm["p"]}
        raw[fam] = dm["p"]
    h = E2.holm(raw)
    for fam, e in out["families"].items():
        e["dm_p_holm"] = h[fam]
        e["replaces_v2"] = bool(e["ci95"][0] > 0 and h[fam] < 0.05)
        e["worse"] = bool(e["ci95"][1] < 0)
    out["verdict"] = "v2.1 replaces v2 for: " + (", ".join(f for f, e in out["families"].items() if e["replaces_v2"] and not e["worse"]) or "no stat") + ". Otherwise v2 stays."
    (ROOT / "docs" / "ingame_eval_v21.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
