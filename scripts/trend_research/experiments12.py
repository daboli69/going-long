"""P4-1: GOING Score v2, a player-level situation index (QB/RB/WR/TE), validated chronologically.

Everything here uses PUBLIC data only (nflverse player stats and snap counts, ffverse ffopportunity expected points, nflverse schedules). No licensed
Fantasy Points value is read or written. Weights are fitted on development seasons 2021-2023 ONLY, frozen into config/going_score_weights.json, then scored
on 2024 (validation) and 2025 (holdout). The runner writes the frozen config and aggregate metrics (no player-level rows) to the ledger.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import going_score_build as gsb  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO / 'config' / 'going_score_weights.json'
DEV, VAL, HOLD = (2021, 2022, 2023), 2024, 2025
POS = gsb.POSITIONS
H_GRID = (3.0, 5.0, 8.0)
RIDGE_PER_ROW = 0.02
MIN_PRIOR = 5
DRAWS = 1000
SEED = 20261009
N_COMPARISONS = 12  # 4 positions x 3 comparators
MODELS = ('SCORE', 'B1_ppr_shrunk', 'B1b_ppr_last6', 'B2_xfp_shrunk', 'B3_champion_window')
MODEL_COL = {'B1_ppr_shrunk': 'production', 'B1b_ppr_last6': 'ppr_l6', 'B2_xfp_shrunk': 'opportunity', 'B3_champion_window': 'champion_ppr'}

SPECS = {
    'P4-1': {
        'id': 'P4-1', 'title': 'GOING Score v2: a player-level situation index vs trailing PPR, trailing xFP and the Champion window (next game and next three games)',
        'hypothesis': 'A position-specific, shrunk, recency-weighted index of expected-points opportunity, team share, efficiency residual, snap role, availability and their trends '
                      'ranks next-game and next-three-game PPR at least as well as shrunk trailing xFP and better than trailing PPR or the Champion window, and moves when roles change.',
        'football_rationale': 'Expected points measure the quality of a player\'s touches rather than their luck; role and availability decide whether the opportunity continues; '
                              'actual-minus-expected is mostly luck so it should earn only a small weight. Independent Researcher B found that a composite adds little over shrunk '
                              'trailing xFP except a half-weighted residual; this experiment tests that claim with a different build.',
        'population': 'QB (games with >= 10 attempts) / RB / WR / TE regular-season appearances 2021-2025 with >= 5 prior appearances since 2019 (the Champion minimum, so all models score identical rows); '
                      'outcome is conditional on playing in the target game',
        'components': {'production': 'EW PPR per game (display only, weight 0: equals opportunity + efficiency)', 'opportunity': 'EW xFP per game (ffopportunity total_fantasy_points_exp)',
                       'team_share': 'EW share of team xFP', 'efficiency': 'EW PPR minus xFP', 'role': 'EW offense snap share', 'availability': 'share of the team\'s last 8 games played',
                       'opp_trend': 'L3 xFP minus preceding six, damped', 'role_trend': 'L3 snap share minus preceding six, damped'},
        'feature_params': {'window': 12, 'half_life_grid': list(H_GRID), 'offseason_discount': 0.7, 'shrink_k': gsb.DEFAULT_PARAMS['shrink_k'], 'availability_prior': 0.85,
                           'availability_k': 2.0, 'trend_k': 3.0},
        'fit': {'seasons': list(DEV), 'method': 'per position: z-score features with development mean/sd, non-negative least squares with ridge lambda = 0.02 n on next-game PPR, weights normalised to sum 1; '
                                                 'half-life chosen by leave-one-development-season-out MAE; linear calibration y ~ a + b*x fitted on development rows for every model'},
        'splits': {'development': list(DEV), 'validation': [VAL], 'holdout': [HOLD]},
        'models': {'SCORE': 'GOING Score raw', 'B1_ppr_shrunk': 'recency-weighted shrunk trailing PPR (same half-life, shrinkage)', 'B1b_ppr_last6': 'plain mean of last 6 PPR',
                   'B2_xfp_shrunk': 'recency-weighted shrunk trailing xFP', 'B3_champion_window': 'Champion window (12 games, 80/20 current/earlier season weights) applied to PPR'},
        'metrics': 'MAE of calibrated predictions (primary), R^2, pooled Spearman rank correlation; horizons next game (primary) and mean of the next three calendar weeks (>= 2 appearances); player-clustered bootstrap',
        'primary_comparisons': ['SCORE vs B1_ppr_shrunk', 'SCORE vs B2_xfp_shrunk', 'SCORE vs B3_champion_window'],
        'bootstrap': f'cluster by player, {DRAWS} draws, seed {SEED}; primary intervals Bonferroni-adjusted over {N_COMPARISONS} comparisons (99.58%)',
        'decision_rule': {'PROMISING (position)': 'relative MAE gain >= 0.5% over each of B1, B2, B3 in BOTH 2024 and 2025 and the adjusted 2025 interval of each excludes 0',
                          'NON-INFERIOR to B2 (position)': 'the adjusted 2025 interval of the relative MAE gain over B2 has lower bound >= -0.5%',
                          'REJECTED': 'for every position the adjusted 2025 upper bound over B1 or B2 is below +0.5%: the index is no better than trailing production/opportunity, and is documented only as a descriptive display',
                          'INCONCLUSIVE': 'anything else'},
        'rule_numbers': {'min_relative_mae_gain': 0.005, 'non_inferiority_margin': -0.005},
        'secondary': ['drop-one-component ablation (validation, holdout)', 'week-to-week rank autocorrelation of the position percentile vs B1/B2', 'responsiveness: change in percentile after a +/-15 point snap-share change over two games',
                      'EXPLORATORY ablation: team implied total from the schedule (spread/total) added as a component, never part of the shipped score'],
        'sources': ['nflverse player stats', 'nflverse snap counts', 'ffverse ffopportunity ep_weekly', 'nflverse players', 'nflverse schedules (games.csv)'],
        'leakage': 'every feature at week w uses rows with (season, week) < w; priors, z-score statistics, weights, calibration and anchors come from 2021-2023 only; the half-life is chosen inside development',
        'limitations': 'outcomes are conditional on playing (availability value is understated); QB filter is attempts >= 10, not verified starts; no injuries or matchups are in the score; '
                       'scoring-error accuracy is not a betting-return backtest',
        'markets': ['player situation index'],
    },
}


# ---------------------------------------------------------------- statistics helpers

def _boot_idx(n_clusters, draws=DRAWS, seed=SEED):
    return np.random.default_rng(seed).integers(0, n_clusters, size=(draws, n_clusters))


def _cluster_sums(values, inverse, n):
    return np.bincount(inverse, weights=values, minlength=n)


def rel_gain_ci(abs_new, abs_base, groups, level):
    """Relative MAE gain 1 - MAE_new/MAE_base with a player-clustered bootstrap interval at `level`."""
    _, inv = np.unique(groups, return_inverse=True)
    n = inv.max() + 1
    a, b = _cluster_sums(abs_new, inv, n), _cluster_sums(abs_base, inv, n)
    idx = _boot_idx(n)
    boot = 1 - a[idx].sum(1) / b[idx].sum(1)
    lo, hi = np.quantile(boot, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(1 - a.sum() / b.sum()), float(lo), float(hi)


def r2_ci(y, pred, groups, level=0.95):
    _, inv = np.unique(groups, return_inverse=True)
    n = inv.max() + 1
    cnt = np.bincount(inv, minlength=n).astype(float)
    sy, syy = _cluster_sums(y, inv, n), _cluster_sums(y * y, inv, n)
    sse = _cluster_sums((y - pred) ** 2, inv, n)
    idx = _boot_idx(n, seed=SEED + 1)

    def r2(i):
        c, s1, s2, e = cnt[i].sum(1), sy[i].sum(1), syy[i].sum(1), sse[i].sum(1)
        return 1 - e / (s2 - s1 ** 2 / c)
    est = float(1 - sse.sum() / (syy.sum() - sy.sum() ** 2 / cnt.sum()))
    lo, hi = np.quantile(r2(idx), [(1 - level) / 2, 1 - (1 - level) / 2])
    return est, float(lo), float(hi)


def spearman(a, b):
    ra, rb = rankdata(a), rankdata(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def spearman_ci(x, y, groups, level=0.95, draws=300):
    _, inv = np.unique(groups, return_inverse=True)
    members = [np.where(inv == i)[0] for i in range(inv.max() + 1)]
    idx = _boot_idx(len(members), draws=draws, seed=SEED + 2)
    boot = []
    for row in idx:
        rows = np.concatenate([members[i] for i in row])
        boot.append(spearman(x[rows], y[rows]))
    lo, hi = np.quantile(boot, [(1 - level) / 2, 1 - (1 - level) / 2])
    return spearman(x, y), float(lo), float(hi)


def mean_ci(values, groups, level=0.95):
    values = np.asarray(values, float)
    _, inv = np.unique(groups, return_inverse=True)
    n = inv.max() + 1
    s, c = _cluster_sums(values, inv, n), np.bincount(inv, minlength=n).astype(float)
    idx = _boot_idx(n, seed=SEED + 3)
    boot = s[idx].sum(1) / c[idx].sum(1)
    lo, hi = np.quantile(boot, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(s.sum() / c.sum()), float(lo), float(hi)


def ols(x, y):
    X = np.column_stack([np.ones(len(x)), x])
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    return float(coef[0]), float(coef[1])


def fit_nnls(Z, y, ridge_per_row=RIDGE_PER_ROW):
    n, k = Z.shape
    yc = y - y.mean()
    A = np.vstack([Z, np.sqrt(ridge_per_row * n) * np.eye(k)])
    b = np.concatenate([yc, np.zeros(k)])
    beta, _ = nnls(A, b)
    return beta


def z_stats(table, cols):
    return {c: {'mean': float(table[c].mean()), 'sd': float(table[c].std(ddof=0) or 1.0)} for c in cols}


def z_matrix(table, stats, cols):
    return np.column_stack([np.where(table[c].isna(), 0.0, (table[c] - stats[c]['mean']) / stats[c]['sd']) for c in cols])


def fit_position(dev, cols, y_col='y1'):
    stats = z_stats(dev, cols)
    Z = z_matrix(dev, stats, cols)
    beta = fit_nnls(Z, dev[y_col].to_numpy())
    if beta.sum() <= 0:
        beta = np.ones(len(cols))
    w = beta / beta.sum()
    return stats, w


def make_config_position(dev, priors, w, stats):
    """Config block for one position given fitted weights (dev supplies calibration and anchors)."""
    comps = {c: {'weight': float(w[i]), 'mean': stats[c]['mean'], 'sd': stats[c]['sd']} for i, c in enumerate(gsb.SCORED)}
    block = {'priors': priors, 'components': comps}
    raw = gsb.raw_score(dev, block)
    a, b = ols(raw, dev.y1.to_numpy())
    block['calibration_next_game'] = {'intercept': a, 'slope': b}
    block['anchors'] = {'low': float(np.quantile(raw, 0.02)), 'high': float(np.quantile(raw, 0.98))}
    return block


# ---------------------------------------------------------------- data

def load_all(cache_root):
    cache = Path(cache_root) / 'research' / 'cache'
    seasons = list(range(2019, 2026))
    weekly, snaps, players, ffopp = gsb.load_public(cache, seasons, current=None, offline=True)
    panel, team_games, league_weeks = gsb.build_panel(weekly, snaps, players, ffopp)
    games = pd.read_csv(cache / 'games.csv', usecols=['season', 'week', 'game_type', 'home_team', 'away_team', 'spread_line', 'total_line'])
    games = games[games.game_type == 'REG']
    home = pd.DataFrame({'season': games.season, 'week': games.week, 'team': games.home_team, 'implied': (games.total_line + games.spread_line) / 2})
    away = pd.DataFrame({'season': games.season, 'week': games.week, 'team': games.away_team, 'implied': (games.total_line - games.spread_line) / 2})
    implied = pd.concat([home, away])
    implied['key'] = implied.season * 100 + implied.week
    return panel, team_games, league_weeks, implied.set_index(['team', 'key']).implied.to_dict()


def build_tables(panel, team_games, league_weeks, half_life):
    params = {**gsb.DEFAULT_PARAMS, 'half_life': half_life}
    priors = gsb.position_priors(panel, DEV)
    pri = {pos: {**priors[pos]} for pos in POS}
    table = gsb.asof_table(panel, team_games, league_weeks, params, pri, all_week_seasons=(VAL, HOLD), appearance_seasons=DEV + (VAL, HOLD))
    return table, params, priors


def mae_calibrated(dev, test, col, y_col='y1'):
    a, b = ols(dev[col].to_numpy(), dev[y_col].to_numpy())
    return np.abs(test[y_col].to_numpy() - (a + b * test[col].to_numpy())).mean()


def choose_half_life(panel, team_games, league_weeks):
    results, tables = {}, {}
    for H in H_GRID:
        table, params, priors = build_tables(panel, team_games, league_weeks, H)
        tables[H] = (table, params, priors)
        dev = table[table.season.isin(DEV) & table.appeared & (table.n_prior >= MIN_PRIOR)]
        total = []
        for pos in POS:
            d = dev[dev.position == pos]
            for held in DEV:
                tr, te = d[d.season != held], d[d.season == held]
                stats, w = fit_position(tr, gsb.SCORED)
                tr = tr.assign(score=z_matrix(tr, stats, gsb.SCORED) @ w)
                te = te.assign(score=z_matrix(te, stats, gsb.SCORED) @ w)
                total.append(mae_calibrated(tr, te, 'score') / te.y1.abs().mean())
        results[H] = float(np.mean(total))
    best = min(results, key=results.get)
    return best, results, tables[best]


# ---------------------------------------------------------------- evaluation

def evaluate(table, cfg, implied):
    out = {'positions': {}}
    ev = table[table.appeared & (table.n_prior >= MIN_PRIOR)].copy()
    ev = gsb.score_table(ev, cfg)
    ev['SCORE'] = ev.raw_score
    for pos in POS:
        block = {}
        d = ev[ev.position == pos]
        dev = d[d.season.isin(DEV)]
        for horizon, ycol in (('next_game', 'y1'), ('next_3', 'y3')):
            dev_h = dev[dev[ycol].notna()]
            cal = {m: ols((dev_h[m] if m == 'SCORE' else dev_h[MODEL_COL[m]]).to_numpy(), dev_h[ycol].to_numpy()) for m in MODELS}
            for season, label in ((VAL, 'validation_2024'), (HOLD, 'holdout_2025')):
                te = d[(d.season == season) & d[ycol].notna()]
                y, g = te[ycol].to_numpy(), te.player_id.to_numpy()
                preds, errs = {}, {}
                for m in MODELS:
                    x = (te[m] if m == 'SCORE' else te[MODEL_COL[m]]).to_numpy()
                    preds[m] = cal[m][0] + cal[m][1] * x
                    errs[m] = np.abs(y - preds[m])
                cell = {'n': int(len(te)), 'players': int(len(set(g))), 'models': {}, 'vs': {}}
                for m in MODELS:
                    x = (te[m] if m == 'SCORE' else te[MODEL_COL[m]]).to_numpy()
                    r2 = r2_ci(y, preds[m], g)
                    rho = spearman_ci(x, y, g)
                    cell['models'][m] = {'mae': float(errs[m].mean()), 'r2': r2[0], 'r2_ci95': [r2[1], r2[2]], 'spearman': rho[0], 'spearman_ci95': [rho[1], rho[2]]}
                for base in ('B1_ppr_shrunk', 'B1b_ppr_last6', 'B2_xfp_shrunk', 'B3_champion_window'):
                    est, lo, hi = rel_gain_ci(errs['SCORE'], errs[base], g, 1 - 0.05 / N_COMPARISONS)
                    e95 = rel_gain_ci(errs['SCORE'], errs[base], g, 0.95)
                    cell['vs'][base] = {'relative_mae_gain': est, 'ci_adj': [lo, hi], 'ci95': [e95[1], e95[2]],
                                        'delta_r2': cell['models']['SCORE']['r2'] - cell['models'][base]['r2']}
                block.setdefault(horizon, {})[label] = cell
        out['positions'][pos] = block
    out['verdicts'] = verdicts(out['positions'])
    return out, ev


def verdicts(positions):
    rule = SPECS['P4-1']['rule_numbers']
    res = {}
    for pos, block in positions.items():
        v, h = block['next_game']['validation_2024']['vs'], block['next_game']['holdout_2025']['vs']
        prom = all(v[b]['relative_mae_gain'] >= rule['min_relative_mae_gain'] and h[b]['relative_mae_gain'] >= rule['min_relative_mae_gain'] and h[b]['ci_adj'][0] > 0
                   for b in ('B1_ppr_shrunk', 'B2_xfp_shrunk', 'B3_champion_window'))
        non_inf = h['B2_xfp_shrunk']['ci_adj'][0] >= rule['non_inferiority_margin']
        no_better = h['B1_ppr_shrunk']['ci_adj'][1] < rule['min_relative_mae_gain'] or h['B2_xfp_shrunk']['ci_adj'][1] < rule['min_relative_mae_gain']
        res[pos] = {'promising': bool(prom), 'non_inferior_to_xfp': bool(non_inf), 'no_better_than_baseline': bool(no_better)}
    if any(r['promising'] for r in res.values()):
        status = 'PROMISING'
    elif all(r['no_better_than_baseline'] for r in res.values()):
        status = 'REJECTED'
    else:
        status = 'INCONCLUSIVE'
    res['overall'] = status
    return res


def ablations(table, cfg, implied):
    ev = table[table.appeared & (table.n_prior >= MIN_PRIOR)].copy()
    ev['implied'] = [implied.get((t, k), np.nan) for t, k in zip(ev.team_now, ev.key)]
    out = {}
    for pos in POS:
        d = ev[ev.position == pos]
        dev = d[d.season.isin(DEV)]
        full_stats, full_w = fit_position(dev, gsb.SCORED)
        cols_sets = {'full': gsb.SCORED, **{f'drop_{c}': tuple(x for x in gsb.SCORED if x != c) for c in gsb.SCORED}, 'only_opportunity': ('opportunity',)}
        rows = {}
        for name, cols in cols_sets.items():
            stats, w = fit_position(dev, cols)
            tr = dev.assign(score=z_matrix(dev, stats, cols) @ w)
            for season, label in ((VAL, 'validation_2024'), (HOLD, 'holdout_2025')):
                te = d[d.season == season]
                te = te.assign(score=z_matrix(te, stats, cols) @ w)
                rows.setdefault(name, {})[label] = float(mae_calibrated(tr, te, 'score'))
        # exploratory: schedule implied team total as an extra regressor
        dev2 = dev[dev.implied.notna()]
        cols2 = gsb.SCORED + ('implied',)
        stats2 = z_stats(dev2, cols2)
        beta = fit_nnls(z_matrix(dev2, stats2, cols2), dev2.y1.to_numpy())
        w2 = beta / beta.sum()
        tr2 = dev2.assign(score=z_matrix(dev2, stats2, cols2) @ w2)
        for season, label in ((VAL, 'validation_2024'), (HOLD, 'holdout_2025')):
            te = d[(d.season == season) & d.implied.notna()]
            te2 = te.assign(score=z_matrix(te, stats2, cols2) @ w2)
            base_stats, base_w = fit_position(dev2, gsb.SCORED)
            trb = dev2.assign(score=z_matrix(dev2, base_stats, gsb.SCORED) @ base_w)
            teb = te.assign(score=z_matrix(te, base_stats, gsb.SCORED) @ base_w)
            rows.setdefault('exploratory_plus_implied_total', {})[label] = {'mae': float(mae_calibrated(tr2, te2, 'score')), 'mae_without': float(mae_calibrated(trb, teb, 'score')),
                                                                            'implied_weight': float(w2[-1])}
        out[pos] = {k: v for k, v in rows.items()}
        out[pos]['relative_mae_change_when_dropped'] = {
            c: {label: (rows['drop_' + c][label] / rows['full'][label] - 1) for label in ('validation_2024', 'holdout_2025')} for c in gsb.SCORED}
    return out


def stability_and_response(table, cfg, league_weeks):
    """Week-to-week rank autocorrelation of the position percentile, and responsiveness to large snap-share changes."""
    t = table[table.season.isin((VAL, HOLD)) & (table.n_prior >= MIN_PRIOR)].copy()
    t = gsb.score_table(t, cfg)
    for name, col in (('B1', 'production'), ('B2', 'opportunity')):
        t['pct_' + name] = np.nan
        for pos in POS:
            m = t.position == pos
            t.loc[m, 'pct_' + name] = gsb.pool_percentile(t.loc[m, col].to_numpy(), (t.loc[m, 'key'].astype(str)).to_numpy())
    t['pct_SCORE'] = t.pctile
    stab = {}
    for pos in POS:
        d = t[t.position == pos]
        per_model = {}
        for model in ('SCORE', 'B1', 'B2'):
            rhos = []
            for season in (VAL, HOLD):
                weeks = sorted(set(d[d.season == season].week))
                for w1, w2 in zip(weeks[1:-1], weeks[2:]):
                    a = d[d.key == season * 100 + w1].set_index('player_id')['pct_' + model]
                    b = d[d.key == season * 100 + w2].set_index('player_id')['pct_' + model]
                    common = a.index.intersection(b.index)
                    if len(common) > 20:
                        rhos.append(spearman(a[common].to_numpy(), b[common].to_numpy()))
            arr = np.array(rhos)
            idx = np.random.default_rng(SEED + 4).integers(0, len(arr), size=(DRAWS, len(arr)))
            boot = arr[idx].mean(1)
            per_model[model] = {'mean_week_to_week_spearman': float(arr.mean()), 'ci95_over_week_pairs': [float(np.quantile(boot, .025)), float(np.quantile(boot, .975))], 'week_pairs': int(len(arr))}
        stab[pos] = per_model
    resp = {}
    for pos in ('RB', 'WR', 'TE'):
        d = t[t.position == pos].copy()
        d['delta'] = np.nan
        look = d.set_index(['player_id', 'key'])
        rows = []
        for season in (VAL, HOLD):
            weeks = sorted(set(league_weeks[season]))
            for i in range(2, len(weeks)):
                k0, k1 = season * 100 + weeks[i - 2], season * 100 + weeks[i]
                a, b = d[d.key == k0].set_index('player_id'), d[d.key == k1].set_index('player_id')
                common = a.index.intersection(b.index)
                for pid in common:
                    l2, p6 = b.at[pid, 'role_snap_l2'], b.at[pid, 'role_snap_prior6']
                    if np.isnan(l2) or np.isnan(p6):
                        continue
                    ch = l2 - p6
                    rows.append({'pid': pid, 'event': 'up' if ch >= 15 else 'down' if ch <= -15 else 'none',
                                 **{f'd_{m}': b.at[pid, 'pct_' + m] - a.at[pid, 'pct_' + m] for m in ('SCORE', 'B1', 'B2')}})
        r = pd.DataFrame(rows)
        cell = {}
        for m in ('SCORE', 'B1', 'B2'):
            up, down = r[r.event == 'up'], r[r.event == 'down']
            cell[m] = {'mean_change_up': float(up['d_' + m].mean()), 'mean_change_down': float(down['d_' + m].mean()), 'mean_change_none': float(r[r.event == 'none']['d_' + m].mean()),
                       'n_up': int(len(up)), 'n_down': int(len(down))}
            sel = r[r.event.isin(['up', 'down'])]
            sign = np.where(sel.event == 'up', 1.0, -1.0)
            est, lo, hi = mean_ci(sign * sel['d_' + m].to_numpy(), sel.pid.to_numpy())
            cell[m]['up_minus_down_half_gap'] = est
            cell[m]['up_minus_down_ci95'] = [lo, hi]
        resp[pos] = cell
    return stab, resp


def run_p4_1(root, manifest):
    spec = SPECS['P4-1']
    panel, team_games, league_weeks, implied = load_all(root)
    best_h, cv, (table, params, priors) = choose_half_life(panel, team_games, league_weeks)
    dev = table[table.season.isin(DEV) & table.appeared & (table.n_prior >= MIN_PRIOR)]
    positions_cfg = {}
    for pos in POS:
        d = dev[dev.position == pos]
        stats, w = fit_position(d, gsb.SCORED)
        positions_cfg[pos] = make_config_position(d, priors[pos], w, stats)
    config = {
        'schema': 'going-score-weights-1', 'version': 'going-score-2.0.0',
        'rollback_note': 'To roll back: restore the previous revision of this file from git (git log -- config/going_score_weights.json), re-run scripts/going_score_build.py and republish data/going_score.json. '
                         'The score is display-only; nothing downstream consumes it for picks, probabilities or stakes, so rollback needs no data migration. Any change to a weight, half-life, shrinkage or '
                         'eligibility rule is a new version and needs a new pre-registered experiment.',
        'params': {**params, 'shrink_k': params['shrink_k']},
        'fit': {'experiment': 'P4-1', 'development_seasons': list(DEV), 'half_life_cv_relative_mae': {str(k): v for k, v in cv.items()}, 'chosen_half_life': best_h,
                'ridge_lambda_per_row': RIDGE_PER_ROW, 'data': 'public nflverse + ffopportunity only', 'spec_sha256': hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()},
        'positions': positions_cfg,
    }
    CONFIG_PATH.write_text(json.dumps(config, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    result, ev = evaluate(table, config, implied)
    result['ablations'] = ablations(table, config, implied)
    result['stability'], result['responsiveness'] = stability_and_response(table, config, league_weeks)
    result['chosen_half_life'] = best_h
    result['half_life_cv'] = {str(k): v for k, v in cv.items()}
    result['weights'] = {pos: {c: positions_cfg[pos]['components'][c]['weight'] for c in gsb.SCORED} for pos in POS}
    result['n_dev_rows'] = {pos: int((dev.position == pos).sum()) for pos in POS}
    return result, result['verdicts']['overall']


RUNNERS = {'P4-1': run_p4_1}
