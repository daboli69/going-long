r"""Does defensive coverage improve the simulated game's receiving numbers? Scored on games the fit never saw.

    .venv\Scripts\python.exe scripts\coverage_check.py

The baseline is the nflverse-only prediction the simulation uses (the player's share of the team's catches or yards, times the team total).
Three families of coverage features (lab/coverage_usage.py) each adjust that prediction: new = old x (1 + features @ weights). Weights are
ridge-fitted on 2022 to 2024 and scored on 2025 and 2026 so far, using only weeks before each game. A family passes the gate only if the whole
90% interval for the change in error is below zero in both years. Writes docs/COVERAGE_CHECK.md and docs/coverage_check.json (aggregate numbers
only) and data/cache/coverage_rule.json. Local files only; no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import coverage_usage as C  # noqa: E402
from lab import fpds_usage as X  # noqa: E402
from lab import usage as U  # noqa: E402
from lab.config import CACHE_DIR  # noqa: E402

STATS = {"rec_yds": "Receiving yards", "rec": "Catches"}
TRAIN = ((2022, 3, 18), (2023, 3, 18), (2024, 3, 18))
RIDGE = 0.05  # in units of the average squared feature column, so every family is shrunk by the same relative amount
RULE_PATH = CACHE_DIR / "coverage_rule.json"


def stack(games, stat, lag, opp, pos):
    names = C.feature_names()
    cols = {n: i for i, n in enumerate(names)}
    old, F, y, gid, grp = [], [], [], [], []
    for i, c in enumerate(games):
        base = c["pool"][f"share_{stat}"].to_numpy(float)
        T = c["u"].totals[stat]
        if base.sum() <= 0 or T <= 0:
            continue
        pids = c["pool"]["pid"].tolist()
        ps = [pos.get(p) for p in pids]
        f = C.team_game_features(lag, opp, c["season"], c["week"], c["team"], pids, ps)
        old.append(base / base.sum() * T)
        F.append(f)
        y.append(c["actual"][stat].reindex(pids).fillna(0).to_numpy(float))
        gid.append(np.full(len(base), i))
        grp.append(np.array([p if p in C.GROUPS else "other" for p in ps]))
    return np.concatenate(old), np.vstack(F), np.concatenate(y), np.concatenate(gid), np.concatenate(grp), cols


def fit(old, F, y, idx):
    A = old[:, None] * F[:, idx]
    r = y - old
    lam = RIDGE * (A ** 2).mean(0).clip(1e-9) * len(y)
    return np.linalg.solve(A.T @ A + np.diag(lam), A.T @ r)


def main():
    lag, opp = C.Lagged(), C.opponents()
    pg = U.player_games(range(2021, 2027))
    pos = pg.sort_values(["season", "week"]).drop_duplicates("pid", keep="last").set_index("pid")["pos"].to_dict()
    sets = {"train": X._games(TRAIN, "last6"), "test_2025": X._games(((2025, 3, 18),), "last6"), "test_2026": X._games(((2026, 3, 7),), "last6")}
    result, rule = {"games": {k: len(v) for k, v in sets.items()}, "stats": {}}, {}
    names = C.feature_names()
    for stat in STATS:
        S = {k: stack(v, stat, lag, opp, pos) for k, v in sets.items()}
        old_t, F_t, y_t = S["train"][:3]
        res = {}
        for fam, feats in C.FAMILIES.items():
            idx = [names.index(f) for f in feats]
            beta = fit(old_t, F_t, y_t, idx)
            r = {"weights": dict(zip(feats, map(float, beta))), "tests": {}}
            for k in ("test_2025", "test_2026"):
                old, F, y, gid, grp, _ = S[k]
                new = old * (1 + F[:, idx] @ beta)
                touched = (np.abs(F[:, idx]).sum(1) > 0)
                r["tests"][k] = {"all": X._paired(new, old, y, gid), "by_group": {g: X._paired(new, old, y, gid, grp == g) for g in (*C.GROUPS,)},
                                 "share_with_features": float(touched.mean())}
            res[fam] = r
            ok = all(r["tests"][k]["all"]["diff_hi"] < 0 for k in ("test_2025", "test_2026"))
            if ok:
                rule.setdefault(stat, []).append({"family": fam, "weights": r["weights"]})
        result["stats"][stat] = res
    # Owner rule (Travis, 2026-11-07): use anything whose typical miss fell in both years, even if the interval includes zero. Only family A is a per-receiver nudge the simulation can read.
    fam_a = next(f for f in C.FAMILIES if f.startswith("A."))
    applied = {}
    for stat in STATS:
        r = result["stats"][stat][fam_a]
        if all(r["tests"][k]["all"]["rmse_new"] < r["tests"][k]["all"]["rmse_old"] for k in ("test_2025", "test_2026")):
            applied[stat] = {"matched": r["weights"]["matched"]}
    C.APPLIED_PATH.write_text(json.dumps(applied, indent=1), encoding="utf-8")
    out = {"passed": bool(rule), "stats": rule, "applied": applied, "created_at": pd.Timestamp.now(tz="UTC").isoformat()}
    RULE_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
    (ROOT / "docs" / "coverage_check.json").write_text(json.dumps({"result": result, "rule": out}, indent=1, default=str), encoding="utf-8")

    L = ["# Defensive coverage in the simulated game: what was tested", "",
         "Generated by `scripts/coverage_check.py`. Fitted on 2022 to 2024, scored on 2025 and on 2026 so far (weeks 3 to 7) using only weeks before each game. "
         "Aggregate numbers only.", "",
         "The baseline is the nflverse-only prediction: the player's recent share of the team's total. Each family adjusts it by a few percent depending on the "
         "defense faced. Error is the typical miss for one player in one game (root mean squared error); lower is better. The interval is 90%, resampling team-games. "
         "A family is used only if the whole interval is below zero in both years.", ""]
    for stat, label in STATS.items():
        L += [f"## {label}", "", "| Family | Year | Player-games | Error before | After | Change, 90% interval | Passes |", "|---|---|---|---|---|---|---|"]
        for fam, r in result["stats"][stat].items():
            ok = all(r["tests"][k]["all"]["diff_hi"] < 0 for k in ("test_2025", "test_2026"))
            for k, yr in (("test_2025", "2025"), ("test_2026", "2026")):
                t = r["tests"][k]["all"]
                L.append(f"| {fam} | {yr} | {t['player_games']} | {t['rmse_old']:.3f} | {t['rmse_new']:.3f} | {t['rmse_new'] - t['rmse_old']:+.3f} ({t['diff_lo']:+.3f} to {t['diff_hi']:+.3f}) | {'yes' if ok else 'no'} |")
        L.append("")
    L += ["Weights are in the JSON next to this report. Coverage rows are each week's final export, so the test uses weeks before the game but not the numbers as posted at the time.", ""]
    (ROOT / "docs" / "COVERAGE_CHECK.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print("RULE passed:", out["passed"], {k: [f["family"][:2] for f in v] for k, v in rule.items()})


if __name__ == "__main__":
    main()
