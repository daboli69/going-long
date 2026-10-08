"""Small, dependency-light modelling and evaluation helpers (numpy/pandas only).

The primary model is a ridge regression with a FIXED penalty chosen before any test data were seen. Nothing is tuned on a test season.
"""
import numpy as np

RIDGE_ALPHA = 10.0  # pre-registered, never tuned on test data
BOOTSTRAPS = 2000
SEED = 20261008


class Ridge:
    """Ridge regression on standardized features (intercept unpenalized)."""

    def __init__(self, alpha=RIDGE_ALPHA):
        self.alpha = alpha

    def fit(self, X, y):
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        self.mean_, self.scale_ = X.mean(0), X.std(0)
        self.scale_[self.scale_ == 0] = 1.0
        Z = (X - self.mean_) / self.scale_
        self.intercept_ = y.mean()
        A = Z.T @ Z + self.alpha * np.eye(Z.shape[1])
        self.coef_ = np.linalg.solve(A, Z.T @ (y - self.intercept_))
        return self

    def predict(self, X):
        return self.intercept_ + ((np.asarray(X, float) - self.mean_) / self.scale_) @ self.coef_

    def standardized_coef(self):
        return self.coef_


def mae(y, p):
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def rmse(y, p):
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def spearman(y, p):
    from scipy.stats import spearmanr
    value = spearmanr(y, p).statistic
    return float(value) if value == value else 0.0


def paired_bootstrap(errors_base, errors_new, groups, confidence=0.95, draws=BOOTSTRAPS, seed=SEED):
    """Cluster bootstrap (by player) of mean(abs error new) - mean(abs error base). Negative = the new model is better."""
    rng = np.random.default_rng(seed)
    base, new = np.abs(np.asarray(errors_base)), np.abs(np.asarray(errors_new))
    groups = np.asarray(groups)
    unique = np.unique(groups)
    index = {g: np.flatnonzero(groups == g) for g in unique}
    diffs = np.empty(draws)
    for i in range(draws):
        pick = rng.choice(unique, size=len(unique), replace=True)
        rows = np.concatenate([index[g] for g in pick])
        diffs[i] = new[rows].mean() - base[rows].mean()
    lo, hi = np.quantile(diffs, [(1 - confidence) / 2, 1 - (1 - confidence) / 2])
    return {'delta_mae': float(new.mean() - base.mean()), 'ci_low': float(lo), 'ci_high': float(hi), 'confidence': confidence}


def verdict(delta, base_mae, years_better, years_total, rule):
    """Apply the PRE-REGISTERED decision rule; never a judgement after seeing the number."""
    rel = -delta['delta_mae'] / base_mae if base_mae else 0.0
    if delta['ci_high'] < 0 and rel >= rule['min_relative_improvement'] and years_better >= rule['min_years_better']:
        return 'PROMISING', rel
    if rule.get('reject_requires_ci'):
        # v2 (experiments registered after the first wave): rejecting needs the CI to exclude a worthwhile gain, so a wide interval is INCONCLUSIVE
        if delta['ci_low'] > 0 or -delta['ci_low'] / base_mae < rule['min_relative_improvement']:
            return 'REJECTED', rel
        return 'INCONCLUSIVE', rel
    if delta['ci_low'] > 0 or rel < rule['reject_below_relative_improvement']:
        return 'REJECTED', rel
    return 'INCONCLUSIVE', rel
