"""Serializable model/protocol settings checked against the committed freeze."""
from __future__ import annotations

import math

from . import TARGETS
from .features import FEATURES
from .members import make_member


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (tuple, list)):
        return [clean(v) for v in value]
    return value


def runtime_spec():
    models = {}
    for stat in TARGETS:
        models[stat] = {}
        for key in ("logreg", "random_forest", "xgboost", "mlp"):
            estimator = make_member(stat, key, threads=7)
            params = {k: clean(v) for k, v in estimator.get_params().items() if "__" in k and
                      (v is None or isinstance(v, (bool, int, float, str, tuple, list)))}
            models[stat][key] = {"class": estimator.named_steps["model"].__class__.__name__, "params": params}
    return {"features": FEATURES, "models": models, "ensemble": "equal",
            "independent_members": ["logreg", "random_forest", "xgboost", "mlp", "sim_independent"],
            "market_informed_members": ["logreg", "random_forest", "xgboost", "mlp", "sim_independent", "simulator_v1"],
            "quantile_head": {"family": "GradientBoostingRegressor", "levels": [.1, .5, .9], "trees": 100,
                              "depth": 2, "learning_rate": .05, "seed": 20261019},
            "recency_weights": {"current_season": 1., "previous_season": .6, "older_seasons": .35,
                                "normalization": "unit-mean sample weights for learned members"},
            "structural_recent_fit": "whole-game importance resampling with these weights, seed 20261019, same count of training games",
            "training_cutoff": "all seasons 2016 through the last fully completed 2026 week; never current partial week",
            "game_anchor": "independent ridge alpha300 coefficients and OOF residuals fitted <=2021; current as-of football features only",
            "probability_calibration": "Platt fitted on earlier emitted 2022 predictions; >=100 rows and both classes",
            "predictive_distribution": "equal mixture: centered 2022 OOF residuals for learned yards, Poisson rates for learned counts, structural samples",
            "simulations": 1000,
            "td_definition": "rushing/receiving TD only; first offensive TD; passing/defensive/special-teams TDs excluded"}
