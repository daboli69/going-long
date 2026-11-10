r"""Screen every numeric FantasyPoints player column as a nudge to the projection, on games the fit never saw.

    .venv\Scripts\python.exe scripts\fpds_column_screen.py

Baseline: the nflverse-only prediction the simulation uses (a player's recent share of the team's total times the total).
Candidate: every column in lab/fpds_extra.py, as the player's mean over his previous six weekly rows, standardised within the game's player pool.
new = old x (1 + w x z). Protocol, fixed before the 2025 and 2026 numbers were read:
  1. Select: fit w by ridge on 2022 to 2023 for each column alone and score it on 2024. Keep the columns that lower the error in 2024.
  2. Combine: take the best five by 2024 improvement for each stat, fit their weights jointly on 2022 to 2024.
  3. Confirm: score the joint model on 2025 and on 2026 so far. It is used when the error falls in both years (point estimate; the owner's rule of 2026-11-07),
     and the report shows the 90% interval beside it.
With about 800 columns tried per stat, a few will look better by chance; step 1 uses a different season from the confirmation for that reason.
Writes docs/FPDS_COLUMN_SCREEN.md, docs/fpds_column_screen.json (aggregate only) and data/cache/fpds_columns_rule.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import fpds_extra as E  # noqa: E402
from lab import fpds_usage as X  # noqa: E402
from lab.config import CACHE_DIR  # noqa: E402

STATS = {"rec_yds": "Receiving yards", "rec": "Catches", "rush_yds": "Rushing yards"}
RIDGE = 0.05
TOP = 5
CLIP = (0.6, 1.5)
RULE_PATH = CACHE_DIR / "fpds_columns_rule.json"
YEARS = {"fit1": ((2022, 3, 18), (2023, 3, 18)), "val": ((2024, 3, 18),), "t25": ((2025, 3, 18),), "t26": ((2026, 3, 7),)}


def design(games, stat, hist):
    old, y, gid, keys = [], [], [], []
    for i, c in enumerate(games):
        base = c["pool"][f"share_{stat}"].to_numpy(float)
        T = c["u"].totals[stat]
        if base.sum() <= 0 or T <= 0:
            continue
        pids = c["pool"]["pid"].astype(str).tolist()
        old.append(base / base.sum() * T)
        y.append(c["actual"][stat].reindex(c["pool"]["pid"]).fillna(0).to_numpy(float))
        gid.append(np.full(len(base), i))
        keys += [(c["season"], c["week"], p) for p in pids]
    F = hist.reindex(pd.MultiIndex.from_tuples(keys, names=["season", "week", "pid"]))
    g = np.concatenate(gid)
    F = F.reset_index(drop=True)
    # standardise within each game's pool; players with no row take the pool mean (z = 0)
    grp = F.groupby(g)
    Z = ((F - grp.transform("mean")) / grp.transform("std").replace(0, np.nan)).clip(-3, 3).fillna(0.0)
    return np.concatenate(old), np.concatenate(y), g, Z


def ridge(old, Z, y, cols):
    A = old[:, None] * Z[:, cols]
    lam = RIDGE * (A ** 2).mean(0).clip(1e-9) * len(y)
    return np.linalg.solve(A.T @ A + np.diag(lam), A.T @ (y - old))


def rmse(p, y):
    return float(np.sqrt(np.mean((p - y) ** 2)))


def apply(old, Z, w, cols):
    return old * np.clip(1 + Z[:, cols] @ w, *CLIP)


def main():
    hist = E.history()
    names = list(hist.columns)
    sets = {k: X._games(v, "last6") for k, v in YEARS.items()}
    report, rule = {}, {"applied": True, "rule": "point estimate lower in both 2025 and 2026 (owner 2026-11-07)", "stats": {}}
    for stat in STATS:
        D = {k: design(v, stat, hist) for k, v in sets.items()}
        old, y, g, Z = D["fit1"]
        Zv = D["val"][3].to_numpy(float)
        Zf = Z.to_numpy(float)
        gain = np.full(len(names), np.nan)
        for j in range(len(names)):
            w = ridge(old, Zf, y, [j])
            gain[j] = rmse(apply(D["val"][0], Zv, w, [j]), D["val"][1]) - rmse(D["val"][0], D["val"][1])
        order = [j for j in np.argsort(gain) if gain[j] < 0][:TOP]
        res = {"columns_tried": len(names), "improved_in_validation": int((gain < 0).sum()), "chosen": [names[j] for j in order]}
        if not order:
            report[stat] = res
            continue
        tr = {k: D[k] for k in ("fit1", "val")}
        oldT = np.concatenate([tr["fit1"][0], tr["val"][0]])
        yT = np.concatenate([tr["fit1"][1], tr["val"][1]])
        ZT = np.vstack([Zf, Zv])
        w = ridge(oldT, ZT, yT, order)
        res["weights"] = {names[j]: float(b) for j, b in zip(order, w)}
        res["tests"] = {}
        for k, yr in (("t25", "2025"), ("t26", "2026")):
            o, yy, gg, ZZ = D[k]
            ZZ = ZZ.to_numpy(float)
            new = apply(o, ZZ, w, order)
            r = X._paired(new, o, yy, gg)
            res["tests"][yr] = r
        res["improves_both"] = all(res["tests"][yr]["rmse_new"] < res["tests"][yr]["rmse_old"] for yr in res["tests"])
        report[stat] = res
        if res["improves_both"]:
            rule["stats"][stat] = {"weights": res["weights"], "clip": list(CLIP)}
    RULE_PATH.write_text(json.dumps(rule, indent=1), encoding="utf-8")
    (ROOT / "docs" / "fpds_column_screen.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    L = ["# Every FantasyPoints player column, screened as a nudge to the projection", "",
         "Generated by `scripts/fpds_column_screen.py`. Aggregate numbers only.", "",
         "Each column (the player's mean over his previous six weekly rows, standardised within the game's player pool) was tried alone: weight fitted on 2022 to 2023, scored on 2024. "
         "The best five per stat by 2024 error were then fitted together on 2022 to 2024 and scored on 2025 and on 2026 so far. A stat's set is used when the typical miss falls in both years "
         "(the owner's rule from 2026-11-07: any improvement counts); the 90% interval is shown next to it. With hundreds of columns tried, some look better by chance, which is why the choice of columns "
         "and the confirmation use different seasons.", ""]
    for stat, label in STATS.items():
        r = report[stat]
        L += [f"## {label}", "", f"Columns tried: {r['columns_tried']}. Lowered the error in 2024: {r['improved_in_validation']}.", ""]
        if "weights" not in r:
            L += ["No column lowered the error in the validation season.", ""]
            continue
        L += ["| Column | Weight |", "|---|---|"] + [f"| {c} | {w:+.3f} |" for c, w in r["weights"].items()] + ["",
              "| Year | Player-games | Error before | After | Change, 90% interval | Used |", "|---|---|---|---|---|---|"]
        for yr, t in r["tests"].items():
            L.append(f"| {yr} | {t['player_games']} | {t['rmse_old']:.3f} | {t['rmse_new']:.3f} | {t['rmse_new'] - t['rmse_old']:+.3f} ({t['diff_lo']:+.3f} to {t['diff_hi']:+.3f}) | {'yes' if r['improves_both'] else 'no'} |")
        L.append("")
    (ROOT / "docs" / "FPDS_COLUMN_SCREEN.md").write_text(chr(10).join(L), encoding="utf-8")
    print(chr(10).join(L))


if __name__ == "__main__":
    main()
