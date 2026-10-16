"""Voting and probability ensembles over the six winner models.

The six votes are correlated (logistic regression and the single-layer network
are nearly the same function), so a vote count is a description of model
agreement, never a probability: a 6-0 vote is not a 100% forecast.
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

from .metrics import EPS, log_loss

MODEL_KEYS = ("logreg", "xgboost", "decision_tree", "random_forest", "mlp", "single_layer")
MODEL_NAMES = {
    "logreg": "Logistic Regression", "xgboost": "XGBoost", "decision_tree": "Decision Tree",
    "random_forest": "Random Forest", "mlp": "Feedforward Neural Network", "single_layer": "Single-Layer Neural Network",
}
FAMILIES = {"logreg": "linear", "single_layer": "linear", "decision_tree": "tree", "random_forest": "tree",
            "xgboost": "tree", "mlp": "neural"}
ENSEMBLE_KEYS = ("majority_vote", "equal_average", "weighted_average", "stacking")
ENSEMBLE_NAMES = {"majority_vote": "Simple Majority Vote", "equal_average": "Equal-Weight Average",
                  "weighted_average": "Validation-Weighted Average", "stacking": "Out-of-Fold Logistic Stacking"}


def vote(probs: dict[str, float]) -> dict:
    """Count one binary vote per available model. A 3-3 split is a tie; the
    tie is reported as such and broken only by the equal-weight average."""
    valid = {k: p for k, p in probs.items() if p is not None and not np.isnan(p)}
    home = sum(1 for p in valid.values() if p > 0.5)
    away = sum(1 for p in valid.values() if p < 0.5)
    exact = len(valid) - home - away  # p == 0.5 abstains
    avg = float(np.mean(list(valid.values()))) if valid else np.nan
    if home > away:
        winner, tie = "home", False
    elif away > home:
        winner, tie = "away", False
    else:
        tie = True
        winner = "home" if avg > 0.5 else "away" if avg < 0.5 else "none"
    return {"home_votes": home, "away_votes": away, "abstain": exact, "n_models": len(valid),
            "winner": winner, "tie": tie, "unanimous": len(valid) > 0 and (home == len(valid) or away == len(valid)),
            "label": f"{max(home, away)}-{min(home, away)}" + (" tie" if tie else "")}


def equal_average(P: np.ndarray) -> np.ndarray:
    return np.nanmean(P, axis=1)


def skill_weights(P_hist: np.ndarray, y_hist: np.ndarray) -> np.ndarray:
    """Weights proportional to log-loss skill over a coin flip, measured on
    earlier out-of-sample seasons only. Falls back to equal weights."""
    ll = np.array([log_loss(y_hist, P_hist[:, j]) for j in range(P_hist.shape[1])])
    skill = np.clip(np.log(2) - ll, 0, None)
    return skill / skill.sum() if skill.sum() > 0 else np.full(P_hist.shape[1], 1 / P_hist.shape[1])


def weighted_average(P: np.ndarray, w: np.ndarray) -> np.ndarray:
    return P @ w


def _logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def fit_stacker(P_hist: np.ndarray, y_hist: np.ndarray, C: float = 1.0) -> LogisticRegression:
    """Logistic regression on logits of out-of-fold base probabilities."""
    return LogisticRegression(C=C, max_iter=1000).fit(_logit(P_hist), y_hist)


def stack_predict(stacker: LogisticRegression, P: np.ndarray) -> np.ndarray:
    return stacker.predict_proba(_logit(P))[:, 1]
