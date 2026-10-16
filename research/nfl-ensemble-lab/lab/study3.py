"""Phase 3 baseline research with nested chronological evaluation.

  python -m lab.study3

Every configuration is re-run with NESTED tuning: each walk-forward season s gets
hyperparameters tuned only on seasons < s. No fresh historical holdout exists:
2019-2022 = development, 2023-2024 = previously inspected validation,
2025 = diagnostic only. Independent evidence can only come from the prospective
archive (Phase 3 snapshots).

Pre-declared gate (written before results were seen):
  A candidate becomes a SHADOW CHALLENGER only if, versus the champion method of the
  nested champion configuration, it
    (1) lowers mean per-season log loss over 2019-2022,
    (2) lowers log loss over 2023-2024, and
    (3) has a Holm-adjusted one-sided p < 0.05 (paired bootstrap over 2019-2024 games,
        adjusted across all candidates tested).
  Shadow challengers are archived alongside the champion in every prospective snapshot.
  PROMOTION (manual, never automatic) requires >= 128 scored prospective final snapshots
  with a paired log-loss improvement whose 95% CI lies below zero.
The production champion is never changed by this script.
"""
from __future__ import annotations

import itertools
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from . import ensemble as ens
from . import metrics as M
from .config import ARTIFACTS_DIR
from .data_pipeline import load_feature_store
from .features import DEFAULT_GROUPS, INJURY_GROUP, PHASE3_GROUP, select_features
from .training import load_run

OUT = ARTIFACTS_DIR / "study_phase3"
COMPACT = ("Context (home field, rest, week, dome)", "Opponent-adjusted ratings", "Quarterback", "Offense-vs-defense matchups")
CONFIGS = {
    "champion_nested": DEFAULT_GROUPS,
    "plus_phase3": DEFAULT_GROUPS + (PHASE3_GROUP,),
    "plus_phase3_injury": DEFAULT_GROUPS + (PHASE3_GROUP, INJURY_GROUP),
    "compact_phase3": COMPACT + (PHASE3_GROUP,),
}
DEV, VAL, DIAG = (2019, 2022), (2023, 2024), (2025, 2025)
MIN_PROSPECTIVE_FOR_PROMOTION = 128


def _ll_vec(y, p):
    p = np.clip(np.asarray(p, float), M.EPS, 1 - M.EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def season_ll(oof, col, lo, hi):
    d = oof[(oof["season"] >= lo) & (oof["season"] <= hi) & oof["home_win"].notna()]
    return float(np.mean([M.log_loss(x["home_win"], x[col]) for _, x in d.groupby("season")]))


def subset_columns(oof: pd.DataFrame) -> dict[str, np.ndarray]:
    """Simpler ensembles built from the same out-of-sample model probabilities (no retraining)."""
    out = {}
    keys = list(ens.MODEL_KEYS)
    for r in (1, 2, 3):
        for combo in itertools.combinations(keys, r):
            out["avg[" + "+".join(combo) + "]"] = oof[[f"p_{k}" for k in combo]].mean(axis=1).to_numpy()
    out["avg[all but single_layer]"] = oof[[f"p_{k}" for k in keys if k != "single_layer"]].mean(axis=1).to_numpy()
    out["avg[all but decision_tree]"] = oof[[f"p_{k}" for k in keys if k != "decision_tree"]].mean(axis=1).to_numpy()
    return out


def redundancy(oof: pd.DataFrame) -> dict:
    d = oof[oof["season"].between(2019, 2024) & oof["home_win"].notna()]
    L = np.column_stack([np.log(np.clip(d[f"p_{k}"], 1e-6, 1 - 1e-6) / (1 - np.clip(d[f"p_{k}"], 1e-6, 1 - 1e-6))) for k in ens.MODEL_KEYS])
    C = np.corrcoef(L.T)
    ev = np.linalg.eigvalsh(C)
    R = np.column_stack([d["home_win"] - d[f"p_{k}"] for k in ens.MODEL_KEYS])
    CE = np.corrcoef(R.T)
    return {"logit_correlation": pd.DataFrame(C, index=ens.MODEL_KEYS, columns=ens.MODEL_KEYS).round(3).to_dict(),
            "error_correlation": pd.DataFrame(CE, index=ens.MODEL_KEYS, columns=ens.MODEL_KEYS).round(3).to_dict(),
            "effective_independent_models": float(ev.sum() ** 2 / (ev ** 2).sum()),
            "mean_offdiag_logit_corr": float((C.sum() - 6) / 30), "mean_offdiag_error_corr": float((CE.sum() - 6) / 30)}


def l1_stability(groups) -> pd.DataFrame:
    """Which features an L1 logistic regression keeps when refit on each expanding window."""
    fs = load_feature_store()
    cols = select_features(fs.columns, groups)
    d = fs[(fs["season"] >= 2016) & fs["completed"] & fs["home_win"].notna()]
    sel = []
    for s in range(2019, 2025):
        tr = d[d["season"] < s]
        X = tr[cols].astype(float)
        X = X.fillna(X.median())
        Z = StandardScaler().fit_transform(X)
        m = LogisticRegression(penalty="l1", C=0.02, solver="liblinear", max_iter=2000).fit(Z, tr["home_win"])
        sel.append(pd.Series(np.abs(m.coef_[0]) > 1e-8, index=cols, name=s))
    S = pd.concat(sel, axis=1)
    out = pd.DataFrame({"feature": cols, "selected_share": S.mean(axis=1).values})
    corr = d[cols].astype(float).corr().abs()
    out["n_near_duplicates_r_gt_0_9"] = [int((corr[c] > 0.9).sum() - 1) for c in cols]
    return out.sort_values("selected_share", ascending=False)


def main(progress=print) -> dict:
    from .training import run_training
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    runs = {}
    for name, groups in CONFIGS.items():
        progress(f"== {name} (nested tuning)")
        r = run_training(groups=groups, production=False, tag=f"p3_{name}", nested_tuning=True, fit_margins=False,
                         progress=lambda m: None)
        runs[name] = r
        progress(f"   {r['summary']['n_features']} features, run {r['run_dir'].name}")
    base = runs["champion_nested"]["oof"]
    champ_method = load_run()["selection"]["champion"]          # production champion method (weighted_average)
    base_col = base[f"p_{champ_method}"].to_numpy()
    # candidate list
    cands = []
    for name, r in runs.items():
        o = r["oof"].set_index("game_id").loc[base["game_id"]]
        for m in list(ens.MODEL_KEYS) + ["equal_average", "weighted_average", "stacking"]:
            if name == "champion_nested" and m == champ_method:
                continue
            cands.append((f"{name}:{m}", o[f"p_{m}"].to_numpy()))
    for k, v in subset_columns(base).items():
        cands.append((f"champion_nested:{k}", v))
    y = base["home_win"].to_numpy()
    season = base["season"].to_numpy()
    rows = []
    pooled = (season >= DEV[0]) & (season <= VAL[1]) & ~np.isnan(y)
    rng = np.random.default_rng(0)
    tmp = base.assign(_base=base_col)
    b_dev, b_val, b_diag = (season_ll(tmp, "_base", *w) for w in (DEV, VAL, DIAG))
    for name, p in cands:
        tmp = base.assign(_c=p)
        ok = pooled & ~np.isnan(p)
        d = _ll_vec(y[ok], p[ok]) - _ll_vec(y[ok], base_col[ok])
        boots = d[rng.integers(0, ok.sum(), (4000, ok.sum()))].mean(axis=1)
        p_one = float((boots >= 0).mean())
        rows.append({"candidate": name, "dev_delta": season_ll(tmp, "_c", *DEV) - b_dev, "val_delta": season_ll(tmp, "_c", *VAL) - b_val,
                     "pooled_delta": float(d.mean()), "pooled_ci_low": float(np.quantile(boots, .025)),
                     "pooled_ci_high": float(np.quantile(boots, .975)), "p_one_sided": p_one,
                     "diag_2025_delta": season_ll(tmp, "_c", *DIAG) - b_diag})
    res = pd.DataFrame(rows)
    from .discovery import holm
    res["p_holm"] = holm(res["p_one_sided"].to_numpy())
    res["passes_gate"] = (res["dev_delta"] < 0) & (res["val_delta"] < 0) & (res["p_holm"] < 0.05)
    res = res.sort_values("pooled_delta").reset_index(drop=True)
    res.to_csv(OUT / "gate_results.csv", index=False)
    red = redundancy(base)
    l1 = l1_stability(DEFAULT_GROUPS + (PHASE3_GROUP,))
    l1.to_csv(OUT / "l1_feature_stability.csv", index=False)
    summary = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "runs": {k: str(v["run_dir"]) for k, v in runs.items()}, "champion_method": champ_method,
               "baseline_nested": {"dev_mean_season_ll": b_dev, "val_mean_season_ll": b_val, "diag_2025_ll": b_diag},
               "n_candidates": int(len(res)), "n_passed": int(res["passes_gate"].sum()),
               "passed": res[res["passes_gate"]]["candidate"].tolist(), "redundancy": red,
               "gate": __doc__.split("Pre-declared gate")[1].split("The production champion")[0].strip()}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    progress(f"{summary['n_candidates']} candidates evaluated; {summary['n_passed']} passed the gate.")
    return {"summary": summary, "gate": res, "l1": l1}


def register_shadow_challenger(groups, progress=print) -> str:
    """Train a production bundle for a gate-passing configuration WITHOUT making it current,
    and register it for prospective shadow tracking."""
    from .prospective import CHALLENGERS, challenger_versions
    from .training import run_training
    r = run_training(groups=groups, production=True, set_current=False, tag="shadow", progress=progress)
    v = r["summary"]["version"]
    CHALLENGERS.write_text(json.dumps({"versions": challenger_versions() + [v]}, indent=2), encoding="utf-8")
    return v


def load_study() -> dict:
    if not (OUT / "summary.json").exists():
        return {}
    return {"summary": json.loads((OUT / "summary.json").read_text(encoding="utf-8")),
            "gate": pd.read_csv(OUT / "gate_results.csv"), "l1": pd.read_csv(OUT / "l1_feature_stability.csv")}


if __name__ == "__main__":
    main()
