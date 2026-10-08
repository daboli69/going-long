"""Phase 3 follow-ups registered after reading P3-2/P3-3/P3-6:

P3-4  Do FREE nflverse role signals (snap share, target share, carry share, with trends) carry the ROLE gain found with Fantasy Points routes / participation, and do
      Fantasy Points role fields add anything beyond them? (Free signals can run in the production build; licensed ones cannot.)
P3-6b Yardage spread: the P3-6 coefficient-of-variation grid started at 0.4, which is above a quarterback's real spread, so repeat with a grid that covers it, and test a
      player/pool shrinkage of the spread.
Both are follow-ups designed after seeing earlier results: a PROMISING label is a candidate for shadow tracking, not proof.
"""
import numpy as np

from . import experiments7 as e7
from . import weekly_features as wf
from .experiments2 import COMMON, RULE_V2, MARKET_RULES, _blend, _eligible, champion_rows
from .experiments5 import _cluster_ci
from .experiments6 import (RECEIVING_BLOCKS, RUSHING_BLOCKS, _build, _cols, _prepare, compare, MIN_PRIOR_FP_GAMES)

SPECS = {
    'P3-4': {**COMMON, 'id': 'P3-4', 'title': 'Free nflverse role signals vs Fantasy Points ROLE signals, beyond Champion + raw recency (follow-up to P3-2/P3-3)',
             'hypothesis': 'Snap share and target/carry share (free, nflverse) trends predict next-game targets/receiving yards (WR/TE) and carries/rushing yards (RB) beyond Champion + raw box-score recency; '
                           'Fantasy Points routes/participation/bell-cow shares add nothing further.',
             'football_rationale': 'P3-2/P3-3 found a ROLE gain (1-2% MAE); most of it may be role share, which is free.',
             'population': 'as P3-2 (WR/TE) and P3-3 (RB), complete-case; Fantasy Points games >= 3', 'models': {'BV': 'as P3-2/P3-3', 'FREE': 'BV + free role block (snap %, target share, carry share) level + trends',
                                                                                                     'FP': 'FREE + Fantasy Points ROLE / RUROLE block'},
             'primary_comparisons': ['FREE vs BV x 4 outcomes (targets, rec_yds, carries, rush_yds)', 'FP vs FREE x 4 outcomes'], 'multiple_testing': 'Bonferroni over 8 comparisons (99.375%)',
             'decision_rule': {'PROMISING': 'as P3-2', 'REJECTED': 'as P3-2', 'INCONCLUSIVE': 'otherwise'}, 'exploratory': True,
             'sources': ['nflverse snap counts, weekly stats', 'Fantasy Points by-game tables'], 'leakage': 'games strictly before the target game', 'markets': ['receptions', 'receiving yards', 'rushing yards'],
             'limitations': 'post-hoc follow-up; mean accuracy only'},
    'P3-6b': {**COMMON, 'id': 'P3-6b', 'title': 'Yardage spread: wider coefficient-of-variation grid and player/pool shrinkage (follow-up to P3-6)',
              'hypothesis': 'A pooled (or shrunk) spread prices yardage thresholds better than the production per-window spread; the P3-6 grid was too coarse at the low end.',
              'football_rationale': 'A quarterback\'s yardage spread is about 0.25-0.35 of the mean, far from the 0.4 grid floor.',
              'population': 'as P3-6', 'markets': list(e7.YARDS),
              'models': {'PROD': 'production', 'POOL2': 'pooled CV per position, grid [0.15..1.2], zero mass shrunk toward position rate, blend mean',
                         'SHRINK': 'sigma^2 = w*window_sigma^2 + (1-w)*pooled_sigma^2, w = n/(n+n0), n0 in [2,5,10,20] learned on development seasons'},
              'splits': {'development': [2021, 2022, 2023], 'validation': [2024], 'holdout': [2025]},
              'metric': 'pinball loss relative gain vs PROD; Brier at lines; 80% coverage', 'multiple_testing': 'Bonferroni over 3 markets x 2 alternatives (99.2%)',
              'decision_rule': {'PROMISING': 'as P3-6', 'REJECTED': 'as P3-6', 'INCONCLUSIVE': 'otherwise'}, 'rule_numbers': {'min_relative_pinball': 0.01}, 'exploratory': True,
              'sources': ['nflverse weekly stats'], 'leakage': 'parameters from 2021-2023', 'limitations': 'post-hoc'},
}

CV_FINE = [0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2]
N0_GRID = [2, 5, 10, 20]


def run_p3_4(root, manifest):
    out, verdicts = {'outcomes': {}}, []
    conf = 1 - 0.05 / 8
    for positions, blocks, outcomes in ((('WR', 'TE'), RECEIVING_BLOCKS, ['targets', 'rec_yds']), (('RB',), RUSHING_BLOCKS, ['carries', 'rush_yds'])):
        fp_cols = sorted({c for cols in blocks.values() for c in cols})
        frame = _build(root, positions, fp_cols, False)
        frame = wf.nfl_role(frame, root)
        frame = wf.with_trends(frame, 'role.', wf.ROLE_FREE)
        free = _cols('role.', wf.ROLE_FREE, ('level', 'trend'))
        role_block = RECEIVING_BLOCKS['ROLE'] if positions[0] == 'WR' else RUSHING_BLOCKS['RUROLE']
        fp = _cols('fp.', role_block, ('level', 'trend'))
        require = [('fp_games', MIN_PRIOR_FP_GAMES)]
        for outcome in outcomes:
            work, base = _prepare(frame, outcome)
            res = {'free_vs_bv': compare(work, outcome, base, free, require, conf), 'fp_beyond_free': compare(work, outcome, base + free, fp, require, conf)}
            # decomposition of the free block: which signal carries the gain
            res['free_components'] = {name: compare(work, outcome, base, _cols('role.', [name], ('level', 'trend')), require, 0.95) for name in wf.ROLE_FREE}
            out['outcomes'][outcome] = res
            verdicts += [res['free_vs_bv']['verdict'], res['fp_beyond_free']['verdict']]
    status = 'NEEDS PROSPECTIVE DATA' if 'PROMISING' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return out, status


def run_p3_6b(root, manifest):
    frame = champion_rows(root)
    chosen = e7._c_from_ledger()
    out, verdicts = {}, []
    conf = 1 - 0.05 / 6
    for market in e7.YARDS:
        rows = _eligible(frame, market)
        rows = rows[(rows['pw_' + market] > 0) & rows['pm_' + market].notna() & rows['ps_' + market].notna() & (rows['pm_' + market] > 0)]
        c = chosen.get(market, 2)
        rows = rows.assign(blend=_blend(rows, market, c))
        rows = rows[rows.blend > 0]
        dev = rows[rows.season <= 2023]
        pool = {}
        for p in dev.position.unique():
            sub = dev[dev.position == p]
            y = sub['y_' + market].to_numpy(float)
            zero_rate = float((y <= 0).mean())
            p0 = np.clip(zero_rate, 0.001, 0.99)
            pm = sub['blend'].to_numpy(float) / (1 - p0)
            scores = {}
            for cv in CV_FINE:
                mu_l, sg = e7._ln_params(pm, pm * cv)
                scores[cv] = float(e7._pinball_neg(y, mu_l, sg, p0).mean())
            pool[p] = {'cv': max(scores, key=scores.get), 'zero_rate': zero_rate, 'n': int(len(sub))}
        # shrinkage strength on development seasons
        def build(df, n0):
            blend = df['blend'].to_numpy(float)
            pw = df['pw_' + market].to_numpy(float)
            n_games = df['n'].to_numpy(float)
            zr = np.array([pool[p]['zero_rate'] for p in df['position']])
            cv = np.array([pool[p]['cv'] for p in df['position']])
            p0 = np.clip((n_games * (1 - pw) + 10 * zr) / (n_games + 10), 0.001, 0.99)
            pm_p = blend / (1 - p0)
            window_cv2 = (df['ps_' + market].to_numpy(float) / df['pm_' + market].to_numpy(float)) ** 2
            w = n_games / (n_games + n0)
            cv_shrunk = np.sqrt(w * window_cv2 + (1 - w) * cv ** 2)
            return pm_p, p0, cv, cv_shrunk
        best_n0, best = None, -np.inf
        ydev = dev['y_' + market].to_numpy(float)
        for n0 in N0_GRID:
            pm_p, p0, cv, cv_s = build(dev, n0)
            mu_l, sg = e7._ln_params(pm_p, pm_p * cv_s)
            score = float(e7._pinball_neg(ydev, mu_l, sg, p0).mean())
            if score > best:
                best_n0, best = n0, score
        res = {'blend_c': c, 'pool': pool, 'n0': best_n0, 'cells': {}}
        for label, season in (('validation', 2024), ('holdout', 2025)):
            test = rows[rows.season == season]
            y = test['y_' + market].to_numpy(float)
            champ_mean = test['champ_' + market].to_numpy(float)
            pw, pm, ps = test['pw_' + market].to_numpy(float), test['pm_' + market].to_numpy(float), test['ps_' + market].to_numpy(float)
            mu_l, sg = e7._ln_params(pm, ps)
            models = {'PROD': (mu_l, sg, 1 - pw)}
            pm_p, p0, cv, cv_s = build(test, best_n0)
            m2, s2 = e7._ln_params(pm_p, pm_p * cv)
            models['POOL2'] = (m2, s2, p0)
            m3, s3 = e7._ln_params(pm_p, pm_p * cv_s)
            models['SHRINK'] = (m3, s3, p0)
            stats = {}
            for name, (m_l, s_l, z0) in models.items():
                qs = [e7._ln_quantile(q, m_l, s_l, z0) for q in e7.QUANTILES]
                brier = np.zeros(len(y))
                for factor in (0.8, 1.0, 1.2):
                    line = np.maximum(champ_mean * factor, 1.0)
                    brier += ((1 - e7._ln_cdf(line, m_l, s_l, z0)) - (y > line)) ** 2
                lo, hi = e7._ln_quantile(0.1, m_l, s_l, z0), e7._ln_quantile(0.9, m_l, s_l, z0)
                stats[name] = {'pinball': e7._pinball(y, qs), 'brier': brier / 3, 'coverage80': float(((y >= lo) & (y <= hi)).mean()), 'below_p10': float((y < lo).mean()), 'above_p90': float((y > hi).mean())}
            cell = {'n': int(len(y))}
            groups = test.player_id.to_numpy()
            for name in models:
                cell[name] = {'pinball': float(stats[name]['pinball'].mean()), 'brier': float(stats[name]['brier'].mean()), 'coverage80': stats[name]['coverage80'],
                              'below_p10': stats[name]['below_p10'], 'above_p90': stats[name]['above_p90']}
                if name != 'PROD':
                    d = (stats['PROD']['pinball'] - stats[name]['pinball']) / stats['PROD']['pinball'].mean()
                    m, lo_ci, hi_ci = _cluster_ci(d, groups, conf)
                    cell[name].update(relative_pinball_gain=m, ci=[lo_ci, hi_ci], brier_relative=float((stats['PROD']['brier'].mean() - stats[name]['brier'].mean()) / stats['PROD']['brier'].mean()))
            res['cells'][label] = cell
        res['verdicts'] = {}
        for name in ('POOL2', 'SHRINK'):
            v, h = res['cells']['validation'][name], res['cells']['holdout'][name]
            ok = v['relative_pinball_gain'] >= 0.01 and h['relative_pinball_gain'] >= 0.01 and h['ci'][0] > 0 and v['brier_relative'] >= -0.002 and h['brier_relative'] >= -0.002
            label = 'NEEDS PROSPECTIVE DATA' if ok else ('REJECTED' if h['ci'][1] < 0.01 else 'INCONCLUSIVE')
            res['verdicts'][name] = label
            verdicts.append(label)
        out[market] = res
    status = 'NEEDS PROSPECTIVE DATA' if 'NEEDS PROSPECTIVE DATA' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return {'markets': out}, status


RUNNERS = {'P3-4': run_p3_4, 'P3-6b': run_p3_6b}
