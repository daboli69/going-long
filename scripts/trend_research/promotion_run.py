"""Run the Champion v2 promotion check against the committed (possibly inactive) policy file. Writes research/trend-intelligence/promotion_check_champion_v2.json."""
import json
import os
import sys
import warnings

from . import promotion_check as pc
from . import promotion_live as pl

cp = pc.cp


def main(root=None):
    warnings.filterwarnings('ignore')
    root = root or os.environ['GOING_FP_ROOT']
    policy = {**json.loads(cp.POLICY_PATH.read_text(encoding='utf-8')), 'active': True}  # evaluate the parameters whether or not the switch is on
    result = pc.evaluate(root, policy)
    result['live_2026'] = pl.live_2026(root, policy)
    result['policy_active_in_repo'] = json.loads(cp.POLICY_PATH.read_text(encoding='utf-8'))['active']
    pc.OUT.write_text(json.dumps(result, indent=1), encoding='utf-8')
    return result


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    r = main()
    for market, v in r['markets'].items():
        a = v['all']
        print(f"{market:10s} n {a['n']:6d} brier {a['brier_v1']:.4f}->{a['brier_v2']:.4f} ({a['brier_relative_gain']*100:+.2f}%) ci {[round(x, 5) for x in v['brier_difference_ci95']]} slope {a['calibration_v1']['slope']}->{a['calibration_v2']['slope']} worst {v['worst_segment_relative_gain']*100:+.2f}%")
    for market, v in r['live_2026']['markets'].items():
        print('LIVE', market, v['n'], v['games'], round(v['brier_v1'], 4), round(v['brier_v2'], 4), round(v['relative_gain'] * 100, 2), [round(x, 4) for x in v['difference_ci95']])
