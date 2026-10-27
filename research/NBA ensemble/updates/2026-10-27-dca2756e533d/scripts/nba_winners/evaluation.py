"""Expanding chronological replay; no holdout fitting or publication."""
from collections import Counter
from datetime import timedelta
import numpy as np

from .data import utc
from .features import FEATURES, feature_rows
from .models import NAMES, fit, probabilities, weights, debate


def replay(games, config):
    rows = feature_rows(games, config)
    forecasts, models, fitted_at = [], None, None
    for row in rows:
        g = row['game']
        # Freeze model/weights at UTC midnight for a complete date block.
        origin = utc(g['tipoff']).replace(hour=0, minute=0, second=0, microsecond=0)
        training = [r for r in rows if r['available_at'] < origin]
        if len(training) < config['minimum_training_games']:
            continue
        if fitted_at is None or origin >= fitted_at + timedelta(days=config['refit_days']):
            models, fitted_at = fit(training, config), origin
            training_count = len(training)
        home_rate = sum(r['y'] for r in training) / len(training)
        earlier = [r for r in forecasts if utc(r['tipoff']) + timedelta(hours=config['historical_result_lag_hours']) < origin]
        p, w = probabilities(models, row['x']), weights(earlier, config)
        result = debate(g, p, w, row['counts'], config)
        result.update(actual=row['y'], probabilities=p, weight_training_games=len(earlier),
                      training_games=training_count, model_fitted_at=fitted_at.isoformat(),
                      forecast_origin=origin.isoformat(), home_frequency=home_rate,
                      feature_values=dict(zip(FEATURES, row['x'].tolist())),
                      evidence_kind='retrospective_replay_assumed_result_lag')
        forecasts.append(result)
    return forecasts, {'eligible_feature_games': len(rows), 'forecast_games': len(forecasts),
                       'final_games': sum(g['completed'] for g in games),
                       'excluded_before_minimum_team_history': sum(g['completed'] for g in games) - len(rows),
                       'training_warmup_games': len(rows) - len(forecasts)}


def metrics(y, p):
    y, p = np.array(y), np.clip(p, .01, .99)
    bins = []
    for low in np.arange(0, 1, .1):
        mask = (p >= low) & (p < low + .1)
        if mask.any():
            bins.append({'lower': round(float(low), 1), 'n': int(mask.sum()),
                         'mean_probability': float(p[mask].mean()), 'home_win_rate': float(y[mask].mean())})
    return {'n': len(y), 'brier': float(np.mean((p - y) ** 2)),
            'log_loss': float(-np.mean(y * np.log(p) + (1-y) * np.log(1-p))),
            'accuracy': float(np.mean((p >= .5) == y)), 'reliability_bins': bins}


def report(forecasts, config):
    if not forecasts:
        raise ValueError('No forecasts: more chronological history is needed')
    y = np.array([r['actual'] for r in forecasts])
    values = {name: np.array([r['probabilities'][name] for r in forecasts]) for name in NAMES}
    values.update(ensemble=np.array([r['home_probability'] for r in forecasts]),
                  equal_weight=np.array([r['equal_weight_home_probability'] for r in forecasts]),
                  home_frequency=np.array([r['home_frequency'] for r in forecasts]))
    days = np.array([r['tipoff'][:10] for r in forecasts])
    unique = sorted(set(days))
    rng = np.random.default_rng(config['random_seed'])
    # Same draws for each paired comparison. Cluster sums retain all games/date.
    draws = rng.integers(0, len(unique), size=(2000, len(unique)))
    counts = np.array([sum(days == d) for d in unique])
    paired = {}
    for baseline in ('equal_weight', 'elo', 'home_frequency'):
        delta = (values['ensemble'] - y) ** 2 - (values[baseline] - y) ** 2
        sums = np.array([delta[days == d].sum() for d in unique])
        samples = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
        paired[baseline] = {'ensemble_minus_baseline_brier': float(delta.mean()),
                            'date_cluster_95_interval': np.quantile(samples, [.025, .975]).tolist()}
    matrix = np.array([values[name] for name in NAMES])
    corr = np.eye(len(NAMES))
    for i in range(len(NAMES)):
        for j in range(i):
            corr[i,j] = corr[j,i] = (float(np.corrcoef(matrix[i], matrix[j])[0,1])
                                     if matrix[i].std() > 0 and matrix[j].std() > 0 else 0.)
    return {'status': 'development_diagnostic_not_holdout_or_promotion', 'date_clusters': len(unique),
            'metrics': {name: metrics(y, p) for name, p in values.items()}, 'paired_comparisons': paired,
            'model_order': list(NAMES), 'prediction_correlations': corr.tolist(),
            'review_flags': dict(Counter(flag for r in forecasts for flag in r['flags'])),
            'limitations': config['limitations'] + ['Date clusters do not capture all serial or team dependence. No tuned calibration layer in v1.']}
