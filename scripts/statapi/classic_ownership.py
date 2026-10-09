"""Classic (full-slate) DraftKings field-ownership model, fitted on the private stat-api archive. Public code; it contains no data.

Usage:  python classic_ownership.py <StatApi dir> <FantasyPoints dir> <nfl_betting.json> [out_dir]
Writes (private, next to the archive): classic_ownership_eval.json (evaluation) and classic_ownership_model.json (schema going-private-classic-ownership-v1).

MODEL ("slot-share softmax").  For every contest and position group g (QB, RB, WR, TE, DST) player i gets a score eta_i = x_i . beta_pos and owns
    own_i = SLOT_TOTAL[pos] * exp(eta_i) / sum_{j in g} exp(eta_j)
so the position totals (QB 100, DST 100, RB 200+f, WR 300+f, TE 100+f; the 9 roster slots = 900%) are met exactly and slate size is handled automatically.
beta is fitted by minimising the cross-entropy between the actual within-position ownership shares and the softmax shares (L2 lambda fixed a priori, never tuned).

PRE-LOCK INFORMATION EACH FEATURE USES (all available at runtime before lock):
  salary                    DK salary of the player (slate pool).
  lrank                     ln(1 + number of same-position players in the slate with a strictly higher salary): slate pool only.
  tp / lp / value / lvr     tp = trailing projection.  REPLAY PROXY: shrunk mean of Fantasy Points weekly PPR points over the player's last 12 games
                            played STRICTLY BEFORE the slate's NFL week (same season or earlier; a per-game row exists only after that game was played).
                            Shrinkage tp=(sum+K*prior)/(n+K), K=3, prior = per-position linear fit of weekly points on salary taken from the TRAINING contests
                            (fixed constants in the model). PRODUCTION: replace tp with GOING's own per-player projected points.
                            Not available in replay for QB and DST (no weekly QB/DST points in the archive) -> those use salary-only features.
  own_it / opp_it           team and opponent implied totals = total/2 -/+ spread/2 from nfl_betting.json (pre-game market line; 2024+ only in the archive).
Actual contest results, actual ownership and the provider's projected ownership are never used as features.  The provider's projected points
(proj_pts, a current-engine value that may have been backfilled) are used ONLY by the clearly labelled 'provider_proj' upper-bound variant.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

POS = ['QB', 'RB', 'WR', 'TE', 'DST']
SHRINK_K = 3.0
TRAIL_N = 12
L2 = 0.5
SEASON_WEEK1_THU = {2021: '2021-09-09', 2022: '2022-09-08', 2023: '2023-09-07', 2024: '2024-09-05', 2025: '2025-09-04', 2026: '2026-09-10'}
TEAM_FIX = {'LAR': 'LA'}  # archive uses LAR, nfl_betting uses LA

FEATURES = {  # feature sets by model name (positions without the needed input fall back to the base set)
    'salary': ['s', 's2', 'lrank'],
    'trail': ['s', 's2', 'lrank', 'lp', 'tp'],
    'trail_value': ['s', 's2', 'lrank', 'lp', 'tp', 'value', 'lvr'],
    'trail_value_total': ['s', 's2', 'lrank', 'lp', 'tp', 'value', 'lvr', 'own_it', 'opp_it'],
    'trail_form': ['s', 's2', 'lrank', 'lp', 'tp', 'form', 'lowg'],
    'provider_proj': ['s', 's2', 'lrank', 'lp', 'tp', 'value', 'lvr'],
}
PROJ_POS = {'RB', 'WR', 'TE'}  # positions with a replay proxy


def norm_name(n):
    return re.sub(r'[^a-z]', '', str(n).lower().replace('jr.', '').replace('sr.', '').replace(' iii', '').replace(' ii', ''))


def week_of(date):
    d = pd.Timestamp(date)
    season = d.year if d.month >= 8 else d.year - 1
    wk = (d - pd.Timestamp(SEASON_WEEK1_THU[season])).days // 7 + 1 if season in SEASON_WEEK1_THU else None
    return season, wk


def load_fp_weekly(fp_root):
    """One row per (player, season, week): Fantasy Points weekly PPR points. Row exists only after the game was played."""
    rows = []
    for f in Path(fp_root).glob('normalized/*/efficiency_weekly/*.json'):
        d = json.loads(f.read_text(encoding='utf-8'))
        for r in d['rows']:
            e, c, m = r['entity'], r['context'], r['metrics']
            if c.get('week') is None or 'FPTS.FP' not in m or e['position'] not in ('RB', 'WR', 'TE', 'FB'):
                continue
            rows.append((norm_name(e['name']), 'RB' if e['position'] == 'FB' else e['position'], e.get('team'), d['season'], c['week'], m['FPTS.FP']))
    df = pd.DataFrame(rows, columns=['nm', 'pos', 'team', 'season', 'week', 'fp'])
    return df.groupby(['nm', 'pos', 'season', 'week'], as_index=False).fp.max()


def trailing(fpw):
    """dict (nm,pos) -> sorted arrays of (season*100+week, fp)."""
    out = {}
    for (nm, pos), g in fpw.groupby(['nm', 'pos']):
        g = g.sort_values(['season', 'week'])
        out[(nm, pos)] = (g.season.values * 100 + g.week.values, g.fp.values)
    return out


def load_lines(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    m = {}
    for g in d['games']:
        if g.get('total') is None or g.get('spread') is None:
            continue
        hi, ai = g['total'] / 2 - g['spread'] / 2, g['total'] / 2 + g['spread'] / 2
        m[(g['season'], g['week'], g['home'])] = (hi, ai)
        m[(g['season'], g['week'], g['away'])] = (ai, hi)
    return m


def build_frame(statapi_root, fp_root, lines_path):
    df = pd.read_parquet(Path(statapi_root) / 'ownership_frame.parquet')
    df = df[(df.game_type == 'classic') & df.field_pct.notna() & df.salary.notna()].copy()
    df = df[df.date >= '2021-09-01']  # FP weekly coverage starts with the 2021 season
    tr = trailing(load_fp_weekly(fp_root))
    lines = load_lines(lines_path)
    sw = {d: week_of(d) for d in df.date.unique()}
    df['season'] = df.date.map(lambda d: sw[d][0])
    df['week'] = df.date.map(lambda d: sw[d][1])
    df['nm'] = df.name.map(norm_name)
    df['ngames'] = 0
    df['tsum'] = 0.0
    df['tsum4'] = 0.0
    df['n4'] = 0
    for idx, (nm, pos, season, week) in zip(df.index, zip(df.nm, df.position, df.season, df.week)):
        arr = tr.get((nm, pos))
        if arr is None or week is None:
            continue
        keys, fp = arr
        k = keys < season * 100 + week
        v = fp[k][-TRAIL_N:]
        df.at[idx, 'ngames'] = len(v)
        df.at[idx, 'tsum'] = float(v.sum())
        df.at[idx, 'tsum4'] = float(v[-4:].sum())
        df.at[idx, 'n4'] = len(v[-4:])
    team = df.team.replace(TEAM_FIX)
    its = [lines.get((s, w, t), (np.nan, np.nan)) for s, w, t in zip(df.season, df.week, team)]
    df['own_it'] = [x[0] for x in its]
    df['opp_it'] = [x[1] for x in its]
    return df.reset_index(drop=True)


def fit_prior(train):
    """Per-position linear fit of trailing mean points on salary, from TRAIN rows with >= 6 games. Returns {pos: (a, b)} points = a + b*salary_k."""
    out = {}
    for p in PROJ_POS:
        t = train[(train.position == p) & (train.ngames >= 6)]
        x, y = t.salary.values / 1000, (t.tsum / t.ngames).values
        b, a = np.polyfit(x, y, 1)
        out[p] = (float(a), float(b))
    return out


def add_features(df, prior, use_provider=False):
    d = df.copy()
    d['s'] = (d.salary - 5000) / 1000
    d['s2'] = d.s ** 2
    gk = ['contest_id', 'position']
    d['lrank'] = np.log1p(d.groupby(gk).salary.rank(ascending=False, method='min') - 1)
    if use_provider:
        d['tp'] = d.proj_pts
    else:
        pr = d.position.map(lambda p: prior[p][0] if p in prior else np.nan) + d.position.map(lambda p: prior[p][1] if p in prior else np.nan) * d.salary / 1000
        d['tp'] = (d.tsum + SHRINK_K * pr) / (d.ngames + SHRINK_K)
    d['lp'] = np.log(np.maximum(d.tp, 1.0))
    if not use_provider:
        t4 = (d.tsum4 + SHRINK_K * pr) / (d.n4 + SHRINK_K)
        d['form'] = (t4 - d.tp) / 10.0  # last-4 form relative to last-12 mean
        d['lowg'] = (d.ngames < 3).astype(float)
    d['value'] = d.tp / (d.salary / 1000) / 3.0
    d['lvr'] = np.log1p(d.groupby(gk).value.rank(ascending=False, method='min') - 1)
    d['tp'] = d.tp / 10.0
    d['own_it'] = (d.own_it - 22.0) / 5.0
    d['opp_it'] = (d.opp_it - 22.0) / 5.0
    return d


def feats_for(pos, name, use_provider):
    f = list(FEATURES[name])
    if name != 'salary' and pos not in PROJ_POS and not (use_provider):
        f = [x for x in f if x in FEATURES['salary'] or x in ('own_it', 'opp_it')]
    return f


def fit_position(d, feats):
    """Softmax-share fit for one position; d has contest_id, field_pct and the feature columns (no NaN)."""
    codes, _ = pd.factorize(d.contest_id)
    X = d[feats].values.astype(float)
    q = d.field_pct.values / d.groupby('contest_id').field_pct.transform('sum').values
    ng = codes.max() + 1

    def f(b):
        eta = X @ b
        m = np.zeros(ng)
        np.maximum.at(m, codes, eta - 0)  # per-group max (eta may be all negative; fine, shift only)
        e = np.exp(eta - m[codes])
        z = np.bincount(codes, e, ng)
        p = e / z[codes]
        loss = -(q * np.log(p + 1e-12)).sum() / ng + L2 * (b ** 2).sum() / ng
        qs = np.bincount(codes, q, ng)
        grad = -(X * (q - qs[codes] * p)[:, None]).sum(0) / ng + 2 * L2 * b / ng
        return loss, grad

    r = minimize(f, np.zeros(len(feats)), jac=True, method='L-BFGS-B')
    return r.x


def predict_share(d, feats, beta):
    eta = d[feats].values.astype(float) @ beta
    e = np.exp(eta - eta.max())
    return e


# ----- salary-only rank table (baseline M0) -----
def size_bucket(n):
    return 0 if n <= 12 else 1 if n <= 30 else 2


RANK_BINS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 30, 1000]  # upper bounds; rank r goes in the first bin with r <= bound


def rank_bin(r):
    for i, ub in enumerate(RANK_BINS):
        if r <= ub:
            return i
    return len(RANK_BINS) - 1


def fit_rank_table(train):
    t = train.copy()
    t['rk'] = t.groupby(['contest_id', 'position']).salary.rank(ascending=False, method='min').astype(int)
    t['n'] = t.groupby(['contest_id', 'position']).salary.transform('size')
    t['sb'] = t.n.map(size_bucket)
    t['rb'] = t.rk.map(rank_bin)
    t['share'] = t.field_pct / t.groupby(['contest_id', 'position']).field_pct.transform('sum')
    tab = {p: np.zeros((3, len(RANK_BINS))) for p in POS}
    for p in POS:
        g = t[t.position == p].groupby(['sb', 'rb']).share.mean()
        for (sb, rb), v in g.items():
            tab[p][sb][rb] = v
        # empty cells (rare): fill from nearest populated size bucket
        for sb in range(3):
            for rb in range(len(RANK_BINS)):
                if tab[p][sb][rb] == 0:
                    nz = [tab[p][o][rb] for o in range(3) if tab[p][o][rb] > 0]
                    tab[p][sb][rb] = float(np.mean(nz)) if nz else 1e-4
    return tab


def predict_table(d, tab):
    rk = d.groupby(['contest_id', 'position']).salary.rank(ascending=False, method='min').astype(int)
    n = d.groupby(['contest_id', 'position']).salary.transform('size')
    return np.array([tab[p][size_bucket(a)][rank_bin(r)] for p, a, r in zip(d.position, n, rk)])


# ----- slot totals -----
def slot_totals(train_complete):
    """Mean within-slate position totals of complete (sum ~ 900) contests: QB/DST exactly 100; the FLEX 100 is split RB/WR/TE as observed."""
    s = train_complete.groupby(['contest_id', 'position']).field_pct.sum().unstack().fillna(0)
    m = s.mean()
    flex = {p: max(m[p] - base, 0) for p, base in (('RB', 200), ('WR', 300), ('TE', 100))}
    tot = sum(flex.values())
    return {'QB': 100.0, 'DST': 100.0, **{p: base + 100.0 * flex[p] / tot for p, base in (('RB', 200), ('WR', 300), ('TE', 100))}}


def complete_contests(df):
    s = df.groupby('contest_id').field_pct.sum()
    ok = s[(s > 880) & (s < 920)].index
    return df[df.contest_id.isin(ok)]


def assemble(d, totals, shares):
    """shares: raw positive score per row; normalise inside each (contest, position) and scale by the slot total."""
    out = pd.Series(shares, index=d.index)
    z = out.groupby([d.contest_id, d.position]).transform('sum')
    return out / z * d.position.map(totals)


def metrics(y, p):
    return {'n': int(len(y)), 'mae': float(np.mean(np.abs(y - p))), 'corr': float(np.corrcoef(y, p)[0, 1]), 'bias': float(np.mean(p - y))}


def decile_calibration(y, p):
    q = pd.qcut(p.rank(method='first'), 10, labels=False)
    return [{'decile': int(k) + 1, 'mean_pred': round(float(p[q == k].mean()), 3), 'mean_actual': round(float(y[q == k].mean()), 3)} for k in range(10)]


def top_recall(d, y, p, k=10):
    """Per contest: |top-k predicted ∩ top-k actual| / k, and overlap on the top-k restricted to players >=10% actual."""
    rec, hit_chalk = [], []
    t = d.assign(y=y, p=p)
    for _, g in t.groupby('contest_id'):
        if len(g) < 2 * k:
            continue
        a = set(g.nlargest(k, 'y').index)
        b = set(g.nlargest(k, 'p').index)
        rec.append(len(a & b) / k)
        chalk = set(g[g.y >= 15].index)
        if chalk:
            hit_chalk.append(len(chalk & set(g.nlargest(k, 'p').index)) / len(chalk))
    return {'top10_recall_mean': float(np.mean(rec)), 'contests': len(rec), 'chalk15_in_pred_top10_mean': float(np.mean(hit_chalk)) if hit_chalk else None}


def fit_models(tr, prior, totals, names, provider=False):
    """Returns {model: {pos: (feats, beta)}} fitted on training rows tr (already feature-augmented)."""
    out = {}
    for name in names:
        out[name] = {}
        for p in POS:
            g = tr[tr.position == p]
            feats = feats_for(p, name, provider and name == 'provider_proj')
            g = g.dropna(subset=feats)
            out[name][p] = (feats, fit_position(g, feats))
    return out


def predict_model(te, mdl, totals):
    sc = pd.Series(np.nan, index=te.index)
    for p in POS:
        feats, beta = mdl[p]
        g = te[te.position == p]
        if len(g) == 0:
            continue
        eta = g[feats].fillna(0).values @ beta  # NaN features (no lines) -> neutral 0
        sc.loc[g.index] = np.exp(eta - eta.max())
    return assemble(te, totals, sc.values)


def stack_rates(statapi_root, contest_ids, max_lineups=20000):
    """Cheap stack analysis: per contest, actual share of lineups with a QB + >=1 same-team WR/TE ('stack') or QB + opposing-team skill ('bring-back'), versus the share expected if
    lineups were drawn independently from the field ownership of the QB and of that team's WR/TE (a lower bound for the true independent expectation; ignores salary/roster coupling).
    Aggregates only."""
    rows = []
    for cid in contest_ids:
        base = Path(statapi_root) / 'normalized' / f'contest_{cid}'
        pool = pd.read_parquet(base / 'pool.parquet')
        pool = pool[~pool.is_unresolved.fillna(False).astype(bool)]
        lu = pd.read_parquet(base / 'lineups.parquet').head(max_lineups)
        team = dict(zip(pool.player_key, pool.team))
        pos = dict(zip(pool.player_key, pool.position))
        seats = [c for c in lu.columns if c.startswith('seat')]
        qb = lu[seats[0]].map(team)
        other = {s: lu[s].map(team) for s in seats[1:8]}
        stack = np.zeros(len(lu), bool)
        for s in other.values():
            stack |= (s == qb).values
        n = len(lu)
        # independence expectation: P(QB team t) * P(at least one of 7 non-DST skill/flex slots on t | marginal field ownership of t's skill players)
        own = pool[pool.position != 'DST'].groupby('team').field_pct.sum() / 100.0
        qbown = pool[pool.position == 'QB'].set_index('team').field_pct.groupby(level=0).sum() / 100.0
        exp = float(sum(qbown.get(t, 0) * (1 - np.exp(-own.get(t, 0))) for t in qbown.index))
        rows.append({'contest_id': int(cid), 'lineups': n, 'actual_stack_rate': float(stack.mean()), 'indep_expected_stack_rate': exp})
    return rows


def main(statapi_root, fp_root, lines_path, out_dir=None):
    out_dir = Path(out_dir or statapi_root)
    df = build_frame(statapi_root, fp_root, lines_path)
    df = complete_contests(df)
    df['nteams'] = df.groupby('contest_id').team.transform('nunique')
    train, test = df[df.date < '2025-01-01'], df[df.date >= '2025-01-01']
    prior = fit_prior(train)
    totals = slot_totals(train)
    tr, te = add_features(train, prior), add_features(test, prior)
    tr_p, te_p = add_features(train, prior, True), add_features(test, prior, True)
    res = {'split': {'train_contests': int(train.contest_id.nunique()), 'test_contests': int(test.contest_id.nunique()), 'train_rows': int(len(train)), 'test_rows': int(len(test)),
                     'train_lines_rows': int(tr.own_it.notna().sum()), 'test_lines_rows': int(te.own_it.notna().sum())},
           'slot_totals': totals, 'prior_points_vs_salary': prior, 'models': {}}
    # in-sample subset for model 4: train rows with lines. For fairness M3 is also reported when trained on the same rows.
    names = ['salary', 'trail', 'trail_form', 'trail_value', 'trail_value_total']
    fits = fit_models(tr, prior, totals, names)
    fits_lines = fit_models(tr.dropna(subset=['own_it']), prior, totals, ['trail_value', 'trail_value_total'])
    fits_p = fit_models(tr_p, prior, totals, ['provider_proj'], provider=True)
    tab = fit_rank_table(train)
    preds = {'rank_table': pd.Series(predict_table(te, tab), index=te.index)}
    preds['rank_table'] = assemble(te, totals, preds['rank_table'].values)
    for n in names:
        preds[n] = predict_model(te, fits[n], totals)
    for n in ('trail_value', 'trail_value_total'):
        preds[n + '_fit_on_lines_rows'] = predict_model(te, fits_lines[n], totals)
    preds['provider_proj'] = predict_model(te_p, fits_p['provider_proj'], totals)
    preds['provider_ownership_ref'] = te.proj_own_pct
    big = te.nteams >= 8
    y = te.field_pct
    for n, p in preds.items():
        ok = p.notna()
        r = {'all': metrics(y[ok], p[ok]), 'slates_ge8_teams': metrics(y[ok & big], p[ok & big])}
        if n != 'provider_ownership_ref':
            r['deciles'] = decile_calibration(y[ok], p[ok])
        r['top10'] = top_recall(te[ok], y[ok], p[ok])
        r['by_position_mae'] = {pp: float(np.mean(np.abs((y - p)[ok & (te.position == pp)]))) for pp in POS}
        r['mean_own_top10_actual_vs_pred'] = None
        res['models'][n] = r
    (out_dir / 'classic_ownership_eval.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    return res, df, prior, totals


def export(statapi_root, fp_root, lines_path, out_dir=None, model_name='trail'):
    """Refit the chosen specification on ALL contests (specification fixed by the chronological evaluation) and write the private JS-appliable model."""
    out_dir = Path(out_dir or statapi_root)
    df = build_frame(statapi_root, fp_root, lines_path)
    df = complete_contests(df)
    prior = fit_prior(df)
    totals = slot_totals(df)
    d = add_features(df, prior)
    dp = add_features(df, prior, True)
    tab = fit_rank_table(df)
    model = {'schema': 'going-private-classic-ownership-v1', 'licensed_derived': True, 'note': 'Private; derived from licensed stat-api archive. Do not commit or serve.',
             'fit_rows': int(len(df)), 'fit_contests': int(df.contest_id.nunique()), 'fit_through': str(df.date.max()),
             'slot_totals': totals, 'positions': POS,
             'normalisation': 'own_i = slot_total[pos] * exp(eta_i - max) / sum_group exp(eta_j - max), group = same-position players in the slate pool',
             'inputs_note': 'tp = player projected DK points (GOING projection in production). features per feature_defs. Missing inputs: use fallback models.',
             'feature_defs': {'s': '(salary-5000)/1000', 's2': 's^2', 'lrank': 'ln(1+count of same-position slate players with strictly higher salary)',
                              'tp': 'proj_points/10', 'lp': 'ln(max(proj_points,1))', 'value': 'proj_points/(salary/1000)/3',
                              'lvr': 'ln(1+count of same-position slate players with strictly higher value)', 'own_it': '(team_implied_total-22)/5', 'opp_it': '(opp_implied_total-22)/5'},
             'models': {}, 'rank_table': {'rank_bin_upper': RANK_BINS, 'size_bucket_upper': [12, 30], 'share': {p: tab[p].round(6).tolist() for p in POS},
                                           'note': 'salary-only baseline: share of the position total by [size bucket][rank bin]; renormalise inside the position group then multiply by slot_total'}}
    specs = {'salary_only': ('salary', d, False), 'projection': ('trail', d, False), 'projection_value': ('trail_value', d, False), 'projection_value_total': ('trail_value_total', d, False),
             'provider_projection_all_positions': ('provider_proj', dp, True)}
    for key, (name, frame, prov) in specs.items():
        m = {}
        for p in POS:
            feats = feats_for(p, name, prov)
            g = frame[frame.position == p].dropna(subset=feats)
            b = fit_position(g, feats)
            m[p] = {'features': feats, 'beta': [round(float(v), 6) for v in b]}
        model['models'][key] = m
    model['default_model'] = 'projection'
    model['default_model_note'] = ('projection = trailing-projection spec: RB/WR/TE use [s,s2,lrank,lp,tp], QB/DST salary-only because the replay proxy has no QB/DST points. '
                                   'If GOING projections exist for QB/DST also, use provider_projection_all_positions only after checking calibration of GOING projection vs the provider engine.')
    (out_dir / 'classic_ownership_model.json').write_text(json.dumps(model, indent=1), encoding='utf-8')
    return model


if __name__ == '__main__':
    a = sys.argv[1:]
    r = main(*a[:4])[0]
    export(*a[:4])
    for n, m in r['models'].items():
        print(n, {k: round(v, 3) for k, v in m['all'].items()}, 'ge8:', round(m['slates_ge8_teams']['mae'], 3), m['top10'])
