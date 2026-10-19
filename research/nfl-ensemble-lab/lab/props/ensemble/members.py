"""Reuse the game model factories; add count likelihoods and quantile heads."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor

from ... import models
from . import COUNTS, YARDS

KEYS = ("logreg", "random_forest", "xgboost", "mlp")


def make_member(stat, key, threads=1):
    if stat in COUNTS and key == "logreg":
        estimator = models._scaled(PoissonRegressor(alpha=1.0, max_iter=1000))
    else:
        kind = "clf" if stat == "anytime_td" else "reg"
        estimator = models.make(kind, key, models.grid(kind, key)[0])
        if stat in COUNTS and key == "xgboost":
            estimator.set_params(model__objective="count:poisson")
    params = estimator.get_params()
    changes = {k: threads for k in params if k.endswith("n_jobs")}
    changes |= {k: True for k in params if k.endswith("keep_empty_features")}
    if changes:
        estimator.set_params(**changes)
    return estimator


def make_quantile(q):
    return models._imputed(GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=100,
        max_depth=2, learning_rate=.05, random_state=20261019)).set_params(impute__keep_empty_features=True)


class Members:
    def fit(self, frame, stat, columns, threads=1, log=print, sample_weight=None, production=False):
        if production:
            from .frozen import load
            load()
        if not len(frame) or (not production and frame["season"].max() > 2021):
            raise ValueError("Member fitting is restricted to seasons <=2021")
        self.stat, self.columns = stat, list(columns)
        self.models, self.errors, self.quantiles = {}, {}, {}
        self.train_rows = len(frame)
        self.train_max_season = int(frame["season"].max())
        X, y = frame[self.columns].to_numpy(float), frame[stat].to_numpy(float)
        for key in KEYS:
            try:
                log(f"fit {stat}/{key} n={len(y)}")
                fit_params = {"model__sample_weight": sample_weight} if sample_weight is not None else {}
                self.models[key] = make_member(stat, key, threads).fit(X, y, **fit_params)
            except Exception as exc:
                self.errors[key] = repr(exc)
                log(f"FAILED {stat}/{key}: {exc}; skipped")
        if stat in YARDS:
            for q in (.10, .50, .90):
                try:
                    fit_params = {"model__sample_weight": sample_weight} if sample_weight is not None else {}
                    self.quantiles[q] = make_quantile(q).fit(X, y, **fit_params)
                except Exception as exc:
                    self.errors[f"quantile_{q}"] = repr(exc)
        if not self.models:
            raise ValueError(f"No fitted members: {self.errors}")
        return self

    def predict(self, frame):
        X = frame[self.columns].to_numpy(float)
        out = {}
        for key, estimator in self.models.items():
            value = estimator.predict_proba(X)[:, 1] if self.stat == "anytime_td" else estimator.predict(X)
            out[key] = np.clip(value, 0, 1) if self.stat == "anytime_td" else np.maximum(value, 0)
        if len(self.quantiles) == 3:
            # Rearrangement prevents crossings; no post-result tuning of the head.
            q = np.sort(np.array([self.quantiles[k].predict(X) for k in sorted(self.quantiles)]), axis=0)
            for k, value in zip((10, 50, 90), q):
                out[f"q{k}"] = value
        return out
