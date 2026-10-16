"""Phase 1.5 reliability study: feature-set and injury-feature comparisons.

Decisions use development walk-forward seasons (2019-2022) and validation
(2023-2024) only. 2025 is reported as an already-inspected diagnostic holdout;
it is never used to choose anything. Production models are not touched.

  python -m lab.study
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import metrics as M
from . import models
from .config import ARTIFACTS_DIR
from .ensemble import MODEL_KEYS
from .features import DEFAULT_GROUPS, INJURY_GROUP
from .training import run_training

COMPACT = ("Context (home field, rest, week, dome)", "Opponent-adjusted ratings", "Quarterback", "Offense-vs-defense matchups")
CONFIGS = {
    "default": DEFAULT_GROUPS,
    "default_injury": DEFAULT_GROUPS + (INJURY_GROUP,),
    "compact": COMPACT,
    "compact_injury": COMPACT + (INJURY_GROUP,),
}
METHODS = list(MODEL_KEYS) + ["equal_average", "weighted_average", "stacking", "base_pointdiff", "market"]
WINDOWS = {"dev 2019-22": (2019, 2022), "validation 2023-24": (2023, 2024), "diagnostic 2025": (2025, 2025),
           "injury-covered 2019-24": (2019, 2024)}


def score(oof: pd.DataFrame, lo: int, hi: int, require_injury: bool = False) -> dict:
    d = oof[(oof["season"] >= lo) & (oof["season"] <= hi) & oof["home_win"].notna()]
    out = {}
    for m in METHODS:
        if f"p_{m}" not in d:
            continue
        x = d[d[f"p_{m}"].notna()]
        if len(x):
            out[m] = {"n": len(x), "log_loss": M.log_loss(x["home_win"], x[f"p_{m}"]), "brier": M.brier(x["home_win"], x[f"p_{m}"]),
                      "ece": M.ece(x["home_win"], x[f"p_{m}"]), "accuracy": M.accuracy(x["home_win"], x[f"p_{m}"])}
    return out


def paired_diff(a: pd.DataFrame, b: pd.DataFrame, method: str, lo: int, hi: int, n_boot: int = 2000) -> dict:
    """Log-loss difference (b - a) on the same games with a bootstrap 95% CI."""
    cols = ["game_id", "home_win", f"p_{method}", "season"]
    m = a[cols].merge(b[["game_id", f"p_{method}"]], on="game_id", suffixes=("_a", "_b"))
    m = m[(m["season"] >= lo) & (m["season"] <= hi) & m["home_win"].notna()].dropna()
    y = m["home_win"].to_numpy()
    def ll(p):
        p = np.clip(p, M.EPS, 1 - M.EPS)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p))
    d = ll(m[f"p_{method}_b"].to_numpy()) - ll(m[f"p_{method}_a"].to_numpy())
    idx = np.random.default_rng(0).integers(0, len(d), (n_boot, len(d)))
    boots = d[idx].mean(axis=1)
    return {"n": int(len(d)), "diff": float(d.mean()), "ci": (float(np.quantile(boots, .025)), float(np.quantile(boots, .975)))}


def main() -> None:
    runs = {}
    for name, groups in CONFIGS.items():
        print(f"== {name}")
        runs[name] = run_training(groups=groups, production=False, tag=name, progress=lambda m: None)
        print(f"   {runs[name]['summary']['n_features']} features, champion {runs[name]['summary']['champion']}")
    # Random Forest regularization variants (development folds only, default features)
    rf_rows = []
    for leaf in (25, 50, 100):
        for mf in (0.3, 0.15):
            models.CLASSIFIERS["random_forest"] = (lambda leaf=leaf, mf=mf, **k: models._imputed(
                models.RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=leaf, max_features=mf,
                                              random_state=models.RANDOM_SEED, n_jobs=-1)), [{}])
            r = run_training(groups=DEFAULT_GROUPS, model_keys=("random_forest",), production=False, tag=f"rf_leaf{leaf}_mf{mf}", progress=lambda m: None)
            o = r["oof"]
            rf_rows.append({"min_samples_leaf": leaf, "max_features": mf,
                            **{w: score(o, *WINDOWS[w])["random_forest"]["log_loss"] for w in ("dev 2019-22", "validation 2023-24")}})
    rows = []
    for name, r in runs.items():
        for w, (lo, hi) in WINDOWS.items():
            for m, v in score(r["oof"], lo, hi).items():
                rows.append({"config": name, "window": w, "method": m, **v})
    table = pd.DataFrame(rows)
    diffs = []
    for base, chal in (("default", "default_injury"), ("compact", "compact_injury"), ("default", "compact")):
        for m in METHODS[:-2]:
            for w in ("dev 2019-22", "validation 2023-24"):
                diffs.append({"baseline": base, "challenger": chal, "method": m, "window": w,
                              **paired_diff(runs[base]["oof"], runs[chal]["oof"], m, *WINDOWS[w])})
    out = ARTIFACTS_DIR / "study_phase1_5"
    out.mkdir(exist_ok=True)
    table.to_csv(out / "feature_set_comparison.csv", index=False)
    pd.DataFrame(diffs).to_csv(out / "paired_differences.csv", index=False)
    pd.DataFrame(rf_rows).to_csv(out / "rf_regularization.csv", index=False)
    (out / "runs.json").write_text(json.dumps({k: str(v["run_dir"]) for k, v in runs.items()}, indent=2))
    pd.set_option("display.width", 220)
    piv = table.pivot_table(index=["config", "method"], columns="window", values="log_loss").round(4)
    print(piv.to_string())
    print(pd.DataFrame(diffs).round(4).to_string())
    print(pd.DataFrame(rf_rows).round(4).to_string())


if __name__ == "__main__":
    main()
