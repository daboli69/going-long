"""Baselines and the XGBoost classifier, plus chronological walk-forward helpers."""
from __future__ import annotations
import itertools
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

SEED = 20261028
FIRST_TRAIN_SEASON = 2016
CORE = ['elo_diff', 'adj_off_diff', 'adj_def_diff', 'recent_net_diff', 'rest_diff', 'b2b_home', 'b2b_away', 'home_court']
GROUPS = {'elo': ['elo_diff'], 'adjusted': ['adj_off_diff', 'adj_def_diff'], 'recent': ['recent_net_diff'],
          'schedule': ['rest_diff', 'b2b_home', 'b2b_away'], 'context': ['home_court']}
ELO_FEATS = ['elo_diff', 'home_court']
C_GRID = [0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 10.0]
R_MAX = 1000
R_GRID = list(range(25, R_MAX + 1, 25))
XGB_SPACE = dict(max_depth=[1, 2, 3, 4, 6], learning_rate=[0.01, 0.03, 0.05], min_child_weight=[5, 20, 50],
                 subsample=[0.6, 0.8, 1.0], colsample_bytree=[0.6, 0.8, 1.0], reg_lambda=[1, 10, 50], reg_alpha=[0, 0.5, 2])


def sample_configs(n=30, seed=SEED):
    keys = list(XGB_SPACE)
    combos = list(itertools.product(*[XGB_SPACE[k] for k in keys]))
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(combos), size=n, replace=False)
    return [dict(zip(keys, combos[i])) for i in sorted(pick)]


def training_frame(F: pd.DataFrame, fold: int, window: int | None = None, exclude=()):
    lo = FIRST_TRAIN_SEASON if window is None else max(FIRST_TRAIN_SEASON, fold - window)
    m = F.eligible & F.season.between(lo, fold - 1) & ~F.season.isin(exclude)
    return F[m]


def eval_frame(F, fold):
    return F[F.eligible & (F.season == fold)]


class Logit:
    def __init__(self, feats, C=None):
        self.feats, self.C = list(feats), C

    def fit(self, df):
        X, y = df[self.feats].values, df.home_win.values
        if self.C is None:
            self.m = LogisticRegression(penalty=None, max_iter=1000).fit(X, y)
            self.sc = None
        else:
            self.sc = StandardScaler().fit(X)
            self.m = LogisticRegression(C=self.C, max_iter=2000).fit(self.sc.transform(X), y)
        return self

    def predict(self, df):
        X = df[self.feats].values
        if self.sc is not None:
            X = self.sc.transform(X)
        return self.m.predict_proba(X)[:, 1]


def make_xgb(cfg, rounds, n_jobs=4):
    return XGBClassifier(objective='binary:logistic', eval_metric='logloss', tree_method='hist', n_estimators=rounds,
                         random_state=SEED, n_jobs=n_jobs, verbosity=0, **cfg)


class XGB:
    def __init__(self, feats, cfg, rounds):
        self.feats, self.cfg, self.rounds = list(feats), dict(cfg), int(rounds)

    def fit(self, df):
        self.m = make_xgb(self.cfg, self.rounds).fit(df[self.feats].values, df.home_win.values)
        return self

    def predict(self, df, rounds=None):
        r = rounds or self.rounds
        return self.m.predict_proba(df[self.feats].values, iteration_range=(0, r))[:, 1]


def xgb_staged(train, test, feats, cfg, rounds_grid=R_GRID):
    m = make_xgb(cfg, max(rounds_grid)).fit(train[feats].values, train.home_win.values)
    X = test[feats].values
    return {r: m.predict_proba(X, iteration_range=(0, r))[:, 1] for r in rounds_grid}


class Calibrator:
    """Chronological probability calibration fitted on earlier out-of-sample predictions."""

    def __init__(self, method):
        self.method = method

    def fit(self, p, y):
        p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
        if self.method == 'platt':
            z = np.log(p / (1 - p)).reshape(-1, 1)
            self.m = LogisticRegression(penalty=None, max_iter=500).fit(z, y)
        elif self.method == 'isotonic':
            self.m = IsotonicRegression(out_of_bounds='clip', y_min=0.01, y_max=0.99).fit(p, y)
        elif self.method != 'none':
            raise ValueError(self.method)
        return self

    def predict(self, p):
        p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
        if self.method == 'none':
            return p
        if self.method == 'platt':
            return self.m.predict_proba(np.log(p / (1 - p)).reshape(-1, 1))[:, 1]
        return self.m.predict(p)
