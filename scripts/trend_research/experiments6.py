"""Phase 3, Week N -> Week N+1 trend experiments on the by-game Fantasy Points panel (P3-2 receiving, P3-3 rushing).

Question: does what changed in a player's role, deployment, opportunity or team environment over his last 1 / 3 / 6 games predict his NEXT game beyond
(a) the production Champion mean and (b) free raw recency from nflverse (his own last-1/3/6-game targets, receptions, yards, carries)? Every Fantasy Points
block is compared with that strong baseline, never with the Champion alone.
All features are computed from games strictly before the target game (see weekly_features.rolling_asof).
"""
import numpy as np
import pandas as pd

from . import weekly_features as wf
from .experiments2 import COMMON, RULE_V2, champion_rows
from .stats import Ridge, paired_bootstrap, verdict

TEST_YEARS = (2023, 2024, 2025)
MIN_PRIOR_FP_GAMES = 3

RECEIVING_BLOCKS = {
    'ROLE': ['rr.Overall.RTE', 'ra.Receiving.RTE %', 'rr.Overall.TPRR', 'ra.Receiving.TGT %'],
    'QUALITY': ['ra.Advanced.1READ %', 'ra.Advanced.DESIGN %', 'ra.Receiving.AY Share', 'ra.Receiving.aDOT'],
    'DEPLOY': ['rr.Slot.SLOT RTE %', 'rr.Wide.WIDE RTE %', 'rr.Inline.INLINE RTE %'],
    'OPP': ['ra.FPTS.XFP', 'ra.FPTS.RecXFP'],
}
RUSHING_BLOCKS = {
    'RUROLE': ['rb.Snaps.Snap %', 'rb.Rushing.ATT %', 'rb.Receiving.TGT %', 'rb.Receiving.RTE %'],
    'RUOPP': ['rb.FPTS.XFP %', 'rb.FPTS.XFP', 'ru.Advanced.EXP YDS', 'ef.FPTS.XFP'],
    'RUGOAL': ['ru.Advanced.i5 %', 'ru.Advanced.TD RATE'],
    'RUEFF': ['ru.Advanced.Success %', 'ru.Advanced.STUFF %', 'ru.Advanced.YACO/ATT', 'ru.Advanced.MTF/ATT'],
}
FFO_RECEIVING = ['receptions_exp', 'rec_yards_gained_exp']
FFO_RUSHING = ['rush_yards_gained_exp', 'rush_touchdown_exp']
TEAM_ENV = ['nfl_pass_rate', 'nfl_att', 'nfl_car']
TEAM_ENV_FP = ['fp_pass_pct', 'fp_neutral_pass_pct', 'fp_i10_pass_pct', 'fp_snaps']

N_PRIMARY = 28
SPECS = {
    'P3-2': {**COMMON, 'id': 'P3-2', 'title': 'Week N -> N+1: receiving role, deployment, opportunity and team-environment trends beyond Champion + raw recency',
             'hypothesis': 'What changed in a WR/TE\'s routes, target quality, alignment, expected fantasy points or team pass environment over his last 1/3/6 games predicts next-game targets and receiving yards '
                           'beyond the Champion mean and his own raw box-score recency.',
             'football_rationale': 'Targets follow routes, deployment and the quality of a player\'s looks; raw counts lag a role change by a game or two. A trend only matters if it carries information the counts do not.',
             'population': 'WR/TE target rows 2021-2025 with a ready Champion window and >= 3 prior Fantasy Points games (complete-case per comparison)',
             'models': {'BV': 'Champion mean, current-season mean, games played, TE flag, nflverse last-1/3/6 targets, receptions, receiving yards',
                        'block LT': 'BV + the block at L6 level plus trends (L3-L6, L1-L6)', 'FFO': 'BV + free ffopportunity expected receptions and yards at L1/L3/L6 (+ trends)'},
             'blocks': RECEIVING_BLOCKS, 'ffopportunity': FFO_RECEIVING, 'team_environment': {'nflverse': TEAM_ENV, 'fantasy_points_run_pass': TEAM_ENV_FP},
             'outcomes': ['targets', 'rec_yds'], 'secondary_outcomes': ['receptions'],
             'primary_comparisons': 'each block (LT form) vs BV, for targets and receiving yards; FFO vs BV; OPP vs FFO (does Fantasy Points beyond ffopportunity add?); nflverse team environment vs BV: 14 receiving + 14 rushing = 28 total across P3-2/P3-3',
             'secondary': 'LEVEL vs TREND vs LEVEL+TREND for each block; windows L1/L3/L6; weeks 1-6 vs later; receptions; Fantasy Points run/pass vs nflverse team pass rate (2024 run/pass file not downloaded: folds 2023 and 2025 only)',
             'multiple_testing': 'Bonferroni over 28 primary comparisons (99.82% intervals)', 'metric': 'MAE of next-game outcome, ridge (fixed penalty 10), rolling origin test 2023/2024/2025, player-clustered paired bootstrap',
             'decision_rule': {'PROMISING': 'relative MAE improvement >= 1% AND adjusted CI excludes 0 AND better in >= 2 of 3 test seasons AND better in 2025 (the latest season)',
                               'REJECTED': 'adjusted CI excludes a 1% gain', 'INCONCLUSIVE': 'otherwise'},
             'sources': ['Fantasy Points by-game tables 2021-2025', 'nflverse weekly stats', 'ffopportunity weekly expected values'], 'leakage': 'all features from games strictly before the target game',
             'markets': ['receptions', 'receiving yards'], 'limitations': 'tests the next-game mean (MAE), not prop prices. Fantasy Points inputs are licensed/local: a production use would need an approved derived-output path.'},
    'P3-3': {**COMMON, 'id': 'P3-3', 'title': 'Week N -> N+1: rushing role, expected opportunity, goal-line usage and efficiency beyond Champion + raw recency',
             'hypothesis': 'Bell-cow role share, expected rushing opportunity and goal-line usage trends predict next-game carries and rushing yards beyond Champion + raw recency; efficiency trends do not.',
             'football_rationale': 'Carries follow role and game script; yards per carry regress; goal-line work drives touchdowns.',
             'population': 'RB target rows 2021-2025 with a ready Champion window and >= 3 prior Fantasy Points games (complete-case per comparison)',
             'models': {'BV': 'Champion mean, current-season mean, games played, nflverse last-1/3/6 carries, rushing yards, targets', 'block LT': 'BV + block level + trends', 'FFO': 'BV + ffopportunity expected rushing yards and TDs'},
             'blocks': RUSHING_BLOCKS, 'ffopportunity': FFO_RUSHING, 'team_environment': {'nflverse': TEAM_ENV}, 'outcomes': ['carries', 'rush_yds'], 'secondary_outcomes': [],
             'primary_comparisons': 'see P3-2', 'multiple_testing': 'Bonferroni over 28 primary comparisons (shared with P3-2)', 'metric': 'as P3-2',
             'decision_rule': {'PROMISING': 'as P3-2', 'REJECTED': 'as P3-2', 'INCONCLUSIVE': 'otherwise'}, 'sources': ['as P3-2'], 'leakage': 'as P3-2', 'markets': ['rushing yards'],
             'limitations': 'as P3-2'},
}


def _cols(prefix, cols, forms):
    out = []
    for c in cols:
        if 'level' in forms:
            out.append(f'{prefix}{c}__L6')
        if 'trend' in forms:
            out += [f'{prefix}{c}__d3', f'{prefix}{c}__d1']
        if 'recent' in forms:
            out += [f'{prefix}{c}__L3', f'{prefix}{c}__L1']
    return out


def _build(root, positions, fp_cols, with_rp):
    frame = champion_rows(root)
    frame = frame[frame.position.isin(positions)].reset_index(drop=True)
    frame = wf.nfl_recency(frame, root)
    frame = wf.ffopp_recency(frame, root)
    frame = wf.fp_recency(frame, root, fp_cols)
    frame = wf.team_recency(frame, root)
    frame = wf.with_trends(frame, 'nfl.', wf.NFL_VOLUME)
    frame = wf.with_trends(frame, 'ffo.', wf.FFO_COLS)
    frame = wf.with_trends(frame, 'fp.', fp_cols)
    frame = wf.with_trends(frame, 'tm.', ['nfl_pass_rate', 'nfl_att', 'nfl_car'])
    frame = wf.with_trends(frame, 'rp.', TEAM_ENV_FP)
    frame['is_te'] = (frame.position == 'TE').astype(float)
    frame['fp_games'] = frame['fp.__cnt']
    return frame


def baseline_cols(outcome):
    nfl = {'targets': ['targets', 'receptions', 'receiving_yards'], 'rec_yds': ['targets', 'receptions', 'receiving_yards'], 'receptions': ['targets', 'receptions', 'receiving_yards'],
           'carries': ['carries', 'rushing_yards', 'targets'], 'rush_yds': ['carries', 'rushing_yards', 'targets']}[outcome]
    champ = {'targets': 'champ_targets', 'rec_yds': 'champ_rec_yds', 'receptions': 'champ_receptions', 'carries': 'champ_carries', 'rush_yds': 'champ_rush_yds'}[outcome]
    cur = {'targets': 'cur_targets', 'rec_yds': 'cur_rec_yds', 'receptions': 'cur_receptions', 'carries': 'cur_carries', 'rush_yds': 'cur_rush_yds'}[outcome]
    cols = [champ, cur, 'k', 'is_te'] + [f'nfl.{c}__{w}' for c in nfl for w in ('L1', 'L3', 'L6')]
    return cols, cur, champ


def _prepare(frame, outcome):
    cols, cur, champ = baseline_cols(outcome)
    work = frame.copy()
    work[cur] = work[cur].fillna(work[champ])
    return work, cols


def compare(frame, outcome, base_cols, new_cols, require=(), confidence=0.95, test_years=TEST_YEARS):
    """Rolling-origin ridge comparison of base vs base+new on a common complete-case population."""
    target = 'y_' + outcome
    work = frame.dropna(subset=list(base_cols) + list(new_cols) + [target]).copy()
    for col, minimum in require:
        work = work[work[col] >= minimum]
    per_year, e_base, e_new, groups, weeks = {}, [], [], [], []
    for year in test_years:
        train, test = work[work.season < year], work[work.season == year]
        if len(train) < 500 or len(test) < 200:
            continue
        y = test[target].to_numpy(float)
        pb = Ridge().fit(train[base_cols], train[target]).predict(test[base_cols])
        pn = Ridge().fit(train[base_cols + new_cols], train[target]).predict(test[base_cols + new_cols])
        per_year[str(year)] = {'base_mae': float(np.abs(y - pb).mean()), 'new_mae': float(np.abs(y - pn).mean()), 'n': int(len(y))}
        e_base.append(y - pb)
        e_new.append(y - pn)
        groups.append(test.player_id.to_numpy())
        weeks.append(test.week.to_numpy())
    if not per_year:
        return {'verdict': 'INCONCLUSIVE', 'note': 'too few rows', 'n': int(len(work))}
    eb, en, g, wk = np.concatenate(e_base), np.concatenate(e_new), np.concatenate(groups), np.concatenate(weeks)
    delta = paired_bootstrap(eb, en, g, confidence=confidence)
    base_mae = float(np.abs(eb).mean())
    better = sum(1 for v in per_year.values() if v['new_mae'] < v['base_mae'])
    label, rel = verdict(delta, base_mae, better, len(per_year), RULE_V2)
    latest = per_year.get('2025')
    if label == 'PROMISING' and latest and not latest['new_mae'] < latest['base_mae']:
        label = 'INCONCLUSIVE'
    early = wk <= 6
    return {'verdict': label, 'relative_improvement': rel, 'base_mae': base_mae, 'new_mae': float(np.abs(en).mean()), 'ci': [delta['ci_low'], delta['ci_high']], 'years_better': int(better),
            'per_year': per_year, 'n': int(len(eb)), 'weeks_1_6_relative': float(1 - np.abs(en[early]).mean() / np.abs(eb[early]).mean()) if early.sum() > 200 else None,
            'weeks_7_plus_relative': float(1 - np.abs(en[~early]).mean() / np.abs(eb[~early]).mean()) if (~early).sum() > 200 else None}


def _run(root, spec_id, positions, blocks, ffo_cols, outcomes, secondary_outcomes, env_blocks):
    spec = SPECS[spec_id]
    fp_cols = sorted({c for cols in blocks.values() for c in cols})
    frame = _build(root, positions, fp_cols, True)
    confidence = 1 - 0.05 / N_PRIMARY
    out, verdicts = {'outcomes': {}}, []
    for outcome in outcomes + secondary_outcomes:
        primary = outcome in outcomes
        work, base = _prepare(frame, outcome)
        res = {'primary': primary, 'blocks': {}, 'forms': {}, 'windows': {}}
        require_fp = [('fp_games', MIN_PRIOR_FP_GAMES)]
        for name, cols in blocks.items():
            lt = _cols('fp.', cols, ('level', 'trend'))
            res['blocks'][name] = compare(work, outcome, base, lt, require_fp, confidence)
            if primary:
                verdicts.append(res['blocks'][name]['verdict'])
            # secondary: level vs trend vs both (descriptive, not part of the registered family)
            res['forms'][name] = {form: compare(work, outcome, base, _cols('fp.', cols, form_set), require_fp, 0.95) for form, form_set in
                                  (('LEVEL', ('level',)), ('TREND', ('trend',)), ('LEVEL+TREND', ('level', 'trend')))}
            res['windows'][name] = {w: compare(work, outcome, base, [f'fp.{c}__{w}' for c in cols], require_fp, 0.95) for w in ('L1', 'L3', 'L6')}
        ffo = _cols('ffo.', ffo_cols, ('level', 'trend'))
        res['blocks']['FFO'] = compare(work, outcome, base, ffo, require_fp, confidence)
        if primary:
            verdicts.append(res['blocks']['FFO']['verdict'])
        if 'OPP' in blocks or 'RUOPP' in blocks:
            opp = 'OPP' if 'OPP' in blocks else 'RUOPP'
            fp_opp = _cols('fp.', blocks[opp], ('level', 'trend'))
            res['fantasy_points_beyond_ffopportunity'] = compare(work, outcome, base + ffo, fp_opp, require_fp, confidence)
            if primary:
                verdicts.append(res['fantasy_points_beyond_ffopportunity']['verdict'])
        env = _cols('tm.', ['nfl_pass_rate', 'nfl_att', 'nfl_car'], ('level', 'trend'))
        res['blocks']['TEAM_NFL'] = compare(work, outcome, base, env, require_fp, confidence)
        if primary:
            verdicts.append(res['blocks']['TEAM_NFL']['verdict'])
        if env_blocks.get('fantasy_points_run_pass'):
            rp = _cols('rp.', TEAM_ENV_FP, ('level', 'trend'))
            res['team_fp_run_pass'] = compare(work, outcome, base, rp, require_fp, 0.95, test_years=(2023, 2025))
            res['team_fp_run_pass_beyond_nflverse'] = compare(work, outcome, base + env, rp, require_fp, 0.95, test_years=(2023, 2025))
        out['outcomes'][outcome] = res
    status = 'PROMISING' if 'PROMISING' in verdicts else ('REJECTED' if verdicts and set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return out, status


def run_p3_2(root, manifest):
    s = SPECS['P3-2']
    return _run(root, 'P3-2', ('WR', 'TE'), RECEIVING_BLOCKS, FFO_RECEIVING, s['outcomes'], s['secondary_outcomes'], s['team_environment'])


def run_p3_3(root, manifest):
    s = SPECS['P3-3']
    return _run(root, 'P3-3', ('RB',), RUSHING_BLOCKS, FFO_RUSHING, s['outcomes'], s['secondary_outcomes'], {})


RUNNERS = {'P3-2': run_p3_2, 'P3-3': run_p3_3}
