#!/usr/bin/env python3
"""Task 2: QB passing yards on ACTUAL posted sportsbook lines (git history of data/nfl_betting.json), point-in-time model inputs only.
usage: passyds_lines.py QUOTES_PARQUET [--boot 3000]
Models (recomputed from public nflverse weekly stats through the game BEFORE each target game; verified starts, last 12, <=730 days, as scripts/build_pipeline does):
  v1       production season_fit(market=None) 80/20 season blend lognormal  (raw Champion v1 / pre-refit)
  v1shr    v1 + shrink_const (w, target) inside +/-50% of mean               (what was deployed before the refit)
  refit    season_fit(market='pass_yds', position='QB') -> lognormal_refit   (deployed now)
  trail    equal-weight mean of the modelled games with the v1 sigma
  mkt      de-vigged price (proportional), averaged over books
Prints aggregates only."""
import json, math, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_pipeline as bp
CACHE = ROOT.parent / 'GOING' / 'FantasyPoints' / 'research' / 'cache'
POL = json.load(open(ROOT / 'config' / 'calibration_policy.json'))['markets']['pass_yds']
SH = POL['superseded_shrink_const']['params']
BOOT = int(sys.argv[sys.argv.index('--boot') + 1]) if '--boot' in sys.argv else 3000
rng = np.random.default_rng(20261010)

# ---------------- history
games = pd.concat([pd.read_csv(CACHE / f'stats_player_week_{y}.csv', low_memory=False,
                               usecols=['player_id', 'season', 'week', 'season_type', 'team', 'position', 'passing_yards', 'attempts', 'game_id']) for y in range(2019, 2027)])
games = games[(games.season_type == 'REG') & (games.position == 'QB')]
sched = pd.read_csv(CACHE / 'games.csv')
sched = sched[(sched.season >= 2019) & (sched.game_type == 'REG')]
gd = dict(zip(sched.game_id, sched.gameday))
starters = set()
for r in sched.itertuples():
    for q in (r.home_qb_id, r.away_qb_id):
        if isinstance(q, str):
            starters.add((q, r.game_id))
games['date'] = games.game_id.map(gd)
games['start'] = [(p, g) in starters for p, g in zip(games.player_id, games.game_id)]
games = games[games.start & games.passing_yards.notna()].sort_values(['player_id', 'date'])
by = {p: g for p, g in games.groupby('player_id')}


def history(pid, day):
    g = by.get(pid)
    if g is None:
        return []
    lim = (pd.Timestamp(day) - pd.Timedelta(days=730)).strftime('%Y-%m-%d')
    g = g[(g.date < day) & (g.date >= lim)].tail(12)
    return [{'season': int(s), 'week': int(w), 'passing_yards': float(y)} for s, w, y in zip(g.season, g.week, g.passing_yards)]


def cdf(x, m):
    mass = m.get('nonpositive') or []
    n = m.get('n') or 1
    wts = m.get('nonpositive_weights')
    emp = sum((wts[i] if wts else 1 / n) for i, v in enumerate(mass) if v <= x)
    w = m.get('positive_weight', 1)
    if x <= 0 or w == 0:
        return emp
    return min(1, emp + w * norm.cdf((math.log(x) - m['mu']) / m['sig']))


def p_over(m, line):
    """JS propProbabilities: rounded lognormal; returns (over, under)."""
    under = cdf(math.ceil(line) - 0.5, m)
    below = cdf(math.floor(line) + 0.5, m)
    return 1 - below, under


def models(pid, day):
    h = history(pid, day)
    if len(h) < 5:
        return None
    mod = bp.season_fit(h, 'passing_yards', 'lognormal', 2026, 5, market='pass_yds', position='QB')
    if mod.get('status') != 'ready' or 'mu_log_raw' not in mod:
        return None  # refit not applicable -> not a production-modelled row
    base = dict(positive_weight=mod['positive_weight'], nonpositive=mod.get('nonpositive'), nonpositive_weights=mod.get('nonpositive_weights'), n=mod['n'])
    mall = float(np.mean([r['passing_yards'] for r in h]))
    s = mod['sigma_log_raw']
    return {'k': len(h),
            'v1': dict(base, mu=mod['mu_log_raw'], sig=s, mean=mod['mean_raw']),
            'refit': dict(base, mu=mod['mu_log'], sig=mod['sigma_log'], mean=mod['mean']),
            'trail': dict(base, mu=math.log(mall) - s * s / 2, sig=s, mean=mall)}


def prob(m, line, kind):
    o, u = p_over(m, line)
    if kind == 'shrink':
        c = m['mean']
        if 0.5 * c <= line <= 1.5 * c and o + u > 0:
            pc = min(1 - 1e-6, max(1e-6, o / (o + u)))
            q = SH['w'] * pc + (1 - SH['w']) * SH['target']
            return q * (o + u), (o + u) * (1 - q), o + u
    return o, u, o + u


def dec(a):
    return 1 + a / 100 if a > 0 else 1 + 100 / -a


# ---------------- quotes
q = pd.read_parquet(sys.argv[1])
q = q[(q.market == 'pass_yds') & q.over.notna() & q.under.notna() & q.pid.notna() & q.actual.notna() & (q.gameday <= '2026-10-08')].copy()
q = q[q.pid.isin(by.keys())]  # has started at least once since 2019
q['pg'] = q.gameday + '|' + q.pid
qo, qu = 1 / q.over.map(dec), 1 / q.under.map(dec)
q['dv'] = qo / (qo + qu)
q['vig'] = qo + qu - 1
q = q[(q.vig > -0.01) & (q.vig < 0.25)]  # a genuine two-way price
rows = []
for (pg, line), g in q.groupby(['pg', 'line']):
    rows.append({'pg': pg, 'pid': g.pid.iloc[0], 'day': g.gameday.iloc[0], 'week': g.week.iloc[0], 'line': line, 'actual': g.actual.iloc[0], 'n_books': g.book.nunique(),
                 'mkt': g.dv.mean(), 'vig': g.vig.mean(), 'hrs': ((g.kick - g.upd).dt.total_seconds() / 3600).min()})
L = pd.DataFrame(rows)
L = L[L.actual != L.line].copy()  # drop pushes
L['y'] = (L.actual > L.line).astype(float)


def pick_main(g):
    c = g[g.n_books >= 2]
    c = c if len(c) else g
    return c.loc[(c.mkt - 0.5).abs().idxmin(), 'line']


main = {pg: pick_main(g) for pg, g in L.groupby('pg')}
L['main'] = L.line == L.pg.map(main)
cache = {}
P = {k: [] for k in ('v1', 'v1shr', 'refit', 'trail')}
ok = []
for r in L.itertuples():
    key = (r.pid, r.day)
    if key not in cache:
        cache[key] = models(r.pid, r.day)
    m = cache[key]
    ok.append(m is not None)
    for k, mk, kind in (('v1', 'v1', 'plain'), ('v1shr', 'v1', 'shrink'), ('refit', 'refit', 'plain'), ('trail', 'trail', 'plain')):
        if m is None:
            P[k].append(np.nan)
        else:
            o, u, t = prob(m[mk], r.line, kind)
            P[k].append(o / t if t > 0 else np.nan)  # no-push over share, as the tracker/JS use
for k in P:
    L[k] = P[k]
L['modelled'] = ok
D = L[L.modelled].copy()
print('QB player-games with settled two-way quotes:', L.pg.nunique(), '| modelled (>=5 verified starts):', D.pg.nunique(), '| lines:', len(L), len(D))
print('weeks:', D.groupby('week').pg.nunique().to_dict(), '| books/line median', D.n_books.median(), '| hours before KO of last quote, median', round(D.hrs.median(), 1))
print('main lines:', int(D.main.sum()), ' alt lines:', int((~D.main).sum()), ' alt lines posted by >=2 books:', int(((~D.main) & (D.n_books >= 2)).sum()))

EPS = 1e-6


def brier(p, y): return np.mean((p - y) ** 2)


def ll(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))


def calib(p, y):
    x = np.log(np.clip(p, EPS, 1 - EPS) / (1 - np.clip(p, EPS, 1 - EPS)))
    a, b = 0.0, 1.0
    for _ in range(50):
        mu = 1 / (1 + np.exp(-(a + b * x)))
        v = mu * (1 - mu)
        g = np.array([np.sum(y - mu), np.sum((y - mu) * x)])
        H = np.array([[v.sum(), (v * x).sum()], [(v * x).sum(), (v * x * x).sum()]]) + 1e-8 * np.eye(2)
        step = np.linalg.solve(H, g)
        a, b = a + step[0], b + step[1]
        if np.abs(step).max() < 1e-8:
            break
    return a, b


def cboot(d, fn, boot=BOOT):
    cl, k = pd.factorize(d.pg)
    idx = [np.flatnonzero(cl == i) for i in range(len(k))]
    pt = fn(d)
    out = []
    for _ in range(boot):
        s = rng.integers(0, len(k), len(k))
        out.append(fn(d.iloc[np.concatenate([idx[i] for i in s])]))
    out = np.array(out)
    return pt, np.nanpercentile(out, 2.5), np.nanpercentile(out, 97.5)


def f(t): return '%+.4f [%+.4f, %+.4f]' % t


def report(name, d):
    print(f'\n== {name}: lines {len(d)}, player-games {d.pg.nunique()}, over rate {d.y.mean():.3f}')
    for k in ('mkt', 'v1', 'v1shr', 'refit', 'trail'):
        a, b = calib(d[k].to_numpy(), d.y.to_numpy())
        bt = cboot(d, lambda x, k=k: brier(x[k].to_numpy(), x.y.to_numpy()), 800)
        print(f'  {k:6s} Brier {bt[0]:.4f} [{bt[1]:.4f}, {bt[2]:.4f}]  LL {ll(d[k].to_numpy(), d.y.to_numpy()):.4f}  cal a={a:+.2f} b={b:.2f}')
    for a_, b_ in (('refit', 'mkt'), ('v1', 'mkt'), ('v1shr', 'mkt'), ('trail', 'mkt'), ('refit', 'v1'), ('refit', 'v1shr'), ('refit', 'trail')):
        fn = lambda x, a_=a_, b_=b_: brier(x[a_].to_numpy(), x.y.to_numpy()) - brier(x[b_].to_numpy(), x.y.to_numpy())
        fl = lambda x, a_=a_, b_=b_: ll(x[a_].to_numpy(), x.y.to_numpy()) - ll(x[b_].to_numpy(), x.y.to_numpy())
        print(f'  dBrier {a_:5s}-{b_:5s} (neg = first better) {f(cboot(d, fn))}   dLL {f(cboot(d, fl, 800))}')


report('MAIN lines (1 per player-game)', D[D.main])
report('ALTERNATE lines, all', D[~D.main])
report('ALTERNATE lines posted by >=2 books', D[(~D.main) & (D.n_books >= 2)])
M = D[D.main].copy()
print('\n== main-line yardage point accuracy (n=%d): median forecast vs actual' % len(M))
for k in ('v1', 'refit', 'trail'):
    M['med_' + k] = [math.exp(cache[(r.pid, r.day)][k]['mu']) for r in M.itertuples()]
for k in ('line', 'v1', 'refit', 'trail'):
    col = 'line' if k == 'line' else 'med_' + k
    e = M.actual - M[col]
    print(f'  {k:6s} MAE {e.abs().mean():6.1f}  bias(actual-pred) {e.mean():+6.1f}  mean pred {M[col].mean():6.1f}  (mean actual {M.actual.mean():.1f})')
print('  mean median-vs-line gap: refit %+.1f  v1 %+.1f  trail %+.1f' % tuple((M['med_' + k] - M.line).mean() for k in ('refit', 'v1', 'trail')))
L.to_parquet(Path(sys.argv[1]).parent / 'passyds_lines_eval.parquet')
