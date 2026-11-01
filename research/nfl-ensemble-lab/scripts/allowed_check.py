"""Do fantasy-points-allowed numbers, converted to actual stats, improve the simulated game's player numbers? Scored on games the fit never saw.

    .venv\\Scripts\\python.exe scripts\\allowed_check.py

Baseline: the nflverse-only prediction the simulation uses (a player's share of the team's total, times the total). Each variant adjusts it:
new = old x (1 + weight x the opposing defense's shrunk gap to the league). "Stat" uses the stat being predicted (yards allowed to that position
for yards, catches for catches); "Fantasy points" uses the single fantasy-points total for every stat. Weights are ridge-fitted by position on
2022 to 2024 and scored on 2025 and 2026 so far from weeks before each game. A variant passes only if the whole 90% interval for the change in
error is below zero in both years. Writes docs/ALLOWED_CHECK.md, docs/allowed_check.json (aggregate only) and data/cache/allowed_rule.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import allowed_usage as A  # noqa: E402
from lab import coverage_usage as C  # noqa: E402
from lab import fpds_usage as X  # noqa: E402
from lab import usage as U  # noqa: E402
from lab.config import CACHE_DIR  # noqa: E402

STATS = {"rec_yds": "Receiving yards", "rec": "Catches", "rush_yds": "Rushing yards"}
TRAIN = ((2022, 3, 18), (2023, 3, 18), (2024, 3, 18))
RIDGE = 0.05
RULE_PATH = A.RULE_PATH
STAT_V, FP_V = "Stat allowed to the position", "Fantasy points allowed to the position"
OWNER_APPLIES = True


def stack(games, stat, allowed, opp, pos, positions):
    n = len(positions)
    old, F, y, gid, grp = [], [], [], [], []
    for i, c in enumerate(games):
        base = c["pool"][f"share_{stat}"].to_numpy(float)
        T = c["u"].totals[stat]
        if base.sum() <= 0 or T <= 0:
            continue
        pids = c["pool"]["pid"].tolist()
        ps = [pos.get(p) for p in pids]
        f = np.zeros((len(pids), 2 * n))   # columns: stat gap by position, then fantasy-points gap by position
        for j, p in enumerate(ps):
            if p not in positions:
                continue
            k = positions.index(p)
            f[j, k] = A.gap(allowed, opp, c["season"], c["week"], c["team"], p, A.STAT_COLS[stat][p])
            f[j, n + k] = A.gap(allowed, opp, c["season"], c["week"], c["team"], p, A.FP_COL)
        old.append(base / base.sum() * T)
        F.append(f)
        y.append(c["actual"][stat].reindex(pids).fillna(0).to_numpy(float))
        gid.append(np.full(len(base), i))
        grp.append(np.array([p if p in positions else "other" for p in ps]))
    return np.concatenate(old), np.vstack(F), np.concatenate(y), np.concatenate(gid), np.concatenate(grp)


def fit(old, F, y, idx):
    Z = old[:, None] * F[:, idx]
    lam = RIDGE * (Z ** 2).mean(0).clip(1e-9) * len(y)
    return np.linalg.solve(Z.T @ Z + np.diag(lam), Z.T @ (y - old))


def main():
    allowed, opp = A.Allowed(), C.opponents()
    pg = U.player_games(range(2021, 2027))
    pos = pg.sort_values(["season", "week"]).drop_duplicates("pid", keep="last").set_index("pid")["pos"].to_dict()
    sets = {"train": X._games(TRAIN, "last6"), "test_2025": X._games(((2025, 3, 18),), "last6"), "test_2026": X._games(((2026, 3, 7),), "last6")}
    result, rule = {"games": {k: len(v) for k, v in sets.items()}, "stats": {}}, {}
    for stat, cols in A.STAT_COLS.items():
        positions = list(cols)
        n = len(positions)
        S = {k: stack(v, stat, allowed, opp, pos, positions) for k, v in sets.items()}
        res = {}
        for name, idx in ((STAT_V, list(range(n))), (FP_V, list(range(n, 2 * n)))):
            beta = fit(*S["train"][:3], idx)
            r = {"weights": {positions[i % n]: float(b) for i, b in zip(idx, beta)}, "tests": {}}
            for k in ("test_2025", "test_2026"):
                old, F, y, gid, grp = S[k]
                new = old * (1 + F[:, idx] @ beta)
                r["tests"][k] = {"all": X._paired(new, old, y, gid), "by_group": {g: X._paired(new, old, y, gid, grp == g) for g in positions}}
            res[name] = r
            if all(r["tests"][k]["all"]["diff_hi"] < 0 for k in ("test_2025", "test_2026")):
                rule.setdefault(stat, {})[name] = r["weights"]
        result["stats"][stat] = res
    # Owner decision (Travis, 2026-11-01): the simulation applies the stat weights whether or not they pass the gate. `passed` records the test.
    weights = {stat: result["stats"][stat][STAT_V]["weights"] for stat in A.STAT_COLS}
    out = {"passed": bool(rule), "applied": OWNER_APPLIES, "applied_by": "owner decision 2026-11-01, regardless of the gate",
           "weights": weights, "stats": rule, "created_at": pd.Timestamp.now(tz="UTC").isoformat()}
    RULE_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
    (ROOT / "docs" / "allowed_check.json").write_text(json.dumps({"result": result, "rule": out}, indent=1, default=str), encoding="utf-8")

    L = ["# Fantasy points allowed to each position, converted to stats: what was tested", "",
         "Generated by `scripts/allowed_check.py`. Fitted on 2022 to 2024, scored on 2025 and on 2026 so far (weeks 3 to 7) from weeks before each game. Aggregate numbers only.", "",
         "The baseline is the nflverse-only prediction. Each variant scales it by how far the opposing defense's last six games sit from the league average against that position "
         "(pulled toward the league when the record is short). \"Stat\" uses the yards or catches that defense allowed to the position. \"Fantasy points\" uses its fantasy-point total instead. "
         "Error is the typical miss for one player in one game; lower is better. The interval is 90%. A variant is used only if the whole interval is below zero in both years.", ""]
    for stat, label in STATS.items():
        L += [f"## {label}", "", "| Variant | Year | Player-games | Error before | After | Change, 90% interval | Passes |", "|---|---|---|---|---|---|---|"]
        for name, r in result["stats"][stat].items():
            ok = all(r["tests"][k]["all"]["diff_hi"] < 0 for k in ("test_2025", "test_2026"))
            for k, yr in (("test_2025", "2025"), ("test_2026", "2026")):
                t = r["tests"][k]["all"]
                L.append(f"| {name} | {yr} | {t['player_games']} | {t['rmse_old']:.3f} | {t['rmse_new']:.3f} | {t['rmse_new'] - t['rmse_old']:+.3f} ({t['diff_lo']:+.3f} to {t['diff_hi']:+.3f}) | {'yes' if ok else 'no'} |")
        w = result["stats"][stat][STAT_V]["weights"]
        L += ["", "Fitted weights for the stat variant (change in a player's prediction per 100% gap to the league): " + ", ".join(f"{p} {v:+.2f}" for p, v in w.items()) + ".", ""]
    L += ["The simulation applies the stat weights whether or not they pass (owner decision, 2026-11-01); this report records whether they would have passed. "
          "Each factor is held between 0.8 and 1.25.", "",
          "A defense's numbers also reflect the offenses it has faced; the test does not adjust for that. Rows are each week's final export, used only for weeks before the game.", ""]
    (ROOT / "docs" / "ALLOWED_CHECK.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print("RULE passed:", out["passed"], {k: list(v) for k, v in rule.items()})


if __name__ == "__main__":
    main()
