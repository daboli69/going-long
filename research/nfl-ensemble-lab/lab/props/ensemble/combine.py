"""Earlier-week-only weighting, stacking and Platt calibration."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

from ... import ensemble, metrics
from . import COUNTS


def loss_rows(stat, y, pred):
    y, p = np.asarray(y, float), np.asarray(pred, float)
    if stat == "anytime_td":
        return (p - y) ** 2
    if stat in COUNTS:
        p = np.maximum(p, 1e-6)
        return 2 * (np.where(y > 0, y * np.log(np.maximum(y, 1e-10) / p), 0) - y + p)
    return np.abs(y - p)


def combine(stat, current, history, week, season=2022):
    """History rows: season, week, actual and available member columns.

    Strictly earlier 2022 weeks only for calibration/meta-learning, including at
    2026 forecast time. Warm-up behavior is explicit, not fitted on target rows.
    """
    names = list(current)
    P = np.column_stack([current[k] for k in names])
    if not np.isfinite(P).all():
        raise ValueError("Cannot combine nonfinite member predictions")
    H = history[(history["season"] == 2022) & ((history["week"] < week) if season == 2022 else True)] if len(history) else history
    if len(H) and all(k in H for k in names):
        H = H.dropna(subset=names + ["actual"])
    else:
        H = H.iloc[:0]
    equal = ensemble.equal_average(P)
    values = {"equal": equal, "weighted": equal.copy(), "stacked": equal.copy()}
    weights = np.full(len(names), 1 / len(names))
    state = {"members": names, "history_rows": len(H), "meta_max_week": int(H["week"].max()) if len(H) else None,
             "stacking": "equal warm-up", "calibration": {k: "uncalibrated" for k in values}}
    if len(H) >= 100:
        HP, y = H[names].to_numpy(float), H["actual"].to_numpy(float)
        if stat == "anytime_td":
            weights = ensemble.skill_weights(HP, y)
        else:
            errors = np.array([loss_rows(stat, y, HP[:, j]).mean() for j in range(len(names))])
            weights = 1 / np.maximum(errors, 1e-6)
            weights /= weights.sum()
        values["weighted"] = ensemble.weighted_average(P, weights)
        if stat != "anytime_td" or len(np.unique(y)) == 2:
            if stat == "anytime_td":
                stacker = ensemble.fit_stacker(HP, y)
                values["stacked"] = ensemble.stack_predict(stacker, P)
            else:
                stacker = Ridge(alpha=100.0, positive=True).fit(HP, y)
                values["stacked"] = np.maximum(stacker.predict(P), 0)
            state["stacking"] = "earlier-week out-of-fold predictions"
    state["weights"] = dict(zip(names, weights.tolist()))
    # Calibrate each method using that method's previously emitted predictions,
    # never in-sample meta-fit values or target-week outcomes.
    raw = {k: v.copy() for k, v in values.items()}
    if stat == "anytime_td" and len(H) >= 100 and H["actual"].nunique() == 2:
        for name in values:
            col = "raw_" + name
            if col not in H or H[col].isna().any():
                continue
            hp = np.clip(H[col].to_numpy(float), metrics.EPS, 1 - metrics.EPS)
            cp = np.clip(raw[name], metrics.EPS, 1 - metrics.EPS)
            calibrator = LogisticRegression(C=1.0, max_iter=1000).fit(np.log(hp / (1 - hp))[:, None], H["actual"])
            values[name] = calibrator.predict_proba(np.log(cp / (1 - cp))[:, None])[:, 1]
            state["calibration"][name] = "Platt on earlier-week emitted predictions"
    return values, raw, state


def first_td_reweight(first, structural_anytime, ensemble_anytime, no_td):
    first, sa, ea = map(lambda a: np.asarray(a, float), (first, structural_anytime, ensemble_anytime))
    if not (np.isfinite(first).all() and np.isfinite(sa).all() and np.isfinite(ea).all()):
        raise ValueError("Invalid TD probabilities")
    if np.any((first < 0) | (sa < 0) | (ea < 0) | (sa > 1) | (ea > 1)) or not 0 <= no_td <= 1:
        raise ValueError("Invalid TD probabilities")
    scores = first * np.divide(ea, sa, out=np.ones_like(ea), where=sa > 1e-9)
    # Keep the structural no-offensive-TD mass; reallocate only player mass.
    if scores.sum() > 0:
        return np.r_[scores / scores.sum() * (1 - no_td), no_td]
    if first.sum() > 0:
        return np.r_[first / first.sum() * (1 - no_td), no_td]
    return np.r_[np.zeros(len(first)), 1.0]
