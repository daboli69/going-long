"""Six deterministic statistical voters, with auditable earlier-OOS weights."""
import math
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import elo_probability

NAMES = ('elo', 'logistic', 'gradient_boosting', 'random_forest', 'naive_bayes', 'ridge_margin')


def fit(rows, config):
    if len(rows) < config['minimum_training_games']:
        raise ValueError('Insufficient chronological training games')
    x = np.array([r['x'] for r in rows])
    y = np.array([r['y'] for r in rows])
    if len(set(y)) != 2:
        raise ValueError('Training needs both home and away wins')
    seed = config['random_seed']
    models = {
        'logistic': make_pipeline(StandardScaler(), LogisticRegression(C=1, max_iter=1000, random_state=seed)),
        'gradient_boosting': HistGradientBoostingClassifier(max_iter=100, max_leaf_nodes=7, l2_regularization=5, random_state=seed),
        'random_forest': RandomForestClassifier(n_estimators=150, max_depth=5, min_samples_leaf=20, random_state=seed, n_jobs=1),
        'naive_bayes': make_pipeline(StandardScaler(), GaussianNB(var_smoothing=.1)),
        'ridge_margin': make_pipeline(StandardScaler(), Ridge(alpha=100)),
    }
    for name, model in models.items():
        model.fit(x, [r['margin'] for r in rows] if name == 'ridge_margin' else y)
    residuals = np.array([r['margin'] for r in rows]) - models['ridge_margin'].predict(x)
    # Residual Gaussian is an explicit approximation, not a calibrated forecast.
    models['residual_sd'] = max(1., float(np.std(residuals, ddof=1)))
    return models


def probabilities(models, x):
    matrix = np.array(x, dtype=float).reshape(-1, len(x))
    p = {'elo': elo_probability(float(x[0]))}
    for name in NAMES[1:-1]:
        p[name] = float(models[name].predict_proba(matrix)[0, 1])
    z = float(models['ridge_margin'].predict(matrix)[0]) / models['residual_sd']
    p['ridge_margin'] = .5 * (1 + math.erf(z / math.sqrt(2)))
    return {key: float(np.clip(value, .01, .99)) for key, value in p.items()}


def weights(earlier, config):
    # Beta-like shrinkage of observed squared error toward .25 with 100 games.
    # Earlier must consist exclusively of settled out-of-sample predictions.
    prior = config['weight_prior_games']
    scores = {name: (sum((r['probabilities'][name] - r['actual']) ** 2 for r in earlier) + prior * .25)
              / (len(earlier) + prior) for name in NAMES}
    inverse = {name: 1 / max(.01, loss) for name, loss in scores.items()}
    return {name: value / sum(inverse.values()) for name, value in inverse.items()}


def debate(g, p, w, counts, config):
    home_p = sum(w[name] * p[name] for name in NAMES)
    equal = sum(p.values()) / len(p)
    pick = g['home'] if home_p >= .5 else g['away']
    voters = {name: {'home_probability': p[name], 'pick': g['home'] if p[name] >= .5 else g['away'],
                     'weight': w[name], 'contribution_to_home_probability': w[name] * p[name]} for name in NAMES}
    home_advocate = max(p, key=p.get)
    away_advocate = min(p, key=p.get)
    flags = []
    if max(p.values()) - min(p.values()) >= config['disagreement_range_flag']:
        flags.append('large_model_disagreement')
    if max(home_p, 1 - home_p) < config['close_probability_flag']:
        flags.append('close_to_tossup')
    if home_p == .5:
        flags.append('exact_tie_designated_home_tiebreak')
    return {'game_id': g['game_id'], 'season': g['season'], 'tipoff': g['tipoff'], 'home': g['home'], 'away': g['away'],
            'pick': pick, 'home_probability': home_p, 'away_probability': 1 - home_p,
            'equal_weight_home_probability': equal, 'votes_for_pick': sum(v['pick'] == pick for v in voters.values()),
            'probability_range': max(p.values()) - min(p.values()), 'team_prior_games': counts,
            'review_status': 'review' if flags else 'research_lean', 'flags': flags, 'models': voters,
            'debate': {'strongest_home_case': home_advocate, 'strongest_away_case': away_advocate,
                       'difference_in_home_probability': p[home_advocate] - p[away_advocate],
                       'resolution': 'Earlier out-of-sample Brier weights combine the six unchanged forecasts; disagreement remains visible.'},
            'interpretation': 'Unvalidated research probabilities; vote agreement is not confidence.'}
