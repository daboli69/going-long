"""Phase 4 feature-group evaluation (nested chronological tuning, same pre-declared gate
as study3): does each new football-intelligence group, alone or combined, improve the
champion out of sample?

  python -m lab.study4
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import ensemble as ens
from . import metrics as M
from .config import ARTIFACTS_DIR
from .discovery import holm
from .features import DEFAULT_GROUPS, INJURY_GROUP, P4_GROUPS, PHASE3_GROUP
from .study3 import DEV, DIAG, VAL, _ll_vec, season_ll
from .training import RUNS_DIR, load_run, run_training

OUT = ARTIFACTS_DIR / "study_phase4"
P4 = tuple(P4_GROUPS)
CONFIGS = {**{f"plus[{g.split(': ', 1)[1]}]": DEFAULT_GROUPS + (g,) for g in P4},
           "plus[all Phase 4]": DEFAULT_GROUPS + P4,
           "everything (Phase 3 + 4 + injuries)": DEFAULT_GROUPS + P4 + (PHASE3_GROUP, INJURY_GROUP)}
METHODS = list(ens.MODEL_KEYS) + ["equal_average", "weighted_average", "stacking"]


def _champion_nested_oof() -> pd.DataFrame:
    runs = sorted(RUNS_DIR.glob("*_p3_champion_nested"))
    if runs:
        return pd.read_parquet(runs[-1] / "oof_predictions.parquet")
    return run_training(groups=DEFAULT_GROUPS, production=False, tag="p4_champion_nested", nested_tuning=True,
                        fit_margins=False, progress=lambda m: None)["oof"]


def main(progress=print) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    base = _champion_nested_oof()
    champ = load_run()["selection"]["champion"]
    runs = {}
    for name, groups in CONFIGS.items():
        progress(f"== {name}")
        r = run_training(groups=groups, production=False, tag="p4_" + "".join(ch for ch in name if ch.isalnum())[:30],
                         nested_tuning=True, fit_margins=False, progress=lambda m: None)
        runs[name] = r
    y = base["home_win"].to_numpy()
    season = base["season"].to_numpy()
    pooled = (season >= DEV[0]) & (season <= VAL[1]) & ~np.isnan(y)
    rng = np.random.default_rng(0)
    bcol = base[f"p_{champ}"].to_numpy()
    tmp = base.assign(_b=bcol)
    b_dev, b_val, b_diag = (season_ll(tmp, "_b", *w) for w in (DEV, VAL, DIAG))
    rows, per_season = [], []
    for name, r in runs.items():
        o = r["oof"].set_index("game_id").loc[base["game_id"]]
        for m in METHODS:
            p = o[f"p_{m}"].to_numpy()
            ok = pooled & ~np.isnan(p)
            d = _ll_vec(y[ok], p[ok]) - _ll_vec(y[ok], bcol[ok])
            boots = d[rng.integers(0, ok.sum(), (4000, ok.sum()))].mean(axis=1)
            t = base.assign(_c=p)
            rows.append({"config": name, "method": m, "n_features": r["summary"]["n_features"],
                         "dev_delta": season_ll(t, "_c", *DEV) - b_dev, "val_delta": season_ll(t, "_c", *VAL) - b_val,
                         "pooled_delta": float(d.mean()), "pooled_ci_low": float(np.quantile(boots, .025)),
                         "pooled_ci_high": float(np.quantile(boots, .975)), "p_one_sided": float((boots >= 0).mean()),
                         "diag_2025_delta": season_ll(t, "_c", *DIAG) - b_diag})
            if m == champ:
                for s_, g in base.assign(_c=p, _b=bcol).groupby("season"):
                    g = g[g["home_win"].notna()]
                    per_season.append({"config": name, "season": int(s_), "champion_ll": M.log_loss(g["home_win"], g["_b"]),
                                       "config_ll": M.log_loss(g["home_win"], g["_c"])})
    res = pd.DataFrame(rows)
    res["p_holm"] = holm(res["p_one_sided"].to_numpy())
    res["passes_gate"] = (res["dev_delta"] < 0) & (res["val_delta"] < 0) & (res["p_holm"] < 0.05)
    res = res.sort_values("pooled_delta").reset_index(drop=True)
    res.to_csv(OUT / "gate_results.csv", index=False)
    pd.DataFrame(per_season).to_csv(OUT / "per_season.csv", index=False)
    imp = []
    for name, r in runs.items():
        fi = pd.read_csv(r["run_dir"] / "feature_importance.csv")
        imp.append(fi.assign(config=name))
    pd.concat(imp).to_csv(OUT / "feature_importance.csv", index=False)
    summary = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "champion_method": champ, "baseline": {"dev": b_dev, "val": b_val, "diag_2025": b_diag},
               "runs": {k: str(v["run_dir"]) for k, v in runs.items()}, "n_candidates": int(len(res)),
               "n_passed": int(res["passes_gate"].sum()), "passed": (res[res["passes_gate"]]["config"] + ":" + res[res["passes_gate"]]["method"]).tolist()}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    progress(f"{summary['n_candidates']} candidates; {summary['n_passed']} passed.")
    return summary


def load_study() -> dict:
    if not (OUT / "summary.json").exists():
        return {}
    r = {"summary": json.loads((OUT / "summary.json").read_text(encoding="utf-8")), "gate": pd.read_csv(OUT / "gate_results.csv")}
    for n in ("per_season", "feature_importance"):
        f = OUT / f"{n}.csv"
        r[n] = pd.read_csv(f) if f.exists() else pd.DataFrame()
    return r


if __name__ == "__main__":
    main()
