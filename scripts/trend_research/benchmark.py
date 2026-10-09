"""Out-of-sample benchmark of the PRODUCTION system from its own frozen 2026 records (data/public_tracker).

Every prediction was written before kickoff with the model's probability, the quoted price and the cohort; settlements and sampled closing prices are
separate records, so nothing here reconstructs unavailable information. Units of analysis: one record per (group, contract); results are clustered by
game for uncertainty because props in one game are correlated. Pushes (refunds) are excluded from win-rate/Brier/log-loss and returned in ROI.
"""
import datetime
import math
from collections import defaultdict

import numpy as np

LATE_QUOTE_HOURS = 6.0
FAMILY = {'player_receiving_yards': 'rec_yds', 'player_receptions': 'receptions', 'player_rushing_yards': 'rush_yds', 'player_passing_yards': 'pass_yds',
          'player_passing_tds': 'pass_tds', 'atd': 'anytime_td', 'totals': 'game_total', 'spreads': 'game_spread', 'h2h': 'game_moneyline'}


def _ts(value):
    return datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def frame(records):
    """Join predictions with their latest settlement and last near-kickoff closing record."""
    settle = {}
    closing = {}
    for r in records:
        p = r['payload']
        if r['kind'] == 'settlement' and p['status'] in ('win', 'loss', 'refund'):
            settle[p['prediction_id']] = p
        elif r['kind'] == 'closing' and p.get('decimal') and p.get('quoted_at'):
            previous = closing.get(p['prediction_id'])
            if previous is None or p['quoted_at'] > previous['quoted_at']:
                closing[p['prediction_id']] = p
    rows = []
    for r in records:
        if r['kind'] != 'prediction':
            continue
        p = r['payload']
        s = settle.get(p['id'])
        if not s:
            continue
        c = closing.get(p['id'])
        if c is not None:  # none of the records is flagged near-kickoff: accept a quote only if it was taken within 6 hours of kickoff
            late = (_ts(p['kickoff']) - _ts(c['quoted_at'])).total_seconds() / 3600
            c = c if 0 <= late <= LATE_QUOTE_HOURS else None
        rows.append({'group': p['tracking_group'], 'family': FAMILY.get(p['market'], p['market']), 'game': f"{p.get('away')}@{p.get('home')}|{str(p['kickoff'])[:10]}",
                     'prob': p['probability'], 'push': (p.get('model_evidence') or {}).get('push') or 0.0, 'dec': p['odds'], 'status': s['status'],
                     'close_dec': c['decimal'] if c else None, 'close_prob': c['probability'] if c else None, 'side': p['side'], 'n': (p.get('model_evidence') or {}).get('n'),
                     'cohort': p.get('model_cohort')})
    return rows


def _boot(values_by_game, stat, draws=1000, seed=7):
    rng = np.random.default_rng(seed)
    games = list(values_by_game)
    out = []
    for _ in range(draws):
        pick = rng.choice(len(games), size=len(games), replace=True)
        out.append(stat(np.concatenate([values_by_game[games[i]] for i in pick])))
    return [float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))]


def summarize(rows):
    """Metrics for a set of settled predictions (wins and losses only for probability metrics)."""
    graded = [r for r in rows if r['status'] in ('win', 'loss')]
    if not graded:
        return None
    p = np.array([r['prob'] for r in graded], float)
    # the stored probability is P(win) with pushes held separately; condition on a decided bet
    q = np.array([r['prob'] / (1 - r['push']) if r['push'] < 1 else r['prob'] for r in graded], float)
    y = np.array([1.0 if r['status'] == 'win' else 0.0 for r in graded])
    q = np.clip(q, 1e-6, 1 - 1e-6)
    dec = np.array([r['dec'] for r in graded], float)
    brier = float(np.mean((q - y) ** 2))
    logloss = float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))
    implied = 1 / dec
    market_brier = float(np.mean((implied - y) ** 2))
    profit = np.where(y == 1, dec - 1, -1.0)
    by_game = defaultdict(list)
    for r, pr in zip(graded, profit):
        by_game[r['game']].append(pr)
    by_game = {g: np.array(v) for g, v in by_game.items()}
    refund_profit = [0.0 for r in rows if r['status'] == 'refund']
    clv = [r['dec'] / r['close_dec'] - 1 for r in rows if r['close_dec']]
    close_graded = [r for r in graded if r['close_prob'] is not None]
    cm = None
    if close_graded:
        yc = np.array([1.0 if r['status'] == 'win' else 0.0 for r in close_graded])
        qc = np.array([r['prob'] / (1 - r['push']) if r['push'] < 1 else r['prob'] for r in close_graded], float).clip(1e-6, 1 - 1e-6)
        cp = np.array([r['close_prob'] for r in close_graded], float).clip(1e-6, 1 - 1e-6)
        cm = {'n': len(close_graded), 'model_brier': float(np.mean((qc - yc) ** 2)), 'closing_novig_brier': float(np.mean((cp - yc) ** 2))}
    # calibration: deciles of predicted probability
    order = np.argsort(q)
    bins = []
    for chunk in np.array_split(order, min(5, max(1, len(order) // 40))) if len(order) >= 40 else []:
        bins.append({'n': int(len(chunk)), 'predicted': float(q[chunk].mean()), 'actual': float(y[chunk].mean())})
    return {'n_graded': len(graded), 'n_refund': len(rows) - len(graded), 'games': len(by_game), 'mean_predicted': float(q.mean()), 'win_rate': float(y.mean()),
            'brier': brier, 'log_loss': logloss, 'brier_of_price_implied_prob': market_brier,
            'roi_flat_stake': float(profit.mean()), 'roi_ci95_by_game': _boot(by_game, lambda v: float(v.mean())) if len(by_game) >= 20 else None,
            'mean_clv_vs_sampled_close': float(np.mean(clv)) if clv else None, 'n_with_close': len(clv), 'vs_closing_novig': cm, 'calibration_bins': bins}


def benchmark(records, groups=('all_projection', 'best_model', 'going_picks_v3', 'going_picks_v2', 'going_picks_v1')):
    rows = frame(records)
    out = {}
    for group in groups:
        in_group = [r for r in rows if r['group'] == group]
        out[group] = {'all': summarize(in_group)}
        for family in sorted({r['family'] for r in in_group}):
            result = summarize([r for r in in_group if r['family'] == family])
            if result and result['n_graded'] >= 20:
                out[group][family] = result
    return out
