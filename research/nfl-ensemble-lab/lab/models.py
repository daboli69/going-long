"""The six winner classifiers and six margin regressors, with small
hyperparameter grids tuned only on development seasons.

Every estimator is an sklearn Pipeline whose imputer/scaler are fit inside
`fit`, so preprocessing never sees validation or test rows.

Single-layer network note: a single linear layer with a sigmoid output
trained with binary cross-entropy and L2 weight decay is mathematically the
same model family as L2-regularized logistic regression. Differences come
only from the optimizer (Adam + early stopping vs. L-BFGS to convergence).
Its vote is therefore NOT independent evidence from the logistic vote.
"""
from __future__ import annotations

import copy
import itertools

import numpy as np
import torch
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from xgboost import XGBClassifier, XGBRegressor

from .config import RANDOM_SEED


class TorchNet(BaseEstimator):
    """Small PyTorch network. hidden=() gives a single linear layer.
    Early stopping uses the chronologically LAST `val_frac` of the training rows
    (callers pass rows in kickoff order), never a random split."""

    def __init__(self, task="clf", hidden=(64, 32), dropout=0.2, weight_decay=1e-3, lr=1e-3,
                 max_epochs=300, patience=20, batch_size=128, val_frac=0.15, seed=RANDOM_SEED):
        self.task, self.hidden, self.dropout, self.weight_decay, self.lr = task, hidden, dropout, weight_decay, lr
        self.max_epochs, self.patience, self.batch_size, self.val_frac, self.seed = max_epochs, patience, batch_size, val_frac, seed

    def _build(self, d):
        layers, prev = [], d
        for h in self.hidden:
            layers += [torch.nn.Linear(prev, h), torch.nn.ReLU(), torch.nn.Dropout(self.dropout)]
            prev = h
        layers.append(torch.nn.Linear(prev, 1))
        return torch.nn.Sequential(*layers)

    def fit(self, X, y, sample_weight=None):
        torch.manual_seed(self.seed)
        torch.use_deterministic_algorithms(True)
        X = np.asarray(X, np.float32)
        y = np.asarray(y, np.float32)
        weights = None if sample_weight is None else np.asarray(sample_weight, np.float32)
        if weights is not None and (weights.shape != y.shape or not np.isfinite(weights).all() or
                                    np.any(weights < 0) or weights.sum() <= 0):
            raise ValueError("Invalid sample weights")
        if self.task == "reg":
            self.y_mean_, self.y_std_ = float(y.mean()), float(y.std() or 1.0)
            y = (y - self.y_mean_) / self.y_std_
        else:
            self.classes_ = np.array([0, 1])
        n_val = max(int(len(X) * self.val_frac), 1) if len(X) >= 50 else 0
        Xtr, ytr = torch.from_numpy(X[: len(X) - n_val]), torch.from_numpy(y[: len(y) - n_val])
        Xva, yva = torch.from_numpy(X[len(X) - n_val:]), torch.from_numpy(y[len(y) - n_val:])
        net = self._build(X.shape[1])
        opt = torch.optim.Adam(net.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        loss_fn = torch.nn.BCEWithLogitsLoss() if self.task == "clf" else torch.nn.MSELoss()
        weighted_loss = (torch.nn.BCEWithLogitsLoss(reduction="none") if self.task == "clf" else
                         torch.nn.MSELoss(reduction="none")) if weights is not None else None
        wt = torch.from_numpy(weights[:len(y) - n_val]) if weights is not None else None
        wv = torch.from_numpy(weights[len(y) - n_val:]) if weights is not None else None
        gen = torch.Generator().manual_seed(self.seed)
        best, best_state, bad = np.inf, copy.deepcopy(net.state_dict()), 0
        self.epochs_ = 0
        for epoch in range(self.max_epochs):
            net.train()
            for idx in torch.randperm(len(Xtr), generator=gen).split(self.batch_size):
                opt.zero_grad()
                output = net(Xtr[idx]).squeeze(1)
                loss = loss_fn(output, ytr[idx]) if wt is None else (weighted_loss(output, ytr[idx]) * wt[idx]).sum() / wt[idx].sum().clamp_min(1e-12)
                loss.backward()
                opt.step()
            self.epochs_ = epoch + 1
            if n_val:
                net.eval()
                with torch.no_grad():
                    output = net(Xva).squeeze(1)
                    v = float(loss_fn(output, yva)) if wv is None else float((weighted_loss(output, yva) * wv).sum() / wv.sum().clamp_min(1e-12))
                if v < best - 1e-5:
                    best, best_state, bad = v, copy.deepcopy(net.state_dict()), 0
                else:
                    bad += 1
                    if bad >= self.patience:
                        break
        if n_val:
            net.load_state_dict(best_state)
        net.eval()
        self.net_ = net
        self.n_features_in_ = X.shape[1]
        return self

    def _raw(self, X):
        with torch.no_grad():
            return self.net_(torch.from_numpy(np.asarray(X, np.float32))).squeeze(1).numpy().astype(float)

    def linear_weights(self):
        """(weights, bias) when the network is a single linear layer."""
        if self.hidden:
            return None
        layer = self.net_[0]
        return layer.weight.detach().numpy()[0].astype(float), float(layer.bias.detach().numpy()[0])


class TorchClassifier(TorchNet, ClassifierMixin):
    def __init__(self, hidden=(64, 32), dropout=0.2, weight_decay=1e-3, lr=1e-3, max_epochs=300,
                 patience=20, batch_size=128, val_frac=0.15, seed=RANDOM_SEED):
        super().__init__("clf", hidden, dropout, weight_decay, lr, max_epochs, patience, batch_size, val_frac, seed)

    def predict_proba(self, X):
        p = 1 / (1 + np.exp(-self._raw(X)))
        return np.column_stack([1 - p, p])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] > 0.5).astype(int)


class TorchRegressor(TorchNet, RegressorMixin):
    def __init__(self, hidden=(64, 32), dropout=0.2, weight_decay=1e-3, lr=1e-3, max_epochs=300,
                 patience=20, batch_size=128, val_frac=0.15, seed=RANDOM_SEED):
        super().__init__("reg", hidden, dropout, weight_decay, lr, max_epochs, patience, batch_size, val_frac, seed)

    def predict(self, X):
        return self._raw(X) * self.y_std_ + self.y_mean_


def _scaled(est):
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", est)])


def _imputed(est):
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("model", est)])


def _grid(**axes):
    keys = list(axes)
    return [dict(zip(keys, vals)) for vals in itertools.product(*axes.values())]


XGB_GRID = _grid(max_depth=[2, 3], n_estimators=[150, 400], learning_rate=[0.03])

CLASSIFIERS = {
    "logreg": (lambda C: _scaled(LogisticRegression(C=C, max_iter=5000)), _grid(C=[0.001, 0.003, 0.01, 0.03, 0.1])),
    "xgboost": (lambda **k: _imputed(XGBClassifier(**k, subsample=0.8, colsample_bytree=0.6, min_child_weight=5,
                                                     reg_lambda=5.0, eval_metric="logloss", random_state=RANDOM_SEED,
                                                     n_jobs=8, tree_method="hist")), XGB_GRID),
    "decision_tree": (lambda **k: _imputed(DecisionTreeClassifier(**k, random_state=RANDOM_SEED)),
                      _grid(max_depth=[3, 4, 5], min_samples_leaf=[40, 80], ccp_alpha=[0.0005])),
    "random_forest": (lambda **k: _imputed(RandomForestClassifier(**k, n_estimators=300, max_features=0.3,
                                                                    random_state=RANDOM_SEED, n_jobs=-1)),
                      _grid(max_depth=[5, 8], min_samples_leaf=[10, 25])),
    "mlp": (lambda **k: _scaled(TorchClassifier(**k)), _grid(hidden=[(32, 16), (64, 32)], weight_decay=[1e-3, 1e-2], dropout=[0.3])),
    "single_layer": (lambda **k: _scaled(TorchClassifier(hidden=(), dropout=0.0, **k)), _grid(weight_decay=[1e-2, 3e-2, 1e-1, 3e-1])),
}

REGRESSORS = {
    "logreg": (lambda alpha: _scaled(Ridge(alpha=alpha)), _grid(alpha=[100.0, 300.0, 1000.0, 3000.0, 10000.0])),
    "xgboost": (lambda **k: _imputed(XGBRegressor(**k, subsample=0.8, colsample_bytree=0.6, min_child_weight=5,
                                                    reg_lambda=5.0, random_state=RANDOM_SEED, n_jobs=8, tree_method="hist")), XGB_GRID),
    "decision_tree": (lambda **k: _imputed(DecisionTreeRegressor(**k, random_state=RANDOM_SEED)),
                      _grid(max_depth=[3, 4, 5], min_samples_leaf=[40, 80])),
    "random_forest": (lambda **k: _imputed(RandomForestRegressor(**k, n_estimators=300, max_features=0.3,
                                                                   random_state=RANDOM_SEED, n_jobs=-1)),
                      _grid(max_depth=[5, 8], min_samples_leaf=[10, 25])),
    "mlp": (lambda **k: _scaled(TorchRegressor(**k)), _grid(hidden=[(32, 16), (64, 32)], weight_decay=[1e-3, 1e-2], dropout=[0.3])),
    "single_layer": (lambda **k: _scaled(TorchRegressor(hidden=(), dropout=0.0, **k)), _grid(weight_decay=[1e-2, 3e-2, 1e-1, 3e-1])),
}

MARGIN_NAMES = {
    "logreg": "Linear Regression (ridge)", "xgboost": "XGBoost Regressor", "decision_tree": "Decision Tree Regressor",
    "random_forest": "Random Forest Regressor", "mlp": "Feedforward Neural Network", "single_layer": "Single-Layer Linear Neural Regression",
}


def make(kind: str, key: str, params: dict):
    factory = (CLASSIFIERS if kind == "clf" else REGRESSORS)[key][0]
    return factory(**params)


def grid(kind: str, key: str) -> list[dict]:
    return (CLASSIFIERS if kind == "clf" else REGRESSORS)[key][1]
