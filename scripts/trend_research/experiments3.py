"""E10: prospective check of the E7 blend on the production system's own frozen 2026 predictions."""
from pathlib import Path

import numpy as np
from scipy.stats import poisson

from . import champion
from .experiments2 import C_GRID, COMMON, _blend, _eligible, champion_rows

SPECS = {'E10': {**COMMON, 'id': 'E10', 'title': 'Prospective check (2026): would the E7 blend have improved the probabilities the production system actually froze?',
                 'hypothesis': 'Replacing the Champion mean with the learned-shrinkage blend (W3) improves the Brier score of the frozen Poisson probabilities on settled 2026 predictions.',
                 'football_rationale': 'Same as E7; this applies it to real, time-stamped production output that no analysis has seen.',
                 'population': 'settled 2026 predictions in the count markets (player_receptions primary; player_passing_tds descriptive) from every tracking group, one record per (contract, group), only where the frozen '
                               'projection_mean equals the reconstructed Champion mean to 1e-6 (so only the blend differs; injury adjustments excluded)',
                 'blend_parameter': 'c per market = argmin MAE of W3 over ALL 2021-2025 target rows (the E7 procedure), fixed before looking at any 2026 outcome',
                 'metric': 'Brier score of P(win | decided bet), paired by prediction, game-clustered bootstrap, 95% CI (one primary comparison)',
                 'primary_comparison': 'receptions: W3 Poisson probability vs frozen Champion probability. PROMISING needs >= 1% relative Brier improvement with a CI below 0',
                 'multiple_testing': 'none (single primary); pass_tds is descriptive',
                 'sources': ['data/public_tracker frozen predictions and settlements', 'nflverse weekly stats 2019-2026'], 'leakage': 'blend inputs are games before each target week; c fixed on 2021-2025 only',
                 'markets': ['receptions'], 'limitations': 'about four weeks of 2026 and a few dozen games: low power. A positive result would be directional, not proof.'}}


def _eastern_date(kickoff):
    """nflverse `gameday` is the local (US Eastern) calendar date; tracker kickoffs are UTC, so a night game would otherwise land on the next day."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    moment = datetime.fromisoformat(str(kickoff).replace('Z', '+00:00'))
    return moment.astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')


def run_e10(root, manifest):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tracker_store import load_tracker
    hist = champion_rows(root)
    c_final = {}
    for market in ('receptions', 'pass_tds'):
        rows = _eligible(hist, market)
        c_final[market] = min(C_GRID, key=lambda c: float(np.abs(rows['y_' + market].to_numpy(float) - _blend(rows, market, c)).mean()))
    games = champion.load_games(root)
    games = games[(games.season == 2026) & (games.game_type == 'REG')]
    week_of = {(r.home_team, r.away_team, r.gameday): r.week for r in games.itertuples()}
    frame = champion.champion_frame(root, {2026})
    index = {(r.player_id, r.week): r for r in frame.itertuples()}
    records = load_tracker(str(Path(__file__).resolve().parents[2] / 'data'))['records']
    settle = {r['payload']['prediction_id']: r['payload'] for r in records if r['kind'] == 'settlement' and r['payload']['status'] in ('win', 'loss')}
    seen, rows = set(), []
    for r in sorted((x for x in records if x['kind'] == 'prediction'), key=lambda x: x['observed_at']):
        p = r['payload']
        market = {'player_receptions': 'receptions', 'player_passing_tds': 'pass_tds'}.get(p['market'])
        if not market or p['id'] not in settle or p.get('sport') != 'nfl' or not p.get('profile_id'):
            continue
        key = p['canonical_contract']  # one record per contract: groups repeat the same bet
        me = p.get('model_evidence') or {}
        week = week_of.get((p['home'], p['away'], _eastern_date(p['kickoff'])))
        got = index.get((p['profile_id'], week))
        if got is None or 'projection_mean' not in me or key in seen:
            continue
        mine = getattr(got, 'champ_' + market)
        if mine != mine or abs(me['projection_mean'] - mine) > 1e-6:
            continue
        seen.add(key)
        cur, prior, k = getattr(got, 'cur_' + market), getattr(got, 'prior_' + market), got.k
        c = c_final[market]
        lam = prior if cur != cur else cur if prior != prior else (k * cur + c * prior) / (k + c)
        line, over = float(p['line']), p['side'] == 'Over'

        def decided_prob(lam_):
            win = 1 - poisson.cdf(np.floor(line), lam_) if over else poisson.cdf(np.ceil(line) - 1, lam_)
            lose = poisson.cdf(np.ceil(line) - 1, lam_) if over else 1 - poisson.cdf(np.floor(line), lam_)
            return float(win / (win + lose)) if win + lose > 0 else 0.5
        rows.append({'market': market, 'game': f"{p['away']}@{p['home']}", 'y': 1.0 if settle[p['id']]['status'] == 'win' else 0.0,
                     'old': decided_prob(me['projection_mean']), 'new': decided_prob(lam), 'k': int(k)})
    out = {}
    for market in ('receptions', 'pass_tds'):
        sub = [r for r in rows if r['market'] == market]
        if len(sub) < 20:
            out[market] = {'n': len(sub), 'note': 'too few matching settled predictions', 'verdict': 'INCONCLUSIVE'}
            continue
        y = np.array([r['y'] for r in sub])
        old, new = np.clip([r['old'] for r in sub], 1e-6, 1 - 1e-6), np.clip([r['new'] for r in sub], 1e-6, 1 - 1e-6)
        e_old, e_new = (old - y) ** 2, (new - y) ** 2
        by_game = {}
        for r, a, b in zip(sub, e_old, e_new):
            by_game.setdefault(r['game'], []).append(b - a)
        names = list(by_game)
        rng = np.random.default_rng(20261008)
        diffs = [np.mean([d for i in rng.choice(len(names), size=len(names), replace=True) for d in by_game[names[i]]]) for _ in range(2000)]
        lo, hi = np.quantile(diffs, [0.025, 0.975])
        brier_old, brier_new = float(e_old.mean()), float(e_new.mean())
        rel = (brier_old - brier_new) / brier_old
        early = sum(r['k'] <= 2 for r in sub)
        label = 'INCONCLUSIVE' if early < 30 else 'PROMISING' if hi < 0 and rel >= 0.01 else ('REJECTED' if lo > 0 or (-lo / brier_old) < 0.01 else 'INCONCLUSIVE')
        out[market] = {'n': len(sub), 'games': len(names), 'c': c_final[market], 'brier_champion': brier_old, 'brier_w3': brier_new, 'relative_improvement': rel,
                       'delta_brier_ci95': [float(lo), float(hi)], 'verdict': label if market == 'receptions' else 'DESCRIPTIVE', 'win_rate': float(y.mean()),
                       'mean_champion_prob': float(old.mean()), 'mean_w3_prob': float(new.mean()), 'n_with_k_le_2': int(early), 'share_with_k_le_3': float(np.mean([r['k'] <= 3 for r in sub]))}
    return {'markets': out, 'c_final': c_final}, out.get('receptions', {}).get('verdict', 'INCONCLUSIVE')


RUNNERS = {'E10': run_e10}
