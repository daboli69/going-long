"""S2 (less shrunk rushing split), selection on 2012-2021 and confirmation on 2022-2025. Rule: docs/QB_RUSH_SPLIT2_PREREG.md.

    .venv/Scripts/python.exe scripts/qb_rush_split2.py

Writes docs/qb_rush_split2_results.json. Research only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import qb_rush_split as q  # noqa: E402
from lab import homewin_deep as h  # noqa: E402

FACTORS = [1.0, 0.5, 0.25]
BASE = {"K_RATE_D": q.K_RATE_D, "K_YPA_D": q.K_YPA_D, "K_RATE_S": q.K_RATE_S, "K_YPA_S": q.K_YPA_S}
DEV = (2013, 2021)  # 2012 has no earlier margin-bearing season to fit on; noted in the results
HOLD = (2022, 2025)
BOOT, SEED = 2000, 20261110
K_B1 = 6.0


def set_factor(f: float):
    for k, v in BASE.items():
        setattr(q, k, v * f)


def prepare():
    p = q.load_plays(range(2004, 2026))
    data, _ = h.load_all(False)
    g = q.add_history(q.starter_games(p), data.games.set_index("gid")["kickoff_utc"])
    grp = g.groupby("qb")["total"]
    g["h_total"] = grp.transform(lambda s: s.shift(1).rolling(q.WINDOW, min_periods=1).sum())
    wf = pd.read_parquet(h.CACHE / "walk_forward.parquet").set_index("gid")["pred_margin"]
    home = data.games.set_index("gid")["home"]
    g["m"] = np.where(g["posteam"] == g["game_id"].map(home), g["game_id"].map(wf), -g["game_id"].map(wf))
    return g


def run(g: pd.DataFrame, seasons, f: float) -> pd.DataFrame:
    set_factor(f)
    outs = []
    for s in range(seasons[0], seasons[1] + 1):
        tr = g[(g["season"] < s) & (g["season"] >= q.FIT_FROM) & g["m"].notna()]
        L = q.league(g[g["season"] < s])
        fit = q.fit_state(q.components(tr, L))
        te = q.predict(q.components(g[(g["season"] == s) & g["m"].notna()], L), fit, L)
        n = te["h_games"].fillna(0)
        te["pred_B1"] = (te["h_total"].fillna(0) + K_B1 * L["total"]) / (n + K_B1)
        outs.append(te)
    return pd.concat(outs, ignore_index=True)


def metrics(t, col):
    e = t[col].to_numpy(float) - t["total"].to_numpy(float)
    return {"rmse": float(np.sqrt((e ** 2).mean())), "mae": float(np.abs(e).mean()), "bias": float(e.mean())}


def delta(t, a, b, rng, mask=None):
    y = t["total"].to_numpy(float)
    mk = np.ones(len(t), bool) if mask is None else mask
    da, db = (t[a].to_numpy(float) - y)[mk], (t[b].to_numpy(float) - y)[mk]
    ix = [rng.integers(0, mk.sum(), mk.sum()) for _ in range(BOOT)]
    r = np.array([np.sqrt((da[i] ** 2).mean()) - np.sqrt((db[i] ** 2).mean()) for i in ix])
    return {"n": int(mk.sum()), "rmse_delta": float(np.sqrt((da ** 2).mean()) - np.sqrt((db ** 2).mean())), "ci95": [float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975))],
            "mae_delta": float(np.abs(da).mean() - np.abs(db).mean())}


def main():
    g = prepare()
    rng = np.random.default_rng(SEED)
    dev = {}
    for f in FACTORS:
        t = run(g, DEV, f)
        dev[f] = {"S": metrics(t, "pred_S"), "B1": metrics(t, "pred_B1"), "B0": metrics(t, "pred_B0")}
        print("dev f", f, {k: round(v["rmse"], 3) for k, v in dev[f].items()}, flush=True)
    best = min(FACTORS, key=lambda f: (round(dev[f]["S"]["rmse"], 6), -f))
    t = run(g, HOLD, best)
    t1 = run(g, HOLD, 1.0)
    t["pred_S1"] = t1["pred_S"].to_numpy()
    rushy = ((t["h_att_d"].fillna(0) + t["h_att_s"].fillna(0)) / t["h_games"].replace(0, np.nan)).fillna(0)
    top = (rushy >= rushy.quantile(0.9)).to_numpy()
    res = {"dev": {str(f): v for f, v in dev.items()}, "f_selected": best, "hold_games": int(len(t)),
           "hold": {c: metrics(t, c) for c in ("pred_B0", "pred_B1", "pred_S1", "pred_S")},
           "hold_top_decile": {c: metrics(t[top], c) for c in ("pred_B0", "pred_B1", "pred_S1", "pred_S")}, "top_decile_games": int(top.sum()),
           "S2_vs_S": delta(t, "pred_S", "pred_S1", rng), "S2_vs_B1": delta(t, "pred_S", "pred_B1", rng), "S2_vs_B0": delta(t, "pred_S", "pred_B0", rng),
           "S_vs_B1": delta(t, "pred_S1", "pred_B1", rng), "S_vs_B0": delta(t, "pred_S1", "pred_B0", rng)}
    if best == 1.0:
        res["note"] = "f = 1.0 selected: S2 is identical to S"
    r = res["hold"]
    res["confirmation_conditions"] = {"rmse_below_S": r["pred_S"]["rmse"] < r["pred_S1"]["rmse"], "rmse_below_B1": r["pred_S"]["rmse"] < r["pred_B1"]["rmse"],
                                      "mae_not_worse_than_S": r["pred_S"]["mae"] <= r["pred_S1"]["mae"],
                                      "top_decile_bias_closer": abs(res["hold_top_decile"]["pred_S"]["bias"]) < abs(res["hold_top_decile"]["pred_S1"]["bias"])}
    (ROOT / "docs" / "qb_rush_split2_results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
