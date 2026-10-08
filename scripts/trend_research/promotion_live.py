"""Champion v1 vs v2 on settled 2026 predictions with the REAL posted lines (the only unseen data).

One record per contract; only where the reconstructed v1 mean equals the frozen projection_mean (so injury/pressure adjustments are out of the comparison and the
difference is purely the policy). Probabilities are the production conventions: counts CDF(floor) / CDF(ceil-1); yardage rounded lognormal F(floor+0.5) / F(ceil-0.5).
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import nbinom, norm, poisson

from . import champion
from .experiments3 import _eastern_date
from .promotion_check import COUNT_LINES, _blend_mean, cp

LIVE_MARKETS = {'player_receptions': 'receptions', 'player_receiving_yards': 'rec_yds', 'player_rushing_yards': 'rush_yds', 'atd': 'atd',
                'player_passing_yards': 'pass_yds', 'player_passing_tds': 'pass_tds'}


def probs(market, row, line, policy, version):
    """(P over, P under) under policy version 'v1' or 'v2'; None when the model cannot price the contract."""
    spec = cp.market_policy(policy, market) if version == 'v2' else None
    if market in COUNT_LINES:
        mean = _blend_mean(row, market, spec['mean']['c']) if spec else row['champ_' + market]
        if mean != mean:
            return None
        mean = max(mean, 1e-9)
        if spec and spec.get('shape', {}).get('family') == 'nbinom':
            n = 1.0 / spec['shape']['phi']
            dist = nbinom(n, n / (n + mean))
        else:
            dist = poisson(mean)
        return float(dist.sf(math.floor(line))), float(dist.cdf(math.ceil(line) - 1))
    if spec:
        mean = _blend_mean(row, market, spec['mean']['c'])
        if mean != mean:
            return None
        fields = cp.pooled_lognormal(mean, row['n'], 1 - row['pw_' + market], row['position'], spec['shape'])
        if fields is None:
            return None
        mu_log, sigma, p0 = fields['mu_log'], fields['sigma_log'], fields['zero_mass']
    else:
        pw, pm, ps = row['pw_' + market], row['pm_' + market], row['ps_' + market]
        if not (pw > 0 and pm > 0) or ps != ps:
            return None
        sigma2 = math.log1p((ps / pm) ** 2)
        mu_log, sigma, p0 = math.log(pm) - sigma2 / 2, math.sqrt(sigma2), 1 - pw

    def cdf(x):
        if x <= 0:
            return p0
        if sigma <= 0:
            return p0 + (1 - p0) * (1.0 if x >= math.exp(mu_log) else 0.0)
        return p0 + (1 - p0) * float(norm.cdf((math.log(x) - mu_log) / sigma))
    return 1 - cdf(math.floor(line) + 0.5), cdf(math.ceil(line) - 0.5)


def live_2026(root, policy, refresh=True):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tracker_store import load_tracker
    cache = champion.cache(root) / 'stats_player_week_2026.csv'
    if refresh and cache.exists():
        cache.unlink()
    schedule = champion.load_games(root)
    schedule = schedule[(schedule.season == 2026) & (schedule.game_type == 'REG')]
    week_of = {(r.home_team, r.away_team, r.gameday): r.week for r in schedule.itertuples()}
    frame = champion.champion_frame(root, {2026})
    index = {(r['player_id'], r['week']): r for r in frame.to_dict('records')}
    records = load_tracker(str(Path(__file__).resolve().parents[2] / 'data'))['records']
    settle = {r['payload']['prediction_id']: r['payload'] for r in records if r['kind'] == 'settlement' and r['payload']['status'] in ('win', 'loss')}
    seen, rows = set(), []
    for r in sorted((x for x in records if x['kind'] == 'prediction'), key=lambda x: x['observed_at']):
        p = r['payload']
        market = LIVE_MARKETS.get(p['market'])
        if not market or p['id'] not in settle or p.get('sport') != 'nfl' or not p.get('profile_id') or p['canonical_contract'] in seen:
            continue
        me = p.get('model_evidence') or {}
        week = week_of.get((p['home'], p['away'], _eastern_date(p['kickoff'])))
        row = index.get((p['profile_id'], week))
        if row is None or 'projection_mean' not in me:
            continue
        mine = row.get('champ_' + market)
        if mine is None or mine != mine or abs(me['projection_mean'] - mine) > 1e-6:
            continue
        line = float(p['line']) if p.get('line') is not None else 0.5
        side_over = p['side'] in ('Over', 'Yes')
        pr1, pr2 = probs(market, row, line, policy, 'v1'), probs(market, row, line, policy, 'v2')
        if pr1 is None or pr2 is None:
            continue
        seen.add(p['canonical_contract'])

        def decided(pr):
            win, lose = (pr[0], pr[1]) if side_over else (pr[1], pr[0])
            return win / (win + lose) if win + lose > 0 else 0.5
        rows.append({'market': market, 'game': f"{p['away']}@{p['home']}", 'y': 1.0 if settle[p['id']]['status'] == 'win' else 0.0, 'p1': decided(pr1), 'p2': decided(pr2),
                     'frozen': float(p['probability']), 'k': int(row['k']), 'week': int(week), 'player_id': p['profile_id']})
    df = pd.DataFrame(rows)
    out = {'n_total': int(len(df)), 'markets': {}}
    for market, sub in list(df.groupby('market')) + [('ALL', df)]:
        e1, e2 = (sub.p1.clip(1e-6, 1 - 1e-6) - sub.y) ** 2, (sub.p2.clip(1e-6, 1 - 1e-6) - sub.y) ** 2
        by_game = {}
        for g, a, b in zip(sub.game, e1, e2):
            by_game.setdefault(g, []).append(a - b)
        names = list(by_game)
        rng = np.random.default_rng(20261008)
        boots = [np.mean([d for i in rng.choice(len(names), size=len(names), replace=True) for d in by_game[names[i]]]) for _ in range(1000)]
        out['markets'][market] = {'n': int(len(sub)), 'games': len(names), 'brier_v1': float(e1.mean()), 'brier_v2': float(e2.mean()), 'relative_gain': float((e1.mean() - e2.mean()) / e1.mean()),
                                  'difference_ci95': [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))], 'win_rate': float(sub.y.mean()),
                                  'mean_p_v1': float(sub.p1.mean()), 'mean_p_v2': float(sub.p2.mean()),
                                  'share_p_beyond_0.9_v1': float((sub.p1.sub(0.5).abs() > 0.4).mean()), 'share_p_beyond_0.9_v2': float((sub.p2.sub(0.5).abs() > 0.4).mean()),
                                  'rows_with_k_le_2': int((sub.k <= 2).sum())}
    return out
