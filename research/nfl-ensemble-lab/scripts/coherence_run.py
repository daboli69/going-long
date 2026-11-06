"""Coherence tests (docs/COHERENCE_PREREG.md).
  python scripts/coherence_run.py gate    Test A gate (forecast structure only) and Test B counts and gate
  python scripts/coherence_run.py lag     Test B estimate on 2026 weeks 1 to 8, once
  python scripts/coherence_run.py freeze  weekly write-once reconciled forecasts
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DOCS = ROOT / "docs"


def lag():
    from lab import coherence_lag as B
    marker = ROOT / "data" / "coherence" / "lag_done.json"
    if marker.exists():
        sys.exit("Test B was already estimated once. No rerun.")
    rng = np.random.default_rng(20261106)
    df = B.design(B.points())
    s = df[df["gid"].str.startswith("2026")].reset_index(drop=True)
    L = B.slope_L(s)
    se, vals = B.boot_se(s, rng, 2000)
    lo, hi = float(np.quantile(vals, 0.05)), float(np.quantile(vals, 0.95))
    verdict = "props lag the game line" if lo > 0 else "no lag of the size of interest" if float(np.quantile(vals, 0.95)) < B.SMALLEST else "cannot say"
    wk = s["gid"].str.split("_").str[1].astype(int)
    desc = {}
    for name, sel in (("weeks_1_4", wk <= 4), ("weeks_5_8", wk >= 5), ("passing", s["series"] == "KXNFLPASSYDS"), ("receiving", s["series"] == "KXNFLRECYDS")):
        t = s[sel]
        desc[name] = {"games": int(t["gid"].nunique()), "ladders": int(len(t)), "L": B.slope_L(t) if len(t) > 20 else None}
    plc = []
    for _ in range(500):
        t = s.copy()
        for ser, g in t.groupby("series"):
            idx = g.index
            gm = g.groupby("gid")["dG"].first()
            perm = dict(zip(gm.index, rng.permutation(gm.to_numpy())))
            t.loc[idx, "dG"] = g["gid"].map(perm).to_numpy()
        plc.append(B.slope_L(t))
    res = {"games": int(s["gid"].nunique()), "ladders": int(len(s)), "L": L, "se": se, "one_sided_95_interval": [lo, hi], "verdict": verdict, "descriptive": desc,
           "placebo_mean": float(np.mean(plc)), "placebo_sd": float(np.std(plc))}
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(res, indent=1))
    (DOCS / "coherence_lag_results.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def freeze():
    from lab import coherence_week as W
    print(W.freeze(), W.verify())


if __name__ == "__main__":
    {"lag": lag, "freeze": freeze}.get(sys.argv[1], lambda: sys.exit("unknown stage"))()
