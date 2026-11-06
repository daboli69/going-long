"""Post hoc check on the basket closing test: keep only snapshot pairs where the same quarterback and the same receivers are listed at both snapshots. python scripts/basket_matched_check.py"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import basket_run as R  # noqa: E402
from lab import basket as K  # noqa: E402

if __name__ == "__main__":
    par = json.load(open(ROOT / "docs" / "basket_gate.json"))["params"]
    share = {int(k): v for k, v in par["share"].items()}; share["pooled"] = par["pooled_share"]
    a = K.adjusted(K.legs(), par["cQ"], par["cR"])
    rows, total, matched = [], 0, 0
    for (book, gid, team), g in a.groupby(["book", "game_id", "team"]):
        snaps = sorted(g["snap"].unique()); st = {s: g[g.snap == s] for s in snaps}
        for i in range(len(snaps) - 1):
            for j in range(i + 1, len(snaps)):
                if not 6 <= (snaps[j] - snaps[i]).total_seconds() / 3600 <= 30:
                    continue
                x, y = st[snaps[i]], st[snaps[j]]
                qx, qy = x[x.stat == "pass_yds"], y[y.stat == "pass_yds"]; rx, ry = x[x.stat == "rec_yds"], y[y.stat == "rec_yds"]
                if len(qx) < 1 or len(qy) < 1 or len(rx) < 2 or len(ry) < 2:
                    break
                total += 1
                if set(rx.gsis_id) != set(ry.gsis_id) or qx.sort_values("line").iloc[-1].gsis_id != qy.sort_values("line").iloc[-1].gsis_id:
                    break
                matched += 1
                rem = share.get(min(len(rx), 5), share["pooled"])
                def gap(q, r):
                    Q = float(q.sort_values("line").iloc[-1].adj); B = float(r.adj.sum()); return (Q - B / (1 - rem)) / Q, Q, B
                g0, Q0, B0 = gap(qx, rx); g1, Q1, B1 = gap(qy, ry)
                rows.append((book, gid, g0, g1 - g0, Q1 / Q0 - 1, B1 / B0 - 1)); break
    pr = pd.DataFrame(rows, columns=["book", "gid", "g0", "dg", "dQ", "dB"])
    rng = np.random.default_rng(5)
    out = {"pairs_total": total, "matched": matched, "kappa": -R.slope(pr.g0.to_numpy(), pr.dg.to_numpy()), "qb_move": R.slope(pr.g0.to_numpy(), pr.dQ.to_numpy()), "basket_move": R.slope(pr.g0.to_numpy(), pr.dB.to_numpy())}
    bs = R.boot_slope(pr, "g0", "dg", rng, 600); out["kappa_90"] = [float(-np.quantile(bs, .95)), float(-np.quantile(bs, .05))]
    (ROOT / "docs" / "basket_matched_check.json").write_text(json.dumps(out, indent=1)); print(out)
