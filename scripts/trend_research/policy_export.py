"""Write config/champion_policy.json from the committed research ledger so every number in production traces to a registered experiment."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROMOTED_MEAN = ('receptions', 'rec_yds', 'rec_tds', 'rush_tds', 'atd', 'pass_tds', 'pass_yds')  # P3-1 PROMISING markets plus pass_yds via the P3-6 chain (see docs)


def build():
    ledger = json.loads((REPO / 'research' / 'trend-intelligence' / 'ledger.json').read_text(encoding='utf-8'))
    ex = ledger.get('experiments', ledger)
    result = lambda key: ex[key].get('result') or ex[key]
    spec_hash = lambda key: ex[key].get('spec_hash') or ex[key].get('spec_sha256')
    p31, p35, p36b = result('P3-1'), result('P3-5'), result('P3-6b')
    markets = {}
    for market in PROMOTED_MEAN:
        markets[market] = {'mean': {'method': 'prior_strength_blend', 'c': p31['chosen_c'][market]}}
    pending = {'receptions_shape': {'family': 'nbinom', 'phi': p35['markets']['receptions']['means']['blend']['params']['NB'],
                                    'blocked_by': 'needs index.html propProbabilities/poissonCDF changes, which the frozen today-ranking-v1 experiment hashes; patch kept in research/trend-intelligence/pending/negative-binomial-receptions.patch',
                                    'activation': 'register today-ranking-v2 (new hashes), apply the patch, then move this block into markets.receptions.shape'}}
    for market in ('rec_yds', 'pass_yds'):
        pool = p36b['markets'][market]['pool']
        markets[market]['shape'] = {'family': 'pooled_lognormal', 'zero_shrink_games': 10, 'cv': {p: v['cv'] for p, v in pool.items()},
                                    'zero_rate': {p: round(v['zero_rate'], 6) for p, v in pool.items()}}
    return {'version': 'champion-v2', 'active': False,  # flipped to True only by the promotion commit
            'rollback': 'set "active": false (or run with GOING_CHAMPION_POLICY=v1) and rebuild: every market returns to the 80% current / 20% earlier weights and per-window spread',
            'markets': markets, 'pending_activation': pending,
            'not_promoted': {'rush_yds': 'P3-1 and P3-6 inconclusive: shadow only', 'comment': 'rush_yds stays on v1 until a holdout supports it'},
            'provenance': {'mean_blend': 'P3-1', 'receptions_shape': 'P3-5', 'yardage_shape': 'P3-6 (gate) with P3-6b development-fitted parameters', 'ledger_spec_hashes': {k: spec_hash(k) for k in ('P3-1', 'P3-5', 'P3-6', 'P3-6b')},
                           'development': '2021-2023', 'validation': '2024', 'holdout': '2025'}}


if __name__ == '__main__':
    path = REPO / 'config' / 'champion_policy.json'
    path.write_text(json.dumps(build(), indent=1) + '\n', encoding='utf-8')
    print('wrote', path)
