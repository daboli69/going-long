"""Second wave: tests against the reconstructed production Champion (see champion.py) instead of toy baselines.

All three experiments use rule v2 (a wide interval is INCONCLUSIVE, not REJECTED), a fixed ridge penalty, chronological rolling-origin splits
(train on earlier seasons only, test 2023-2025) and player-clustered paired bootstrap intervals with Bonferroni adjustment over the registered
comparisons. Champion = the production 12-appearance window with 80% current-season / 20% earlier-season weights.
"""
import numpy as np
import pandas as pd
from scipy.stats import poisson

from . import champion, data
from .stats import Ridge, mae, paired_bootstrap, verdict

RULE_V2 = {'min_relative_improvement': 0.01, 'min_years_better': 2, 'reject_below_relative_improvement': 0.0025, 'reject_requires_ci': True}
COMMON = {'ridge_alpha': 10, 'bootstrap': 'cluster by player, 2000 draws, seed 20261008', 'rule_numbers': RULE_V2,
          'decision_rule': {'PROMISING': 'relative MAE improvement >= 1% over the comparison base AND the Bonferroni-adjusted CI of the paired difference excludes 0 AND better in >= 2 of 3 test seasons',
                            'REJECTED (v2)': 'the adjusted CI excludes a gain of 1% (or lies entirely on the wrong side)', 'INCONCLUSIVE': 'anything else, including wide intervals'},
          'champion': 'production window mean: last 12 regular-season appearances (QB: verified starts), min 5, 80% current-season / 20% earlier-season weights (reconstruction validated against the 2026 frozen projection_mean: 91% exact for receptions and receiving yards)',
          'splits': {'train': 'all earlier target seasons', 'test': [2023, 2024, 2025], 'history_from': 2019, 'rolling_origin': True}}

MARKET_RULES = {  # market -> (positions, workload column used as raw volume, count family?)
    'receptions': (('WR', 'TE', 'RB'), 'champ_targets', True), 'rec_yds': (('WR', 'TE', 'RB'), 'champ_targets', False),
    'rec_tds': (('WR', 'TE', 'RB'), 'champ_targets', True), 'rush_yds': (('RB',), 'champ_carries', False), 'rush_tds': (('RB',), 'champ_carries', True),
    'atd': (('WR', 'TE', 'RB'), 'champ_targets', True), 'pass_yds': (('QB',), 'champ_attempts', False), 'pass_tds': (('QB',), 'champ_attempts', True)}
C_GRID = [0.5, 1, 2, 3, 4, 6, 8, 12, 20, 40]

SPECS = {
    'E7': {**COMMON, 'id': 'E7', 'title': 'Dynamic blend of prior and current-season usage vs the production 80/20 policy',
           'hypothesis': 'The production policy gives 80% of the weight to the current season\'s games however few there are; a blend whose prior strength is learned '
                         '(prior games count as c pseudo-games) predicts weekly outcomes better, mainly in the first six weeks.',
           'football_rationale': 'One or two games are a noisy read of a role; early in a season the earlier seasons contain most of the real information, and by midseason '
                                 'the current role dominates. The 80/20 rule jumps to 80% after a single game.',
           'population': 'player appearances 2021-2025 with a production-ready window (>= 5 games; QBs: verified starters only); markets receptions, rec_yds, rec_tds, rush_yds, rush_tds, atd, pass_yds, pass_tds by position',
           'comparators': {'W0': 'Champion (production 80/20)', 'W1': 'equal weights over the window (no season weighting)',
                           'W3': 'learned shrinkage: (k*current_mean + c*prior_mean)/(k+c), c from the grid [0.5..40] chosen on TRAIN seasons only per market',
                           'W4': 'ridge on current mean, prior mean, k, k=0 flag, prior games'},
           'primary_comparison': 'W3 vs W0, weeks 1-6, per market (8 markets, Bonferroni 99.375% CI)', 'secondary': 'all weeks; W1 and W4; MAE by number of current games; Poisson log score for count markets',
           'outcomes': 'the weekly stat of each market', 'metric': 'MAE of the projected mean (primary), Poisson log score (secondary)',
           'multiple_testing': 'Bonferroni over 8 markets', 'sources': ['nflverse weekly player stats, snap counts, schedules 2019-2025'], 'leakage': 'window = games strictly before the target week',
           'markets': ['receptions', 'receiving yards', 'rushing yards', 'TDs', 'QB passing'],
           'limitations': 'tests the projected MEAN; no historical prop lines exist, so no ROI. The Poisson/lognormal distribution layer and the injury adjustments are not reconstructed.'},
    'E8': {**COMMON, 'id': 'E8', 'title': 'Fantasy Points XFP vs ffopportunity expected points vs raw volume, each against the Champion',
           'hypothesis': 'Expected-opportunity information adds to the Champion\'s mean; Fantasy Points XFP adds something beyond ffopportunity (which GOING already has).',
           'football_rationale': 'Expected points describe the quality of touches (location, depth, down) that raw production and counts miss.',
           'population': 'appearances 2022-2025 with a ready Champion window and available prior-season Fantasy Points efficiency and ffopportunity rows (complete-case, identical across models)',
           'models': {'M0': 'Champion mean + position flags', 'MV': 'M0 + raw volume (Champion-window targets/g or carries/g)', 'MFP': 'M0 + Fantasy Points prior-season XFP/G, XTD/G',
                      'MEOP': 'M0 + ffopportunity prior-season per-game expected value of the market stat (apples-to-apples with MFP)',
                      'MEO': 'MEOP + ffopportunity current-season rolling expected value + games count (the in-season advantage ffopportunity has)',
                      'MEOFP': 'MEOP + Fantasy Points XFP/G, XTD/G'},
           'primary_comparisons': ['MFP vs M0', 'MEOP vs M0', 'MEOFP vs MEOP (does Fantasy Points add beyond ffopportunity?)', 'MEO vs M0'],
           'markets': ['receptions', 'rec_yds', 'rec_tds', 'rush_yds', 'rush_tds'], 'multiple_testing': 'Bonferroni over 5 markets x 4 comparisons = 20 (99.75% CI)',
           'sources': ['Fantasy Points efficiency 2021-2024 (prior season, retrospective)', 'ffverse/ffopportunity weekly expected points 2020-2025', 'nflverse weekly stats'],
           'leakage': 'Fantasy Points features are prior-season only; ffopportunity current-season values use earlier weeks only',
           'limitations': 'Fantasy Points XFP exists only as a prior-season total (no weekly history before 2026), ffopportunity has weekly values; a fair test of timing advantage is the MEO row.'},
    'E9': {**COMMON, 'id': 'E9', 'title': 'Rushing / bell-cow: role share, advanced rushing efficiency, role stability and expected opportunity over Champion plus raw volume',
           'hypothesis': 'Bell-cow role shares and role stability predict weekly carries/rushing yards beyond Champion + raw volume; efficiency metrics (success, stuff, contact yards) do not.',
           'football_rationale': 'Carries follow role and game script; yards per carry are mostly noise and regress; goal-line TDs follow role.',
           'population': 'RB appearances 2022-2025 with a ready Champion window and the prior-season Fantasy Points rows needed by each block (complete-case per comparison)',
           'models': {'M0': 'Champion mean of the outcome + RB-only constant', 'MV': 'M0 + Champion-window carries/g and targets/g',
                      'R1': 'MV + Fantasy Points bell-cow block (snap %, carry share %, target share %, XFP share %) from the prior season',
                      'R2': 'MV + Fantasy Points advanced rushing block (success %, stuff %, contact yards/att, missed tackles/att, explosive run %, yards before contact/att, zone share)',
                      'R3': 'MV + role stability from nflverse (window mean, window SD and current-vs-prior change of the team carry share)',
                      'R4': 'MV + ffopportunity prior-season expected rushing yards and TDs per game'},
           'primary_comparisons': ['R1 vs MV', 'R2 vs MV', 'R3 vs MV', 'R4 vs MV'], 'outcomes': ['carries', 'rush_yds', 'rush_tds'],
           'multiple_testing': 'Bonferroni over 3 outcomes x 4 blocks = 12 (99.58% CI)',
           'sources': ['Fantasy Points rushing_bell_cow, rushing_advanced 2021-2024 (prior season)', 'nflverse weekly stats', 'ffopportunity'], 'leakage': 'prior-season features only; share statistics from games before the target week',
           'markets': ['rushing yards', 'rushing TD', 'carries'], 'limitations': 'carries are not a market GOING prices, but they drive the markets that it does'},
}


# ------------------------------------------------------------------ frames
def champion_rows(root):
    path = champion.cache(root) / 'champion_2021_2025.parquet'
    if path.exists():
        frame = pd.read_parquet(path)
    else:
        frame = champion.champion_frame(root, {2021, 2022, 2023, 2024, 2025})
        frame.to_parquet(path)
    return frame[frame.ready].reset_index(drop=True)


def _eligible(frame, market):
    positions, _, _ = MARKET_RULES[market]
    rows = frame[frame.position.isin(positions)]
    if market.startswith('pass_'):
        rows = rows[rows.start]
    cols = ['champ_' + market, 'cur_' + market, 'prior_' + market, 'y_' + market]
    return rows.dropna(subset=[c for c in cols if c not in ('cur_' + market, 'prior_' + market)])


def _folds(frame, test_years=(2023, 2024, 2025), first_train=2021):
    return {y: (frame[(frame.season < y) & (frame.season >= first_train)], frame[frame.season == y]) for y in test_years}


def _summary(errors_base, errors_new, groups, per_year, base_name, new_name, confidence, label_rule=RULE_V2):
    delta = paired_bootstrap(errors_base, errors_new, groups, confidence=confidence)
    base_mae = float(np.abs(errors_base).mean())
    better = sum(1 for y in per_year.values() if y[new_name] < y[base_name])
    label, rel = verdict(delta, base_mae, better, len(per_year), label_rule)
    return {'verdict': label, 'pooled': {'base_mae': base_mae, 'new_mae': float(np.abs(errors_new).mean()), 'n': int(len(errors_base)), **delta, 'relative_improvement': rel,
                                         'years_better': int(better), 'years_total': len(per_year)}}


# ------------------------------------------------------------------ E7
def _blend(frame, market, c):
    cur, prior, k = frame['cur_' + market].to_numpy(float), frame['prior_' + market].to_numpy(float), frame['k'].to_numpy(float)
    out = np.where(np.isnan(cur), prior, np.where(np.isnan(prior), cur, (k * np.nan_to_num(cur) + c * np.nan_to_num(prior)) / (k + c)))
    return out


def _equal(frame, market):
    cur, prior = frame['cur_' + market].to_numpy(float), frame['prior_' + market].to_numpy(float)
    k, p = frame['k'].to_numpy(float), frame['n_prior'].to_numpy(float)
    return np.where(np.isnan(cur), prior, np.where(np.isnan(prior), cur, (k * np.nan_to_num(cur) + p * np.nan_to_num(prior)) / (k + p)))


def _w4_features(frame, market):
    cur, prior = frame['cur_' + market].to_numpy(float), frame['prior_' + market].to_numpy(float)
    cur_f = np.where(np.isnan(cur), prior, cur)
    prior_f = np.where(np.isnan(prior), cur, prior)
    return np.column_stack([cur_f, prior_f, frame['k'], (frame['k'] == 0).astype(float), frame['n_prior']])


def run_e7(root, manifest):
    spec = SPECS['E7']
    frame = champion_rows(root)
    out, verdicts = {}, []
    confidence = 1 - 0.05 / 8
    for market in MARKET_RULES:
        rows = _eligible(frame, market)
        folds = _folds(rows)
        per_year, errs = {}, {name: [] for name in ('W0', 'W1', 'W3', 'W4')}
        early = {name: [] for name in errs}
        early_groups, groups, y_all, weeks_all, k_all = [], [], [], [], []
        c_chosen = {}
        for year, (train, test) in folds.items():
            ytr = train['y_' + market].to_numpy(float)
            best_c, best = None, np.inf
            for c in C_GRID:
                m = float(np.abs(ytr - _blend(train, market, c)).mean())
                if m < best:
                    best, best_c = m, c
            c_chosen[str(year)] = best_c
            ridge = Ridge().fit(_w4_features(train, market), ytr)
            y = test['y_' + market].to_numpy(float)
            preds = {'W0': test['champ_' + market].to_numpy(float), 'W1': _equal(test, market), 'W3': _blend(test, market, best_c), 'W4': ridge.predict(_w4_features(test, market))}
            per_year[str(year)] = {name: float(np.abs(y - p).mean()) for name, p in preds.items()}
            early_mask = (test.week <= 6).to_numpy()
            per_year[str(year)]['weeks1_6'] = {name: float(np.abs(y[early_mask] - p[early_mask]).mean()) for name, p in preds.items()}
            per_year[str(year)]['n'] = int(len(y))
            for name, p in preds.items():
                errs[name].append(y - p)
                early[name].append((y - p)[early_mask])
            groups.append(test.player_id.to_numpy())
            early_groups.append(test.player_id.to_numpy()[early_mask])
            y_all.append(y)
            weeks_all.append(test.week.to_numpy())
            k_all.append(test.k.to_numpy())
        early_year = {y: {n: v for n, v in row['weeks1_6'].items()} for y, row in per_year.items()}
        primary = _summary(np.concatenate(early['W0']), np.concatenate(early['W3']), np.concatenate(early_groups), early_year, 'W0', 'W3', confidence)
        allweeks = _summary(np.concatenate(errs['W0']), np.concatenate(errs['W3']), np.concatenate(groups), per_year, 'W0', 'W3', confidence)
        by_k = {}
        e0, e3, kk = np.concatenate(errs['W0']), np.concatenate(errs['W3']), np.concatenate(k_all)
        for k in range(0, 9):
            mask = kk == k
            if mask.sum() >= 50:
                by_k[str(k)] = {'n': int(mask.sum()), 'champion_mae': float(np.abs(e0[mask]).mean()), 'w3_mae': float(np.abs(e3[mask]).mean())}
        secondary = {}
        for name in ('W1', 'W4'):
            secondary[name] = {'pooled_mae_weeks1_6': float(np.abs(np.concatenate(early[name])).mean()), 'champion_pooled_mae_weeks1_6': float(np.abs(np.concatenate(early['W0'])).mean())}
        block = {'primary_weeks1_6_W3_vs_W0': primary, 'all_weeks_W3_vs_W0': allweeks, 'per_test_year': per_year, 'chosen_prior_strength_c': c_chosen, 'mae_by_current_games_in_window': by_k,
                 'secondary': secondary, 'n_rows': int(len(rows))}
        if MARKET_RULES[market][2]:  # Poisson log score for count markets (descriptive)
            ls = {}
            for name, key in (('W0', None), ('W3', None)):
                scores = []
                for year, (train, test) in folds.items():
                    lam = np.maximum(test['champ_' + market].to_numpy(float) if name == 'W0' else _blend(test, market, c_chosen[str(year)]), 0.01)
                    scores.append(poisson.logpmf(test['y_' + market].to_numpy(float), lam))
                ls[name] = float(np.concatenate(scores).mean())
            block['poisson_log_score'] = ls
        out[market] = block
        verdicts.append(primary['verdict'])
    labels = set(verdicts)
    status = 'PROMISING' if 'PROMISING' in labels and labels <= {'PROMISING', 'INCONCLUSIVE', 'REJECTED'} and verdicts.count('PROMISING') >= 1 else \
        ('REJECTED' if labels == {'REJECTED'} else 'INCONCLUSIVE')
    return {'markets': out}, status


# ------------------------------------------------------------------ E8 / E9 feature builders
EO_FIELDS = ['receptions_exp', 'rec_yards_gained_exp', 'rec_touchdown_exp', 'rush_yards_gained_exp', 'rush_touchdown_exp', 'total_fantasy_points_exp']


def with_ffopp(frame, root):
    ep = data_ffopp(root)
    prior = ep.groupby(['player_id', 'season'])[EO_FIELDS].mean().reset_index()
    prior['season'] = prior['season'] + 1
    prior = prior.rename(columns={f: 'eop_' + f for f in EO_FIELDS})
    ep = ep.sort_values(['player_id', 'season', 'week'])
    roll = ep.groupby(['player_id', 'season'])[EO_FIELDS].transform(lambda s: s.expanding().mean().shift(1))
    ep_roll = ep[['player_id', 'season', 'week']].join(roll.rename(columns={f: 'eor_' + f for f in EO_FIELDS}))
    ep_roll['k_eo'] = ep.groupby(['player_id', 'season']).cumcount()
    out = frame.merge(prior, on=['player_id', 'season'], how='left').merge(ep_roll, on=['player_id', 'season', 'week'], how='left')
    for f in EO_FIELDS:
        out['eor_' + f] = out['eor_' + f].fillna(out['eop_' + f])
    out['k_eo'] = out['k_eo'].fillna(0)
    return out


_FFOPP = {}


def data_ffopp(root):
    if 'ep' not in _FFOPP:
        ep = champion.load_ffopp(root, range(2020, 2026))
        _FFOPP['ep'] = ep[['player_id', 'season', 'week'] + EO_FIELDS].dropna(subset=['player_id'])
    return _FFOPP['ep']


def with_fp(frame, root, manifest, table_id, columns, rename=None):
    parts = []
    for season in sorted(frame.season.unique()):
        prior = data.prior_features(root, manifest, int(season), table_id)
        if prior is None:
            continue
        data.assert_no_same_season(int(season) - 1, int(season))
        keep = prior[['player_id'] + columns].copy()
        keep['season'] = int(season)
        parts.append(keep)
    fp = pd.concat(parts, ignore_index=True).rename(columns=rename or {})
    return frame.merge(fp, on=['player_id', 'season'], how='left')


def _model_compare(frame, target, base_cols, models, comparisons, confidence, drop_cols):
    """Rolling-origin comparison of ridge models on a COMMON complete-case population."""
    work = frame.dropna(subset=drop_cols + [target]).copy()
    folds = _folds(work, first_train=2022)
    folds = {y: (tr, te) for y, (tr, te) in folds.items() if len(tr) > 50 and len(te) > 50}
    per_year, errs, groups = {}, {m: [] for m in models}, []
    for year, (train, test) in folds.items():
        y = test[target].to_numpy(float)
        row = {}
        for name, cols in models.items():
            p = Ridge().fit(train[cols], train[target]).predict(test[cols])
            row[name] = float(np.abs(y - p).mean())
            errs[name].append(y - p)
        row['n'] = int(len(y))
        per_year[str(year)] = row
        groups.append(test.player_id.to_numpy())
    results = {}
    g = np.concatenate(groups)
    for new, base in comparisons:
        results[f'{new} vs {base}'] = _summary(np.concatenate(errs[base]), np.concatenate(errs[new]), g, per_year, base, new, confidence)
    return {'per_test_year': per_year, 'comparisons': results, 'n_rows': int(len(work))}


def run_e8(root, manifest):
    frame = with_ffopp(champion_rows(root), root)
    frame = with_fp(frame, root, manifest, 'efficiency', ['FPTS.XFP/G', 'FPTS.XTD/G'], {'FPTS.XFP/G': 'fp_xfpg', 'FPTS.XTD/G': 'fp_xtdg'})
    frame = frame[frame.season >= 2022].copy()
    frame['is_te'], frame['is_rb'] = (frame.position == 'TE').astype(float), (frame.position == 'RB').astype(float)
    spec_markets = {'receptions': ('receptions_exp', 'champ_targets'), 'rec_yds': ('rec_yards_gained_exp', 'champ_targets'), 'rec_tds': ('rec_touchdown_exp', 'champ_targets'),
                    'rush_yds': ('rush_yards_gained_exp', 'champ_carries'), 'rush_tds': ('rush_touchdown_exp', 'champ_carries')}
    out, verdicts = {}, []
    confidence = 1 - 0.05 / 20
    for market, (eo, volume) in spec_markets.items():
        rows = _eligible(frame, market)
        base = ['champ_' + market, 'is_te', 'is_rb']
        models = {'M0': base, 'MV': base + [volume], 'MFP': base + ['fp_xfpg', 'fp_xtdg'], 'MEOP': base + ['eop_' + eo],
                  'MEO': base + ['eop_' + eo, 'eor_' + eo, 'k_eo'], 'MEOFP': base + ['eop_' + eo, 'fp_xfpg', 'fp_xtdg']}
        comparisons = [('MFP', 'M0'), ('MEOP', 'M0'), ('MEOFP', 'MEOP'), ('MEO', 'M0')]
        result = _model_compare(rows, 'y_' + market, base, models, comparisons, confidence, ['fp_xfpg', 'fp_xtdg', 'eop_' + eo, volume])
        # extra descriptive context: volume baseline vs Champion
        result['descriptive_MV_vs_M0'] = _model_compare(rows, 'y_' + market, base, models, [('MV', 'M0')], confidence, ['fp_xfpg', 'fp_xtdg', 'eop_' + eo, volume])['comparisons']['MV vs M0']
        out[market] = result
        verdicts += [c['verdict'] for c in result['comparisons'].values()]
    labels = set(verdicts)
    return {'markets': out}, ('PROMISING' if 'PROMISING' in labels else 'REJECTED' if labels == {'REJECTED'} else 'INCONCLUSIVE')


def run_e9(root, manifest):
    frame = with_ffopp(champion_rows(root), root)
    frame = frame[(frame.position == 'RB') & (frame.season >= 2022)].copy()
    frame = with_fp(frame, root, manifest, 'rushing_bell_cow', ['Snaps.Snap %', 'Rushing.ATT %', 'Receiving.TGT %', 'FPTS.XFP %'],
                    {'Snaps.Snap %': 'bc_snap', 'Rushing.ATT %': 'bc_att', 'Receiving.TGT %': 'bc_tgt', 'FPTS.XFP %': 'bc_xfp'})
    adv_cols = ['Advanced.Success %', 'Advanced.STUFF %', 'Advanced.YACO/ATT', 'Advanced.MTF/ATT', 'Advanced.EXP RUN %', 'Advanced.YBCO/ATT', 'Zone Concept.ATT %']
    frame = with_fp(frame, root, manifest, 'rushing_advanced', adv_cols, {c: 'ra_' + str(i) for i, c in enumerate(adv_cols)})
    ra = ['ra_' + str(i) for i in range(len(adv_cols))]
    bc = ['bc_snap', 'bc_att', 'bc_tgt', 'bc_xfp']
    rs = ['champ_carry_share', 'sd_carry_share', 'trend_carry_share']
    out, verdicts = {}, []
    confidence = 1 - 0.05 / 12
    for outcome, base_col, eo in (('carries', 'champ_carries', 'rush_yards_gained_exp'), ('rush_yds', 'champ_rush_yds', 'rush_yards_gained_exp'), ('rush_tds', 'champ_rush_tds', 'rush_touchdown_exp')):
        target = 'y_' + ('carries' if outcome == 'carries' else outcome)
        base = [base_col]
        vol = base + ['champ_carries', 'champ_targets']
        eo_cols = ['eop_rush_yards_gained_exp', 'eop_rush_touchdown_exp']
        models = {'M0': base, 'MV': vol, 'R1': vol + bc, 'R2': vol + ra, 'R3': vol + rs, 'R4': vol + eo_cols}
        comparisons = [('R1', 'MV'), ('R2', 'MV'), ('R3', 'MV'), ('R4', 'MV')]
        drop = bc + ra + rs + eo_cols + ['champ_carries', 'champ_targets', base_col]
        rows = frame[frame.ready]
        result = _model_compare(rows, target, base, models, comparisons, confidence, drop)
        out[outcome] = result
        verdicts += [c['verdict'] for c in result['comparisons'].values()]
    labels = set(verdicts)
    return {'outcomes': out}, ('PROMISING' if 'PROMISING' in labels else 'REJECTED' if labels == {'REJECTED'} else 'INCONCLUSIVE')


RUNNERS = {'E7': run_e7, 'E8': run_e8, 'E9': run_e9}
