"""Phase 2: automated upset / mispricing discovery engine.

Question asked of the data: in which pregame circumstances do actual outcomes
systematically differ from a baseline probability? Baselines:
  * "ensemble": the Phase 1 research champion's walk-forward OUT-OF-SAMPLE probability
  * "market":   the closing no-vig probability (benchmark only: no timestamps, never executable)

Everything is oriented to the underdog of the baseline (p_dog < 0.5) so a pattern
reads "underdogs in situation S win more/less often than the baseline says".
A single upset is not evidence; a pattern is the sum over many games of
(outcome - baseline probability), scored with proper likelihood statistics.

Chronology per research origin (no overlap):
  discovery seasons  -> generate and screen candidates (BH FDR reported)
  validation seasons -> carried candidates re-tested (Holm), stability checked,
                        correction-layer shrinkage chosen
  evaluation season  -> adjusted vs baseline, touched by nothing above
  2025               -> diagnostic only (already inspected in Phase 1)
  2026+              -> prospective only from predictions archived before kickoff
Nothing here changes Phase 1 models or predictions.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import xgboost
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.tree import DecisionTreeRegressor

from . import metrics as M
from .config import ARTIFACTS_DIR, SNAPSHOTS_DIR

DISCOVERY_DIR = ARTIFACTS_DIR / "discovery"
DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
CURRENT = DISCOVERY_DIR / "CURRENT.json"
EPS = 1e-6

DEFAULT_CONFIG = {
    "seed": 20261017,
    "origins": [
        {"name": "primary", "discovery": [2018, 2021], "validation": [2022, 2023], "evaluation": [2024, 2024]},
        {"name": "replication", "discovery": [2018, 2020], "validation": [2021, 2022], "evaluation": [2023, 2023]},
    ],
    "diagnostic": [2025, 2025],
    "prospective_from": 2026,
    "baselines": ["ensemble", "market"],
    "quantiles": [0.1, 0.25, 0.5, 0.75, 0.9],
    "pair_quantiles": [0.25, 0.5, 0.75],
    "pair_top_features": 14,
    "symbolic_top_features": 16,
    "gbm_top_features": 60,
    "n_clusters": 8,
    "rule_trees": 25,
    "min_n_discovery": 40,
    "min_n_validation": 25,
    "carry_top_k": 30,
    "dedup_jaccard": 0.6,
    "dedup_corr": 0.9,
    "fdr_q": 0.10,
    "validation_alpha": 0.05,
    "min_season_sign_share": 0.5,
    "adjuster_l2": 4.0,
    "gbm_shrink_grid": [0.0, 0.25, 0.5, 0.75, 1.0],
}

STAT_LABELS = {
    "epa_pp": "offensive EPA/play", "pass_epa": "passing EPA/play", "rush_epa": "rushing EPA/play", "sr": "success rate",
    "pass_sr": "passing success rate", "rush_sr": "rushing success rate", "points": "points per game", "turnovers": "turnovers",
    "explosive_rate": "explosive-play rate", "sack_rate": "sack rate allowed", "early_epa": "early-down EPA", "early_sr": "early-down success",
    "third_conv": "third-down conversion", "rz_td_rate": "red-zone TD rate", "plays": "plays per game", "sec_per_play": "seconds per play (pace)",
    "pass_rate": "pass rate", "pass_yds": "passing yards", "rush_yds": "rushing yards", "total_yds": "total yards",
    "pass_td": "passing TDs", "rush_td": "rushing TDs", "rating_margin": "opponent-adjusted margin rating",
    "rating_epa": "opponent-adjusted EPA rating", "qb_eff": "projected-QB efficiency", "qb_log_exp": "projected-QB experience",
    "rest_days": "rest days",
}
WINDOW_LABELS = {"blend": "season-blended", "l3": "last-3-games", "l5": "last-5-games", "prev": "previous-season", "std": "season-to-date"}


# --------------------------------------------------------------------------- base table

def _hash_df(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()[:16]


def orient(fs_rows: pd.DataFrame, p_home: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
    """Underdog-oriented feature matrix. dmf_* = underdog minus favorite."""
    p_home = np.asarray(p_home, float)
    dog_home = p_home < 0.5
    s = np.where(dog_home, 1.0, -1.0)
    cols: dict[str, np.ndarray] = {}
    for c in fs_rows.columns:
        if fs_rows[c].dtype.kind not in "fib":
            continue
        v = fs_rows[c].astype(float).to_numpy()
        if c.startswith("diff_") and not c.startswith(("diff_std_", "diff_l5_")):
            cols["dmf_" + c[5:]] = v * s
        elif c.startswith("mx_net_") or c in ("mx_turnover_margin", "mx_recent_form", "mx_form_vs_season"):
            cols["dmf_" + c[3:]] = v * s
        elif c.startswith(("p3_diff_", "p4mx_net_")):   # Phase 3/4 matchup differences (home minus away)
            cols["dmf_" + c.split("_", 2)[2] if c.startswith("p3_diff_") else "dmf_" + c] = v * s
        elif c.startswith("mx_home_off_vs_def_"):
            other = fs_rows[c.replace("mx_home_", "mx_away_")].astype(float).to_numpy()
            k = c[len("mx_home_"):]
            cols["dog_" + k], cols["fav_" + k] = np.where(dog_home, v, other), np.where(dog_home, other, v)
        elif c.startswith("inj_mx_home_"):
            other = fs_rows[c.replace("inj_mx_home_", "inj_mx_away_")].astype(float).to_numpy()
            k = "inj_" + c[len("inj_mx_home_"):]
            cols["dog_" + k], cols["fav_" + k] = np.where(dog_home, v, other), np.where(dog_home, other, v)
        elif c.startswith("home_") and ("away_" + c[5:]) in fs_rows.columns:
            k = c[5:]
            keep = (k.startswith(("blend_", "l3_", "inj_out_", "inj_q_", "inj_starters_out_")) or
                    k in ("rating_margin", "rating_epa", "qb_eff", "qb_log_exp", "qb_change", "qb_projected_out",
                          "qb_questionable", "qb_offseason", "rest_days", "inj_report_available"))
            if keep:
                other = fs_rows["away_" + k].astype(float).to_numpy()
                cols["dog_" + k], cols["fav_" + k] = np.where(dog_home, v, other), np.where(dog_home, other, v)
        elif c in ("ctx_week", "ctx_playoff", "ctx_div_game", "ctx_dome", "ctx_retractable", "ctx_neutral", "inj_available"):
            cols[c] = v
    hf = fs_rows["ctx_home_field"].astype(float).to_numpy() if "ctx_home_field" in fs_rows else np.ones(len(fs_rows))
    cols["ctx_dog_is_home"] = (dog_home & (hf == 1)).astype(float)
    cols["ctx_fav_is_home"] = (~dog_home & (hf == 1)).astype(float)
    if "ctx_rest_diff" in fs_rows:
        cols["dmf_rest_days"] = fs_rows["ctx_rest_diff"].astype(float).to_numpy() * s
    for side in ("home", "away"):
        for f in ("short_week", "off_bye"):
            c = f"ctx_{side}_{f}"
            if c in fs_rows:
                v = fs_rows[c].astype(float).to_numpy()
                o = fs_rows[c.replace(side, "away" if side == "home" else "home")].astype(float).to_numpy()
                if side == "home":
                    cols[f"dog_{f}"], cols[f"fav_{f}"] = np.where(dog_home, v, o), np.where(dog_home, o, v)
    p_dog = np.where(dog_home, p_home, 1 - p_home)
    cols["base_p_dog"] = p_dog
    X = pd.DataFrame(cols, index=fs_rows.index)
    return X, dog_home


def load_base(baseline: str) -> dict:
    """Frozen out-of-sample base table for one baseline."""
    from .data_pipeline import load_feature_store
    from .training import load_run
    run = load_run()
    if not run:
        raise FileNotFoundError("No Phase 1 training run found. Train models first.")
    oof, champion = run["oof"], run["selection"]["champion"]
    fs = load_feature_store()
    if baseline == "ensemble":
        p = oof[["game_id", f"p_{champion}"]].rename(columns={f"p_{champion}": "p_home"})
    else:
        p = oof[["game_id", "market_p_home_novig"]].rename(columns={"market_p_home_novig": "p_home"})
    d = oof[["game_id", "season", "week", "split", "home_win", "train_seasons"]].merge(p, on="game_id")
    d = d[d["home_win"].notna() & d["p_home"].notna() & (d["p_home"] != 0.5)]
    # residual targets must come from genuinely out-of-sample predictions
    trained_through = d["train_seasons"].str.split("-").str[1].astype(int)
    if (trained_through >= d["season"]).any():
        raise ValueError("base predictions include in-sample rows; refusing to build residual targets")
    rows = fs.set_index("game_id").loc[d["game_id"]].reset_index()
    X, dog_home = orient(rows, d["p_home"].to_numpy())
    y_dog = np.where(dog_home, d["home_win"].to_numpy(), 1 - d["home_win"].to_numpy())
    meta = d.reset_index(drop=True).assign(dog_home=dog_home, y_dog=y_dog, p_dog=X["base_p_dog"].to_numpy(),
                                           home_team=rows["home_team"].values, away_team=rows["away_team"].values)
    return {"meta": meta, "X": X.reset_index(drop=True), "baseline": baseline, "model_version": run["version"],
            "champion": champion, "feature_store_built_at": str(fs["features_built_at"].max())}


# --------------------------------------------------------------------------- statistics

def logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def screen_masks(Mask: np.ndarray, y: np.ndarray, p: np.ndarray) -> dict:
    """Vectorized residual z-scores for many boolean masks (n x K)."""
    Mf = Mask.astype(float)
    n = Mf.sum(axis=0)
    resid = Mf.T @ (y - p)
    var = Mf.T @ (p * (1 - p))
    z = np.divide(resid, np.sqrt(var), out=np.zeros_like(resid), where=var > 0)
    return {"n": n, "obs": np.divide(Mf.T @ y, n, out=np.full_like(n, np.nan), where=n > 0),
            "exp": np.divide(Mf.T @ p, n, out=np.full_like(n, np.nan), where=n > 0), "z": z}


def offset_effect(x: np.ndarray, y: np.ndarray, p: np.ndarray, iters: int = 25) -> tuple[float, float]:
    """MLE of beta in logit(P) = logit(p) + beta*x (x indicator or standardized score), with SE."""
    ok = ~np.isnan(x)
    x, y, off = x[ok], y[ok], logit(p[ok])
    if len(x) == 0 or np.all(x == 0):
        return np.nan, np.nan
    b = 0.0
    for _ in range(iters):
        q = sigmoid(off + b * x)
        g = np.sum(x * (y - q))
        h = np.sum(x * x * q * (1 - q))
        if h <= 0:
            break
        step = g / h
        b += np.clip(step, -2, 2)
        if abs(step) < 1e-8:
            break
    q = sigmoid(off + b * x)
    h = np.sum(x * x * q * (1 - q))
    return float(b), float(1 / np.sqrt(h)) if h > 0 else np.nan


def bh_qvalues(pv: np.ndarray) -> np.ndarray:
    pv = np.asarray(pv, float)
    n = len(pv)
    order = np.argsort(pv)
    q = np.empty(n)
    q[order] = np.minimum.accumulate((pv[order] * n / np.arange(1, n + 1))[::-1])[::-1]
    return np.minimum(q, 1.0)


def holm(pv: np.ndarray) -> np.ndarray:
    pv = np.asarray(pv, float)
    n = len(pv)
    order = np.argsort(pv)
    adj = np.empty(n)
    adj[order] = np.minimum(np.maximum.accumulate(pv[order] * (n - np.arange(n))), 1.0)
    return adj


def fit_offset_ridge(X: np.ndarray, y: np.ndarray, off: np.ndarray, l2: float, iters: int = 50) -> np.ndarray:
    """Ridge-penalized logistic regression with a fixed offset (no intercept)."""
    if X.shape[1] == 0:
        return np.zeros(0)
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        q = sigmoid(off + X @ b)
        g = X.T @ (y - q) - l2 * b
        H = (X * (q * (1 - q))[:, None]).T @ X + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        b += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return b


# --------------------------------------------------------------------------- candidates

@dataclass
class Candidate:
    cid: str
    method: str
    kind: str                 # "mask" or "score"
    spec: dict
    features: list
    description: str
    disc: dict = field(default_factory=dict)


def humanize(f: str) -> str:
    if f == "base_p_dog":
        return "baseline underdog win probability"
    if f.startswith("ctx_"):
        return {"ctx_dog_is_home": "underdog is the home team", "ctx_fav_is_home": "favorite is the home team",
                "ctx_week": "week of season", "ctx_playoff": "playoff game", "ctx_div_game": "divisional game",
                "ctx_dome": "dome stadium", "ctx_retractable": "retractable-roof stadium", "ctx_neutral": "neutral site"}.get(f, f)
    if f == "inj_available":
        return "verified injury report available"
    side = {"dmf": "underdog minus favorite", "dog": "underdog", "fav": "favorite"}.get(f.split("_", 1)[0])
    rest = f.split("_", 1)[1] if side else f
    win = rest.split("_", 1)[0]
    if win in WINDOW_LABELS:
        stat = rest.split("_", 1)[1]
        defense = stat.startswith("d_")
        stat = stat[2:] if defense else stat
        if defense and stat == "sack_rate":
            label = f"{WINDOW_LABELS[win]} defensive sack rate (pass rush)"
        else:
            label = f"{WINDOW_LABELS[win]} {STAT_LABELS.get(stat, stat).replace(' allowed', '')}{' allowed' if defense else ''}"
    elif rest.startswith("inj_"):
        parts = rest.split("_")
        kind = {"out": "out/doubtful snap share", "q": "questionable snap share", "starters": "starters out"}.get(parts[1], parts[1])
        label = f"{parts[-1]} injuries ({kind})" if parts[1] in ("out", "q", "starters") else rest.replace("_", " ")
    elif rest.startswith("off_vs_def_"):
        label = f"own offense vs opponent defense, {STAT_LABELS.get(rest[11:], rest[11:])}"
    else:
        label = STAT_LABELS.get(rest, rest.replace("_", " "))
    return f"{side}: {label}" if side else label


def describe_conditions(conds) -> str:
    return " AND ".join(f"{humanize(f)} {'<=' if op == 'le' else '>'} {t:.4g}" for f, op, t in conds)


def eval_mask(spec: dict, X: pd.DataFrame, models: dict) -> np.ndarray:
    """Float array: 1/0 where evaluable, NaN where a required feature is missing."""
    t = spec["type"]
    if t == "conds":
        out = np.ones(len(X))
        miss = np.zeros(len(X), bool)
        for f, op, thr in spec["conds"]:
            v = X[f].to_numpy(float)
            miss |= np.isnan(v)
            out *= (v <= thr) if op == "le" else (v > thr)
        out = out.astype(float)
        out[miss] = np.nan
        return out
    if t == "cluster":
        km, mu, sd, feats = models["kmeans"]
        Z = ((X[feats].to_numpy(float) - mu) / sd)
        miss = np.isnan(Z).mean(axis=1) > 0.5
        lab = km.predict(np.nan_to_num(Z))
        out = (lab == spec["k"]).astype(float)
        out[miss] = np.nan
        return out
    if t == "anomaly":
        iso, mu, sd, feats, thr = models["iso"]
        Z = np.nan_to_num((X[feats].to_numpy(float) - mu) / sd)
        return (iso.score_samples(Z) <= thr).astype(float)
    raise KeyError(t)


def eval_score(spec: dict, X: pd.DataFrame, models: dict) -> np.ndarray:
    """Standardized continuous score (discovery mean 0, sd 1); NaN when inputs missing."""
    t = spec["type"]
    if t == "expr":
        a = X[spec["a"]].to_numpy(float)
        b = X[spec["b"]].to_numpy(float) if spec.get("b") else None
        op = spec["op"]
        if op == "sum":
            v = a + b
        elif op == "diff":
            v = a - b
        elif op == "prod":
            v = a * b
        elif op == "ratio":
            v = a / (np.abs(b) + spec["eps"])
        elif op == "square":
            v = a * a
        elif op == "abs":
            v = np.abs(a)
        elif op == "slog":
            v = np.sign(a) * np.log1p(np.abs(a))
        else:
            raise KeyError(op)
    elif t == "gbm":
        g, feats = models["gbm"]
        v = gbm_margin(g, X, feats)
    else:
        raise KeyError(t)
    return (v - spec["mu"]) / spec["sd"]


def candidate_values(c: Candidate, X: pd.DataFrame, models: dict) -> np.ndarray:
    return eval_mask(c.spec, X, models) if c.kind == "mask" else eval_score(c.spec, X, models)


# --------------------------------------------------------------------------- discovery methods

def _thresholds(v, qs):
    v = v[~np.isnan(v)]
    if len(np.unique(v)) <= 2:
        return [0.5] if set(np.unique(v)) <= {0.0, 1.0} else []
    return sorted(set(np.round(np.quantile(v, qs), 8)))


def gen_univariate(X, cfg) -> list[Candidate]:
    out = []
    for f in X.columns:
        for t in _thresholds(X[f].to_numpy(float), cfg["quantiles"]):
            for op in ("le", "gt"):
                conds = [(f, op, float(t))]
                out.append(Candidate(f"uni:{f}:{op}:{t:.6g}", "subgroup_univariate", "mask", {"type": "conds", "conds": conds},
                                     [f], describe_conditions(conds)))
    return out


def gen_pairs(X, feats, cfg, method="subgroup_pairs") -> list[Candidate]:
    out = []
    for a, b in itertools.combinations(feats, 2):
        ta, tb = _thresholds(X[a].to_numpy(float), cfg["pair_quantiles"]), _thresholds(X[b].to_numpy(float), cfg["pair_quantiles"])
        for t1, t2 in itertools.product(ta, tb):
            for o1, o2 in itertools.product(("le", "gt"), repeat=2):
                conds = [(a, o1, float(t1)), (b, o2, float(t2))]
                out.append(Candidate(f"{method}:{a}:{o1}:{t1:.6g}|{b}:{o2}:{t2:.6g}", method, "mask",
                                     {"type": "conds", "conds": conds}, [a, b], describe_conditions(conds)))
    return out


def gen_calibration(X, cfg) -> list[Candidate]:
    out = []
    edges = [0.0, 0.2, 0.3, 0.4, 0.5]
    binary = [c for c in X.columns if set(np.unique(X[c].dropna())) <= {0.0, 1.0} and X[c].notna().mean() > 0.5]
    for lo, hi in zip(edges[:-1], edges[1:]):
        base = [("base_p_dog", "gt", lo), ("base_p_dog", "le", hi)]
        out.append(Candidate(f"cal:{lo}-{hi}", "miscalibration", "mask", {"type": "conds", "conds": base}, ["base_p_dog"],
                             f"baseline underdog probability in ({lo:.0%}, {hi:.0%}]"))
        for f in binary:
            for val, op in ((1, "gt"), (0, "le")):
                conds = base + [(f, op, 0.5)]
                out.append(Candidate(f"cal:{lo}-{hi}|{f}={val}", "miscalibration", "mask", {"type": "conds", "conds": conds},
                                     ["base_p_dog", f], f"baseline underdog probability in ({lo:.0%}, {hi:.0%}] AND "
                                                        f"{'' if val else 'NOT '}{humanize(f)}"))
    return out


def gen_rules(X, y, p, cfg, rng) -> list[Candidate]:
    """RuleFit-style: conjunction rules read off shallow trees fit to residuals."""
    feats = [c for c in X.columns if c != "base_p_dog"]
    Xi = X[feats].to_numpy(float)
    med = np.nanmedian(Xi, axis=0)
    Xf = np.where(np.isnan(Xi), med, Xi)
    r = y - p
    seen, out = set(), []
    for k in range(cfg["rule_trees"]):
        idx = rng.choice(len(r), len(r), replace=True)
        cols = rng.choice(len(feats), max(5, int(0.3 * len(feats))), replace=False)
        t = DecisionTreeRegressor(max_depth=3, min_samples_leaf=cfg["min_n_discovery"], random_state=int(rng.integers(1e9)))
        t.fit(Xf[idx][:, cols], r[idx])
        tr = t.tree_
        stack = [(0, [])]
        while stack:
            node, path = stack.pop()
            if path:
                key = tuple(sorted(path))
                if key not in seen:
                    seen.add(key)
                    conds = [(f, op, thr) for f, op, thr in path]
                    out.append(Candidate("rule:" + "|".join(f"{f}:{o}:{v:.6g}" for f, o, v in key), "tree_rules", "mask",
                                         {"type": "conds", "conds": conds}, sorted({c[0] for c in conds}), describe_conditions(conds)))
            if tr.children_left[node] != -1:
                f = feats[cols[tr.feature[node]]]
                thr = float(tr.threshold[node])
                stack.append((tr.children_left[node], path + [(f, "le", thr)]))
                stack.append((tr.children_right[node], path + [(f, "gt", thr)]))
    return out


def gen_symbolic(X, feats, cfg) -> list[Candidate]:
    out = []
    def add(spec, desc, used):
        out.append(Candidate("expr:" + ":".join(str(spec.get(k)) for k in ("op", "a", "b")), "symbolic", "score", spec, used, desc))
    for a in feats:
        for op, d in (("square", f"({humanize(a)})^2"), ("abs", f"|{humanize(a)}|"), ("slog", f"signed log(1+|{humanize(a)}|)")):
            add({"type": "expr", "op": op, "a": a}, d, [a])
    for a, b in itertools.combinations(feats, 2):
        for op, sym in (("sum", "+"), ("diff", "-"), ("prod", "x")):
            add({"type": "expr", "op": op, "a": a, "b": b}, f"({humanize(a)}) {sym} ({humanize(b)})", [a, b])
        eps = float(np.nanstd(X[b]) * 0.1 + 1e-9)
        add({"type": "expr", "op": "ratio", "a": a, "b": b, "eps": eps}, f"({humanize(a)}) / |{humanize(b)}|", [a, b])
    return out


def fit_regimes(X, feats, cfg, seed) -> tuple[dict, list[Candidate]]:
    Z = X[feats].to_numpy(float)
    mu, sd = np.nanmean(Z, axis=0), np.nanstd(Z, axis=0) + 1e-9
    Zs = np.nan_to_num((Z - mu) / sd)
    km = KMeans(n_clusters=cfg["n_clusters"], n_init=10, random_state=seed).fit(Zs)
    iso = IsolationForest(n_estimators=200, random_state=seed).fit(Zs)
    thr = float(np.quantile(iso.score_samples(Zs), 0.1))
    models = {"kmeans": (km, mu, sd, feats), "iso": (iso, mu, sd, feats, thr)}
    cands = []
    for k in range(cfg["n_clusters"]):
        centre = km.cluster_centers_[k]
        top = np.argsort(-np.abs(centre))[:3]
        desc = "regime: " + ", ".join(f"{humanize(feats[j])} {'high' if centre[j] > 0 else 'low'} ({centre[j]:+.1f} sd)" for j in top)
        cands.append(Candidate(f"cluster:{k}", "clustering", "mask", {"type": "cluster", "k": k}, list(feats), desc))
    cands.append(Candidate("anomaly:top10", "anomaly", "mask", {"type": "anomaly"}, list(feats),
                           "most unusual 10% of matchup profiles (isolation forest)"))
    return models, cands


def fit_gbm(X, y, p, feats, seed, n_rounds: int | None = None, inner_last_season: np.ndarray | None = None):
    """Gradient-boosted residual model with the baseline as fixed offset."""
    params = {"objective": "binary:logistic", "max_depth": 2, "eta": 0.03, "min_child_weight": 20, "subsample": 0.8,
              "colsample_bytree": 0.7, "lambda": 10.0, "seed": seed, "nthread": 8}
    Xa = X[feats].to_numpy(float)
    if n_rounds is None:
        tr, va = ~inner_last_season, inner_last_season
        dtr = xgboost.DMatrix(Xa[tr], label=y[tr], base_margin=logit(p[tr]))
        dva = xgboost.DMatrix(Xa[va], label=y[va], base_margin=logit(p[va]))
        b = xgboost.train(params, dtr, 400, evals=[(dva, "va")], early_stopping_rounds=40, verbose_eval=False)
        n_rounds = max(int(b.best_iteration) + 1, 1)
    d = xgboost.DMatrix(Xa, label=y, base_margin=logit(p))
    return xgboost.train(params, d, n_rounds), n_rounds


def gbm_margin(g, X, feats) -> np.ndarray:
    """Learned residual log-odds f(x) (prediction without the offset)."""
    return g.predict(xgboost.DMatrix(X[feats].to_numpy(float)), output_margin=True)


# --------------------------------------------------------------------------- one origin

def _split(meta, rng_):
    return ((meta["season"] >= rng_[0]) & (meta["season"] <= rng_[1])).to_numpy()


def _dedup(cands, vals, z, cfg):
    kept, kept_vals = [], []
    for i in np.argsort(-np.abs(z)):
        v = vals[i]
        dup = False
        for kv in kept_vals:
            if cands[i].kind == "mask":
                a, b = np.nan_to_num(v) > 0, np.nan_to_num(kv) > 0
                if kv.dtype == v.dtype and (a | b).sum() and (a & b).sum() / (a | b).sum() > cfg["dedup_jaccard"]:
                    dup = True
                    break
            else:
                ok = ~np.isnan(v) & ~np.isnan(kv)
                if ok.sum() > 10 and abs(np.corrcoef(v[ok], kv[ok])[0, 1]) > cfg["dedup_corr"]:
                    dup = True
                    break
        if not dup:
            kept.append(i)
            kept_vals.append(v)
        if len(kept) >= cfg["carry_top_k"]:
            break
    return kept


def run_origin(base: dict, origin: dict, cfg: dict, progress=print) -> dict:
    t0 = time.time()
    rng = np.random.default_rng(cfg["seed"])
    meta, X = base["meta"], base["X"]
    y, p = meta["y_dog"].to_numpy(float), meta["p_dog"].to_numpy(float)
    D = _split(meta, origin["discovery"])
    if not origin.get("discovery_only"):
        V, E = _split(meta, origin["validation"]), _split(meta, origin["evaluation"])
        assert not (D & V).any() and not (V & E).any() and not (D & E).any()
        assert meta.loc[D, "season"].max() < meta.loc[V, "season"].min() <= meta.loc[V, "season"].max() < meta.loc[E, "season"].min()
    XD, yD, pD = X[D].reset_index(drop=True), y[D], p[D]
    feats_all = [c for c in X.columns if X.loc[D, c].notna().mean() > 0.5 and X.loc[D, c].nunique() > 1]
    XD = XD[feats_all]
    progress(f"  [{origin['name']}] discovery {origin['discovery']} n={D.sum()}, {len(feats_all)} candidate input features")

    # univariate screening (also used to choose features for pair / symbolic / GBM searches)
    cands = gen_univariate(XD, cfg)
    cont_z = {}
    for f in feats_all:
        v = XD[f].to_numpy(float)
        ok = ~np.isnan(v)
        if ok.sum() > 50 and np.nanstd(v) > 0:
            b, se = offset_effect((v - np.nanmean(v)) / np.nanstd(v), yD, pD)
            cont_z[f] = abs(b / se) if se and not np.isnan(se) else 0.0
    ranked = sorted(cont_z, key=cont_z.get, reverse=True)
    def top_uncorrelated(k):
        sel = []
        for f in ranked:
            if f == "base_p_dog":
                continue
            v = XD[f].to_numpy(float)
            if all(abs(pd.Series(v).corr(pd.Series(XD[g].to_numpy(float)))) < 0.8 for g in sel):
                sel.append(f)
            if len(sel) >= k:
                break
        return sel
    pair_feats = top_uncorrelated(cfg["pair_top_features"])
    cands += gen_pairs(XD, pair_feats, cfg)
    cands += gen_calibration(XD, cfg)
    cands += gen_rules(XD, yD, pD, cfg, rng)
    sym_feats = top_uncorrelated(cfg["symbolic_top_features"])
    sym = gen_symbolic(XD, sym_feats, cfg)
    regime_feats = top_uncorrelated(40)
    models, reg_cands = fit_regimes(XD, regime_feats, cfg, cfg["seed"])
    cands += reg_cands
    # GBM residual model (inner early stopping on the last discovery season only)
    gbm_feats = [f for f in ranked if f != "base_p_dog"][: cfg["gbm_top_features"]] + ["base_p_dog"]
    last = (meta.loc[D, "season"] == origin["discovery"][1]).to_numpy()
    gD, n_rounds = fit_gbm(XD, yD, pD, gbm_feats, cfg["seed"], inner_last_season=last)
    models["gbm"] = (gD, gbm_feats)
    inter = gD.predict(xgboost.DMatrix(XD[gbm_feats].to_numpy(float), base_margin=logit(pD)), pred_interactions=True)
    strength = np.abs(inter[:, :-1, :-1]).mean(axis=0)
    np.fill_diagonal(strength, 0)
    pairs = sorted(((strength[i, j], gbm_feats[i], gbm_feats[j]) for i in range(len(gbm_feats)) for j in range(i + 1, len(gbm_feats))),
                   reverse=True)[:12]
    interactions = pd.DataFrame([{"feature_a": a, "feature_b": b, "mean_abs_shap_interaction": float(s),
                                  "description": f"{humanize(a)} x {humanize(b)}"} for s, a, b in pairs])
    for _, a, b in pairs:
        cands += gen_pairs(XD, [a, b], cfg, method="gbm_interaction")
    gm = gbm_margin(gD, XD, gbm_feats)
    gbm_spec = {"type": "gbm", "mu": float(np.mean(gm)), "sd": float(np.std(gm) + 1e-9)}
    sym.append(Candidate("gbm:residual_score", "gbm_residual", "score", gbm_spec, gbm_feats,
                         f"gradient-boosted residual score ({n_rounds} trees, depth 2) over {len(gbm_feats)} features"))
    # standardize symbolic scores on discovery
    for c in sym:
        if c.spec["type"] == "expr":
            c.spec["mu"], c.spec["sd"] = 0.0, 1.0
            raw = eval_score(c.spec, XD, models)
            c.spec["mu"], c.spec["sd"] = float(np.nanmean(raw)), float(np.nanstd(raw) + 1e-12)

    # ---- discovery screening
    mask_c = [c for c in cands if c.kind == "mask"]
    seen, uniq = set(), []
    for c in mask_c:
        if c.cid not in seen:
            seen.add(c.cid)
            uniq.append(c)
    mask_c = uniq
    MV = np.column_stack([eval_mask(c.spec, XD, models) for c in mask_c])
    sc = screen_masks(np.nan_to_num(MV) > 0, yD, pD)
    for i, c in enumerate(mask_c):
        c.disc = {"n": int(sc["n"][i]), "obs": float(sc["obs"][i]), "exp": float(sc["exp"][i]), "z": float(sc["z"][i])}
    for c in sym:
        v = eval_score(c.spec, XD, models)
        b, se = offset_effect(v, yD, pD)
        c.disc = {"n": int((~np.isnan(v)).sum()), "obs": np.nan, "exp": np.nan,
                  "z": float(b / se) if se and not np.isnan(se) else 0.0, "beta": b, "se": se}
    allc = mask_c + sym
    zs = np.array([c.disc["z"] for c in allc])
    ns = np.array([c.disc["n"] for c in allc])
    pv = 2 * stats.norm.sf(np.abs(zs))
    elig = ns >= cfg["min_n_discovery"]
    q = np.ones(len(allc))
    q[elig] = bh_qvalues(pv[elig])
    for c, pv_, q_ in zip(allc, pv, q):
        c.disc |= {"p": float(pv_), "q_bh": float(q_), "eligible": bool(c.disc["n"] >= cfg["min_n_discovery"])}
    # empirical-Bayes prior for shrinkage: spread of indicator effects beyond sampling noise
    betas, ses = [], []
    eligible_idx = np.flatnonzero(elig)
    carry_pool = eligible_idx[np.argsort(-np.abs(zs[eligible_idx]))][: cfg["carry_top_k"] * 20]
    for i in carry_pool:
        c = allc[i]
        x = eval_mask(c.spec, XD, models) if c.kind == "mask" else eval_score(c.spec, XD, models)
        b, se = offset_effect(x, yD, pD)
        c.disc |= {"beta": b, "se": se}
        if not np.isnan(b):
            betas.append(b)
            ses.append(se)
    tau2 = max(float(np.var(betas) - np.mean(np.square(ses))), 1e-4) if betas else 1e-4
    pool_vals = [candidate_values(allc[i], XD, models) for i in carry_pool]
    keep = _dedup([allc[i] for i in carry_pool], pool_vals, zs[carry_pool], cfg)
    carried = [allc[carry_pool[i]] for i in keep]
    progress(f"  [{origin['name']}] tested {len(allc)} candidates; {int((q < cfg['fdr_q']).sum())} pass BH q<{cfg['fdr_q']} "
             f"in discovery; carrying top {len(carried)} de-duplicated to validation")

    if origin.get("discovery_only"):
        return {"origin": origin, "candidates": allc, "carried": carried, "models": models, "n_tested": len(allc),
                "features": feats_all, "tau2": tau2}
    # ---- validation (independent seasons)
    XV, yV, pV = X[V].reset_index(drop=True), y[V], p[V]
    sv = meta.loc[V, "season"].to_numpy()
    val_p = []
    for c in carried:
        x = candidate_values(c, XV, models)
        b, se = offset_effect(x, yV, pV)
        ok = ~np.isnan(x)
        n = int((x[ok] > 0).sum()) if c.kind == "mask" else int(ok.sum())
        z = b / se if se and not np.isnan(se) else 0.0
        seas = []
        for s in np.unique(sv):
            m = sv == s
            bs, ses_ = offset_effect(x[m], yV[m], pV[m])
            if not np.isnan(bs):
                seas.append(np.sign(bs) == np.sign(c.disc["beta"]))
        pval = 2 * stats.norm.sf(abs(z)) if not np.isnan(z) else 1.0
        same_sign = bool(np.sign(b) == np.sign(c.disc["beta"])) if not np.isnan(b) else False
        mask_obs = float(yV[ok][x[ok] > 0].mean()) if c.kind == "mask" and n else np.nan
        mask_exp = float(pV[ok][x[ok] > 0].mean()) if c.kind == "mask" and n else np.nan
        c.val = {"n": n, "beta": float(b) if not np.isnan(b) else np.nan, "se": float(se) if se else np.nan, "z": float(z),
                 "p": float(pval), "same_sign": same_sign, "season_sign_share": float(np.mean(seas)) if seas else 0.0,
                 "obs": mask_obs, "exp": mask_exp,
                 "beta_shrunk": float(b * tau2 / (tau2 + se ** 2)) if se and not np.isnan(b) else 0.0}
        val_p.append(pval)
    adj = holm(np.array(val_p)) if val_p else np.array([])
    validated = []
    for c, a in zip(carried, adj):
        reasons = []
        if c.val["n"] < cfg["min_n_validation"]:
            reasons.append(f"only {c.val['n']} validation games")
        if not c.val["same_sign"]:
            reasons.append("effect reversed in validation")
        if a >= cfg["validation_alpha"]:
            reasons.append(f"not significant after Holm correction (adj p={a:.3f})")
        if c.val["season_sign_share"] < cfg["min_season_sign_share"]:
            reasons.append("unstable across validation seasons")
        c.val["p_holm"] = float(a)
        c.status = "validated" if not reasons else "rejected"
        c.reasons = reasons
        if not reasons:
            validated.append(c)
    progress(f"  [{origin['name']}] validated {len(validated)} of {len(carried)} carried candidates")

    # ---- correction layers (fit on discovery+validation, evaluated on untouched evaluation seasons)
    DV = D | V
    XDV, yDV, pDV = X[DV].reset_index(drop=True), y[DV], p[DV]
    layers = {}
    if validated:
        Zdv = np.column_stack([np.nan_to_num(candidate_values(c, XDV, models)) for c in validated])
        beta = fit_offset_ridge(Zdv, yDV, logit(pDV), cfg["adjuster_l2"])
    else:
        beta = np.zeros(0)
    layers["validated_patterns"] = {"candidates": [c.cid for c in validated], "beta": beta.tolist()}
    # GBM adjuster: shrink factor chosen on validation using the discovery-only model
    fV = gbm_margin(gD, XV, gbm_feats)
    lam_scores = {lam: M.log_loss(yV, sigmoid(logit(pV) + lam * fV)) for lam in cfg["gbm_shrink_grid"]}
    lam = min(lam_scores, key=lam_scores.get)
    gDV, _ = fit_gbm(XDV, yDV, pDV, gbm_feats, cfg["seed"], n_rounds=n_rounds)
    layers["gbm_residual"] = {"lambda": lam, "validation_log_loss_by_lambda": lam_scores, "n_rounds": n_rounds}
    models["gbm_final"] = (gDV, gbm_feats)

    def adjust(Xn, pn, which):
        if which == "validated_patterns":
            if not validated:
                return pn.copy()
            Z = np.column_stack([np.nan_to_num(candidate_values(c, Xn, models)) for c in validated])
            return sigmoid(logit(pn) + Z @ beta)
        return sigmoid(logit(pn) + lam * gbm_margin(gDV, Xn, gbm_feats))

    evals = {}
    for name, rng_ in (("evaluation", origin["evaluation"]), ("diagnostic_2025", cfg["diagnostic"])):
        m = _split(meta, rng_)
        if not m.any():
            continue
        Xn, yn, pn = X[m].reset_index(drop=True), y[m], p[m]
        res = {"seasons": rng_, "n": int(m.sum()), "baseline": M.prob_summary(yn, pn)}
        for which in ("validated_patterns", "gbm_residual"):
            pa = adjust(Xn, pn, which)
            d = _paired(yn, pn, pa)
            res[which] = M.prob_summary(yn, pa) | {"delta_log_loss": d["delta"], "delta_ci": d["ci"],
                                                   "delta_brier": float(M.brier(yn, pa) - M.brier(yn, pn)),
                                                   "mean_abs_adjustment": float(np.mean(np.abs(pa - pn)))}
        evals[name] = res
    progress(f"  [{origin['name']}] done in {time.time() - t0:.0f}s")
    return {"origin": origin, "candidates": allc, "carried": carried, "validated": validated, "models": models,
            "layers": layers, "beta": beta, "evals": evals, "interactions": interactions, "tau2": tau2,
            "n_tested": len(allc), "n_bh": int((q < cfg["fdr_q"]).sum()), "features": feats_all,
            "method_counts": pd.Series([c.method for c in allc]).value_counts().to_dict(), "adjust": adjust}


def _paired(y, pa, pb, n_boot=2000, seed=0):
    def ll(p):
        p = np.clip(p, EPS, 1 - EPS)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p))
    d = ll(pb) - ll(pa)
    idx = np.random.default_rng(seed).integers(0, len(d), (n_boot, len(d)))
    b = d[idx].mean(axis=1)
    return {"delta": float(d.mean()), "ci": (float(np.quantile(b, .025)), float(np.quantile(b, .975)))}


# --------------------------------------------------------------------------- catalog & experiment

def catalog_frame(res: dict, base: dict) -> pd.DataFrame:
    meta, X = base["meta"], base["X"]
    rows = []
    carried_ids = {c.cid for c in res["carried"]}
    D = _split(meta, res["origin"]["discovery"])
    V = _split(meta, res["origin"]["validation"])
    ss = meta["season"].to_numpy()
    for c in res["candidates"]:
        if c.cid not in carried_ids and not (c.disc.get("q_bh", 1) < 0.5):
            continue
        r = {"candidate_id": c.cid, "method": c.method, "kind": c.kind, "description": c.description,
             "expression": json.dumps(c.spec, default=str) if c.spec["type"] != "gbm" else "xgboost residual model (see artifacts)",
             "features": ", ".join(c.features[:6]) + (" ..." if len(c.features) > 6 else ""),
             "provenance": provenance(c.features), "disc_n": c.disc["n"], "disc_underdog_win_rate": c.disc.get("obs"),
             "disc_favorite_win_rate": 1 - c.disc["obs"] if c.kind == "mask" else np.nan,
             "disc_baseline_underdog_prob": c.disc.get("exp"), "disc_residual": (c.disc.get("obs") or np.nan) - (c.disc.get("exp") or np.nan),
             "disc_z": c.disc["z"], "disc_p_nominal": c.disc.get("p"), "disc_q_bh_nominal": c.disc.get("q_bh"), "disc_logodds_effect": c.disc.get("beta"),
             "carried_to_validation": c.cid in carried_ids}
        if c.cid in carried_ids:
            v = c.val
            r |= {"val_n": v["n"], "val_underdog_win_rate": v["obs"], "val_baseline_underdog_prob": v["exp"],
                  "val_logodds_effect": v["beta"], "val_effect_ci_low": v["beta"] - 1.96 * v["se"], "val_effect_ci_high": v["beta"] + 1.96 * v["se"],
                  "val_effect_shrunk": v["beta_shrunk"], "val_p": v["p"], "val_p_holm": v["p_holm"],
                  "val_season_sign_share": v["season_sign_share"], "status": c.status, "rejection_reasons": "; ".join(c.reasons)}
            x = candidate_values(c, X, res["models"])
            stab = []
            for s in np.unique(ss[D | V]):
                m = ss == s
                b, se = offset_effect(x[m], meta["y_dog"].to_numpy(float)[m], meta["p_dog"].to_numpy(float)[m])
                stab.append(f"{s}:{b:+.2f}" if not np.isnan(b) else f"{s}:n/a")
            r["season_effects"] = " ".join(stab)
        else:
            r["status"] = "exploratory (not carried)"
        rows.append(r)
    df = pd.DataFrame(rows)
    order = {"validated": 0, "rejected": 1, "exploratory (not carried)": 2}
    df["_o"] = df["status"].map(order)
    df["_rank"] = -df.get("val_effect_shrunk", pd.Series(0, index=df.index)).abs().fillna(0) - df["disc_z"].abs() * 1e-3
    return df.sort_values(["_o", "_rank"]).drop(columns=["_o", "_rank"]).reset_index(drop=True)


def provenance(features) -> str:
    srcs = set()
    for f in features:
        if "inj" in f:
            srcs.add("official injury report (verified pre-kickoff) + snap counts")
        elif "qb" in f:
            srcs.add("pbp QB EPA + projected starter rule")
        elif f == "base_p_dog":
            srcs.add("baseline probability")
        elif f.startswith("ctx_") or "rest" in f:
            srcs.add("schedule")
        else:
            srcs.add("nflverse play-by-play")
    return "; ".join(sorted(srcs))


def run_experiment(cfg: dict | None = None, progress=print, base_loader=load_base, out_dir=None) -> dict:
    """Run discovery for every baseline and origin; write immutable artifacts.
    Note: discovery-stage p/q values are NOMINAL. Rules and pairs are searched adaptively on the
    same discovery games, so only the independent validation test (Holm) is a valid significance test."""
    user_cfg = cfg or {}
    cfg = {**DEFAULT_CONFIG, **user_cfg}
    # Every experiment re-uses the same validation seasons. Count the looks and divide the
    # validation alpha so repeated mining is not treated as new independent evidence.
    base_dir = out_dir or DISCOVERY_DIR
    looks = 1 + sum(1 for d in base_dir.glob("d*") if (d / "summary.json").exists())
    if "validation_alpha" not in user_cfg:
        cfg["validation_alpha"] = DEFAULT_CONFIG["validation_alpha"] / looks
    cfg["validation_look"] = looks
    t0 = time.time()
    exp_id = datetime.now(timezone.utc).strftime("d%Y%m%d_%H%M%S")
    out = (out_dir or DISCOVERY_DIR) / exp_id
    out.mkdir(parents=True, exist_ok=False)
    summary = {"experiment": exp_id, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "config": cfg,
               "baselines": {}}
    bundle = {}
    for bl in cfg["baselines"]:
        progress(f"Baseline: {bl}")
        base = base_loader(bl)
        base["meta"].to_parquet(out / f"input_meta_{bl}.parquet", index=False)
        base["X"].to_parquet(out / f"input_features_{bl}.parquet", index=False)
        info = {"model_version": base.get("model_version"), "champion": base.get("champion"),
                "feature_store_built_at": base.get("feature_store_built_at"), "rows": int(len(base["meta"])),
                "input_hash": _hash_df(base["meta"][["game_id", "p_dog", "y_dog"]]) + "/" + _hash_df(base["X"]),
                "origins": {}}
        for origin in cfg["origins"]:
            res = run_origin(base, origin, cfg, progress)
            cat = catalog_frame(res, base)
            cat.to_csv(out / f"catalog_{bl}_{origin['name']}.csv", index=False)
            res["interactions"].to_csv(out / f"interactions_{bl}_{origin['name']}.csv", index=False)
            historical_matches(res, base).to_csv(out / f"matches_{bl}_{origin['name']}.csv", index=False)
            info["origins"][origin["name"]] = {
                "n_tested": res["n_tested"], "n_pass_bh_discovery": res["n_bh"], "n_carried": len(res["carried"]),
                "n_validated": len(res["validated"]), "validated": [c.description for c in res["validated"]],
                "method_counts": res["method_counts"], "layers": res["layers"], "evals": res["evals"], "tau2": res["tau2"],
                "n_features": len(res["features"])}
            bundle[(bl, origin["name"])] = {"models": res["models"], "validated": res["validated"], "beta": res["beta"],
                                            "lambda": res["layers"]["gbm_residual"]["lambda"], "carried": res["carried"]}
        info["verdict"] = verdict(info)
        summary["baselines"][bl] = info
        calibration_table(base).to_csv(out / f"calibration_{bl}.csv", index=False)
    summary["minutes"] = round((time.time() - t0) / 60, 1)
    joblib.dump(bundle, out / "adjusters.joblib")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=_json_default), encoding="utf-8")
    for f in out.iterdir():
        f.chmod(0o444)
    if out_dir is None:
        CURRENT.write_text(json.dumps({"experiment": exp_id}), encoding="utf-8")
    progress(f"Experiment {exp_id} finished in {summary['minutes']} min.")
    return {"summary": summary, "dir": out, "bundle": bundle}


def historical_matches(res: dict, base: dict, top: int = 5) -> pd.DataFrame:
    """Games matching validated patterns and the top carried mask patterns (all periods)."""
    meta, X = base["meta"], base["X"]
    rows = []
    vids = {c.cid for c in res["validated"]}
    picks = res["validated"] + [c for c in res["carried"] if c.cid not in vids and c.kind == "mask"][:top]
    for c in picks:
        if c.kind != "mask":
            continue
        v = candidate_values(c, X, res["models"])
        for i in np.flatnonzero(np.nan_to_num(v) > 0):
            r = meta.iloc[i]
            period = next((k for k in ("discovery", "validation", "evaluation")
                           if res["origin"][k][0] <= r["season"] <= res["origin"][k][1]), "diagnostic/other")
            rows.append({"pattern": c.description, "status": getattr(c, "status", ""), "season": int(r["season"]),
                         "week": int(r["week"]), "game_id": r["game_id"],
                         "underdog": r["home_team"] if r["dog_home"] else r["away_team"],
                         "baseline_underdog_prob": float(r["p_dog"]), "underdog_won": int(r["y_dog"]), "period": period})
    return pd.DataFrame(rows)


def calibration_table(base: dict) -> pd.DataFrame:
    meta = base["meta"]
    t = meta.assign(bucket=pd.cut(meta["p_dog"], [0, .2, .3, .4, .5])).groupby(["season", "bucket"], observed=True).agg(
        n=("y_dog", "size"), expected=("p_dog", "mean"), observed=("y_dog", "mean")).reset_index()
    t["bucket"] = t["bucket"].astype(str)
    return t


def verdict(info: dict) -> dict:
    """Pre-declared rule: an adjustment is 'demonstrated' only if it lowers log loss on the
    evaluation season of BOTH origins with the primary origin's 95% CI below zero."""
    out = {}
    for layer in ("validated_patterns", "gbm_residual"):
        ev = [info["origins"][o]["evals"].get("evaluation", {}).get(layer, {}) for o in info["origins"]]
        prim = info["origins"].get("primary", {}).get("evals", {}).get("evaluation", {}).get(layer, {})
        ok = (all(e.get("delta_log_loss", 1) < 0 for e in ev) and prim.get("delta_ci", (1, 1))[1] < 0
              and prim.get("mean_abs_adjustment", 0) > 0)
        out[layer] = "demonstrated out-of-sample improvement" if ok else "not demonstrated (experimental only)"
    return out


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, tuple):
        return list(o)
    return str(o)


# --------------------------------------------------------------------------- loading & upcoming games

def current_experiment() -> str | None:
    return json.loads(CURRENT.read_text())["experiment"] if CURRENT.exists() else None


def load_experiment(exp: str | None = None) -> dict:
    exp = exp or current_experiment()
    if not exp:
        return {}
    d = DISCOVERY_DIR / exp
    out = {"experiment": exp, "dir": d, "summary": json.loads((d / "summary.json").read_text(encoding="utf-8")), "catalogs": {}, "interactions": {}}
    for f in d.glob("catalog_*.csv"):
        out["catalogs"][f.stem[len("catalog_"):]] = pd.read_csv(f)
    for f in d.glob("interactions_*.csv"):
        out["interactions"][f.stem[len("interactions_"):]] = pd.read_csv(f)
    return out


def list_experiments() -> list[dict]:
    rows = []
    for d in sorted(DISCOVERY_DIR.glob("d*"), reverse=True):
        f = d / "summary.json"
        if f.exists():
            s = json.loads(f.read_text(encoding="utf-8"))
            for bl, info in s["baselines"].items():
                rows.append({"experiment": s["experiment"], "created_at": s["created_at"], "baseline": bl,
                             "minutes": s.get("minutes"), **{f"{o}_tested": v["n_tested"] for o, v in info["origins"].items()},
                             **{f"{o}_validated": v["n_validated"] for o, v in info["origins"].items()},
                             "verdict_patterns": info["verdict"]["validated_patterns"], "verdict_gbm": info["verdict"]["gbm_residual"]})
        else:
            rows.append({"experiment": d.name, "created_at": None, "baseline": "incomplete (no summary: failed or running)"})
    return rows


def upcoming_adjustments(table: pd.DataFrame, fs_rows: pd.DataFrame, exp: str | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """Experimental adjustments for upcoming games from the primary ensemble origin.
    table: weekly predict_games output (p_champion); fs_rows: matching feature-store rows."""
    exp = exp or current_experiment()
    if not exp:
        return pd.DataFrame(), []
    d = DISCOVERY_DIR / exp
    bundle = joblib.load(d / "adjusters.joblib")
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    b = bundle[("ensemble", "primary")]
    verdicts = summary["baselines"]["ensemble"]["verdict"]
    p_home = table["p_champion"].to_numpy(float)
    X, dog_home = orient(fs_rows.reset_index(drop=True), p_home)
    p_dog = X["base_p_dog"].to_numpy()
    models = b["models"]
    gbm, feats = models["gbm_final"]
    f = gbm_margin(gbm, X, feats)
    p_gbm = sigmoid(logit(p_dog) + b["lambda"] * f)
    contrib = np.zeros(len(X))
    signals = [[] for _ in range(len(X))]
    for c, beta in zip(b["validated"], b["beta"]):
        v = candidate_values(c, X, models)
        for i, val in enumerate(v):
            if np.isnan(val):
                signals[i].append({"pattern": c.description, "status": "not evaluable: required feature missing",
                                   "missing": [ft for ft in c.features[:6] if np.isnan(X.loc[i, ft])]})
            elif (c.kind == "mask" and val > 0) or c.kind == "score":
                contrib[i] += beta * val
                signals[i].append({"pattern": c.description, "status": "applies", "logodds_contribution": float(beta * val),
                                   "validation_effect": c.val["beta"], "validation_ci": (c.val["beta"] - 1.96 * c.val["se"],
                                                                                         c.val["beta"] + 1.96 * c.val["se"])})
    # exploratory (carried but rejected) matches are shown for context only; they never adjust
    validated_ids = {c.cid for c in b["validated"]}
    for c in b["carried"][:15]:
        if c.cid in validated_ids or c.kind != "mask":
            continue
        v = candidate_values(c, X, models)
        for i, val in enumerate(v):
            if val == 1:
                signals[i].append({"pattern": c.description, "status": f"exploratory only ({c.status}); no adjustment"})
    p_pat = sigmoid(logit(p_dog) + contrib)
    rows = []
    for i in range(len(X)):
        to_home = (lambda q: q if dog_home[i] else 1 - q)
        miss = [c for c in feats if np.isnan(X.loc[i, c])]
        rows.append({"game_id": table["game_id"].iloc[i], "home_team": table["home_team"].iloc[i], "away_team": table["away_team"].iloc[i],
                     "underdog": table["home_team"].iloc[i] if dog_home[i] else table["away_team"].iloc[i],
                     "p_home_original": p_home[i], "p_underdog_original": p_dog[i],
                     "p_home_adj_patterns": to_home(p_pat[i]), "p_home_adj_gbm": to_home(p_gbm[i]),
                     "adj_patterns": to_home(p_pat[i]) - p_home[i], "adj_gbm": to_home(p_gbm[i]) - p_home[i],
                     "n_validated_signals": sum(s["status"] == "applies" for s in signals[i]),
                     "missing_gbm_inputs": len(miss), "missing_examples": ", ".join(miss[:5]),
                     "patterns_verdict": verdicts["validated_patterns"], "gbm_verdict": verdicts["gbm_residual"],
                     "primary_forecast": "original ensemble"
                     + ("" if "not demonstrated" in verdicts["gbm_residual"] else " (GBM adjustment has passed its pre-declared test)")})
    return pd.DataFrame(rows), signals


def prospective_check(exp: str | None = None) -> dict:
    """Completed games whose predictions were archived BEFORE kickoff (immutable snapshots)."""
    from .data_pipeline import load_feature_store
    fs = load_feature_store().set_index("game_id")
    rows = []
    for f in SNAPSHOTS_DIR.glob("*/*.json"):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for r in payload.get("predictions", []):
            g = r.get("game_id")
            if g in fs.index and bool(fs.loc[g, "completed"]) and pd.Timestamp(r["predicted_at"]) < pd.Timestamp(fs.loc[g, "kickoff_utc"]):
                rows.append({"game_id": g, "p": r.get("p_champion"), "y": fs.loc[g, "home_win"], "snapshot": f.name})
    df = pd.DataFrame(rows).drop_duplicates("game_id", keep="first") if rows else pd.DataFrame()
    df = df[df["y"].notna()] if len(df) else df
    return {"n_games": int(len(df)), "summary": M.prob_summary(df["y"], df["p"], ci=False) if len(df) else None,
            "note": "Only predictions saved before kickoff count. Adjusted forecasts are archived in discovery snapshots from Phase 2 onward."}



# --------------------------------------------------------------------------- prospective hypotheses

HYP_FILE = DISCOVERY_DIR / "prospective_hypotheses.joblib"


def register_prospective_hypotheses(k: int = 10, progress=print) -> dict:
    """Generate hypotheses from ALL completed historical seasons (no historical validation look is
    consumed) and freeze them. They are tested only on games archived before kickoff AFTER this
    registration, with Holm correction across the k hypotheses."""
    if HYP_FILE.exists():
        raise FileExistsError("Prospective hypotheses are already registered; they are frozen by design.")
    cfg = {**DEFAULT_CONFIG, "carry_top_k": k}
    base = load_base("ensemble")
    seasons = sorted(int(s) for s in base["meta"]["season"].unique() if s <= 2025)
    res = run_origin(base, {"name": "hypothesis_generation", "discovery": [seasons[0], seasons[-1]], "discovery_only": True}, cfg, progress)
    hyps = [{"id": c.cid, "description": c.description, "method": c.method, "kind": c.kind, "features": c.features,
             "direction": float(np.sign(c.disc.get("beta", 0.0))), "historical_effect": c.disc.get("beta"),
             "historical_z_nominal": c.disc.get("z")} for c in res["carried"]]
    payload = {"registered_at": pd.Timestamp.now(tz="UTC").isoformat(), "generated_from_seasons": [seasons[0], seasons[-1]],
               "n_candidates_searched": res["n_tested"], "hypotheses": hyps, "candidates": res["carried"], "models": res["models"]}
    joblib.dump(payload, HYP_FILE)
    return {k_: v for k_, v in payload.items() if k_ not in ("candidates", "models")}


def evaluate_prospective_hypotheses(min_matches: int = 30) -> pd.DataFrame:
    """Score frozen hypotheses on archived pregame predictions of games completed after registration."""
    from .data_pipeline import load_feature_store
    from .prospective import scored_table
    if not HYP_FILE.exists():
        return pd.DataFrame()
    payload = joblib.load(HYP_FILE)
    t = scored_table()
    if t.empty:
        return pd.DataFrame([{"hypothesis": h["description"], "status": "no scored prospective games yet"} for h in payload["hypotheses"]])
    t = t[(t["window"] == "final") & (t["predicted_at"] > pd.Timestamp(payload["registered_at"]))]
    fs = load_feature_store().drop_duplicates("game_id").set_index("game_id")
    rows = fs.loc[t["game_id"]].reset_index()
    X, dog_home = orient(rows, t["p_home"].to_numpy())
    y = np.where(dog_home, t["home_win"].to_numpy(), 1 - t["home_win"].to_numpy())
    p = X["base_p_dog"].to_numpy()
    out = []
    for h, c in zip(payload["hypotheses"], payload["candidates"]):
        v = candidate_values(c, X, payload["models"])
        n = int(np.nansum(v > 0)) if c.kind == "mask" else int((~np.isnan(v)).sum())
        b, se = offset_effect(v, y, p) if n else (np.nan, np.nan)
        z = b / se if se and not np.isnan(se) else np.nan
        p_one = float(stats.norm.sf(z * h["direction"])) if not np.isnan(z) else 1.0
        out.append({"hypothesis": h["description"], "direction": h["direction"], "prospective_matches": n, "effect": b,
                    "z": z, "p_one_sided": p_one})
    df = pd.DataFrame(out)
    df["p_holm"] = holm(df["p_one_sided"].fillna(1).to_numpy())
    df["status"] = np.where(df["prospective_matches"] < min_matches, "accumulating evidence",
                            np.where(df["p_holm"] < 0.05, "supported prospectively", "not supported so far"))
    return df
