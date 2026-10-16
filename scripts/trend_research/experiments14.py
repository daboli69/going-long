"""Runners for the frozen P5-1 (TD end-zone targets) and P5-2 (pace and totals) protocols in protocol_p5.py.

The specifications are imported, never edited here; the ledger refuses a result for a spec that differs from its registration.
Outputs are aggregates only (no licensed player rows) and are written through the ledger.
"""
import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import champion, weekly, weekly_features as wf
from .experiments11 import (PEN_ANY, DEV, HOLD, VAL, BLOCK_DEFS, _population, cols_for, fit_logit, predict_logit, _rows)
from .experiments5 import _cluster_ci
from .protocol_p5 import FP_EZ, FREE_BLOCKS, SPECS
from .stats import Ridge

EZ_SOURCE = {'fp_eztgt12': ('ra.Advanced.EZTGT', 'L12'), 'fp_eztd12': ('ra.Advanced.EZTD', 'L12'), 'fp_i20tgt12': ('ra.Advanced.i20 TGT', 'L12'), 'fp_eztgt6': ('ra.Advanced.EZTGT', 'L6')}
PEN = SPECS['P5-1']['fit']
SEED = SPECS['P5-1']['fit']['seed']


def _conf_adj(n):
    return 1 - 0.05 / n


def _calibration(p, y):
    """Slope and intercept of logit(y) on logit(p) (1.0 / 0.0 is perfect) and 10-bin expected calibration error."""
    z = np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))
    w = fit_logit(z[:, None], y, 0.0, n_unpenalised=1)
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(abs(y[bins == b].mean() - p[bins == b].mean()) * (bins == b).sum() for b in range(10) if (bins == b).any()) / len(p)
    return {'intercept': float(w[0]), 'slope': float(w[1]), 'ece10': float(ece)}


def p51_frame(root):
    """JP-2 population plus lagged FP end-zone features, restricted to the common eligible rows. Returns (frame, coverage)."""
    pop = _population(root).copy()
    pop = pop[pop.position.isin(['RB', 'WR', 'TE'])].reset_index(drop=True)
    panel = weekly.game_panel(root)
    src = ['ra.Advanced.EZTGT', 'ra.Advanced.EZTD', 'ra.Advanced.i20 TGT']
    panel = panel[['player_id', 'season', 'week'] + src]
    out = wf.rolling_asof(pop, panel, 'player_id', src, 'fpz.', windows=(6, 12))
    for name, (col, window) in EZ_SOURCE.items():
        out[name] = out[f'fpz.{col}__{window}']
    out['fp_eligible'] = out['fpz.ra.Advanced.EZTGT__L6'].notna()
    coverage = {}
    for season, g in out.groupby('season'):
        coverage[str(season)] = {'jp2_rows_rb_wr_te': int(len(g)), 'with_fp_history': int(g.fp_eligible.sum()), 'lost': int((~g.fp_eligible).sum()),
                                 'by_position_kept': {p: int(((g.position == p) & g.fp_eligible).sum()) for p in ('RB', 'WR', 'TE')},
                                 'by_position_lost': {p: int(((g.position == p) & ~g.fp_eligible).sum()) for p in ('RB', 'WR', 'TE')}}
    elig = out[out.fp_eligible].reset_index(drop=True)
    dev = elig[elig.season.isin(DEV)]
    for f in FP_EZ:
        med = float(dev[f].median())
        lo, hi = np.nanquantile(dev[f].fillna(med), [0.01, 0.99])
        filled = dev[f].fillna(med).clip(lo, hi)
        elig[f + '_z'] = (elig[f].fillna(med).clip(lo, hi) - filled.mean()) / (filled.std() or 1.0)
    return elig, coverage


def _design(frame, spec):
    return np.column_stack([frame[spec['base']].to_numpy(float)] + ([frame[spec['cols']].to_numpy(float)] if spec['cols'] else []))


def run_p5_1(root, manifest):
    spec = SPECS['P5-1']
    frame, coverage = p51_frame(root)
    free_all = cols_for(FREE_BLOCKS)
    ez = [f + '_z' for f in FP_EZ]
    models = {'B0c': dict(base='log_rate', cols=[]), 'B1c': dict(base='log_tds12', cols=[]),
              'B2c': dict(base='log_rate', cols=cols_for(features=['rz_tgt12', 'inside5_touch12'])), 'BF': dict(base='log_rate', cols=free_all),
              'M1': dict(base='log_rate', cols=ez), 'M2': dict(base='log_rate', cols=free_all + ez)}
    for f in FP_EZ:
        models['f:' + f] = dict(base='log_rate', cols=[f + '_z'])
    dev = frame[frame.season.isin(DEV)]
    params = {n: fit_logit(_design(dev, s), dev.y_any.to_numpy(float), PEN_ANY) for n, s in models.items()}
    per = {}
    out = {'coverage': coverage, 'seasons': {}, 'models': {}, 'comparisons': {}}
    for label, season in (('validation', VAL), ('holdout', HOLD)):
        rows = _rows(frame, season)
        y = rows.y_any.to_numpy(float)
        preds = {n: predict_logit(params[n], _design(rows, s)) for n, s in models.items()}
        preds['B0'] = rows.p_champion.to_numpy(float)
        per[label] = (rows, y, preds)
        out['seasons'][label] = {'n': int(len(rows)), 'players': int(rows.player_id.nunique()), 'base_rate': float(y.mean())}
        out['models'][label] = {}
        for n, p in preds.items():
            ll = -(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1)))
            out['models'][label][n] = {'logloss': float(ll.mean()), 'brier': float(((p - y) ** 2).mean()), **_calibration(np.clip(p, 1e-6, 1 - 1e-6), y)}

    def gain(label, new, base):
        rows, y, preds = per[label]
        l = lambda p: -(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1)))
        return l(preds[base]) - l(preds[new]), rows.player_id.to_numpy()

    primary = [('M1', 'B0c'), ('M2', 'BF')]
    conf = _conf_adj(len(primary))
    verdicts = []
    for new, base in primary + [('M1', 'B2c')] + [('f:' + f, 'B0c') for f in FP_EZ] + [('BF', 'B0c'), ('B2c', 'B0c')]:
        cell = {}
        for label in ('validation', 'holdout'):
            g, groups = gain(label, new, base)
            cell[label] = {'gain_logloss_nats': _cluster_ci(g, groups, 0.95), 'gain_logloss_adjusted_ci': _cluster_ci(g, groups, conf)}
        gv, gh = cell['validation']['gain_logloss_nats'][0], cell['holdout']['gain_logloss_nats'][0]
        lo, hi = cell['holdout']['gain_logloss_adjusted_ci'][1:]
        if (new, base) in primary:
            cell['verdict'] = 'REJECT' if (gh <= 0 or hi < 0.001) else 'ACCEPT_FOR_SHADOW' if (gv > 0 and gh >= 0.001 and lo > 0) else 'INCONCLUSIVE'
            verdicts.append(cell['verdict'])
        else:
            cell['verdict'] = 'DESCRIPTIVE'
        out['comparisons'][f'{new} vs {base}'] = cell
    rows, y, preds = per['holdout']
    out['holdout_by_position_gain_M1_vs_B0c'] = {}
    g, _ = gain('holdout', 'M1', 'B0c')
    for pos in ('RB', 'WR', 'TE'):
        m = (rows.position == pos).to_numpy()
        if m.sum() > 100:
            out['holdout_by_position_gain_M1_vs_B0c'][pos] = {'n': int(m.sum()), 'gain': _cluster_ci(g[m], rows.player_id.to_numpy()[m], 0.95)}
    out['coefficients_M2_ez'] = dict(zip(['intercept', 'log_rate'] + [c[:-2] for c in models['M2']['cols']], [float(x) for x in params['M2']]))
    status = 'ACCEPT_FOR_SHADOW' if verdicts and all(v == 'ACCEPT_FOR_SHADOW' for v in verdicts) else ('REJECT' if verdicts and all(v == 'REJECT' for v in verdicts) else 'INCONCLUSIVE')
    return out, status


# ====================================================================== P5-2
REPO = Path(__file__).resolve().parents[2]
WINDOW, MIN_PRIOR, AS_OF_DELAY_H = 6, 3, 4
FEATS = {'B_PTS': ['pts6'], 'B_NFL': ['pts6', 'nfl_plays6', 'nfl_pass6'], 'C_FP': ['pts6', 'nfl_plays6', 'nfl_pass6', 'fp_snaps6', 'fp_pass6', 'fp_neutral6']}


def derived_dir():
    return Path(os.environ.get('GOING_ODDS_DERIVED') or Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'GOING' / 'private' / 'odds-history-derived')


def _team(code):
    from fp_ingest.identity import canonical_team
    return canonical_team(code)


def _kick_utc(games):
    local = pd.to_datetime(games.gameday + ' ' + games.gametime.fillna('13:00'))
    return local.dt.tz_localize('America/New_York', ambiguous='NaT', nonexistent='shift_forward').dt.tz_convert('UTC')


def team_games(root):
    """Long team-game table with strictly lagged same-season rolling features. No feature crosses a season boundary."""
    games = champion.load_games(root)
    games = games[(games.game_type == 'REG') & (games.season >= 2021)].copy()
    games['kick'] = _kick_utc(games)
    games['home'], games['away'] = games.home_team.map(_team), games.away_team.map(_team)
    rows = []
    for side, other in (('home', 'away'), ('away', 'home')):
        rows.append(pd.DataFrame({'game_id': games.game_id, 'season': games.season, 'week': games.week, 'team': games[side], 'kick': games.kick,
                                  'pf': games[side + '_score'], 'pa': games[other + '_score']}))
    tg = pd.concat(rows, ignore_index=True)
    w = champion.load_weekly(root, list(range(2021, 2027)))
    w = w[w.season_type == 'REG'].copy()
    w['team'] = w.team.map(lambda c: _team(c) if isinstance(c, str) else None)
    nfl = w.groupby(['team', 'season', 'week'], as_index=False).agg(att=('attempts', 'sum'), car=('carries', 'sum'))
    nfl['nfl_plays'], nfl['nfl_pass'] = nfl.att + nfl.car, nfl.att / (nfl.att + nfl.car).replace(0, np.nan)
    tg = tg.merge(nfl[['team', 'season', 'week', 'nfl_plays', 'nfl_pass']], on=['team', 'season', 'week'], how='left')
    rp = weekly.load_table(root, 'run_pass_report_weekly').dropna(subset=['team'])
    rp['team'] = rp.team.map(_team)
    rp = rp.rename(columns={'Overall.SNAPS': 'fp_snaps', 'Overall.PASS %': 'fp_pass', 'Neutral.PASS %': 'fp_neutral'}).drop_duplicates(['team', 'season', 'week'])
    tg = tg.merge(rp[['team', 'season', 'week', 'fp_snaps', 'fp_pass', 'fp_neutral']], on=['team', 'season', 'week'], how='left')
    tg = tg.sort_values(['team', 'season', 'week']).reset_index(drop=True)
    grp = tg.groupby(['team', 'season'], sort=False)
    # a feature of game g uses ONLY earlier games of the same season (shift(1) before the rolling mean); needs >= MIN_PRIOR non-missing games
    for col in ('pf', 'pa', 'nfl_plays', 'nfl_pass', 'fp_snaps', 'fp_pass', 'fp_neutral'):
        tg['r_' + col] = grp[col].transform(lambda s: s.shift(1).rolling(WINDOW, min_periods=MIN_PRIOR).mean())
    tg['prior_kick'] = grp['kick'].shift(1)
    return games, tg


def game_features(games, tg):
    h = tg.rename(columns=lambda c: 'h_' + c if c != 'game_id' else c)
    a = tg.rename(columns=lambda c: 'a_' + c if c != 'game_id' else c)
    g = games[['game_id', 'season', 'week', 'home', 'away', 'kick', 'total', 'total_line']].merge(h.drop(columns=['h_season', 'h_week', 'h_kick']), on='game_id')
    g = g.merge(a.drop(columns=['a_season', 'a_week', 'a_kick']), on='game_id')
    g = g[(g.h_team == g.home) & (g.a_team == g.away)].copy()
    g['exp_total'] = (g.h_r_pf + g.a_r_pa + g.a_r_pf + g.h_r_pa) / 2
    g['nfl_plays6'], g['nfl_pass6'] = g.h_r_nfl_plays + g.a_r_nfl_plays, (g.h_r_nfl_pass + g.a_r_nfl_pass) / 2
    g['fp_snaps6'], g['fp_pass6'], g['fp_neutral6'] = g.h_r_fp_snaps + g.a_r_fp_snaps, (g.h_r_fp_pass + g.a_r_fp_pass) / 2, (g.h_r_fp_neutral + g.a_r_fp_neutral) / 2
    g['asof'] = g[['h_prior_kick', 'a_prior_kick']].max(axis=1) + timedelta(hours=AS_OF_DELAY_H)
    return g.reset_index(drop=True)


def _fit_totals(dev):
    out = {}
    r = (dev.total - dev.total_line).to_numpy(float)
    for name, cols in FEATS.items():
        model = Ridge().fit(dev[cols].to_numpy(float), r)
        resid = r - model.predict(dev[cols].to_numpy(float))
        out[name] = (model, float(resid.std()))
    out['CH_RAW'] = (None, float((r - dev.pts6.to_numpy(float)).std()))
    return out


def _brier(p, y):
    return (p - y) ** 2


def _cell(frame, new, base):
    y = frame.y.to_numpy(float)
    pb = frame['p_' + base].to_numpy(float) if base != 'MKT' else frame.p_mkt.to_numpy(float)
    pn = frame['p_' + new].to_numpy(float)
    gain = _brier(pb, y) - _brier(pn, y)
    mean, lo, hi = _cluster_ci(gain, np.arange(len(frame)), 0.95)
    base_b = float(_brier(pb, y).mean())
    ll = lambda p: float(-(y * np.log(np.clip(p, 1e-9, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-9, 1))).mean())
    return {'n': int(len(frame)), 'brier_base': base_b, 'brier_new': float(_brier(pn, y).mean()), 'gain': [mean, lo, hi], 'relative_gain': float(mean / base_b),
            'logloss_base': ll(pb), 'logloss_new': ll(pn)}


def run_p5_2(root, manifest):
    games, tg = team_games(root)
    g = game_features(games, tg)
    dev = g[g.season.isin([2021, 2022, 2023]) & g.total_line.notna() & g.total.notna()].copy()
    dev['pts6'] = dev.exp_total - dev.total_line
    dev = dev.dropna(subset=FEATS['C_FP'])
    fitted = _fit_totals(dev)
    market_path = derived_dir() / 'market-probs.json'
    if not market_path.exists():
        raise SystemExit(f'{market_path} missing: run scripts/missions_history_export.py then scripts/archive_market_probs.cjs first')
    market = pd.DataFrame(json.loads(market_path.read_text(encoding='utf-8')))
    market = market[market.market == 'total'].copy()
    market['line'] = market.line.astype(float)
    ev = market.merge(g, left_on='gameId', right_on='game_id', how='left')
    ev['pts6'] = ev.exp_total - ev.line
    out = {'development': {'games': int(len(dev)), 'sigma': {k: v[1] for k, v in fitted.items()}, 'seasons': [2021, 2022, 2023]},
           'archive_total_records': {str(s): int((market.gameId.str[:4] == str(s)).sum()) for s in (2024, 2025, 2026)}, 'coverage': {}}
    out['coverage']['archive_total_records_unmatched_to_schedule'] = int(ev.game_id.isna().sum())
    ev = ev[ev.game_id.notna()]
    forecasts, rows = {}, []
    for r in ev.itertuples():
        feats = {c: getattr(r, c) for c in ('pts6', 'nfl_plays6', 'nfl_pass6', 'fp_snaps6', 'fp_pass6', 'fp_neutral6')}
        fin = lambda cols: bool(np.isfinite([feats[c] for c in cols]).all())
        row = {'gameId': r.gameId, 'season': int(r.season), 'week': int(r.week), 'y': int(r.y), 'p_mkt': float(r.pEqual), 'line': float(r.line), 'snapshot': r.snapshotAt,
               'asof': r.asof, 'have_pts': fin(['pts6']), 'have_nfl': fin(FEATS['B_NFL']), 'have_fp': fin(FEATS['C_FP'])}
        for name, (model, sigma) in fitted.items():
            cols = ['pts6'] if name == 'CH_RAW' else FEATS[name]
            ok = fin(cols)
            rhat = feats['pts6'] if name == 'CH_RAW' else (float(model.predict(np.array([[feats[c] for c in cols]], float))[0]) if ok else np.nan)
            row['p_' + name] = float(norm.cdf(rhat / sigma)) if ok else np.nan
        rows.append(row)
        if np.isfinite(row['p_C_FP']) and pd.notna(r.asof):
            forecasts[f'{r.gameId}|total|{r.line}'] = {'p': row['p_C_FP'], 'asOf': pd.Timestamp(r.asof).strftime('%Y-%m-%dT%H:%M:%SZ')}
    df = pd.DataFrame(rows)
    out['coverage']['by_season'] = {str(s): {'records': int(len(d)), 'with_prior_games_pts': int(d.have_pts.sum()), 'with_nfl_pace': int(d.have_nfl.sum()), 'with_fp_pace': int(d.have_fp.sum()),
                                             'excluded_from_fp_models': int((~d.have_fp).sum())} for s, d in df.groupby('season')}
    out['coverage']['note_2024'] = 'no run_pass_report_weekly export exists for 2024: every 2024 game is excluded from FP-feature models (not imputed, not taken from season totals)'
    out['coverage']['forecasts_written_for_C_FP'] = len(forecasts)
    ok = df.dropna(subset=['asof'])
    lag = (pd.to_datetime(ok.snapshot, utc=True) - pd.to_datetime(ok['asof'], utc=True)).dt.total_seconds() / 3600
    out['timestamps'] = {'forecast_asof_after_snapshot': int((lag < 0).sum()), 'min_hours_asof_to_snapshot': float(lag.min()), 'median_hours_asof_to_snapshot': float(lag.median()),
                         'asof_rule': f'kickoff of the latest prior game used + {AS_OF_DELAY_H}h'}
    common = df[df.have_fp & df.season.isin([2025, 2026])].copy()
    pooled = {}
    for new, base in [('C_FP', 'MKT'), ('B_NFL', 'MKT'), ('B_PTS', 'MKT'), ('CH_RAW', 'MKT'), ('C_FP', 'B_NFL')]:
        res = _cell(common, new, base)
        res['periods'] = {'A_2025': _cell(common[common.season == 2025], new, base), 'B_2026_wk1_5': _cell(common[common.season == 2026], new, base)}
        pooled[f'{new} vs {base}'] = res
    out['common_rows'] = {'n': int(len(common)), 'over_rate': float(common.y.mean()), 'n_2025': int((common.season == 2025).sum()), 'n_2026': int((common.season == 2026).sum())}
    out['comparisons'] = pooled
    primary = pooled['C_FP vs MKT']
    both = all(primary['periods'][k]['gain'][0] > 0 for k in primary['periods'])
    if primary['gain'][0] <= 0 or primary['gain'][2] < 0.005 * primary['brier_base']:
        verdict = 'REJECT'
    elif primary['gain'][1] > 0 and primary['relative_gain'] >= 0.005 and both:
        verdict = 'ACCEPT_FOR_SHADOW'
    else:
        verdict = 'INCONCLUSIVE'
    c24 = df[(df.season == 2024) & df.have_nfl]
    out['season_2024_no_fp'] = {m: _cell(c24, m, 'MKT') for m in ('B_PTS', 'B_NFL')} if len(c24) > 50 else {'note': 'too few rows'}
    y, p = common.y.to_numpy(float), common.p_C_FP.to_numpy(float)
    bins = np.minimum((p * 10).astype(int), 9)
    out['calibration_C_FP'] = [{'bin': b, 'n': int((bins == b).sum()), 'mean_p': float(p[bins == b].mean()), 'observed': float(y[bins == b].mean())} for b in range(10) if (bins == b).any()]
    out['missions_backtest_check'] = _backtest_with_forecasts(forecasts)
    return out, verdict


def _backtest_with_forecasts(forecasts):
    d = derived_dir()
    inp = d / 'missions-input.json'
    if not inp.exists():
        return {'skipped': 'missions-input.json not found'}
    path = d / 'p52-forecasts.json'
    path.write_text(json.dumps(forecasts), encoding='utf-8')
    try:
        run = subprocess.run(['node', str(REPO / 'scripts' / 'missions_backtest.cjs'), str(inp), '--model', str(path)], capture_output=True, text=True, timeout=120, check=True)
        report = json.loads(run.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return {'skipped': f'node backtest unavailable: {type(exc).__name__}'}
    total = report['markets']['total']['comparison']
    return {'externalForecastsRefused': report['externalForecastsRefused'], 'comparison_total': {k: total.get(k) for k in ('ok', 'n', 'matched', 'equal', 'model')}}


RUNNERS = {'P5-1': run_p5_1, 'P5-2': run_p5_2}


# ====================================================================== P5-3
def run_p5_3(root, manifest):
    import sys
    sys.path.insert(0, str(REPO / 'scripts'))
    from archive_game_line_audit import audit
    from odds_history import default_root
    odds_root = Path(os.environ.get('GOING_ODDS_ROOT') or default_root())
    result = audit(odds_root, champion.cache(root) / 'games.csv')
    inp = derived_dir() / 'missions-input.json'
    comparison = {}
    if inp.exists():
        run = subprocess.run(['node', str(REPO / 'scripts' / 'missions_backtest.cjs'), str(inp)], capture_output=True, text=True, timeout=120, check=True)
        report = json.loads(run.stdout)
        for market, m in report['markets'].items():
            c = m['comparison']
            comparison[market] = {'records': m['records'], 'games': m['games'], 'books': m['sources'], 'first_snapshot': m['firstSnapshot'], 'last_snapshot': m['lastSnapshot'],
                                  'walk_forward': {k: c.get(k) for k in ('ok', 'n', 'matched', 'equal', 'research', 'learned', 'differencesVsEqual')}}
    result['missions_backtest_equal_research_learned'] = comparison
    result['clv_supported'] = False
    result['clv_note'] = 'one pregame board per game about 30 minutes before the actual kickoff; no closing series, so only a matched pregame-price comparison is supported'
    return result, result['status']


RUNNERS['P5-3'] = run_p5_3
