"""Post hoc cost check for the fusion reversion result (outcome-free). python scripts/fusion_cost_check.py
For book quotes that sit far from the fused line, value the bet against the book (under if its line is above fused, over if below) at the book's own odds,
using the fused line at the book's next snapshot (6 to 30 hours later) as the truth. Not registered; descriptive."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import fusion_run as R  # noqa: E402
from lab import basket as K  # noqa: E402
from lab import fusion as F  # noqa: E402

if __name__ == "__main__":
    q, books, par = R.prepare()
    thr = json.load(open(ROOT / "data" / "cache" / "fusion_params.json"))["thr"]
    o = F.encode(q, books)
    m, d = F.fused(o, par)
    q = q.assign(m=m[o.prop], d=d, lvl=np.exp(m[o.prop]))
    q = q.sort_values("snap")
    rows = []
    for (b, gid, pid, st), g in q.groupby(["book", "game_id", "gsis_id", "stat"]):
        if len(g) < 2:
            continue
        s = g["snap"].to_numpy(); gg = g.reset_index(drop=True)
        for i in range(len(gg) - 1):
            if abs(gg.loc[i, "d"]) < thr:
                continue
            for j in range(i + 1, len(gg)):
                dt = (s[j] - s[i]) / np.timedelta64(1, "h")
                if 6 <= dt <= 30:
                    under = gg.loc[i, "d"] > 0
                    L0 = gg.loc[i, "line"]; lvl = gg.loc[j, "lvl"]; sg = F.C_FUSION[st] * lvl
                    po = 1 - stats.norm.cdf((L0 - lvl) / sg)
                    prob = (1 - po) if under else po
                    odds = gg.loc[i, "under_odds"] if under else gg.loc[i, "over_odds"]
                    rows.append((gid, b, prob, float(K.american_p(odds)), gg.loc[i, "hold"]))
                    break
    r = pd.DataFrame(rows, columns=["game", "book", "prob", "be", "hold"])
    r["net"] = r["prob"] - r["be"]
    gm = r.groupby("game")["net"].mean().to_numpy()
    rng = np.random.default_rng(1)
    mu = np.array([gm[rng.integers(0, len(gm), len(gm))].mean() for _ in range(2000)])
    out = {"outlier_bets": int(len(r)), "games": int(len(gm)), "mean_net_value": float(gm.mean()), "ci95": [float(np.quantile(mu, .025)), float(np.quantile(mu, .975))],
           "mean_gross_value": float((r["prob"] - 0.5).mean()), "mean_hold": float(r["hold"].mean()), "mean_break_even": float(r["be"].mean())}
    (ROOT / "docs" / "fusion_cost_check.json").write_text(json.dumps(out, indent=1)); print(out)
