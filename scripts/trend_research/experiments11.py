"""Jackpot touchdown markets: anytime TD, FIRST TD, LAST TD and King of the Endzone (longest TD).

JP-1  Structure: are first, anytime and last touchdowns different events? (who scores them, by position / type / team side)
JP-2  Anytime TD: free-data scoring-role blocks over the Champion v2 anytime rate (per-player-game log loss, Brier, weekly top-k precision)
JP-3  FIRST TD: the same blocks plus opening-script features in a conditional-logit game model (one first scorer per game, "other" alternative)
JP-4  LAST TD: the same blocks plus late-lead features
JP-5  King of the Endzone (longest TD): long-TD propensity and depth of target over the Champion rate

Protocol (all fixed before any 2024 / 2025 number was computed): parameters are fit on development seasons 2021-2023 ONLY (history for rolling windows from 2019); 2024 is
validation, 2025 is the holdout; no refit, no tuning. Features of a player-game use only that player's EARLIER appearances (shift(1) before every window), pre-game schedule
lines, and who was active (inactives are public ~90 minutes before kickoff). Outcomes come from play-by-play of the target game only.

Specs are hashed at registration (`python scripts/trend_research.py register`); the run refuses a changed spec (ledger.py).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import champion, jackpot_data as jd
from .experiments2 import champion_rows
from .experiments5 import _cluster_ci

DEV, VAL, HOLD = (2021, 2022, 2023), 2024, 2025
PEN_ANY, PEN_GAME = 1.0, 5.0
LAM_FLOOR = 0.01
C_V2 = 4  # Champion v2 anytime prior strength (config/champion_policy.json)
SEED = 20261009
TOPK_GAME = (1, 3, 5, 10)
TOPK_SLATE = (10, 25)
OUT = Path(__file__).resolve().parents[2] / 'research' / 'trend-intelligence' / 'jackpot_td_results.json'

# feature blocks: block -> list of (feature name, definition used in `derive`)
BLOCK_DEFS = {
    'OPP': {'xtd12': 'expected TDs per game from carries and targets by yard-line zone, last 12 appearances',
            'xtd6': 'same, last 6', 'inside5_touch12': 'carries + targets inside the 5, per game, last 12', 'rz_tgt12': 'targets inside the 20 per game, last 12'},
    'ROLE': {'snap3': 'offensive snap share, last 3', 'snap6': 'offensive snap share, last 6', 'xshare6': "player's share of his team's expected-TD mass, last 6"},
    'TREND': {'d_xtd36': 'xtd L3 minus xtd L6', 'd_share36': 'xTD share L3 minus L6', 'd_snap36': 'snap share L3 minus L6'},
    'TEAM': {'team_implied': 'closing implied team total (total +/- spread)/2', 'team_win_p': 'normal(spread/13.5) win probability'},
    'INJ': {'vac_alloc': "xTD per game of teammates who were regulars (>=3 of the last 6 team games) and are inactive today, allocated by the player's share of active xTD"},
    'REG': {'tdres12': 'actual TDs minus xTD per game, last 12 (luck)', 'tdres6': 'same, last 6'},
    'POS': {'is_rb': 'RB', 'is_te': 'TE', 'is_qb': 'QB'},
    'OPEN': {'open_share6': "share of the team's carries+targets on its first two possessions, last 6", 'tm_first_td_rate': 'share of the team\'s last 8 games in which it scored the first TD'},
    'LATE': {'late_share6': "share of the team's 4th-quarter-lead carries, last 6", 'team_win_p_late': 'win probability (as TEAM)'},
    'KING': {'long_prop': 'shrunk share of own earlier rush/receiving TDs of >=30 yards: (long + 8*b)/(TDs + 8), b = dev league share', 'adot12': 'average depth of target, last 12'},
}
ANY_BLOCKS = ['OPP', 'ROLE', 'TREND', 'TEAM', 'INJ', 'REG', 'POS']
BLOCKS_BY_MARKET = {'JP-2': ANY_BLOCKS, 'JP-3': ANY_BLOCKS + ['OPEN'], 'JP-4': ANY_BLOCKS + ['LATE'], 'JP-5': ['OPP', 'POS', 'TEAM', 'KING']}
ALL_BY_MARKET = {'JP-2': ANY_BLOCKS, 'JP-3': ANY_BLOCKS + ['OPEN'], 'JP-4': ANY_BLOCKS + ['LATE'], 'JP-5': ['OPP', 'POS', 'TEAM', 'KING']}
MIN_EFFECT = {'JP-2': 0.001, 'JP-3': 0.005, 'JP-4': 0.005, 'JP-5': 0.005}  # nats per unit (player-game for JP-2, game for JP-3..5)

RULE = {'PROMOTE': 'validation gain > 0 AND holdout gain >= the minimum effect AND the Bonferroni-adjusted cluster interval of the holdout gain has a lower bound > 0',
        'REJECT': 'holdout gain <= 0 OR the adjusted holdout interval lies below the minimum effect',
        'SHADOW': 'anything else (a positive but unproven gain: collect it, do not rank by it)', 'min_effect_nats': MIN_EFFECT,
        'clusters': 'player (JP-2), game (JP-3, JP-4, JP-5), NFL week (top-k precision)'}

COMMON = {'seed': SEED, 'ridge': {'anytime_logit': PEN_ANY, 'game_conditional_logit': PEN_GAME, 'note': 'on standardized features; log Champion rate slope and intercepts unpenalised; fixed, never tuned'},
          'splits': {'development': list(DEV), 'validation': [VAL], 'holdout': [HOLD], 'history_from': 2019, 'refit': 'none: development parameters are applied unchanged to 2024 and 2025'},
          'standardisation': 'median fill, 1st/99th percentile winsorising, mean and sd on development rows only',
          'population': 'Champion-ready appearances 2021-2025 (>= 5 earlier appearances; QBs verified starters) at QB/RB/WR/TE; FB excluded',
          'champion_rate': 'WR/TE/RB: Champion v2 anytime rate (k*cur + 4*prior)/(k+4) over the 12-game window; QB: v1 window mean; floored at 0.01',
          'tds': 'any non-two-point touchdown by the scorer incl. return and defensive scores (td_player_id); a passing TD credits the receiver',
          'sources': ['nflverse play-by-play 2019-2025', 'nflverse weekly player stats, snap counts, schedules and lines 2019-2025'],
          'zone_rates': 'league TD per carry / target by yard-line zone fitted on 2019-2023 plays', 'features': BLOCK_DEFS, 'decision_rule': RULE,
          'leakage': 'player windows use earlier appearances only (shift(1)); lines are pre-game; inactives are pre-game; outcomes from the target game only',
          'limitations': 'No historical prop prices: probabilities are scored, ROI and closing-line value are not. Candidate set = Champion-ready skill players; scorers outside it (backup QBs sneaks, kick returners, '
                         'defence) form the "other" alternative. Inactive status is taken from the appearance table (snaps or a stat line), which equals the inactive list except for players injured on their first snap.'}

SPECS = {
    'JP-1': {**COMMON, 'id': 'JP-1', 'title': 'Jackpot TD structure: are first, anytime and last touchdowns different events?',
             'hypothesis': 'The first TD of a game is more often a passing-game TD and the last TD more often a rushing TD by the favourite (closing out a lead). Directions pre-registered: '
                           'H1 RB share last > first; H2 WR share first > last; H3 rushing-TD share last > first; H4 share scored by the pre-game favourite last > first.',
             'football_rationale': 'Opening drives are scripted and pass-heavy against a rested defence; late scores come from teams ahead running the clock and from goal-line carries.',
             'population': 'all touchdown events 2021-2025 (regular season) in games with >= 2 touchdowns; category by scorer position (QB/RB/WR/TE/other), event kind and team side',
             'comparators': {'first': 'first TD of the game', 'last': 'last TD of the game', 'all': 'average over all TDs of the game'},
             'primary_comparison': 'H1-H4 on validation+holdout pooled (2024-2025), game-clustered 98.75% interval (Bonferroni 4), direction as pre-registered and same sign on development',
             'metric': 'difference in share (last minus first), per game', 'multiple_testing': 'Bonferroni over 4 pre-registered directions; other categories descriptive',
             'markets': ['first TD', 'anytime TD', 'last TD']},
    'JP-2': {**COMMON, 'id': 'JP-2', 'title': 'Anytime TD: free-data scoring-role blocks over the Champion v2 anytime rate',
             'hypothesis': 'Goal-line/red-zone opportunity, snap share, scoring-role trend, team scoring environment, injury-created opportunity and TD-luck regression each add information to the Champion v2 rate.',
             'football_rationale': 'Touchdowns follow short-yardage touches and team scoring; results (TD counts) regress, opportunity persists.',
             'comparators': {'B0': 'Champion v2 anytime rate, p = 1 - exp(-rate), uncalibrated', 'B0c': 'logit(p) recalibrated on development (intercept + slope on log rate): the fair baseline',
                             'B1c': "historical TD totals: last-12 TDs per game, recalibrated the same way", 'M(block)': 'B0c plus one block', 'M(ALL)': 'B0c plus all blocks'},
             'primary_comparison': 'M(block) and M(ALL) vs B0c, log loss per player-game, validation 2024 and holdout 2025, player-clustered Bonferroni intervals over the blocks',
             'secondary': 'single-feature additions (Bonferroni over all features); Brier; top-10 / top-25 weekly precision; B0 and B1c vs B0c',
             'metric': 'mean log loss (primary), Brier, weekly top-k precision', 'multiple_testing': 'Bonferroni over 8 comparisons (7 blocks + ALL); single features over 25',
             'markets': ['anytime TD']},
    'JP-3': {**COMMON, 'id': 'JP-3', 'title': 'FIRST TD: scoring-role and opening-script blocks in a game-level conditional-logit',
             'hypothesis': 'P(first scorer) is not simply proportional to the anytime rate: the slope on log rate differs from 1, position and opening-script usage matter, and the blocks improve the game log loss.',
             'football_rationale': 'The first score comes from the first one or two possessions: scripted plays, the team that scores early, short-yardage specialists matter less than for the last TD.',
             'comparators': {'B0': 'first-TD probability proportional to the Champion anytime rate (slope fixed at 1, "other" intercept fit on development)',
                             'B0c': 'conditional logit on log Champion rate (slope free): the fair baseline', 'B1c': 'same on log(last-12 TD totals per game + 0.05)', 'M(block)': 'B0c plus one block', 'M(ALL)': 'B0c plus all blocks'},
             'primary_comparison': 'M(block) and M(ALL) vs B0c, game log loss (each game one first scorer, "other" alternative), game-clustered Bonferroni intervals over 9 comparisons',
             'secondary': 'top-1/3/5/10 hit rate (scorer in the top k candidates), per-candidate Brier; B0, B1c vs B0c', 'metric': 'mean game log loss, hit rate, Brier',
             'multiple_testing': 'Bonferroni over 9 comparisons (8 blocks + ALL)', 'markets': ['first TD']},
    'JP-4': {**COMMON, 'id': 'JP-4', 'title': 'LAST TD: scoring-role and late-lead blocks in a game-level conditional-logit',
             'hypothesis': 'The last scorer is predicted by the same opportunity blocks but with a different slope, a rushing/favourite tilt (late-lead carry share, win probability) and position effects.',
             'football_rationale': 'A team ahead runs the clock: its carries near the goal line close the game; the trailing team has to pass.',
             'comparators': {'B0': 'last-TD probability proportional to the Champion anytime rate', 'B0c': 'conditional logit on log Champion rate (slope free)', 'B1c': 'same on log(last-12 TD totals per game + 0.05)',
                             'M(block)': 'B0c plus one block', 'M(ALL)': 'B0c plus all blocks'},
             'primary_comparison': 'M(block) and M(ALL) vs B0c, game log loss, game-clustered Bonferroni intervals over 9 comparisons', 'secondary': 'top-k hit rate, Brier',
             'metric': 'mean game log loss, hit rate, Brier', 'multiple_testing': 'Bonferroni over 9 comparisons', 'markets': ['last TD']},
    'JP-5': {**COMMON, 'id': 'JP-5', 'title': 'King of the Endzone: long-TD propensity and target depth over the Champion rate (longest TD of the game)',
             'hypothesis': 'Who owns the longest TD depends on how long a scorer\'s touchdowns tend to be (share of own TDs of 30+ yards, average depth of target), not only on how often he scores.',
             'football_rationale': 'Goal-line backs score from inside the 5 and cannot win a longest-TD market; deep threats and explosive runners can.',
             'comparators': {'B0c': 'conditional logit on log Champion rate (slope free), "other" alternative holds returns, defence and non-candidates',
                             'M(block)': 'B0c plus one block', 'M(ALL)': 'B0c plus OPP, POS, TEAM and KING'},
             'primary_comparison': 'M(KING) vs B0c, game log loss (ties share the win fractionally), game-clustered 98.75% interval', 'secondary': 'other blocks, hit rate',
             'metric': 'mean game log loss, fractional top-k hit', 'multiple_testing': 'Bonferroni over 4 comparisons (3 blocks + ALL)', 'markets': ['King of the Endzone']},
}

# ====================================================================== data
_STATE = {}


def _feature_table(root):
    """Player-game features and outcomes 2019-2025 (zone conversion rates fitted on 2019-2023 plays); cached next to the other free caches."""
    if 'table' in _STATE:
        return _STATE['table'], _STATE['events']
    cache_dir = champion.cache(root)
    table_path, event_path = cache_dir / 'jackpot_features_v1.parquet', cache_dir / 'jackpot_events_v1.parquet'
    if table_path.exists() and event_path.exists():
        table, events = pd.read_parquet(table_path), pd.read_parquet(event_path)
    else:
        apps, events, _rates = jd.build_player_games(root, list(range(2019, 2026)), [2019, 2020, 2021, 2022, 2023])
        table = jd.add_features(apps, events, root)
        table.to_parquet(table_path)
        events.to_parquet(event_path)
    _STATE['table'], _STATE['events'] = table, events
    return table, events


def champion_rate(frame):
    cur, prior, k = frame['cur_atd'].to_numpy(float), frame['prior_atd'].to_numpy(float), frame['k'].to_numpy(float)
    blend = np.where(np.isnan(cur), prior, np.where(np.isnan(prior), cur, (k * cur + C_V2 * prior) / (k + C_V2)))
    rate = np.where(frame.position.to_numpy() == 'QB', frame['champ_atd'].to_numpy(float), blend)
    rate = np.where(np.isnan(rate), frame['champ_atd'].to_numpy(float), rate)
    return np.maximum(rate, LAM_FLOOR)


def _population(root):
    if 'pop' in _STATE:
        return _STATE['pop']
    table, events = _feature_table(root)
    champ = champion_rows(root)
    champ = champ[champ.position.isin(['QB', 'RB', 'WR', 'TE'])][['player_id', 'season', 'week', 'k', 'n', 'cur_atd', 'prior_atd', 'champ_atd']]
    pop = table.merge(champ, on=['player_id', 'season', 'week'], how='inner')
    pop = pop[pop.season >= 2021].copy()
    pop['rate'] = champion_rate(pop)
    pop['log_rate'] = np.log(pop.rate)
    pop['p_champion'] = 1 - np.exp(-pop.rate)
    pop['log_tds12'] = np.log(pop['y_tds__L12'].fillna(0) + 0.05)
    # derived features (names as in BLOCK_DEFS)
    d = pop
    d['xtd12'], d['xtd6'] = d['xtd__L12'], d['xtd__L6']
    d['inside5_touch12'] = d['i5_car__L12'] + d['i5_tgt__L12']
    d['rz_tgt12'] = d['rz_tgt__L12']
    d['snap3'], d['snap6'] = d['offense_pct__L3'], d['offense_pct__L6']
    d['xshare6'] = d['xtd_share__L6']
    d['d_xtd36'] = d['xtd__L3'] - d['xtd__L6']
    d['d_share36'] = d['xtd_share__L3'] - d['xtd_share__L6']
    d['d_snap36'] = d['offense_pct__L3'] - d['offense_pct__L6']
    d['tdres12'] = d['y_tds__L12'] - d['xtd__L12']
    d['tdres6'] = d['y_tds__L6'] - d['xtd__L6']
    d['is_rb'], d['is_te'], d['is_qb'] = (d.position == 'RB').astype(float), (d.position == 'TE').astype(float), (d.position == 'QB').astype(float)
    d['open_share6'] = d['open_share__L6']
    d['late_share6'] = d['late_share__L6']
    d['team_win_p_late'] = d['team_win_p']
    dev_td = events[(events.season.isin(DEV)) & events.kind.isin(['rush', 'receive'])]
    base = float((dev_td.distance >= 30).mean())
    d['long_prop'] = (d['prior_td_long'] + 8 * base) / (d['prior_td_n'] + 8)
    d['adot12'] = d['adot__L12']
    # per-game truths
    games = events.groupby('game_id').agg(n_td=('is_first', 'size'), n_long=('is_longest', 'sum'))
    pop = pop.merge(games, left_on='game_id', right_index=True, how='left')
    pop['n_td'] = pop.n_td.fillna(0)
    pop['n_long'] = pop.n_long.fillna(0)
    feats = sorted({f for b in BLOCK_DEFS.values() for f in b})
    dev = pop[pop.season.isin(DEV)]
    stats = {}
    for f in feats:
        col = pop[f].astype(float)
        med = float(dev[f].median())
        lo, hi = np.nanquantile(dev[f].fillna(med), [0.01, 0.99])
        filled = dev[f].fillna(med).clip(lo, hi)
        stats[f] = (med, float(lo), float(hi), float(filled.mean()), float(filled.std() or 1.0))
        pop[f + '_z'] = (col.fillna(med).clip(lo, hi) - stats[f][3]) / stats[f][4]
    _STATE['pop'], _STATE['stats'] = pop.reset_index(drop=True), stats
    return _STATE['pop']


def cols_for(blocks=(), features=()):
    names = [f for b in blocks for f in BLOCK_DEFS[b]] + list(features)
    return [f + '_z' for f in names]


# ====================================================================== models
def fit_logit(X, y, pen, n_unpenalised=1, iters=60):
    """Ridge logistic regression by Newton steps. Column 0 of X is log rate; an intercept is added; the intercept and the first `n_unpenalised` columns are not penalised."""
    A = np.column_stack([np.ones(len(X)), X])
    w = np.zeros(A.shape[1])
    P = np.full(A.shape[1], pen)
    P[:1 + n_unpenalised] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(A @ w, -30, 30)))
        g = A.T @ (p - y) + P * w
        H = (A * (p * (1 - p))[:, None]).T @ A + np.diag(P) + 1e-9 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def predict_logit(w, X):
    return 1 / (1 + np.exp(-np.clip(np.column_stack([np.ones(len(X)), X]) @ w, -30, 30)))


def _clogit_parts(theta, X, gid, G):
    u0, w = theta[0], theta[1:]
    s = np.clip(X @ w, -30, 30)
    e = np.exp(s)
    D = np.exp(u0) + np.bincount(gid, weights=e, minlength=G)
    return e, D


def fit_clogit(X, gid, y, pen, n_unpenalised=1, fixed_slope=None):
    """Game-level conditional logit with an 'other' alternative (utility u0, no features). y holds each candidate's (fractional) win weight; other = 1 - sum per game.
    Column 0 of X is log rate. If fixed_slope is given, the coefficient of column 0 is held there (B0)."""
    G = int(gid.max()) + 1
    k = X.shape[1]
    P = np.full(k, pen)
    P[:n_unpenalised] = 0.0
    if fixed_slope is not None:
        free_idx = np.arange(1, k)
        base_s = fixed_slope * X[:, 0]
        Xf = X[:, 1:]
    else:
        free_idx = np.arange(k)
        base_s = np.zeros(len(X))
        Xf = X
    Pf = P[free_idx]
    y_other = 1 - np.bincount(gid, weights=y, minlength=G)

    def objective(theta):
        u0, w = theta[0], theta[1:]
        s = np.clip(base_s + (Xf @ w if len(w) else 0.0), -30, 30)
        e = np.exp(s)
        D = np.exp(u0) + np.bincount(gid, weights=e, minlength=G)
        p = e / D[gid]
        po = np.exp(u0) / D
        loss = -(y * np.log(np.maximum(p, 1e-300))).sum() - (y_other * np.log(np.maximum(po, 1e-300))).sum() + 0.5 * (Pf * w * w).sum()
        grad_s = -(y - p)  # d loss / d s_i  with weights summing to 1 per game
        gw = Xf.T @ grad_s + Pf * w if len(w) else np.zeros(0)
        g0 = -(y_other - po).sum()
        return loss, np.concatenate([[g0], gw])

    theta0 = np.zeros(1 + Xf.shape[1])
    res = minimize(objective, theta0, jac=True, method='L-BFGS-B', options={'maxiter': 500})
    theta = np.zeros(1 + k)
    theta[0] = res.x[0]
    theta[1 + free_idx] = res.x[1:]
    if fixed_slope is not None:
        theta[1] = fixed_slope
    return theta


def predict_clogit(theta, X, gid):
    G = int(gid.max()) + 1
    e, D = _clogit_parts(theta, X, gid, G)
    return e / D[gid], np.exp(theta[0]) / D


# ====================================================================== evaluation
def _conf(n_comparisons):
    return 1 - 0.05 / max(1, n_comparisons)


def _rows(pop, season):
    return pop[pop.season == season].reset_index(drop=True)


def _gid(frame):
    codes, uniq = pd.factorize(frame.game_id)
    return codes, uniq


def game_targets(frame, market):
    """Per-row win weight for a game market and the mask of games that enter (>= 1 qualifying touchdown)."""
    if market == 'first':
        y, ok = frame.y_first.to_numpy(float), frame.n_td.to_numpy() >= 1
    elif market == 'last':
        y, ok = frame.y_last.to_numpy(float), frame.n_td.to_numpy() >= 1
    else:
        y, ok = (frame.y_longest / frame.n_long.replace(0, np.nan)).fillna(0).to_numpy(float), frame.n_long.to_numpy() >= 1
    return y, ok


def _game_frame(pop, season, market):
    frame = _rows(pop, season)
    y, ok = game_targets(frame, market)
    frame, y = frame[ok].reset_index(drop=True), y[ok]
    gid, uniq = _gid(frame)
    return frame, y, gid, uniq


def game_metrics(p, po, y, gid, G, ks=TOPK_GAME):
    yo = 1 - np.bincount(gid, weights=y, minlength=G)
    ll = -(np.bincount(gid, weights=y * np.log(np.maximum(p, 1e-300)), minlength=G) + yo * np.log(np.maximum(po, 1e-300)))
    order = np.lexsort((-p, gid))
    rank = np.empty(len(p), int)
    sorted_gid = gid[order]
    starts = np.r_[0, np.flatnonzero(np.diff(sorted_gid)) + 1]
    rank[order] = np.arange(len(p)) - np.repeat(starts, np.diff(np.r_[starts, len(p)]))
    hits = {k: np.bincount(gid, weights=y * (rank < k), minlength=G) for k in ks}
    brier = np.bincount(gid, weights=(p - y) ** 2, minlength=G) / np.bincount(gid, minlength=G)
    return {'ll': ll, 'hit': hits, 'brier': brier}


def row_metrics_any(p, y, frame, ks=TOPK_SLATE):
    ll = -(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1)))
    brier = (p - y) ** 2
    slate = (frame.season * 100 + frame.week).to_numpy()
    codes, _ = pd.factorize(slate)
    order = np.lexsort((-p, codes))
    rank = np.empty(len(p), int)
    s = codes[order]
    starts = np.r_[0, np.flatnonzero(np.diff(s)) + 1]
    rank[order] = np.arange(len(p)) - np.repeat(starts, np.diff(np.r_[starts, len(p)]))
    prec = {k: np.bincount(codes, weights=y * (rank < k)) / k for k in ks}
    return {'ll': ll, 'brier': brier, 'prec': prec}


def _summ(values, groups, conf):
    m, lo, hi = _cluster_ci(values, groups, conf)
    return [m, lo, hi]


def judge(gain_v, gain_h, ci_h, min_effect):
    if gain_h <= 0 or ci_h[1] < min_effect:
        return 'REJECT'
    if gain_v > 0 and gain_h >= min_effect and ci_h[0] > 0:
        return 'PROMOTE'
    return 'SHADOW'


def fit_models(market, pop, specs):
    """Fit every named model on the development seasons. specs: name -> dict(cols=[...], fixed_slope=None). Returns name -> parameters."""
    out = {}
    if market == 'any':
        dev = pop[pop.season.isin(DEV)]
        for name, s in specs.items():
            X = np.column_stack([dev[s['base']].to_numpy(float)] + ([dev[s['cols']].to_numpy(float)] if s['cols'] else []))
            out[name] = fit_logit(X, dev.y_any.to_numpy(float), PEN_ANY)
    else:
        frames = [_game_frame(pop, s, market) for s in DEV]
        frame = pd.concat([f[0] for f in frames], ignore_index=True)
        y = np.concatenate([f[1] for f in frames])
        gid = pd.factorize(frame.game_id)[0]
        for name, s in specs.items():
            X = np.column_stack([frame[s['base']].to_numpy(float)] + ([frame[s['cols']].to_numpy(float)] if s['cols'] else []))
            out[name] = fit_clogit(X, gid, y, PEN_GAME, fixed_slope=s.get('fixed_slope'))
    return out


def evaluate_market(spec_id, root):
    """Fit on development, score 2024 and 2025, compare every block with B0c."""
    pop = _population(root)
    market = {'JP-2': 'any', 'JP-3': 'first', 'JP-4': 'last', 'JP-5': 'king'}[spec_id]
    blocks = BLOCKS_BY_MARKET[spec_id]
    specs = {'B0c': dict(base='log_rate', cols=[]), 'ALL': dict(base='log_rate', cols=cols_for(ALL_BY_MARKET[spec_id]))}
    if market in ('any', 'first', 'last'):
        specs['B1c'] = dict(base='log_tds12', cols=[])
    if market in ('first', 'last', 'king'):
        specs['B0'] = dict(base='log_rate', cols=[], fixed_slope=1.0)
    for b in blocks:
        specs[b] = dict(base='log_rate', cols=cols_for([b]))
    if market == 'any':
        for b in blocks:
            for f in BLOCK_DEFS[b]:
                specs['f:' + f] = dict(base='log_rate', cols=cols_for(features=[f]))
    params = fit_models(market, pop, specs)
    n_block = len(blocks) + 1
    result = {'seasons': {}, 'blocks': {}, 'models': {}, 'n_block_comparisons': n_block}
    ev = {}
    for label, season in (('validation', VAL), ('holdout', HOLD)):
        if market == 'any':
            frame = _rows(pop, season)
            y = frame.y_any.to_numpy(float)
            per = {}
            for name, s in specs.items():
                X = np.column_stack([frame[s['base']].to_numpy(float)] + ([frame[s['cols']].to_numpy(float)] if s['cols'] else []))
                p = predict_logit(params[name], X)
                per[name] = row_metrics_any(p, y, frame)
            per['B0'] = row_metrics_any(frame.p_champion.to_numpy(float), y, frame)
            groups, slate_groups = frame.player_id.to_numpy(), None
            result['seasons'][label] = {'n': int(len(frame)), 'players': int(frame.player_id.nunique()), 'base_rate': float(y.mean()), 'slates': int(frame[['season', 'week']].drop_duplicates().shape[0])}
            ev[label] = (per, groups, frame)
        else:
            frame, y, gid, uniq = _game_frame(pop, season, market)
            G = len(uniq)
            per = {}
            for name, s in specs.items():
                X = np.column_stack([frame[s['base']].to_numpy(float)] + ([frame[s['cols']].to_numpy(float)] if s['cols'] else []))
                p, po = predict_clogit(params[name], X, gid)
                per[name] = game_metrics(p, po, y, gid, G)
            groups = np.arange(G)
            coverage = float(np.bincount(gid, weights=y, minlength=G).mean())
            result['seasons'][label] = {'games': int(G), 'candidates': int(len(frame)), 'candidate_coverage': coverage, 'mean_candidates_per_game': float(len(frame) / G)}
            ev[label] = (per, groups, frame)
    conf_block = _conf(n_block)
    compared = list(specs) + (['B0'] if market == 'any' else [])
    for name in compared:
        cell = {}
        for label in ('validation', 'holdout'):
            per, groups, frame = ev[label]
            m = per[name]
            if market == 'any':
                cell[label] = {'logloss': float(m['ll'].mean()), 'brier': float(m['brier'].mean()), 'prec': {str(k): float(v.mean()) for k, v in m['prec'].items()}}
            else:
                cell[label] = {'logloss': float(m['ll'].mean()), 'brier': float(m['brier'].mean()), 'hit': {str(k): float(v.mean()) for k, v in m['hit'].items()}}
        result['models'][name] = cell
    base_name = 'B0c'
    for name in compared:
        if name == base_name:
            continue
        is_feature = name.startswith('f:')
        n_cmp = 25 if is_feature else n_block
        conf = _conf(n_cmp)
        cell = {}
        for label in ('validation', 'holdout'):
            per, groups, frame = ev[label]
            gain = per[base_name]['ll'] - per[name]['ll']  # positive = better than B0c
            entry = {'gain_logloss': _summ(gain, groups, 0.95), 'gain_logloss_adj': _summ(gain, groups, conf)}
            if market == 'any':
                brier_gain = per[base_name]['brier'] - per[name]['brier']
                entry['gain_brier'] = _summ(brier_gain, groups, 0.95)
                slate_codes = pd.factorize((frame.season * 100 + frame.week).to_numpy())[0]
                entry['gain_prec'] = {str(k): _summ(per[name]['prec'][k] - per[base_name]['prec'][k], np.arange(len(per[name]['prec'][k])), 0.95) for k in TOPK_SLATE}
            else:
                brier_gain = per[base_name]['brier'] - per[name]['brier']
                entry['gain_brier'] = _summ(brier_gain, groups, 0.95)
                entry['gain_hit'] = {str(k): _summ(per[name]['hit'][k] - per[base_name]['hit'][k], groups, 0.95) for k in TOPK_GAME}
            cell[label] = entry
        gv, gh = cell['validation']['gain_logloss'][0], cell['holdout']['gain_logloss'][0]
        cell['verdict'] = 'BASELINE-COMPARISON' if name in ('B0', 'B1c') else judge(gv, gh, cell['holdout']['gain_logloss_adj'][1:], MIN_EFFECT[spec_id])
        cell['n_comparisons'] = n_cmp
        result['blocks'][name] = cell
    # coefficients (standardised features), development fit: shown so the markets can be compared
    if market == 'any':
        result['coefficients_ALL'] = dict(zip(['intercept', 'log_rate'] + [c[:-2] for c in specs['ALL']['cols']], [float(x) for x in params['ALL']]))
        result['coefficients_B0c'] = dict(zip(['intercept', 'log_rate'], [float(x) for x in params['B0c']]))
    else:
        result['coefficients_ALL'] = dict(zip(['other_utility'] + ['log_rate'] + [c[:-2] for c in specs['ALL']['cols']], [float(x) for x in params['ALL']]))
        result['coefficients_B0c'] = dict(zip(['other_utility', 'log_rate'], [float(x) for x in params['B0c']]))
    return result


def _market_status(result, spec_id):
    verdicts = {k: v['verdict'] for k, v in result['blocks'].items() if not k.startswith('f:') and k not in ('B0', 'B1c')}
    if 'PROMOTE' in verdicts.values():
        return 'PROMISING'
    if all(v == 'REJECT' for v in verdicts.values()):
        return 'REJECTED'
    return 'INCONCLUSIVE'


# ====================================================================== JP-1: structure
def _event_frame(root):
    table, events = _feature_table(root)
    games = champion.load_games(root)
    games = games[games.game_type == 'REG']
    fav = {}
    for r in games.itertuples():
        fav[(r.game_id, r.home_team)] = r.spread_line
        fav[(r.game_id, r.away_team)] = -r.spread_line
    ev = events[(events.season >= 2021) & (events.n_td >= 2)].copy()
    pos = table.drop_duplicates(['game_id', 'player_id']).set_index(['game_id', 'player_id']).position
    ev['pos'] = [pos.get((g, p), 'other') if k in ('rush', 'receive') else 'other' for g, p, k in zip(ev.game_id, ev.td_player_id, ev.kind)]
    ev['fav'] = [fav.get((g, t), np.nan) > 0 for g, t in zip(ev.game_id, ev.td_team)]
    ev['short'] = ev.distance <= 5
    ev['rush_kind'] = ev.kind == 'rush'
    ev['pass_kind'] = ev.kind == 'receive'
    return ev


CATS = {'QB': lambda e: e.pos == 'QB', 'RB': lambda e: e.pos == 'RB', 'WR': lambda e: e.pos == 'WR', 'TE': lambda e: e.pos == 'TE', 'other_scorer': lambda e: e.pos == 'other',
        'rushing TD': lambda e: e.rush_kind, 'receiving TD': lambda e: e.pass_kind, 'return/defence TD': lambda e: e.kind.isin(['return', 'defense']),
        'favourite scores': lambda e: e.fav, 'TD within 5 yards': lambda e: e.short}
HYP = {'H1': ('RB', 'last > first'), 'H2': ('WR', 'first > last'), 'H3': ('rushing TD', 'last > first'), 'H4': ('favourite scores', 'last > first')}


def run_jp1(root, manifest):
    ev = _event_frame(root)
    out = {'categories': {}, 'hypotheses': {}}
    periods = {'development 2021-2023': ev.season.isin(DEV), 'validation 2024': ev.season == VAL, 'holdout 2025': ev.season == HOLD, 'pooled 2024-2025': ev.season.isin([VAL, HOLD]),
              'all 2021-2025': ev.season >= 2021}
    for cat, fn in CATS.items():
        flag = fn(ev).astype(float)
        e = ev.assign(flag=flag)
        per_game = e.groupby('game_id').apply(lambda g: pd.Series({'first': g.flag[g.is_first].sum(), 'last': g.flag[g.is_last].sum(), 'all': g.flag.mean(), 'season': g.season.iloc[0]}), include_groups=False)
        cell = {}
        for label, mask in periods.items():
            seasons = ev[mask].season.unique()
            sub = per_game[per_game.season.isin(seasons)]
            if not len(sub):
                continue
            groups = np.arange(len(sub))
            cell[label] = {'games': int(len(sub)), 'share_first': float(sub['first'].mean()), 'share_all': float(sub['all'].mean()), 'share_last': float(sub['last'].mean()),
                           'last_minus_first': _summ((sub['last'] - sub['first']).to_numpy(), groups, 0.95), 'first_minus_all': _summ((sub['first'] - sub['all']).to_numpy(), groups, 0.95),
                           'last_minus_all': _summ((sub['last'] - sub['all']).to_numpy(), groups, 0.95)}
            if label == 'pooled 2024-2025':
                cell[label]['last_minus_first_adj'] = _summ((sub['last'] - sub['first']).to_numpy(), groups, 1 - 0.05 / 4)
        out['categories'][cat] = cell
    confirmed = {}
    for h, (cat, direction) in HYP.items():
        cell = out['categories'][cat]
        pooled, dev = cell['pooled 2024-2025'], cell['development 2021-2023']
        m, lo, hi = pooled['last_minus_first_adj']
        sign = 1 if direction.startswith('last') else -1
        ok = (sign * m > 0) and ((lo > 0) if sign > 0 else (hi < 0)) and (sign * dev['last_minus_first'][0] > 0)
        confirmed[h] = {'category': cat, 'direction': direction, 'pooled_diff': pooled['last_minus_first'], 'pooled_diff_adj_ci': pooled['last_minus_first_adj'], 'development_diff': dev['last_minus_first'][0], 'confirmed': bool(ok)}
    out['hypotheses'] = confirmed
    # role-tier table (descriptive): scorer rates by the team-relative xTD share of the last 6 games
    pop = _population(root)
    pop = pop.assign(tier=pd.cut(pop['xtd_share__L6'].fillna(0), [-1, 0.05, 0.15, 0.30, 2.0], labels=['FRINGE <5%', 'TERTIARY 5-15%', 'SECONDARY 15-30%', 'PRIMARY >=30%']))
    tiers = {}
    for label, mask in (('development', pop.season.isin(DEV)), ('validation', pop.season == VAL), ('holdout', pop.season == HOLD)):
        sub = pop[mask]
        g = sub.groupby('tier', observed=True).agg(n=('y_any', 'size'), anytime=('y_any', 'mean'), first=('y_first', 'mean'), last=('y_last', 'mean'), champion_rate=('p_champion', 'mean'))
        g['first_per_anytime'] = g['first'] / g['anytime']
        g['last_per_anytime'] = g['last'] / g['anytime']
        tiers[label] = {k: {c: float(v) for c, v in row.items()} for k, row in g.iterrows()}
    out['role_tiers'] = tiers
    confirmed_n = sum(v['confirmed'] for v in confirmed.values())
    out['summary'] = {'confirmed': [h for h, v in confirmed.items() if v['confirmed']], 'games': int(ev.game_id.nunique())}
    return out, ('PROMISING' if confirmed_n >= 2 else 'INCONCLUSIVE')


# ====================================================================== runners
def _runner(spec_id):
    def run(root, manifest):
        result = evaluate_market(spec_id, root)
        status = _market_status(result, spec_id)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        existing = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
        existing[spec_id] = result
        OUT.write_text(json.dumps(existing, indent=1, sort_keys=True), encoding='utf-8')
        return result, status
    return run


def run_jp1_and_save(root, manifest):
    result, status = run_jp1(root, manifest)
    existing = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    existing['JP-1'] = result
    OUT.write_text(json.dumps(existing, indent=1, sort_keys=True), encoding='utf-8')
    return result, status


RUNNERS = {'JP-1': run_jp1_and_save, 'JP-2': _runner('JP-2'), 'JP-3': _runner('JP-3'), 'JP-4': _runner('JP-4'), 'JP-5': _runner('JP-5')}
