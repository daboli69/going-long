"""Lagged current-season team state. Each game is featurized before its result."""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import numpy as np

from .data import utc

FEATURES = ['elo_difference', 'season_margin_difference', 'last5_margin_difference',
            'last10_margin_difference', 'win_rate_difference', 'points_for_difference',
            'points_allowed_difference', 'margin_sd_difference', 'rest_difference',
            'back_to_back_difference', 'games_last4days_difference', 'home_court']


def elo_probability(difference):
    return 1 / (1 + 10 ** (-max(-2000, min(2000, difference)) / 400))


class State:
    def __init__(self, config):
        self.config = config
        self.history = defaultdict(list)
        self.elo = defaultdict(lambda: 1500.)
        self.appearances = defaultdict(list)

    def note_schedule(self, g):
        for code in (g['home'], g['away']):
            self.appearances[(g['season'], code)].append(utc(g['tipoff']))

    def apply(self, g):
        h, a = (g['season'], g['home']), (g['season'], g['away'])
        diff = self.elo[h] - self.elo[a] + (0 if g['neutral'] else self.config['elo_home_advantage'])
        update = self.config['elo_k'] * ((g['home_score'] > g['away_score']) - elo_probability(diff))
        self.elo[h] += update
        self.elo[a] -= update
        for key, scored, allowed in ((h, g['home_score'], g['away_score']), (a, g['away_score'], g['home_score'])):
            self.history[key].append((utc(g['tipoff']), scored, allowed))

    def features(self, g):
        now = utc(g['tipoff'])
        h, a = (g['season'], g['home']), (g['season'], g['away'])
        counts = [len(self.history[key]) for key in (h, a)]
        if min(counts) < self.config['minimum_team_games']:
            return None, counts

        def summary(key):
            past = self.history[key]
            margins = np.array([s - c for _, s, c in past], dtype=float)
            # Rest uses prior tipoffs, including games whose scores remain embargoed.
            schedule = self.appearances[key]
            days = (now - (schedule[-1] if schedule else past[-1][0])).total_seconds() / 86400
            return np.array([margins.mean(), margins[-5:].mean(), margins[-10:].mean(),
                             (sum(margins > 0) + 1) / (len(margins) + 2),
                             np.mean([s for _, s, _ in past]), np.mean([c for _, _, c in past]),
                             margins.std(), min(7., days), float(days < 1.5),
                             sum((now - tip).total_seconds() < 4 * 86400 for tip in schedule)])

        home_court = 0. if g['neutral'] else 1.
        difference = self.elo[h] - self.elo[a] + home_court * self.config['elo_home_advantage']
        return np.r_[difference, summary(h) - summary(a), home_court], counts


def feature_rows(games, config, as_of=None):
    """36h lag prevents simultaneous/unfinished-game leakage in archive replay.

    This is a documented availability assumption, not a historical receipt.
    """
    completed = sorted([g for g in games if g['completed']], key=lambda g: (g['tipoff'], g['game_id']))
    targets = sorted(games, key=lambda g: (g['tipoff'], g['game_id']))
    state, cursor, schedule_cursor, rows = State(config), 0, 0, []
    lag = timedelta(hours=config['historical_result_lag_hours'])
    for g in targets:
        tip = utc(g['tipoff'])
        if as_of is not None and tip >= as_of:
            continue
        while schedule_cursor < len(targets) and utc(targets[schedule_cursor]['tipoff']) < tip:
            state.note_schedule(targets[schedule_cursor])
            schedule_cursor += 1
        while cursor < len(completed) and utc(completed[cursor]['tipoff']) + lag < tip:
            state.apply(completed[cursor])
            cursor += 1
        x, counts = state.features(g)
        if g['completed'] and x is not None and (as_of is None or tip + lag < as_of):
            rows.append({'game': g, 'x': x, 'y': int(g['home_score'] > g['away_score']),
                         'margin': g['home_score'] - g['away_score'], 'counts': counts,
                         'available_at': tip + lag})
    return rows


def state_at(games, config, origin):
    state = State(config)
    lag = timedelta(hours=config['historical_result_lag_hours'])
    for g in sorted(games, key=lambda g: (g['tipoff'], g['game_id'])):
        if utc(g['tipoff']) < origin:
            state.note_schedule(g)
        if g['completed'] and utc(g['tipoff']) + lag < origin:
            state.apply(g)
    return state
