"""Phase 3 DFS distributions: P3-8 (one player's DraftKings points) and P3-9 (how players move together, and stack-total calibration).

P3-8  Predictive distribution of a player's core DraftKings points (modelled components plus yardage bonuses): independent components vs a within-player Gaussian copula,
      Champion v1 chain vs v2 chain. Parameters (copula correlations) are measured on development seasons 2021-2023; 2024 validates and 2025 confirms.
P3-9  Cross-player correlations by role pair (QB with his WR1/WR2/WR3/TE1/RB1, same-team pass catchers, opposing offences) measured on 2021-2023 normal scores of the player-level
      probability integral transforms; validated on 2024-2025 by the calibration of the predicted total of QB stacks (independent players vs measured copula).
"""
import numpy as np
import pandas as pd
from scipy.stats import norm

from . import dfs_sim as ds
from .experiments2 import COMMON, champion_rows
from .experiments5 import _cluster_ci
from .experiments9 import actual_partial  # noqa: F401  (kept for symmetry with P3-7)

DRAWS = 400
STACK_DRAWS = 2000
QUANTILES = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
POSITIONS = ('QB', 'RB', 'WR', 'TE')
SEED = 20261008

SPECS = {
    'P3-8': {**COMMON, 'id': 'P3-8', 'title': 'DraftKings player distributions: independent components vs within-player copula, Champion v1 vs v2 chain',
             'hypothesis': 'A Gaussian copula with measured within-player correlations (receptions-yards-TDs, rushing yards-TDs) and the v2 marginals give better floor / median / ceiling quantiles of next-game core DraftKings points than independent components.',
             'football_rationale': 'A receiver\'s catches, yards and touchdowns rise together; independent components understate both ceilings and floors.',
             'population': 'reconstructed Champion rows 2021-2025, QB (starts) / RB / WR / TE; outcome = core DK points (7 modelled components plus 300/100/100 yardage bonuses)',
             'models': {'INDEP-v1': 'independent components, 80/20 chain', 'INDEP-v2': 'independent components, v2 chain', 'COP-v1': 'within-player copula, v1 chain', 'COP-v2': 'within-player copula, v2 chain'},
             'splits': {'development': [2021, 2022, 2023], 'validation': [2024], 'holdout': [2025]}, 'draws': DRAWS,
             'metric': 'mean pinball loss over quantiles .05/.1/.25/.5/.75/.9/.95; coverage of the central 80% interval; share of outcomes above the predicted 90th percentile',
             'primary_comparisons': ['COP-v2 vs INDEP-v2 (value of dependence)', 'INDEP-v2 vs INDEP-v1 (value of the v2 chain)', 'COP-v2 vs INDEP-v1 (both)'],
             'multiple_testing': 'Bonferroni over 4 positions x 3 comparisons = 12 (99.58% intervals)',
             'decision_rule': {'PROMISING': 'pinball improves >= 0.5% in BOTH 2024 and 2025 with the 2025 interval excluding 0', 'REJECTED': 'the 2025 interval lies below 0.5%', 'INCONCLUSIVE': 'otherwise'},
             'rule_numbers': {'min_relative_pinball': 0.005}, 'sources': ['nflverse weekly stats'], 'leakage': 'marginals from games before the target game; copula correlations from 2021-2023 only',
             'markets': ['DFS projection'], 'limitations': 'no salaries or contest data: calibration only, not lineup value'},
    'P3-9': {**COMMON, 'id': 'P3-9', 'title': 'DFS correlations by role pair and stack-total calibration',
             'hypothesis': 'Measured role-pair correlations (QB with WR1/WR2/TE1, opposing offences) make the predicted distribution of a QB-stack total better calibrated than treating players as independent.',
             'football_rationale': 'A quarterback\'s passing outcomes are the receivers\' outcomes; a shootout lifts both offences.',
             'population': 'team-games 2021-2025 with a starting QB1, WR1, WR2 and TE1 (roles by pre-game champion targets / carries)', 'stacks': ['QB+WR1', 'QB+WR1+TE1', 'QB+WR1+WR2', 'QB+WR1+opponent WR1', 'QB+RB1'],
             'models': {'INDEP': 'independent players with their own predicted distributions', 'COPULA': 'Gaussian copula with the role-pair correlations measured on 2021-2023'},
             'splits': {'development': [2021, 2022, 2023], 'validation': [2024], 'holdout': [2025]},
             'metric': 'pinball loss of the stack-total quantiles; coverage of the central 80% interval; PIT standard deviation (1 = calibrated spread)',
             'multiple_testing': 'Bonferroni over 5 stacks (99% intervals)',
             'decision_rule': {'PROMISING': 'pinball improves >= 0.5% in BOTH 2024 and 2025 with the 2025 interval excluding 0', 'REJECTED': 'the 2025 interval lies below 0.5%', 'INCONCLUSIVE': 'otherwise'},
             'rule_numbers': {'min_relative_pinball': 0.005}, 'sources': ['nflverse weekly stats'], 'leakage': 'as P3-8', 'markets': ['DFS stacks'],
             'limitations': 'defence/special teams are not modelled; no ownership or salary data'},
}


def _prep(root):
    frame = champion_rows(root)
    frame = frame[frame.position.isin(POSITIONS) & ~(frame.position.eq('QB') & ~frame.start)].reset_index(drop=True)
    return frame


def _sample_core(frame, version, corr, draws, rng, independent):
    """(rows x draws) core DK samples for a frame of one position; corr is the within-player normal-score correlation matrix of the position's components."""
    pos = frame.position.iloc[0]
    comps = ds.COMPONENTS[pos]
    marg = {m: ds.Marginal(m, frame, version) for m in comps}
    z = rng.standard_normal((len(frame), draws, len(comps)))
    if not independent:
        L = np.linalg.cholesky(corr + 1e-9 * np.eye(len(comps)))
        z = z @ L.T
    out = {m: marg[m].ppf(norm.cdf(z[:, :, j])) for j, m in enumerate(comps)}
    return ds.dk_core(out), marg


def _pits(frame, version, seed):
    """Normal scores of the randomised PIT of every realised component (rows x components)."""
    pos = frame.position.iloc[0]
    comps = ds.COMPONENTS[pos]
    rng = np.random.default_rng(seed)
    cols = []
    for m in comps:
        marg = ds.Marginal(m, frame, version)
        y = frame['y_' + m].to_numpy(float)
        cols.append(norm.ppf(np.clip(marg.pit(np.nan_to_num(y), rng), 1e-6, 1 - 1e-6)))
    return np.column_stack(cols)


def _actual_core(frame):
    comps = ds.COMPONENTS[frame.position.iloc[0]]
    return ds.dk_core({m: np.nan_to_num(frame['y_' + m].to_numpy(float)) for m in comps})


def _pinball(samples, y):
    qs = np.quantile(samples, QUANTILES, axis=1)
    loss = 0.0
    for q, pred in zip(QUANTILES, qs):
        d = y - pred
        loss = loss + np.maximum(q * d, (q - 1) * d)
    return loss / len(QUANTILES), qs


def run_p3_8(root, manifest):
    frame = _prep(root)
    conf = 1 - 0.05 / 12
    out, verdicts = {'positions': {}}, []
    for pos in POSITIONS:
        sub = frame[frame.position == pos].reset_index(drop=True)
        dev = sub[sub.season <= 2023].reset_index(drop=True)
        cors = {}
        for version in ('v1', 'v2'):
            scores = _pits(dev, version, SEED)
            cors[version] = ds.nearest_correlation(np.corrcoef(scores.T))
        res = {'within_player_correlation_v2': np.round(cors['v2'], 3).tolist(), 'components': ds.COMPONENTS[pos], 'cells': {}}
        gates = {}
        for label, season in (('validation', 2024), ('holdout', 2025)):
            t = sub[sub.season == season].reset_index(drop=True)
            y = _actual_core(t)
            rng = np.random.default_rng(SEED + season)
            models, per_row = {}, {}
            for name, (version, indep) in {'INDEP-v1': ('v1', True), 'INDEP-v2': ('v2', True), 'COP-v1': ('v1', False), 'COP-v2': ('v2', False)}.items():
                samples, _ = _sample_core(t, version, cors[version], DRAWS, rng, indep)
                loss, qs = _pinball(samples, y)
                per_row[name] = loss
                models[name] = {'pinball': float(loss.mean()), 'coverage80': float(((y >= qs[1]) & (y <= qs[5])).mean()), 'above_p90': float((y > qs[5]).mean()), 'below_p10': float((y < qs[1]).mean()),
                                'mean_pred': float(samples.mean()), 'mean_actual': float(y.mean())}
            comparisons = {}
            for new, base in (('COP-v2', 'INDEP-v2'), ('INDEP-v2', 'INDEP-v1'), ('COP-v2', 'INDEP-v1')):
                gain = (per_row[base] - per_row[new]) / per_row[base].mean()
                m, lo, hi = _cluster_ci(gain, t.player_id.to_numpy(), conf)
                comparisons[f'{new} vs {base}'] = {'relative_pinball_gain': m, 'ci': [lo, hi]}
                gates.setdefault(f'{new} vs {base}', {})[label] = (m, lo, hi)
            res['cells'][label] = {'n': int(len(t)), 'models': models, 'comparisons': comparisons}
        res['verdicts'] = {}
        for name, g in gates.items():
            ok = g['validation'][0] >= 0.005 and g['holdout'][0] >= 0.005 and g['holdout'][1] > 0
            lab = 'PROMISING' if ok else ('REJECTED' if g['holdout'][2] < 0.005 else 'INCONCLUSIVE')
            res['verdicts'][name] = lab
            verdicts.append(lab)
        out['positions'][pos] = res
    status = 'PROMISING' if 'PROMISING' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return out, status


# ------------------------------------------------------------------ P3-9
ROLE_ORDER = ['QB', 'RB1', 'WR1', 'WR2', 'WR3', 'TE1']


def _player_distributions(root):
    """Core DK samples (rows x draws) and the PIT normal score of every player-game, with the v2 chain and the within-player copula fitted on development seasons."""
    frame = _prep(root)
    parts, samples_all = [], {}
    for pos in POSITIONS:
        sub = frame[frame.position == pos].reset_index(drop=True)
        dev = sub[sub.season <= 2023]
        corr = ds.nearest_correlation(np.corrcoef(_pits(dev, 'v2', SEED).T))
        rng = np.random.default_rng(SEED + 7)
        samples, _ = _sample_core(sub, 'v2', corr, DRAWS, rng, False)
        y = _actual_core(sub)
        # randomised PIT of the realised core against the sampled core distribution
        below = (samples < y[:, None]).mean(axis=1)
        equal = (samples == y[:, None]).mean(axis=1)
        u = below + rng.random(len(sub)) * equal
        sub = sub.assign(core=y, core_u=np.clip(u, 1 / (2 * DRAWS), 1 - 1 / (2 * DRAWS)))
        sub['core_z'] = norm.ppf(sub.core_u)
        sub['ridx'] = np.arange(len(sub))
        samples_all[pos] = samples
        parts.append((pos, sub))
    return parts, samples_all


def _roles(parts, samples_all):
    rows = []
    for pos, sub in parts:
        for r in sub.itertuples():
            rows.append((r.season, r.week, r.team, pos, r.player_id, r.champ_targets if pos in ('WR', 'TE') else (r.champ_carries if pos == 'RB' else 0.0), r.core, r.core_z, pos, r.ridx, r.opponent))
    df = pd.DataFrame(rows, columns=['season', 'week', 'team', 'pos', 'player_id', 'rank_key', 'core', 'z', 'pos2', 'idx', 'opponent'])
    df['role'] = None
    for _, g in df.groupby(['season', 'week', 'team']):
        for pos, label, n in (('QB', 'QB', 1), ('RB', 'RB', 1), ('WR', 'WR', 3), ('TE', 'TE', 1)):
            ranked = g[g.pos == pos].sort_values('rank_key', ascending=False).head(n)
            for k, ix in enumerate(ranked.index):
                df.at[ix, 'role'] = f'{label}{k + 1}' if label != 'QB' else 'QB'
    return df[df.role.notna()]


def run_p3_9(root, manifest):
    parts, samples_all = _player_distributions(root)
    df = _roles(parts, samples_all)
    pivot = df.pivot_table(index=['season', 'week', 'team'], columns='role', values='z', aggfunc='first')
    opp = df.pivot_table(index=['season', 'week', 'opponent'], columns='role', values='z', aggfunc='first')
    opp.index = opp.index.set_names(['season', 'week', 'team'])
    opp = opp.add_prefix('opp_')
    joined = pivot.join(opp, how='left')
    dev = joined[joined.index.get_level_values('season') <= 2023]
    names = ROLE_ORDER + [f'opp_{r}' for r in ROLE_ORDER]
    corr = dev[names].corr(min_periods=100)
    counts = dev[names].apply(lambda a: dev[names].notna().mul(a.notna(), axis=0).sum())
    out = {'role_correlations_dev_2021_2023': {a: {b: (None if corr.loc[a, b] != corr.loc[a, b] else round(float(corr.loc[a, b]), 3)) for b in names} for a in names},
           'pair_counts': {a: {b: int(counts.loc[a, b]) for b in names} for a in names}}
    # bootstrap uncertainty for the headline pairs
    headline = [('QB', 'WR1'), ('QB', 'WR2'), ('QB', 'TE1'), ('QB', 'RB1'), ('QB', 'opp_QB'), ('QB', 'opp_WR1'), ('WR1', 'WR2'), ('WR1', 'TE1'), ('RB1', 'opp_QB')]
    rng = np.random.default_rng(SEED)
    out['headline_pairs'] = {}
    for a, b in headline:
        x = dev[[a, b]].dropna().to_numpy()
        boots = [np.corrcoef(x[idx, 0], x[idx, 1])[0, 1] for idx in (rng.integers(0, len(x), len(x)) for _ in range(500))]
        out['headline_pairs'][f'{a}~{b}'] = {'r': float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]), 'ci95': [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))], 'n': int(len(x))}
    # stack-total calibration on validation / holdout
    by_key = {}
    for pos, sub in parts:
        for r in sub.itertuples():
            by_key[(r.season, r.week, r.team, r.player_id)] = (pos, r.ridx)
    lookup = df.set_index(['season', 'week', 'team', 'role'])
    stacks = {'QB+WR1': ['QB', 'WR1'], 'QB+WR1+TE1': ['QB', 'WR1', 'TE1'], 'QB+WR1+WR2': ['QB', 'WR1', 'WR2'], 'QB+WR1+opp_WR1': ['QB', 'WR1', 'opp_WR1'], 'QB+RB1': ['QB', 'RB1']}
    conf = 1 - 0.05 / len(stacks)
    rng = np.random.default_rng(SEED + 1)
    results, verdicts = {}, []
    for name, roles in stacks.items():
        cell = {}
        sub_corr_roles = roles
        R = np.eye(len(roles))
        for i, a in enumerate(roles):
            for j, b in enumerate(roles):
                if i != j:
                    v = corr.loc[a, b] if a in corr.index and b in corr.columns and corr.loc[a, b] == corr.loc[a, b] else 0.0
                    R[i, j] = v
        R = ds.nearest_correlation(R)
        for label, season in (('validation', 2024), ('holdout', 2025)):
            idx = [i for i in joined.index if i[0] == season]
            gains, cover, pit_vals = {'INDEP': [], 'COPULA': []}, {'INDEP': [], 'COPULA': []}, {'INDEP': [], 'COPULA': []}
            groups = []
            for key in idx:
                season_, week_, team_ = key
                members = []
                ok = True
                for role in roles:
                    if role.startswith('opp_'):
                        row = df[(df.season == season_) & (df.week == week_) & (df.opponent == team_) & (df.role == role[4:])]
                        if row.empty:
                            ok = False
                            break
                        r = row.iloc[0]
                    else:
                        try:
                            r = lookup.loc[(season_, week_, team_, role)]
                        except KeyError:
                            ok = False
                            break
                        if isinstance(r, pd.DataFrame):
                            r = r.iloc[0]
                    members.append(r)
                if not ok:
                    continue
                draws_each = []
                actual = 0.0
                for r in members:
                    pos2 = r['pos']
                    sub = dict(parts)[pos2]
                    draws_each.append(np.sort(samples_all[pos2][r['idx']]))
                    actual += r['core']
                zi = rng.standard_normal((STACK_DRAWS, len(members)))
                zc = zi @ np.linalg.cholesky(R).T
                q = lambda z, d: d[np.clip((norm.cdf(z) * len(d)).astype(int), 0, len(d) - 1)]
                tot_i = sum(q(zi[:, k], draws_each[k]) for k in range(len(members)))
                tot_c = sum(q(zc[:, k], draws_each[k]) for k in range(len(members)))
                for nm, tot in (('INDEP', tot_i), ('COPULA', tot_c)):
                    qs = np.quantile(tot, QUANTILES)
                    loss = sum(np.maximum(qq * (actual - p), (qq - 1) * (actual - p)) for qq, p in zip(QUANTILES, qs)) / len(QUANTILES)
                    gains[nm].append(loss)
                    cover[nm].append(float(qs[1] <= actual <= qs[5]))
                    pit_vals[nm].append(float(((tot < actual).mean() + (tot == actual).mean() * rng.random())))
                groups.append(f'{season_}-{week_}-{team_}')
            li, lc = np.array(gains['INDEP']), np.array(gains['COPULA'])
            gain = (li - lc) / li.mean()
            m, lo, hi = _cluster_ci(gain, np.array(groups), conf)
            cell[label] = {'n': int(len(li)), 'pinball_indep': float(li.mean()), 'pinball_copula': float(lc.mean()), 'relative_gain': m, 'ci': [lo, hi],
                           'coverage80_indep': float(np.mean(cover['INDEP'])), 'coverage80_copula': float(np.mean(cover['COPULA'])),
                           'pit_sd_indep': float(norm.ppf(np.clip(pit_vals['INDEP'], 1e-3, 1 - 1e-3)).std()), 'pit_sd_copula': float(norm.ppf(np.clip(pit_vals['COPULA'], 1e-3, 1 - 1e-3)).std())}
        ok = cell['validation']['relative_gain'] >= 0.005 and cell['holdout']['relative_gain'] >= 0.005 and cell['holdout']['ci'][0] > 0
        lab = 'PROMISING' if ok else ('REJECTED' if cell['holdout']['ci'][1] < 0.005 else 'INCONCLUSIVE')
        cell['verdict'] = lab
        results[name] = cell
        verdicts.append(lab)
    out['stacks'] = results
    status = 'PROMISING' if 'PROMISING' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return out, status


RUNNERS = {'P3-8': run_p3_8, 'P3-9': run_p3_9}
