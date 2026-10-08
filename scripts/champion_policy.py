"""Champion policy v2 (versioned, switchable): prior-strength blend of current and earlier-season games, pooled yardage spread, negative-binomial receptions.

Validated in research/trend-intelligence (experiments P3-1, P3-5, P3-6/P3-6b). The numbers live in config/champion_policy.json; setting "active": false there, or
running with GOING_CHAMPION_POLICY=v1, restores the previous 80% current / 20% earlier policy exactly. Only markets listed in the config change.

The functions below are the production implementation of formulas that the research code evaluates in vectorised form; tests/test_champion_policy.py checks that the two agree.
"""
import json
import math
import os
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parent.parent / 'config' / 'champion_policy.json'
V1_NAME = 'champion-v1'


def load(path=None):
    """The active policy, or None when v1 is in force (inactive config, missing file, or GOING_CHAMPION_POLICY=v1)."""
    if os.environ.get('GOING_CHAMPION_POLICY', '').lower() == 'v1':
        return None
    try:
        policy = json.loads(Path(path or POLICY_PATH).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return policy if policy.get('active') else None


def market_policy(policy, market):
    return (policy or {}).get('markets', {}).get(market)


def blend_weights(years, season, c):
    """Per-game weights summing to 1 whose weighted mean is (k*current_mean + c*prior_mean)/(k + c); equal weights when only one source exists."""
    current = sum(1 for y in years if y == season)
    prior = sum(1 for y in years if y < season)
    if not current and not prior:
        return [0.0 for _ in years]
    if not prior:
        return [1.0 / current if y == season else 0.0 for y in years]
    if not current:
        return [1.0 / prior if y < season else 0.0 for y in years]
    return [1.0 / (current + c) if y == season else (c / (current + c)) / prior if y < season else 0.0 for y in years]


def legacy_weights(years, season):
    """The v1 policy (80% current / 20% earlier). Kept here so v2's zero-mass window estimate uses exactly the weights the research used."""
    current = sum(y == season for y in years)
    prior = sum(y < season for y in years)
    return [(0.8 / current if prior else 1 / current) if y == season else (0.2 / prior if current else 1 / prior) if y < season else 0 for y in years]


def _clip(value, low, high):
    return min(high, max(low, value))


def pooled_lognormal(mean, n_games, window_nonpositive_fraction, position, shape):
    """Yardage distribution: lognormal on positive games with a pooled coefficient of variation, nonpositive mass shrunk toward the position rate.

    Returns the model fields to merge into the profile stat, or None when the position has no pooled parameters or the mean is not positive."""
    cv = (shape.get('cv') or {}).get(position)
    zero_rate = (shape.get('zero_rate') or {}).get(position)
    if cv is None or zero_rate is None or not (mean > 0):
        return None
    strength = shape.get('zero_shrink_games', 10)
    p0 = _clip((n_games * window_nonpositive_fraction + strength * zero_rate) / (n_games + strength), 0.001, 0.99)
    positive_mean = mean / (1 - p0)
    positive_sd = positive_mean * cv
    sigma2 = math.log1p((positive_sd / positive_mean) ** 2)
    overall_var = (1 - p0) * (positive_sd ** 2 + positive_mean ** 2) - mean ** 2
    return {'mu_log': math.log(positive_mean) - sigma2 / 2, 'sigma_log': math.sqrt(sigma2), 'positive_weight': 1 - p0, 'nonpositive': [0], 'nonpositive_weights': [p0],
            'sd': math.sqrt(max(overall_var, 0.0)), 'zero_mass': p0, 'pooled_cv': cv}


def negative_binomial_sd(mean, phi):
    return math.sqrt(mean + phi * mean * mean)
