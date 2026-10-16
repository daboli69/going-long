"""Chronological training, walk-forward out-of-sample evaluation, calibration,
ensemble comparison, champion selection, and production refits.

Protocol (see docs/METHODOLOGY.md):
  1. Tune each model's hyperparameters on development seasons only
     (train < s, score s for s in TUNING_FOLDS).
  2. Walk forward: for every season s >= WALK_FORWARD_START, fit on all
     completed games from seasons < s and predict season s. These are the
     saved out-of-sample probabilities (the Phase 2 input).
  3. Calibrators, ensemble weights and the stacker for season s are fit only
     on out-of-sample predictions from seasons < s.
  4. Calibration methods and the research champion are chosen on the
     validation seasons and written to disk BEFORE test seasons are scored.
  5. Production models are refit on every completed game as a separate
     version; historical results are preserved under artifacts/runs/<version>.
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from . import ensemble as ens
from . import metrics as M
from . import models
from .config import (ARTIFACTS_DIR, DEV_SEASONS, FIRST_SEASON, LAB_ROOT, MODELS_DIR, PROSPECTIVE_FROM,
                     TEST_SEASONS, TUNING_FOLDS, VALIDATION_SEASONS, WALK_FORWARD_START)
from .data_pipeline import load_feature_store
from .features import DEFAULT_GROUPS, select_features

RUNS_DIR = ARTIFACTS_DIR / "runs"
CURRENT = MODELS_DIR / "CURRENT.json"
BASELINE_FEATURES = ["diff_blend_points", "diff_blend_d_points", "ctx_home_field"]
# Isotonic was removed in Phase 1.5: with ~270 games per season it overfit early walk-forward
# seasons (e.g. 2019, 2021) on development data. Calibrator.isotonic remains available for study.
CAL_METHODS = ("none", "platt")


def split_of(season: int) -> str:
    if season in TEST_SEASONS:
        return "test"
    if season in VALIDATION_SEASONS:
        return "validation"
    if season >= PROSPECTIVE_FROM:
        return "prospective"
    return "development"


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=LAB_ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------- calibration

class Calibrator:
    def __init__(self, method: str):
        self.method = method

    def fit(self, p, y):
        p, y = np.asarray(p, float), np.asarray(y, float)
        if self.method == "platt":
            self.m = LogisticRegression(C=100.0, max_iter=1000).fit(ens._logit(p)[:, None], y)
        elif self.method == "isotonic":
            self.m = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip").fit(p, y)
        return self

    def transform(self, p):
        p = np.asarray(p, float)
        if self.method == "platt":
            return self.m.predict_proba(ens._logit(p)[:, None])[:, 1]
        if self.method == "isotonic":
            return self.m.predict(p)
        return p


# --------------------------------------------------------------------------- helpers

def _xy(df, cols, target):
    return df[cols].astype(float).to_numpy(), df[target].astype(float).to_numpy()


def tune(kind: str, key: str, data: pd.DataFrame, cols: list[str], progress) -> tuple[dict, list[dict]]:
    """Pick hyperparameters by mean score over development-only tuning folds."""
    target = "home_win" if kind == "clf" else "margin"
    rows = data[data[target].notna()]
    results = []
    for params in models.grid(kind, key):
        scores = []
        for s in TUNING_FOLDS:
            tr, va = rows[rows["season"] < s], rows[rows["season"] == s]
            Xtr, ytr = _xy(tr, cols, target)
            Xva, yva = _xy(va, cols, target)
            est = models.make(kind, key, params).fit(Xtr, ytr)
            if kind == "clf":
                scores.append(M.log_loss(yva, est.predict_proba(Xva)[:, 1]))
            else:
                scores.append(float(np.mean(np.abs(est.predict(Xva) - yva))))
        results.append({"params": params, "score": float(np.mean(scores)), "fold_scores": scores})
    best = min(results, key=lambda r: r["score"])
    progress(f"    tuned {kind} {key}: {best['params']} ({'log loss' if kind == 'clf' else 'MAE'} {best['score']:.4f})")
    return best["params"], results


def _baseline_home_prior(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    hf = train[(train["ctx_home_field"] == 1) & train["home_win"].notna()]["home_win"].mean()
    return np.where(test["ctx_home_field"] == 1, hf, 0.5)


def _baseline_pointdiff(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    tr = train[train["home_win"].notna()]
    m = models._scaled(LogisticRegression(C=1.0, max_iter=1000)).fit(*_xy(tr, BASELINE_FEATURES, "home_win"))
    return m.predict_proba(test[BASELINE_FEATURES].astype(float).to_numpy())[:, 1]


# --------------------------------------------------------------------------- main

def select_champion(oof: pd.DataFrame, candidates: list[str], n_boot: int = 2000, seed: int = 0) -> dict:
    """Champion rule (validation + earlier seasons only; test seasons never read):
    1. best = lowest log loss on the validation seasons;
    2. a candidate is tied with best when its paired-bootstrap log-loss difference to
       best is within one standard error (validation games resampled);
    3. among tied candidates, choose the lowest mean per-season log loss over all
       walk-forward seasons before the test seasons (stability over more history)."""
    val = oof[(oof["split"] == "validation") & oof["home_win"].notna()]
    y = val["home_win"].to_numpy()
    def ll_vec(p):
        p = np.clip(p, M.EPS, 1 - M.EPS)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p))
    losses = {c: ll_vec(val[f"p_{c}"].to_numpy()) for c in candidates if val[f"p_{c}"].notna().all()}
    best = min(losses, key=lambda c: losses[c].mean())
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(y), (n_boot, len(y)))
    tied, details = [], {}
    for c, l in losses.items():
        d = l - losses[best]
        se = float(d[idx].mean(axis=1).std())
        details[c] = {"validation_log_loss": float(l.mean()), "diff_vs_best": float(d.mean()), "se_diff": se}
        if d.mean() <= se:
            tied.append(c)
    hist = oof[(oof["split"].isin(["development", "validation"])) & (oof["season"] >= WALK_FORWARD_START + 1) & oof["home_win"].notna()]
    stab = {c: float(hist.groupby("season").apply(lambda d: M.log_loss(d["home_win"], d[f"p_{c}"]), include_groups=False).mean()) for c in tied}
    for c in tied:
        details[c]["mean_season_log_loss_history"] = stab[c]
    champion = min(stab, key=stab.get)
    return {"best_on_validation": best, "tied_within_1se": tied, "champion": champion, "details": details,
            "history_seasons": sorted(int(s) for s in hist["season"].unique())}


def run_training(groups=DEFAULT_GROUPS, model_keys=ens.MODEL_KEYS, progress=print,
                 progress_frac=lambda f: None, training_from: int = FIRST_SEASON,
                 production: bool = True, tag: str = "") -> dict:
    """production=False runs the full chronological evaluation without refitting or
    replacing the current production models (used for experiments)."""
    t0 = time.time()
    fs = load_feature_store()
    cols = select_features(fs.columns, groups)
    model_keys = tuple(k for k in ens.MODEL_KEYS if k in model_keys)
    data = fs[(fs["season"] >= training_from) & fs["completed"]].sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    version = datetime.now(timezone.utc).strftime("v%Y%m%d_%H%M%S") + (f"_{tag}" if tag else "")
    run_dir = RUNS_DIR / version
    run_dir.mkdir(parents=True, exist_ok=True)
    progress(f"Training run {version}: {len(data)} completed games {data['season'].min()}-{data['season'].max()}, "
             f"{len(cols)} features, models: {', '.join(model_keys)}")

    # 1. tuning (development seasons only)
    dev = data[data["season"].isin(DEV_SEASONS)]
    params, tuning_log = {"clf": {}, "reg": {}}, []
    steps = len(model_keys) * 2
    for i, key in enumerate(model_keys):
        for kind in ("clf", "reg"):
            progress(f"Step 1/5 tuning {models.MARGIN_NAMES[key] if kind == 'reg' else ens.MODEL_NAMES[key]} ...")
            best, res = tune(kind, key, dev, cols, progress)
            params[kind][key] = best
            tuning_log += [{"kind": kind, "model": key, **r} for r in res]
        progress_frac(0.35 * (i + 1) / len(model_keys))

    # 2. walk-forward out-of-sample predictions
    seasons = [s for s in sorted(data["season"].unique()) if s >= WALK_FORWARD_START]
    oof_parts, importance = [], []
    for si, s in enumerate(seasons):
        tr, te = data[data["season"] < s], data[data["season"] == s]
        trc = tr[tr["home_win"].notna()]
        Xtr, ytr = _xy(trc, cols, "home_win")
        Xm, ym = _xy(tr, cols, "margin")
        Xte = te[cols].astype(float).to_numpy()
        out = te[["game_id", "season", "week", "game_type", "kickoff_utc", "home_team", "away_team",
                  "home_win", "margin", "spread_line", "market_p_home_novig"]].copy()
        out["split"] = split_of(int(s))
        out["train_seasons"] = f"{int(tr['season'].min())}-{int(tr['season'].max())}"
        progress(f"Step 2/5 walk-forward season {s} (train {out['train_seasons'].iloc[0]}, {len(te)} games)")
        for key in model_keys:
            clf = models.make("clf", key, params["clf"][key]).fit(Xtr, ytr)
            out[f"raw_{key}"] = clf.predict_proba(Xte)[:, 1]
            reg = models.make("reg", key, params["reg"][key]).fit(Xm, ym)
            out[f"margin_{key}"] = reg.predict(Xte)
            if s == VALIDATION_SEASONS[0]:
                tec = te[te["home_win"].notna()]
                pi = permutation_importance(clf, tec[cols].astype(float).to_numpy(), tec["home_win"].to_numpy(),
                                            scoring="neg_log_loss", n_repeats=5, random_state=0, n_jobs=1)
                importance += [{"model": key, "feature": c, "importance": float(m), "std": float(sd),
                                "scope": f"global: permutation importance (log loss) on {s} games, model trained on seasons < {s}"}
                               for c, m, sd in zip(cols, pi.importances_mean, pi.importances_std)]
        out["base_home_prior"] = _baseline_home_prior(tr, te)
        out["base_pointdiff"] = _baseline_pointdiff(tr, te)
        oof_parts.append(out)
        progress_frac(0.35 + 0.45 * (si + 1) / len(seasons))
    oof = pd.concat(oof_parts, ignore_index=True)

    # 3. walk-forward calibration; method chosen per model on validation seasons
    progress("Step 3/5 calibration (fit only on earlier out-of-sample seasons)")
    cal_scores = {}
    for key in model_keys:
        cands = {}
        for method in CAL_METHODS:
            col = np.full(len(oof), np.nan)
            for s in seasons:
                idx = (oof["season"] == s).to_numpy()
                hist = oof[(oof["season"] < s) & oof["home_win"].notna()]
                if method == "none" or len(hist) < 200:
                    col[idx] = oof.loc[idx, f"raw_{key}"]
                else:
                    col[idx] = Calibrator(method).fit(hist[f"raw_{key}"], hist["home_win"]).transform(oof.loc[idx, f"raw_{key}"])
            cands[method] = col
        # choose on every pre-test walk-forward season that had calibration history (not just validation)
        sel_rows = (oof["split"].isin(["development", "validation"]) & (oof["season"] > WALK_FORWARD_START)
                    & oof["home_win"].notna()).to_numpy()
        seasons_sel = oof.loc[sel_rows, "season"].to_numpy()
        y_sel = oof.loc[sel_rows, "home_win"].to_numpy()
        scores = {m: float(np.mean([M.log_loss(y_sel[seasons_sel == s_], c[sel_rows][seasons_sel == s_]) for s_ in np.unique(seasons_sel)]))
                  for m, c in cands.items()}
        chosen = min(scores, key=scores.get)
        cal_scores[key] = {"mean_season_log_loss_2019_2024": scores, "chosen": chosen}
        oof[f"p_{key}"] = cands[chosen]

    # 4. walk-forward ensembles
    progress("Step 4/5 ensembles (weights and stacker fit only on earlier seasons)")
    pcols = [f"p_{k}" for k in model_keys]
    oof["p_equal_average"] = ens.equal_average(oof[pcols].to_numpy())
    oof["p_weighted_average"] = np.nan
    oof["p_stacking"] = np.nan
    for s in seasons:
        idx = (oof["season"] == s).to_numpy()
        hist = oof[(oof["season"] < s) & oof["home_win"].notna()]
        P = oof.loc[idx, pcols].to_numpy()
        if len(hist) >= 200:
            w = ens.skill_weights(hist[pcols].to_numpy(), hist["home_win"].to_numpy())
            oof.loc[idx, "p_weighted_average"] = ens.weighted_average(P, w)
            oof.loc[idx, "p_stacking"] = ens.stack_predict(ens.fit_stacker(hist[pcols].to_numpy(), hist["home_win"].to_numpy()), P)
        else:
            oof.loc[idx, "p_weighted_average"] = oof.loc[idx, "p_equal_average"]
    votes = [ens.vote({k: r[f"p_{k}"] for k in model_keys}) for _, r in oof.iterrows()]
    oof["home_votes"] = [v["home_votes"] for v in votes]
    oof["away_votes"] = [v["away_votes"] for v in votes]
    oof["vote_tie"] = [v["tie"] for v in votes]
    oof["vote_home_pick"] = [1.0 if v["winner"] == "home" else 0.0 if v["winner"] == "away" else np.nan for v in votes]
    oof["margin_ensemble"] = oof[[f"margin_{k}" for k in model_keys]].mean(axis=1)

    # 5. champion selection on validation seasons ONLY, saved before test scoring
    candidates = list(model_keys) + ["equal_average", "weighted_average", "stacking"]
    val = oof[(oof["split"] == "validation") & oof["home_win"].notna()]
    sel = {c: {"log_loss": M.log_loss(val["home_win"], val[f"p_{c}"]), "brier": M.brier(val["home_win"], val[f"p_{c}"])}
           for c in candidates}
    rule = select_champion(oof, candidates)
    champion = rule["champion"]
    selection = {"selected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "rule": "validation log loss; candidates within 1 paired-bootstrap SE of the best are tied; "
                         "ties broken by mean per-season log loss over earlier walk-forward seasons; test seasons not consulted",
                 "validation_seasons": list(VALIDATION_SEASONS), "candidates": sel, "champion": champion,
                 "tie_analysis": rule, "calibration": cal_scores, "feature_groups": list(groups)}
    (run_dir / "selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")
    progress(f"Step 5/5 research champion (validation log loss): {champion}")

    # metrics, now including test and prospective seasons
    leaderboard, season_rows, calib_rows = [], [], []
    methods = {**{k: ens.MODEL_NAMES[k] for k in model_keys}, "equal_average": ens.ENSEMBLE_NAMES["equal_average"],
               "weighted_average": ens.ENSEMBLE_NAMES["weighted_average"], "stacking": ens.ENSEMBLE_NAMES["stacking"],
               "base_home_prior": "Baseline: home-field prior", "base_pointdiff": "Baseline: point-differential logistic",
               "market": "Sportsbook closing no-vig (benchmark)"}
    oof["p_base_home_prior"], oof["p_base_pointdiff"], oof["p_market"] = oof["base_home_prior"], oof["base_pointdiff"], oof["market_p_home_novig"]
    lab = oof[oof["home_win"].notna()]
    for split in ("development", "validation", "test", "prospective"):
        part = lab[lab["split"] == split]
        if not len(part):
            continue
        for key, name in methods.items():
            sub = part[part[f"p_{key}"].notna()]
            leaderboard.append({"split": split, "method": key, "name": name, **M.prob_summary(sub["home_win"], sub[f"p_{key}"])})
            if split in ("validation", "test"):
                for _, row in M.calibration_table(sub["home_win"], sub[f"p_{key}"]).iterrows():
                    calib_rows.append({"split": split, "method": key, **row.to_dict()})
        mv = part[part["vote_home_pick"].notna()]
        leaderboard.append({"split": split, "method": "majority_vote", "name": ens.ENSEMBLE_NAMES["majority_vote"], "n": int(len(mv)),
                            "accuracy": float((mv["vote_home_pick"] == mv["home_win"]).mean()),
                            "accuracy_ci": M.bootstrap_ci(lambda a, b: float(np.mean(a == b)), mv["vote_home_pick"].to_numpy(), mv["home_win"].to_numpy()),
                            "brier": np.nan, "log_loss": np.nan, "ece": np.nan})
    for s, part in lab.groupby("season"):
        for key, name in methods.items():
            sub = part[part[f"p_{key}"].notna()]
            if len(sub):
                season_rows.append({"season": int(s), "split": split_of(int(s)), "method": key, "name": name,
                                    **M.prob_summary(sub["home_win"], sub[f"p_{key}"], ci=False)})
    margin_rows = []
    for split in ("development", "validation", "test", "prospective"):
        part = oof[oof["split"] == split]
        if not len(part):
            continue
        for key in list(model_keys) + ["ensemble"]:
            margin_rows.append({"split": split, "method": key, "name": models.MARGIN_NAMES.get(key, "Ensemble mean margin"),
                                **M.margin_summary(part["margin"], part[f"margin_{key}"])})
        margin_rows.append({"split": split, "method": "spread", "name": "Sportsbook closing spread (benchmark)",
                            **M.margin_summary(part["margin"], part["spread_line"])})
    # model agreement (validation + test), for the debate's disagreement analysis
    agree = []
    vt = oof[oof["split"].isin(["validation", "test"])]
    for a in model_keys:
        for b in model_keys:
            agree.append({"model_a": a, "model_b": b,
                          "vote_agreement": float(((vt[f"p_{a}"] > 0.5) == (vt[f"p_{b}"] > 0.5)).mean()),
                          "prob_correlation": float(np.corrcoef(vt[f"p_{a}"], vt[f"p_{b}"])[0, 1])})

    lb = pd.DataFrame(leaderboard)
    if not production:
        summary = {"version": version, "tag": tag, "production": False, "n_features": len(cols), "groups": list(groups),
                   "champion": champion, "params": params, "calibration": {k: v["chosen"] for k, v in cal_scores.items()},
                   "minutes": round((time.time() - t0) / 60, 1)}
        oof.to_parquet(run_dir / "oof_predictions.parquet", index=False)
        lb.to_csv(run_dir / "leaderboard.csv", index=False)
        pd.DataFrame(season_rows).to_csv(run_dir / "season_results.csv", index=False)
        pd.DataFrame(margin_rows).to_csv(run_dir / "margin_results.csv", index=False)
        pd.DataFrame(importance).to_csv(run_dir / "feature_importance.csv", index=False)
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        progress(f"Experiment {version} finished (production models unchanged).")
        return {"summary": summary, "leaderboard": lb, "run_dir": run_dir, "oof": oof}

    # production refit on every completed game
    progress("Refitting production models on all completed games ...")
    allc = data[data["home_win"].notna()]
    X_all, y_all = _xy(allc, cols, "home_win")
    Xm_all, ym_all = _xy(data, cols, "margin")
    hist = oof[oof["home_win"].notna()]
    bundle = {"version": version, "features": cols, "groups": list(groups), "model_keys": list(model_keys),
              "params": params, "clf": {}, "reg": {}, "calibrators": {},
              "train_means": dict(zip(cols, np.nanmean(X_all, axis=0))),
              "trained_through": str(data["kickoff_utc"].max()), "n_train_games": int(len(data))}
    for key in model_keys:
        bundle["clf"][key] = models.make("clf", key, params["clf"][key]).fit(X_all, y_all)
        bundle["reg"][key] = models.make("reg", key, params["reg"][key]).fit(Xm_all, ym_all)
        method = cal_scores[key]["chosen"]
        bundle["calibrators"][key] = Calibrator(method).fit(hist[f"raw_{key}"], hist["home_win"])
    bundle["weights"] = dict(zip(model_keys, ens.skill_weights(hist[pcols].to_numpy(), hist["home_win"].to_numpy())))
    bundle["stacker"] = ens.fit_stacker(hist[pcols].to_numpy(), hist["home_win"].to_numpy())
    bundle["champion"] = champion
    model_dir = MODELS_DIR / version
    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_dir / "bundle.joblib")

    summary = {
        "version": version, "tag": tag, "groups": list(groups), "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_sha": _git_sha(),
        "n_games": int(len(data)), "n_features": len(cols), "seasons": [int(data["season"].min()), int(data["season"].max())],
        "walk_forward_seasons": [int(s) for s in seasons], "champion": champion, "params": params,
        "calibration": {k: v["chosen"] for k, v in cal_scores.items()}, "weights": {k: float(v) for k, v in bundle["weights"].items()},
        "minutes": round((time.time() - t0) / 60, 1),
        "test_champion": lb[(lb["split"] == "test") & (lb["method"] == champion)].drop(columns=["split"]).to_dict("records"),
    }
    oof.to_parquet(run_dir / "oof_predictions.parquet", index=False)
    lb.to_csv(run_dir / "leaderboard.csv", index=False)
    pd.DataFrame(season_rows).to_csv(run_dir / "season_results.csv", index=False)
    pd.DataFrame(calib_rows).to_csv(run_dir / "calibration.csv", index=False)
    pd.DataFrame(margin_rows).to_csv(run_dir / "margin_results.csv", index=False)
    pd.DataFrame(importance).to_csv(run_dir / "feature_importance.csv", index=False)
    pd.DataFrame(agree).to_csv(run_dir / "model_agreement.csv", index=False)
    pd.DataFrame(tuning_log).to_json(run_dir / "tuning_log.json", orient="records", indent=1)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (model_dir / "manifest.json").write_text(json.dumps(summary | {"features": cols}, indent=2, default=str), encoding="utf-8")
    CURRENT.write_text(json.dumps({"version": version}), encoding="utf-8")
    progress_frac(1.0)
    progress(f"Finished in {summary['minutes']} min. Models: {model_dir}  Results: {run_dir}")
    return {"summary": summary, "leaderboard": lb, "run_dir": run_dir}


# --------------------------------------------------------------------------- loading

def current_version() -> str | None:
    return json.loads(CURRENT.read_text())["version"] if CURRENT.exists() else None


def load_bundle(version: str | None = None) -> dict:
    version = version or current_version()
    if not version:
        raise FileNotFoundError("No trained models yet. Use 'Train All Six Models' first.")
    return joblib.load(MODELS_DIR / version / "bundle.joblib")


def load_run(version: str | None = None) -> dict:
    version = version or current_version()
    if not version:
        return {}
    d = RUNS_DIR / version
    read = lambda n: pd.read_csv(d / n) if (d / n).exists() else pd.DataFrame()
    return {"version": version, "dir": d,
            "summary": json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else {},
            "selection": json.loads((d / "selection.json").read_text()) if (d / "selection.json").exists() else {},
            "oof": pd.read_parquet(d / "oof_predictions.parquet") if (d / "oof_predictions.parquet").exists() else pd.DataFrame(),
            "leaderboard": read("leaderboard.csv"), "seasons": read("season_results.csv"), "calibration": read("calibration.csv"),
            "margins": read("margin_results.csv"), "importance": read("feature_importance.csv"), "agreement": read("model_agreement.csv")}
