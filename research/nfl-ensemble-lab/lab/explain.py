"""Game-specific (local) explanations for each model. Every explanation is
computed from the fitted model; nothing is narrated or invented.

  Logistic Regression / Single-Layer NN: exact coefficient x standardized value (log-odds).
  XGBoost: exact TreeSHAP contributions from the booster (log-odds).
  Random Forest: Saabas path attribution averaged over trees (probability).
  Decision Tree: the literal decision path plus the leaf's training win rate.
  Feedforward NN: occlusion, replacing one feature at a time with its training
  mean (approximate; interactions are not captured).
Explanations describe the raw model before calibration.
"""
from __future__ import annotations

import numpy as np
import xgboost

TOP_N = 8


def _parts(pipe, X):
    Xi = pipe.named_steps["impute"].transform(X)
    Xs = pipe.named_steps["scale"].transform(Xi) if "scale" in pipe.named_steps else Xi
    return Xi, Xs, pipe.named_steps["model"]


def _rank(features, values, contrib, unit, method, extra=None):
    order = np.argsort(-np.abs(contrib))[:TOP_N]
    rows = [{"feature": features[i], "value": float(values[i]), "contribution": float(contrib[i]),
             "favors": "home" if contrib[i] > 0 else "away" if contrib[i] < 0 else "neither"} for i in order]
    return {"method": method, "unit": unit, "scope": "local (this game)", "top": rows,
            "all": dict(zip(features, map(float, contrib))), **(extra or {})}


def explain(key: str, pipe, X: np.ndarray, features: list[str]) -> dict:
    """X is a single row (1 x d) in original feature units."""
    Xi, Xs, model = _parts(pipe, X)
    vals = Xi[0]
    if key == "logreg":
        c = model.coef_[0] * Xs[0]
        return _rank(features, vals, c, "log-odds", "coefficient x standardized value",
                     {"intercept": float(model.intercept_[0])})
    if key == "single_layer":
        w, b = model.linear_weights()
        return _rank(features, vals, w * Xs[0], "log-odds", "weight x standardized value", {"intercept": b})
    if key == "xgboost":
        contrib = model.get_booster().predict(xgboost.DMatrix(Xi), pred_contribs=True)[0]
        return _rank(features, vals, contrib[:-1], "log-odds", "TreeSHAP (xgboost pred_contribs)", {"base_value": float(contrib[-1])})
    if key == "random_forest":
        total = np.zeros(len(features))
        for est in model.estimators_:
            t = est.tree_
            node_p = t.value[:, 0, 1] / t.value[:, 0, :].sum(axis=1)
            path = est.decision_path(Xi).indices
            for parent, child in zip(path[:-1], path[1:]):
                total[t.feature[parent]] += node_p[child] - node_p[parent]
        return _rank(features, vals, total / len(model.estimators_), "probability", "Saabas path attribution (mean over trees)")
    if key == "decision_tree":
        t = model.tree_
        path = model.decision_path(Xi).indices
        node_p = t.value[:, 0, 1] / t.value[:, 0, :].sum(axis=1)
        rules, contrib = [], np.zeros(len(features))
        for parent, child in zip(path[:-1], path[1:]):
            f, thr = t.feature[parent], t.threshold[parent]
            went_left = Xi[0, f] <= thr
            rules.append(f"{features[f]} {'<=' if went_left else '>'} {thr:.4g} (game value {Xi[0, f]:.4g})")
            contrib[f] += node_p[child] - node_p[parent]
        leaf = path[-1]
        return _rank(features, vals, contrib, "probability", "decision path",
                     {"rules": rules, "leaf_samples": int(t.n_node_samples[leaf]), "leaf_home_rate": float(node_p[leaf])})
    if key == "mlp":
        base = model.predict_proba(Xs)[0, 1]
        occl = np.repeat(Xs, Xs.shape[1], axis=0)
        np.fill_diagonal(occl, 0.0)  # standardized 0 == training mean
        c = base - model.predict_proba(occl)[:, 1]
        return _rank(features, vals, c, "probability", "occlusion to training mean (approximate)")
    raise KeyError(key)


def normalized_shares(expl: dict) -> dict[str, float]:
    """Contributions rescaled to sum(|share|)=1 so models with different units can be compared."""
    allc = expl["all"]
    tot = sum(abs(v) for v in allc.values()) or 1.0
    return {k: v / tot for k, v in allc.items()}


FACTOR_RULES = [
    ("Player availability / injuries", ("inj_",)),
    ("Quarterback", ("qb_",)),
    ("Coaching", ("coach",)),
    ("Roster experience & depth", ("p4roster", "ol_churn")),
    ("Next Gen Stats", ("p4ngs",)),
    ("Personnel, pressure & tackling", ("p4pers", "p4pfr", "p4mx_")),
    ("Opponent-adjusted strength", ("rating", "p4sos")),
    ("Recent form", ("_l3_", "_l5_", "recent_form", "form_vs_season")),
    ("Travel, rest & schedule", ("travel", "tz_shift", "body_clock", "rest", "short_week", "off_bye", "ctx_week", "playoff")),
    ("Home field & venue", ("home_field", "neutral", "dome", "retractable", "div_game")),
    ("Volume & pace", ("plays", "sec_per_play", "pass_rate", "_yds", "_td")),
    ("Season efficiency (EPA / success)", ("blend_", "prev_", "mx_")),
]


def factor_of(feature: str) -> str:
    """Football factor a feature belongs to (for summarising real model attributions)."""
    for name, keys in FACTOR_RULES:
        if any(k in feature for k in keys):
            return name
    return "Other"


def factor_shares(expl: dict) -> dict[str, dict]:
    """Per football factor: share of the model's total |attribution| and the net direction
    (positive = pushes toward the home team). Computed from the model's own attributions."""
    shares = normalized_shares(expl)
    out: dict[str, dict] = {}
    for f, v in shares.items():
        k = factor_of(f)
        d = out.setdefault(k, {"share": 0.0, "net": 0.0})
        d["share"] += abs(v)
        d["net"] += v
    return out
