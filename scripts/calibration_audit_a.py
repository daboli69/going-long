#!/usr/bin/env python3
"""Calibration audit A: re-derive and stress-test data/charts/model_calibration.json from the immutable tracker store.

Read-only with respect to the repository data. Reads data/public_tracker (via scripts/tracker_store.py), data/results.json,
data/charts/model_calibration.json and, optionally, a public nflverse stats file for independent regrading. It writes only to
research/calibration/A/. It never contacts a service, scanner or database and uses no licensed Fantasy Points data.

    python scripts/calibration_audit_a.py [--nflverse-dir DIR] [--boot 1000] [--out research/calibration/A]

DIR must hold stats_player_week_2026.csv and games.csv from https://github.com/nflverse/nflverse-data (public).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from tracker_store import load_tracker  # noqa: E402

EDGES = np.linspace(0, 1, 11)
EPS = 1e-6
SEED = 20261009


# ------------------------------------------------------------------------------------------------ loading
def model_cohort(p):
    """Python port of shared/model-cohort.mjs modelCohort()."""
    if p.get('model_cohort'):
        return p['model_cohort']
    e = p.get('model_evidence') or {}
    season, game = e.get('seasonEvidence'), e.get('gameSeasonEvidence')
    method = str((season or {}).get('method') or (game or {}).get('policy') or '')
    if 'champion-v2' in str((season or {}).get('method') or ''):
        return 'champion-v2'
    if '80% current' in method:
        return 'current-80-20'
    if e.get('roleEvidence') or season:
        return 'role-aware-equal-weight'
    return 'legacy'


def load_frame():
    recs = load_tracker(ROOT / 'data')['records']
    settle = {}
    for r in recs:
        if r['kind'] == 'settlement':
            p = r['payload']
            prev = settle.get(p['prediction_id'])
            if not prev or str(p['observed_at']) >= str(prev['observed_at']):
                settle[p['prediction_id']] = p
    rows = []
    for r in recs:
        if r['kind'] != 'prediction':
            continue
        p = r['payload']
        s = settle.get(p['id'])
        ev = p.get('model_evidence') or {}
        ref = ev.get('reference') or {}
        rw, rl = ref.get('win'), ref.get('loss')
        mref = rw / (rw + rl) if isinstance(rw, (int, float)) and isinstance(rl, (int, float)) and rw + rl > 0 else np.nan
        rows.append({
            'id': p['id'], 'group': p['tracking_group'], 'cohort': model_cohort(p), 'model_version': p.get('model_version'),
            'contract': p.get('canonical_contract') or p.get('selection'), 'sport': p['sport'], 'home': p['home'], 'away': p['away'],
            'kickoff': p['kickoff'], 'player': p.get('player'), 'profile_id': p.get('profile_id'), 'market': p['market'], 'line': p['line'],
            'side': p['side'], 'book': p['book'], 'american': p['american'], 'odds': p['odds'], 'prob': p['probability'], 'push': ev.get('push') or 0,
            'obs': p['observed_at'], 'quoted': p.get('quoted_at'), 'odds_band': p.get('odds_band'),
            'status': s['status'] if s else None, 'actual': s['actual'] if s else None, 'settled_at': s['observed_at'] if s else None,
            'official_kickoff': s.get('official_kickoff') if s else None, 'mref': mref, 'proj_mean': ev.get('projection_mean'), 'proj_sd': ev.get('projection_sd'),
        })
    df = pd.DataFrame(rows)
    df['obs_t'] = pd.to_datetime(df['obs'], utc=True, format='ISO8601')
    df['ko_t'] = pd.to_datetime(df['kickoff'], utc=True, format='ISO8601')
    df['quoted_t'] = pd.to_datetime(df['quoted'], utc=True, format='ISO8601', errors='coerce')
    df['okick_t'] = pd.to_datetime(df['official_kickoff'], utc=True, format='ISO8601', errors='coerce')
    df['game'] = df['sport'] + '|' + df['home'].str.lower() + '|' + df['away'].str.lower() + '|' + df['ko_t'].dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    df['entity'] = df['profile_id'].fillna(df['game'])
    df['family'] = df['game'] + '|' + df['entity'] + '|' + df['market']
    df['p'] = df['prob'] / (1 - df['push'])
    df['y'] = np.where(df['status'] == 'win', 1.0, np.where(df['status'] == 'loss', 0.0, np.nan))
    df['impl_raw'] = 1 / df['odds']
    df['lag_h'] = (df['obs_t'] - df['quoted_t']).dt.total_seconds() / 3600
    df['tte_h'] = (df['ko_t'] - df['obs_t']).dt.total_seconds() / 3600
    df['week'] = df['obs_t'].dt.strftime('%G-W%V')
    med = df.groupby('family')['line'].transform('median')
    df['alt_proxy'] = (df['line'] - med).abs() > np.maximum(0.15 * med.abs(), 1.0)
    df['pband'] = pd.cut(df['p'], [-0.001, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0], labels=['0-.1', '.1-.2', '.2-.3', '.3-.4', '.4-.5', '.5-.6', '.6-.7', '.7-.8', '.8-.9', '.9-1']).astype(str)
    df['pcoarse'] = pd.cut(df['p'], [-0.001, .3, .5, .7, .9, 1.0], labels=['<.3', '.3-.5', '.5-.7', '.7-.9', '>=.9']).astype(str)
    return df, recs


def settled_universe(df):
    """Win/loss rows observed strictly before BOTH the vendor kickoff and (when known) the official kickoff, in observation order."""
    d = df[df['status'].isin(['win', 'loss'])].copy()
    ok = (d['obs_t'] < d['ko_t']) & (d['okick_t'].isna() | (d['obs_t'] < d['okick_t']))
    d = d[ok & (d['push'] >= 0) & (d['push'] < 1) & d['p'].between(0, 1)]
    return d.sort_values(['obs_t', 'id'], kind='stable')


# ------------------------------------------------------------------------------------------------ metrics
def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def fit_cal(x, y, w, start=(0.0, 1.0), iters=40):
    """Weighted logistic recalibration y ~ a + b*logit(p). Returns (a, b) or (nan, nan) when not identified."""
    if w.sum() <= 0 or np.ptp(x[w > 0]) < 1e-9 or y[w > 0].min() == y[w > 0].max():
        return np.nan, np.nan
    a, b = start
    for _ in range(iters):
        mu = 1 / (1 + np.exp(-np.clip(a + b * x, -30, 30)))
        v = w * mu * (1 - mu)
        g = np.array([np.sum(w * (y - mu)), np.sum(w * (y - mu) * x)])
        h = np.array([[v.sum(), (v * x).sum()], [(v * x).sum(), (v * x * x).sum()]]) + 1e-9 * np.eye(2)
        try:
            step = np.linalg.solve(h, g)
        except np.linalg.LinAlgError:
            return np.nan, np.nan
        step = np.clip(step, -3, 3)
        a, b = a + step[0], b + step[1]
        if np.abs(step).max() < 1e-8:
            break
    if abs(a) > 25 or abs(b) > 25:
        return np.nan, np.nan
    return a, b


def fit_citl(x, y, w, iters=30):
    """Calibration-in-the-large: intercept with slope fixed at 1 (logit offset)."""
    if w.sum() <= 0 or y[w > 0].min() == y[w > 0].max():
        return np.nan
    a = 0.0
    for _ in range(iters):
        mu = 1 / (1 + np.exp(-np.clip(a + x, -30, 30)))
        step = np.sum(w * (y - mu)) / max(np.sum(w * mu * (1 - mu)), 1e-9)
        a += np.clip(step, -3, 3)
        if abs(step) < 1e-9:
            break
    return a


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def metrics(p, y, w, bin_idx, gcode, mref, want_fit=True, start=(0.0, 1.0)):
    """All scalar metrics for one (re)weighted sample. w are integer bootstrap multiplicities (ones for the point estimate)."""
    sw = w.sum()
    if sw <= 0:
        return {}
    base = np.sum(w * y) / sw
    brier = np.sum(w * (p - y) ** 2) / sw
    pc = np.clip(p, EPS, 1 - EPS)
    ll = -np.sum(w * (y * np.log(pc) + (1 - y) * np.log(1 - pc))) / sw
    ref_pooled = base * (1 - base)
    out = {'base_rate': base, 'mean_p': np.sum(w * p) / sw, 'brier': brier, 'logloss': ll,
           'skill_pooled_slice': 1 - brier / ref_pooled if ref_pooled > 0 else np.nan}
    # per (market, side) base-rate reference
    gs = np.bincount(gcode, weights=w * y, minlength=gcode.max() + 1)
    gn = np.bincount(gcode, weights=w, minlength=gcode.max() + 1)
    bg = np.divide(gs, gn, out=np.zeros_like(gs), where=gn > 0)
    ref_ms = np.sum(w * (bg[gcode] - y) ** 2) / sw
    out['skill_per_market_side'] = 1 - brier / ref_ms if ref_ms > 0 else np.nan
    # vs de-vigged market reference on rows that carry one
    m = ~np.isnan(mref) & (w > 0)
    if m.sum() >= 10:
        bm = np.sum(w[m] * (p[m] - y[m]) ** 2) / w[m].sum()
        br = np.sum(w[m] * (mref[m] - y[m]) ** 2) / w[m].sum()
        out['skill_vs_market'] = 1 - bm / br if br > 0 else np.nan
        out['brier_model_on_ref_rows'], out['brier_market_ref'] = bm, br
    # ECE (10 equal-width bins)
    bn = np.bincount(bin_idx, weights=w, minlength=10)
    bp = np.bincount(bin_idx, weights=w * p, minlength=10)
    by = np.bincount(bin_idx, weights=w * y, minlength=10)
    nz = bn > 0
    out['ece'] = float(np.sum(np.abs(bp[nz] - by[nz])) / sw)
    if want_fit:
        x = logit(p)
        a, b = fit_cal(x, y, w, start)
        out['intercept'], out['slope'] = a, b
        out['citl'] = fit_citl(x, y, w)
    return out


CI_KEYS = ['brier', 'logloss', 'skill_pooled_slice', 'skill_per_market_side', 'skill_vs_market', 'intercept', 'slope', 'citl', 'ece']


def slice_report(d, name, kind, rng, boot, want_fit=True, min_boot=60):
    """Point estimates plus cluster (game) bootstrap CIs for one slice of a de-duplicated frame."""
    if len(d) == 0:
        return None
    p, y = d['p'].to_numpy(float), d['y'].to_numpy(float)
    bin_idx = np.clip(np.digitize(p, EDGES[1:-1]), 0, 9)
    gcode = pd.factorize(d['market'] + '|' + d['side'])[0]
    mref = d['mref'].to_numpy(float)
    cl, ncl = pd.factorize(d['game'])
    k = len(ncl)
    one = np.ones(len(d))
    pt = metrics(p, y, one, bin_idx, gcode, mref, want_fit)
    row = {'slice_type': kind, 'slice': name, 'n': len(d), 'n_games': k, 'n_families': d['family'].nunique(), 'n_players': d['profile_id'].nunique(),
           'n_ref': int(np.sum(~np.isnan(mref)))}
    row.update(pt)
    a0, b0 = pt.get('intercept', np.nan), pt.get('slope', np.nan)
    start = (a0, b0) if np.isfinite(a0) and np.isfinite(b0) else (0.0, 1.0)
    if len(d) >= min_boot and k >= 5 and boot > 0:
        draws = {key: [] for key in CI_KEYS}
        for _ in range(boot):
            cnt = rng.multinomial(k, np.full(k, 1.0 / k))
            w = cnt[cl].astype(float)
            m = metrics(p, y, w, bin_idx, gcode, mref, want_fit, start)
            for key in CI_KEYS:
                if key in m:
                    draws[key].append(m[key])
        for key, v in draws.items():
            v = np.asarray(v, float)
            v = v[np.isfinite(v)]
            if len(v) >= 0.8 * boot:
                row[key + '_lo'], row[key + '_hi'] = np.percentile(v, 2.5), np.percentile(v, 97.5)
    # ECE under perfect calibration (parametric): the chance-level floor for this n and probability spread
    sims = []
    for _ in range(200):
        ys = (rng.random(len(p)) < p).astype(float)
        bn = np.bincount(bin_idx, minlength=10)
        sims.append(np.sum(np.abs(np.bincount(bin_idx, weights=p, minlength=10) - np.bincount(bin_idx, weights=ys, minlength=10))) / len(p))
        del bn
    row['ece_null_mean'], row['ece_null_p95'] = float(np.mean(sims)), float(np.percentile(sims, 95))
    row['low_n'] = len(d) < 100
    return row


def bins_report(d, name, kind):
    out = []
    for i in range(10):
        s = d[(d['p'] >= EDGES[i]) & ((d['p'] < EDGES[i + 1]) | (i == 9))]
        if len(s) == 0:
            continue
        k = int(s['y'].sum())
        lo, hi = wilson(k, len(s))
        out.append({'slice_type': kind, 'slice': name, 'lo': EDGES[i], 'hi': EDGES[i + 1], 'n': len(s), 'n_games': s['game'].nunique(), 'mean_p': s['p'].mean(), 'freq': k / len(s),
                    'wilson_lo': lo, 'wilson_hi': hi, 'mean_market_ref': s['mref'].mean() if s['mref'].notna().any() else np.nan, 'n_ref': int(s['mref'].notna().sum()),
                    'mean_implied_raw_vig_incl': s['impl_raw'].mean()})
    return out


# ------------------------------------------------------------------------------------------------ reproduction
def reproduce(df, recs):
    import charts_build as cb  # the audited code itself
    items, latest = cb.settled_items(recs)
    rep = json.loads((ROOT / 'data/charts/model_calibration.json').read_text(encoding='utf-8'))['data']
    it = pd.DataFrame(items)
    u = it.drop_duplicates('contract')
    out = {'reported_overall': {k: rep['overall'][k] for k in ('n', 'brier', 'base_rate', 'brier_base_rate_ref', 'skill_vs_base_rate')},
           'audited_code_rerun': {'n': len(u), 'brier': round(float(((u.p - u.y) ** 2).mean()), 4), 'base_rate': round(float(u.y.mean()), 3)},
           'rows_before_cross_group_dedup': len(it), 'by_group_rows': it.groupby('group').size().to_dict()}
    # independent re-implementation (this script's own loader, timestamps parsed instead of compared as strings)
    d = settled_universe(df)
    ug = d.drop_duplicates(['group', 'contract'])
    uu = ug.drop_duplicates('contract')
    out['independent_rebuild'] = {'n': len(uu), 'brier': round(float(((uu.p - uu.y) ** 2).mean()), 4), 'base_rate': round(float(uu.y.mean()), 3),
                                  'rows_group_level': len(ug)}
    out['market_check'] = {}
    for m, v in rep['markets'].items():
        s = uu[uu.market == m]
        out['market_check'][m] = {'reported_n': v['n'], 'rebuilt_n': len(s), 'reported_brier': v['brier'], 'rebuilt_brier': round(float(((s.p - s.y) ** 2).mean()), 4)}
    out['group_check'] = {}
    for g, v in rep['groups'].items():
        s = ug[ug.group == g]
        out['group_check'][g] = {'reported_n': v['n'], 'rebuilt_n': len(s), 'reported_brier': v['brier'], 'rebuilt_brier': round(float(((s.p - s.y) ** 2).mean()), 4)}
    out['bin_check'] = [{'bin': b['lo'], 'reported_n': b['n'], 'reported_freq': b['freq'],
                         'rebuilt_n': int(((uu.p >= b['lo']) & ((uu.p < b['hi']) | (b['hi'] == 1.0))).sum()),
                         'rebuilt_freq': round(float(uu[(uu.p >= b['lo']) & ((uu.p < b['hi']) | (b['hi'] == 1.0))].y.mean()), 3)} for b in rep['overall']['bins']]
    # sensitivity of the headline to the audit's own design choices
    sens = {}
    pooled_ref = uu.y.mean() * (1 - uu.y.mean())
    sens['pooled_ref_brier'] = round(float(pooled_ref), 4)
    bg = uu.groupby(['market', 'side']).y.transform('mean')
    ref_ms = float(((bg - uu.y) ** 2).mean())
    sens['per_market_side_ref_brier'] = round(ref_ms, 4)
    sens['skill_vs_pooled_base'] = round(1 - float(((uu.p - uu.y) ** 2).mean()) / pooled_ref, 4)
    sens['skill_vs_per_market_side_base'] = round(1 - float(((uu.p - uu.y) ** 2).mean()) / ref_ms, 4)
    fam = uu.drop_duplicates('family')
    sens['family_dedup_n'] = len(fam)
    sens['family_dedup_brier'] = round(float(((fam.p - fam.y) ** 2).mean()), 4)
    sens['n_with_same_family_other_side_present'] = int(uu.duplicated('family', keep=False).sum())
    out['sensitivity'] = sens
    return out


# ------------------------------------------------------------------------------------------------ independent regrade
STAT = {'player_receiving_yards': 'receiving_yards', 'player_receptions': 'receptions', 'player_rushing_yards': 'rushing_yards',
        'player_passing_yards': 'passing_yards', 'player_passing_tds': 'passing_tds'}


def regrade(df, nfl_dir, out_dir, rng):
    """Re-grade every settled record from first principles. NFL: nflverse weekly stats + schedule scores. NCAA: only results.json scores
    (no independent public source is bundled), so those rows test the grading arithmetic, not the data."""
    res = json.loads((ROOT / 'data/results.json').read_text(encoding='utf-8'))
    games = pd.DataFrame(res['games'].values())
    games['ko'] = pd.to_datetime(games['kickoff'], utc=True, format='ISO8601')
    games['day'] = games['ko'].dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    games['hn'], games['an'] = games['home'].str.lower(), games['away'].str.lower()
    s = df[df['status'].notna()].copy()
    s['day'] = s['ko_t'].dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    nfl_games = nfl_stats = None
    if nfl_dir:
        nfl_games = pd.read_csv(Path(nfl_dir) / 'games.csv')
        nfl_games = nfl_games[(nfl_games.season == 2026) & nfl_games.home_score.notna()].copy()
        nfl_stats = pd.read_csv(Path(nfl_dir) / 'stats_player_week_2026.csv', low_memory=False)
        nfl_stats = nfl_stats.set_index(['player_id', 'game_id'])
        nfl_games['ko'] = pd.to_datetime(nfl_games['gameday'] + ' ' + nfl_games['gametime'].fillna('00:00'), utc=False).dt.tz_localize('America/New_York').dt.tz_convert('UTC')
    out = []
    pr = res['players']
    for r in s.itertuples():
        rec = {'id': r.id, 'sport': r.sport, 'market': r.market, 'player': r.player, 'side': r.side, 'line': r.line, 'tracker_status': r.status, 'tracker_actual': r.actual}
        cand = games[(games.sport == r.sport) & (games.hn == r.home.lower()) & (games.an == r.away.lower()) & (games.day == r.day)]
        if len(cand) == 0:  # vendor/official clocks can straddle Eastern midnight (e.g. 23:59 vs 00:00); accept a unique matchup within 10 minutes
            near = games[(games.sport == r.sport) & (games.hn == r.home.lower()) & (games.an == r.away.lower()) & ((games.ko - r.ko_t).abs() <= pd.Timedelta(minutes=10))]
            cand = near
        if len(cand) != 1:
            rec['note'] = 'results_game_match_%d' % len(cand)
            out.append(rec)
            continue
        g = cand.iloc[0]
        rec['game_id'] = g['id']
        hs, as_ = g['homeScore'], g['awayScore']
        # source 1: results.json
        if r.market == 'totals':
            act = hs + as_
        elif r.market == 'spreads':
            act = hs - as_ + r.line
        elif r.market == 'h2h':
            act = hs - as_
        else:
            row = pr.get(f'{r.profile_id}|{g["day"]}')
            key = {'player_receiving_yards': 'rec_yds', 'player_receptions': 'receptions', 'player_rushing_yards': 'rush_yds', 'player_passing_yards': 'pass_yds',
                   'player_passing_tds': 'pass_tds', 'atd': 'atd'}[r.market]
            act = row.get(key) if row else np.nan
        rec['regraded_actual_results_json'] = act
        rec['regraded_status_results_json'] = grade(r.market, r.side, r.line, act)
        # source 2 (NFL only): nflverse
        if nfl_games is not None and r.sport == 'nfl':
            ng = nfl_games[(nfl_games.home_team == r.home) & (nfl_games.away_team == r.away) & ((nfl_games.ko - g['ko']).abs() < pd.Timedelta(days=1))]
            if len(ng) == 1:
                ng = ng.iloc[0]
                if r.market == 'totals':
                    a2 = ng.home_score + ng.away_score
                elif r.market == 'spreads':
                    a2 = ng.home_score - ng.away_score + r.line
                elif r.market == 'h2h':
                    a2 = ng.home_score - ng.away_score
                else:
                    try:
                        st = nfl_stats.loc[(r.profile_id, ng.game_id)]
                    except KeyError:
                        st = None
                    if st is None:
                        a2 = np.nan
                    elif r.market == 'atd':
                        a2 = float((st['rushing_tds'] + st['receiving_tds']) > 0)
                        rec['nflverse_st_tds'] = float(st['special_teams_tds'])
                    else:
                        a2 = float(st[STAT[r.market]])
                rec['nflverse_actual'] = a2
                rec['nflverse_status'] = grade(r.market, r.side, r.line, a2)
            else:
                rec['note'] = 'nflverse_game_match_%d' % len(ng)
        out.append(rec)
    o = pd.DataFrame(out)
    nfl_player = o['sport'].eq('nfl') & o['market'].isin(['atd'] + list(STAT))
    o['nflverse_no_row'] = nfl_player & o['nflverse_status'].isna() if 'nflverse_status' in o else False
    o['match_results_json'] = o['regraded_status_results_json'] == o['tracker_status']
    if 'nflverse_status' in o:
        o['match_nflverse'] = (o['nflverse_status'] == o['tracker_status']).where(o['nflverse_status'].notna())
    o.to_csv(out_dir / 'regrade_all.csv', index=False)
    # hand-check sample: 5 per market + 5 refunds, fixed seed
    pick = []
    for m, g in o.groupby('market'):
        pick.append(g.sample(min(5, len(g)), random_state=SEED))
    ref = o[o.tracker_status == 'refund']
    pick.append(ref.sample(min(5, len(ref)), random_state=SEED))
    smp = pd.concat(pick).drop_duplicates('id')
    if len(smp) < 50:
        smp = pd.concat([smp, o[~o.id.isin(smp.id)].sample(50 - len(smp), random_state=SEED)])
    smp.to_csv(out_dir / 'regrade_sample50.csv', index=False)
    summ = {'graded': len(o), 'match_results_json': int(o['match_results_json'].sum()),
            'mismatch_results_json': o[~o['match_results_json']].groupby(['sport', 'market']).size().to_dict().__repr__(),
            'nfl_player_rows_settled_with_no_nflverse_stat_row': int(o['nflverse_no_row'].sum()) if 'nflverse_no_row' in o else None,
            'sample_n': len(smp), 'sample_mismatch_results_json': int((~smp['match_results_json']).sum())}
    if 'match_nflverse' in o:
        chk = o[o['match_nflverse'].notna()]
        summ.update({'nflverse_checked': len(chk), 'nflverse_match': int(chk['match_nflverse'].sum()),
                     'nflverse_mismatch_by_market': chk[chk['match_nflverse'] == False].groupby('market').size().to_dict().__repr__(),  # noqa: E712
                     'nflverse_unavailable': int(o['nflverse_status'].isna().sum()) if 'nflverse_status' in o else None,
                     'sample_nflverse_mismatch': int((smp['match_nflverse'] == False).sum())})  # noqa: E712
        bad = chk[chk['match_nflverse'] == False]  # noqa: E712
        bad.to_csv(out_dir / 'regrade_nflverse_mismatches.csv', index=False)
    return summ


def grade(market, side, line, actual):
    if actual is None or (isinstance(actual, float) and np.isnan(actual)):
        return None
    if market in ('spreads', 'h2h'):
        target, over = 0.0, side in ('Home', 'Over')
    elif market == 'atd':
        target, over = 0.5, True
    else:
        target, over = line, side == 'Over'
    if actual == target:
        return 'refund'
    return 'win' if (actual > target) == over else 'loss'


# ------------------------------------------------------------------------------------------------ pending / selection
def pending_audit(df, res_path):
    """Predictions whose game is final and whose kickoff passed, split by whether a settlement exists."""
    res = json.loads(Path(res_path).read_text(encoding='utf-8'))
    games = pd.DataFrame(res['games'].values())
    games['day'] = pd.to_datetime(games['kickoff'], utc=True, format='ISO8601').dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    keys = set(zip(games.sport, games.home.str.lower(), games.away.str.lower(), games.day))
    now = pd.Timestamp(json.loads((ROOT / 'data/public_tracker/manifest.json').read_text())['generated_at'])
    d = df[df['ko_t'] < now].copy()
    d['day'] = d['ko_t'].dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    d['final_known'] = [(a, b.lower(), c.lower(), e) in keys for a, b, c, e in zip(d.sport, d.home, d.away, d.day)]
    d = d[d.final_known]
    d['settled'] = d.status.notna()
    t = d.groupby(['market', 'side']).agg(past_final=('id', 'size'), settled=('settled', 'sum'), mean_p=('p', 'mean')).reset_index()
    t['unsettled_share'] = 1 - t['settled'] / t['past_final']
    prop = d[d.market.isin(['atd'] + list(STAT))]
    detail = prop.groupby(['market', 'side', 'settled']).agg(n=('id', 'size'), mean_p=('p', 'mean'), median_line=('line', 'median')).reset_index()
    return t, detail


# ------------------------------------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse-dir', default=None)
    ap.add_argument('--boot', type=int, default=1000)
    ap.add_argument('--out', default=str(ROOT / 'research/calibration/A'))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    df, recs = load_frame()
    import subprocess
    sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    manifest = json.loads((ROOT / 'data/public_tracker/manifest.json').read_text())

    rep = reproduce(df, recs)
    rep['store'] = {'total_records': manifest['total_records'], 'manifest_generated_at': manifest['generated_at'], 'head_ref': sha}
    d = settled_universe(df)
    U = d.drop_duplicates('contract')                       # as published: first observation of a contract across groups
    G = d.drop_duplicates(['group', 'contract'])           # within tracking group
    C = d.drop_duplicates(['cohort', 'contract'])          # within model cohort
    F = U.drop_duplicates('family')                        # one row per game x entity x market (removes Over/Under double counting)
    rep['frames'] = {'universe_rows': len(d), 'U_contract': len(U), 'G_group_contract': len(G), 'C_cohort_contract': len(C), 'F_family': len(F)}

    rows, bins = [], []

    def add(frame, name, kind, fit=True):
        r = slice_report(frame, name, kind, rng, a.boot, fit)
        if r:
            rows.append(r)
            bins.extend(bins_report(frame, name, kind))
        return r

    add(U, 'ALL (pooled, as published)', 'overall')
    add(F, 'ALL family-dedup', 'overall_family')
    for m, s in U.groupby('market'):
        add(s, m, 'market')
    for (m, sd), s in U.groupby(['market', 'side']):
        add(s, f'{m}|{sd}', 'market_side')
    for m, s in F.groupby('market'):
        add(s, m, 'market_family_dedup')
    for g, s in G.groupby('group'):
        add(s, g, 'group')
    for (g, m), s in G.groupby(['group', 'market']):
        add(s, f'{g}|{m}', 'group_market')
    for c, s in C.groupby('cohort'):
        add(s, c, 'cohort')
    for (c, m), s in C.groupby(['cohort', 'market']):
        add(s, f'{c}|{m}', 'cohort_market')
    for sp, s in U.groupby('sport'):
        add(s, sp, 'sport_season2026')
    for (sp, m), s in U.groupby(['sport', 'market']):
        add(s, f'{sp}|{m}', 'sport_market')
    for w, s in U.groupby('week'):
        add(s, w, 'obs_week')
    for b, s in U.groupby('odds_band'):
        add(s, b, 'odds_band')
    U2 = U.assign(alt=np.where(U.alt_proxy, 'line_far_from_family_median', 'near_median'))
    for b, s in U2.groupby('alt'):
        add(s, b, 'alt_line_proxy')
    U2['lagb'] = pd.cut(U2.lag_h, [-1, 1, 6, 1e9], labels=['quote<1h_old', 'quote1-6h_old', 'quote>6h_old']).astype(str)
    for b, s in U2.groupby('lagb'):
        add(s, b, 'quote_age')
    U2['tteb'] = pd.cut(U2.tte_h, [0, 2, 24, 1e9], labels=['<2h_to_ko', '2-24h_to_ko', '>24h_to_ko']).astype(str)
    for b, s in U2.groupby('tteb'):
        add(s, b, 'time_to_kickoff')
    # probability ranges: descriptive only (a logistic fit inside a truncated range is meaningless), no bootstrap
    for b, s in U.groupby('pcoarse'):
        add(s, b, 'prob_range_pooled', fit=False)
    for (m, b), s in U.groupby(['market', 'pcoarse']):
        add(s, f'{m}|{b}', 'prob_range_market', fit=False)
    for (g, b), s in G.groupby(['group', 'pcoarse']):
        add(s, f'{g}|{b}', 'prob_range_group', fit=False)

    res = pd.DataFrame(rows)
    res.to_csv(out / 'calibration_results.csv', index=False)
    pd.DataFrame(bins).to_csv(out / 'reliability_bins.csv', index=False)

    # the 90-100% bin
    hi = U[U.p >= 0.9]
    comp = {'n': len(hi), 'win_rate': float(hi.y.mean()), 'mean_p': float(hi.p.mean()), 'mean_implied_raw': float(hi.impl_raw.mean()),
            'mean_american_median': float(hi.american.median()), 'n_games': int(hi.game.nunique()), 'n_players': int(hi.profile_id.nunique()),
            'n_ref_rows': int(hi.mref.notna().sum()), 'mean_market_ref_where_available': float(hi.mref.mean()) if hi.mref.notna().any() else None,
            'share_alt_proxy': float(hi.alt_proxy.mean()), 'share_american_gt_minus200': float((hi.american > -200).mean())}
    for col in ('market', 'side', 'group', 'cohort', 'sport', 'odds_band', 'book'):
        comp['by_' + col] = hi.groupby(col).agg(n=('y', 'size'), win=('y', 'mean'), mean_p=('p', 'mean'), implied=('impl_raw', 'mean')).round(3).reset_index().to_dict('records')
    comp['by_market_side_line'] = hi.groupby(['market', 'side']).agg(n=('y', 'size'), win=('y', 'mean'), line_median=('line', 'median'), line_min=('line', 'min'), line_max=('line', 'max')).round(3).reset_index().to_dict('records')
    # bootstrap of that bin's hit rate by game cluster, and the same bin on the family-dedup frame
    cl, ncl = pd.factorize(hi.game)
    yv = hi.y.to_numpy()
    bs = []
    for _ in range(2000):
        cnt = rng.multinomial(len(ncl), np.full(len(ncl), 1 / len(ncl)))[cl]
        bs.append((cnt * yv).sum() / cnt.sum())
    comp['win_rate_cluster_boot_ci'] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    hf = F[F.p >= 0.9]
    comp['family_dedup_bin'] = {'n': len(hf), 'win_rate': float(hf.y.mean())}
    comp['p_gap_to_implied'] = float((hi.p - hi.impl_raw).mean())
    rep['bin_90_100'] = comp

    t, detail = pending_audit(df, ROOT / 'data/results.json')
    t.to_csv(out / 'pending_by_market_side.csv', index=False)
    detail.to_csv(out / 'pending_detail_props.csv', index=False)

    if a.nflverse_dir:
        rep['regrade'] = regrade(df, a.nflverse_dir, out, rng)
    else:
        rep['regrade'] = regrade_nonflverse(df, out)
    rg = pd.read_csv(out / 'regrade_all.csv')
    if 'nflverse_no_row' in rg:
        ids = set(rg.loc[rg['nflverse_no_row'] == True, 'id'])  # noqa: E712
        rep['no_row_sensitivity'] = no_row_sensitivity(U, ids)
    (out / 'audit_summary.json').write_text(json.dumps(rep, indent=1, default=float), encoding='utf-8')
    print('wrote', out)


def no_row_sensitivity(U, ids):
    """Re-score with settlements dropped where nflverse has no stat row for the player-game but the tracker recorded a zero (likely inactive/DNP, void at books)."""
    rows = []
    V = U[~U['id'].isin(ids)]
    for name, f in (('ALL', lambda x: x),) + tuple((m, (lambda x, m=m: x[x.market == m])) for m in sorted(U.market.unique())):
        a, b = f(U), f(V)
        if len(a) == 0:
            continue
        aa, bb = a[a.p >= .9], b[b.p >= .9]
        rows.append({'slice': name, 'n_all': len(a), 'n_dropped': len(a) - len(b), 'brier_all': ((a.p - a.y) ** 2).mean(), 'brier_ex': ((b.p - b.y) ** 2).mean(),
                     'base_all': a.y.mean(), 'base_ex': b.y.mean(), 'n90_all': len(aa), 'n90_ex': len(bb), 'win90_all': aa.y.mean() if len(aa) else None, 'win90_ex': bb.y.mean() if len(bb) else None})
    return rows


def regrade_nonflverse(df, out):
    return regrade(df, None, out, None)


if __name__ == '__main__':
    main()
