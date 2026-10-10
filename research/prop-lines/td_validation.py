#!/usr/bin/env python3
"""Task 3: calibration of the DEPLOYED touchdown probabilities, P(>=1) = 1 - exp(-lambda) with lambda = Champion-v2 blended mean x policy mean_scale factor.
Read-only. Licensed Champion frame is read in memory; only aggregates are printed. Public nflverse pbp (cache) feeds the scoring-role tier baseline.
usage: td_validation.py [--boot 600]
Walk-forward: baselines and the WF factor are fitted on seasons < T only. The policy factors were fit on 2021-24, so only 2025 is out-of-sample for them."""
import json, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import calibration_models as cm  # noqa: E402
import scoring_role as sr  # noqa: E402
CACHE = ROOT.parent / 'GOING' / 'FantasyPoints' / 'research' / 'cache'
BOOT = int(sys.argv[sys.argv.index('--boot') + 1]) if '--boot' in sys.argv else 600
rng = np.random.default_rng(20261010)
ONLY = '--played' in sys.argv  # participants only: books void a player who does not play
FACT = {k: v['params']['factor'] for k, v in json.load(open(ROOT / 'config' / 'calibration_policy.json'))['markets'].items() if v['method'] == 'mean_scale'}
EPS = 1e-6
frame = cm.load_frame()

# ---------------- point-in-time scoring-role tier (xtd_share_l6, strictly earlier appearances; same rule as scripts/scoring_role.py record_for)
rates = sr.load_rates()
parts = []
for y in range(2019, 2026):
    p = pd.read_parquet(CACHE / f'pbp_{y}.parquet', columns=[c for c in sr.PBP_COLUMNS if c != 'game_date'])
    parts.append(p[p.season_type == 'REG'])
pbp = pd.concat(parts)
agg = sr.aggregate_plays(pbp.to_dict('records'), rates)
pg = agg['player_games']
app = pd.concat([pd.read_csv(CACHE / f'stats_player_week_{y}.csv', low_memory=False, usecols=['player_id', 'season', 'week', 'season_type', 'position']) for y in range(2019, 2026)])
app = app[(app.season_type == 'REG') & app.position.isin(['QB', 'RB', 'WR', 'TE'])].sort_values(['player_id', 'season', 'week'])
app['xsh'] = [pg[(p, s, w)]['xtd_share'] if (p, s, w) in pg else 0.0 for p, s, w in zip(app.player_id, app.season, app.week)]
app['key'] = app.season * 100 + app.week
hist = {p: (g.key.to_numpy(), g.xsh.to_numpy()) for p, g in app.groupby('player_id')}
played_set = set(zip(app.player_id, app.season, app.week))
def tier_pit(pid, season, week):
    """Point-in-time tier from appearances strictly before (season, week); does NOT depend on whether the player appeared in this game."""
    h = hist.get(pid)
    if h is None:
        return np.nan
    i = np.searchsorted(h[0], season * 100 + week, side='left')
    if i < sr.MIN_APPEARANCES:
        return np.nan
    return float(np.mean(h[1][max(0, i - 6):i]))

def tier_of(v):
    return 'NA' if not np.isfinite(v) else sr.tier(v)


# ---------------- helpers
def logit(p):
    p = np.clip(p, EPS, 1 - EPS); return np.log(p / (1 - p))
def wcal(x, y, w):
    a, b = 0.0, 1.0
    for _ in range(40):
        mu = 1 / (1 + np.exp(-(a + b * x))); v = w * mu * (1 - mu)
        g = np.array([np.sum(w * (y - mu)), np.sum(w * (y - mu) * x)])
        H = np.array([[v.sum(), (v * x).sum()], [(v * x).sum(), (v * x * x).sum()]]) + 1e-9 * np.eye(2)
        s = np.linalg.solve(H, g); a, b = a + s[0], b + s[1]
        if np.abs(s).max() < 1e-8: break
    return a, b
def brier_w(p, y, w): return np.sum(w * (p - y) ** 2) / w.sum()
def ll_w(p, y, w):
    p = np.clip(p, EPS, 1 - EPS); return -np.sum(w * (y * np.log(p) + (1 - y) * np.log(1 - p))) / w.sum()
def boot_ci(d, fn, boot=BOOT):
    cl, k = pd.factorize(d.game)
    out = []
    for _ in range(boot):
        w = rng.multinomial(k.size, np.full(k.size, 1 / k.size))[cl].astype(float)
        out.append(fn(w))
    out = np.array(out); return np.nanpercentile(out, 2.5), np.nanpercentile(out, 97.5)
def fmt(pt, ci): return '%.3f [%.3f,%.3f]' % (pt, ci[0], ci[1])
def fmt4(pt, ci): return '%+.4f [%+.4f,%+.4f]' % (pt, ci[0], ci[1])

def build(market):
    rows = cm.eligible_rows(frame, market).copy()
    lam_v2 = cm.model_params(rows, market, 'v2')['lam']
    rows['lam_v1'] = rows['champ_' + market].to_numpy(float)
    rows['lam_v2'] = lam_v2
    rows['lam_dep'] = lam_v2 * FACT[market]
    rows['y1'] = (rows['y_' + market] >= 1).astype(float)
    rows['game'] = rows.season.astype(str) + '-' + rows.week.astype(str) + '-' + rows[['team', 'opponent']].apply(lambda r: '|'.join(sorted(map(str, r))), axis=1)
    rows['xshare'] = [tier_pit(p, s, w) for p, s, w in zip(rows.player_id, rows.season, rows.week)]
    rows['tier'] = rows.xshare.map(tier_of)
    rows['played'] = [(p, s, w) in played_set for p, s, w in zip(rows.player_id, rows.season, rows.week)]
    if ONLY:
        rows = rows[rows.played].reset_index(drop=True)
    for c in ('v1', 'v2', 'dep'):
        rows['p_' + c] = 1 - np.exp(-rows['lam_' + c])
    # walk-forward baselines (seasons < T): base rate by position, tier rate by position; WF factor
    rows['p_base'] = np.nan; rows['p_tier'] = np.nan; rows['p_wf'] = np.nan; rows['wf_factor'] = np.nan
    for T in range(2022, 2026):
        tr, te = rows.season < T, rows.season == T
        rows.loc[te, 'p_base'] = rows.loc[te, 'position'].map(rows[tr].groupby('position').y1.mean()).to_numpy()
        tt = rows[tr].groupby(['position', 'tier']).y1.agg(['mean', 'size'])
        bb = rows[tr].groupby('position').y1.mean()
        def tp(r):
            k = (r.position, r.tier)
            if k in tt.index and tt.loc[k, 'size'] >= 30:
                return tt.loc[k, 'mean']
            return bb[r.position]
        rows.loc[te, 'p_tier'] = rows[te].apply(tp, axis=1).to_numpy()
        f = rows.loc[tr, 'y_' + market].sum() / rows.loc[tr, 'lam_v2'].sum()
        rows.loc[te, 'wf_factor'] = f
        rows.loc[te, 'p_wf'] = 1 - np.exp(-rows.loc[te, 'lam_v2'] * f)
    # tier-augmented logistic fitted walk-forward on [logit p_dep, tier dummies]
    rows['p_combo'] = np.nan
    X = np.column_stack([logit(rows.p_dep.to_numpy())] + [(rows.tier == t).astype(float).to_numpy() for t in ('PRIMARY', 'SECONDARY', 'TERTIARY', 'FRINGE')])
    for T in range(2022, 2026):
        tr, te = (rows.season < T).to_numpy(), (rows.season == T).to_numpy()
        beta = fit_multi(X[tr], rows.y1.to_numpy()[tr])
        rows.loc[te, 'p_combo'] = 1 / (1 + np.exp(-(beta[0] + X[te] @ beta[1:])))
    rows['p_platt'] = np.nan
    xd = logit(rows.p_dep.to_numpy())
    for T in range(2022, 2026):
        tr, te = (rows.season < T).to_numpy(), (rows.season == T).to_numpy()
        a, b = wcal(xd[tr], rows.y1.to_numpy()[tr], np.ones(tr.sum()))
        rows.loc[te, 'p_platt'] = 1 / (1 + np.exp(-(a + b * xd[te])))
    return rows

def fit_multi(X, y, ridge=1e-3):
    Z = np.column_stack([np.ones(len(X)), X]); b = np.zeros(Z.shape[1])
    for _ in range(50):
        mu = 1 / (1 + np.exp(-Z @ b)); W = mu * (1 - mu)
        H = (Z * W[:, None]).T @ Z + ridge * np.eye(len(b)); g = Z.T @ (y - mu)
        s = np.linalg.solve(H, g); b += s
        if np.abs(s).max() < 1e-8: break
    return b

def block(name, d, cols=('p_v1', 'p_v2', 'p_dep')):
    y = d.y1.to_numpy(); w1 = np.ones(len(d))
    print(f'  {name}: n={len(d)} games={d.game.nunique()} base={y.mean():.3f}')
    for c in cols:
        p = d[c].to_numpy()
        a, b = wcal(logit(p), y, w1)
        ci_s = boot_ci(d, lambda w, p=p: wcal(logit(p), y, w)[1])
        ci_a = boot_ci(d, lambda w, p=p: wcal(logit(p), y, w)[0])
        print(f'    {c:7s} mean p {p.mean():.3f} obs {y.mean():.3f} ratio {y.mean() / p.mean():.3f} | Brier {brier_w(p, y, w1):.4f} LL {ll_w(p, y, w1):.4f} | slope {fmt(b, ci_s)} int {fmt(a, ci_a)}')

def paired(d, a, b, label=''):
    y = d.y1.to_numpy(); pa, pb = d[a].to_numpy(), d[b].to_numpy()
    fn = lambda w: brier_w(pa, y, w) - brier_w(pb, y, w)
    fl = lambda w: ll_w(pa, y, w) - ll_w(pb, y, w)
    one = np.ones(len(d))
    print(f'    dBrier {a}-{b} {label}: {fmt4(fn(one), boot_ci(d, fn))}   dLL {fmt4(fl(one), boot_ci(d, fl))}')

for market in ('atd', 'rec_tds', 'rush_tds'):
    R = build(market)
    print(f'DNP/no-appearance rows (zero-filled): {int((~R.played).sum())} of {len(R)} = {(~R.played).mean():.3%}, TD rate among them {R[~R.played].y1.mean():.3f}')
    print(f'\n######## {market}  (policy factor {FACT[market]}, rows {len(R)}, WF factors ' + ', '.join(f'{t}:{R[R.season == t].wf_factor.iloc[0]:.3f}' for t in range(2022, 2026)) + ')')
    for T in (2023, 2024, 2025):
        block(f'season {T}', R[R.season == T])
    block('pooled 2023-25 (factor in-sample for 2023-24)', R[R.season >= 2023])
    H = R[R.season == 2025]
    print('  -- 2025 holdout paired vs baselines (negative = first better)')
    for a, b in (('p_dep', 'p_v2'), ('p_dep', 'p_base'), ('p_dep', 'p_tier'), ('p_tier', 'p_base'), ('p_combo', 'p_dep'), ('p_platt', 'p_dep'), ('p_dep', 'p_wf')):
        paired(H, a, b, '2025')
    P = R[R.season >= 2023]
    print('  -- pooled 2023-25 paired (WF baselines only use earlier seasons)')
    for a, b in (('p_dep', 'p_v2'), ('p_dep', 'p_base'), ('p_dep', 'p_tier'), ('p_tier', 'p_base'), ('p_combo', 'p_dep'), ('p_platt', 'p_dep')):
        paired(P, a, b, 'pooled')
    print('  -- by position (pooled 2023-25, deployed)')
    for pos, d in P.groupby('position'):
        block(pos, d, ('p_dep',))
    print('  -- by k = current-season games played (pooled 2023-25, deployed)')
    P = P.assign(kb=pd.cut(P.k, [-1, 0, 2, 5, 9, 99], labels=['k=0', 'k1-2', 'k3-5', 'k6-9', 'k10+']))
    for kb, d in P.groupby('kb', observed=True):
        block(str(kb), d, ('p_dep',))
    print('  -- predicted-probability bands (pooled 2023-25, deployed): band n meanP obs [95% cluster CI]')
    edges = [0, .1, .2, .3, .4, .5, 1.0]
    P = P.assign(band=pd.cut(P.p_dep, edges, include_lowest=True))
    for b, d in P.groupby('band', observed=True):
        cl, k = pd.factorize(d.game); y = d.y1.to_numpy(); out = []
        for _ in range(400):
            w = rng.multinomial(k.size, np.full(k.size, 1 / k.size))[cl].astype(float); out.append(np.sum(w * y) / w.sum())
        print(f'    {str(b):12s} n={len(d):5d} meanP {d.p_dep.mean():.3f} obs {y.mean():.3f} [{np.percentile(out, 2.5):.3f},{np.percentile(out, 97.5):.3f}] tierBase {d.p_tier.mean():.3f}')
    print('  -- scoring-role tier hit rate (pooled 2023-25) tier n obs meanP_dep')
    for t, d in P.groupby('tier'):
        print(f'    {t:10s} n={len(d):5d} obs {d.y1.mean():.3f}  deployed meanP {d.p_dep.mean():.3f}')
