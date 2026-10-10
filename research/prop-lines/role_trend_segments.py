#!/usr/bin/env python3
"""Task 4: where is the Champion mean demonstrably wrong as a function of the role trend? Segmented by position, games played k, season phase, teammate-out.
Read-only; licensed frame in memory, aggregates only. usage: role_trend_segments.py [--boot 1500]
Statistic (stated because the earlier doc does not define it):
   R_g      = sum(actual) / sum(Champion mean) - 1                      mean calibration inside a group
   TREND    = (1 + R_top15) / (1 + R_bottom15) - 1                       ratio of ratios; top/bottom 15% of the share change (trend_target_share for receptions & rec yds, trend_carry_share for rush yds), k >= 4
Cluster bootstrap resamples player-seasons (serial dependence inside a player-season is the dominant dependence), 95% intervals."""
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import calibration_models as cm  # noqa: E402
CACHE = ROOT.parent / 'GOING' / 'FantasyPoints' / 'research' / 'cache'
BOOT = int(sys.argv[sys.argv.index('--boot') + 1]) if '--boot' in sys.argv else 1500
rng = np.random.default_rng(20261010)
frame = cm.load_frame()

# appearance flags (players who did not play are zero-filled rows in the frame; a teammate's absence is public before kickoff via the inactive list)
app = pd.concat([pd.read_csv(CACHE / f'stats_player_week_{y}.csv', low_memory=False, usecols=['player_id', 'season', 'week', 'season_type']) for y in range(2021, 2026)])
played = set(zip(app.player_id, app.season, app.week))
frame = frame.copy()
frame['played'] = [(p, s, w) in played for p, s, w in zip(frame.player_id, frame.season, frame.week)]
# share of the team's expected target / carry mass that is absent this week
for col, nm in (('champ_target_share', 'out_tgt'), ('champ_carry_share', 'out_car')):
    gone = frame[~frame.played].groupby(['season', 'week', 'team'])[col].sum()
    frame[nm] = [gone.get((s, w, t), 0.0) for s, w, t in zip(frame.season, frame.week, frame.team)]
    frame.loc[~frame.played, nm] = np.nan  # only defined for players who played

SPEC = {  # market: (trend col, mean source, positions, out col)
    'receptions': ('trend_target_share', 'v1' if '--v1' in sys.argv else 'v2', 'out_tgt'),
    'rec_yds': ('trend_target_share', 'v2', 'out_tgt'),
    'rush_yds': ('trend_carry_share', 'v1', 'out_car'),
}


def mean_of(rows, market, source):
    if cm.MARKETS[market]['kind'] == 'count':
        return cm.model_params(rows, market, source)['lam']
    p = cm.model_params(rows, market, source)
    return (1 - p['p0']) * np.exp(p['mu'] + p['sig'] ** 2 / 2)


def stat_ci(d, y, m, fn):
    """fn(sum_y_by_cluster_fn) -> scalar. Bootstrap over player-seasons."""
    cl, ncl = pd.factorize(d.cluster)
    k = len(ncl)
    def sums(mask):
        return np.bincount(cl, weights=(y * mask), minlength=k), np.bincount(cl, weights=(m * mask), minlength=k)
    base = {}
    return cl, k, sums


def ratio_ci(d, mask_fn_list, boot=BOOT):
    """mask_fn_list: list of boolean masks (arrays) ; returns point & CI for [(1+R_a)/(1+R_b)-1] when two masks, or R when one."""
    cl, ncl = pd.factorize(d.cluster)
    k = len(ncl)
    y, m = d.y.to_numpy(float), d.m.to_numpy(float)
    S = [(np.bincount(cl, weights=y * mk, minlength=k), np.bincount(cl, weights=m * mk, minlength=k)) for mk in mask_fn_list]
    def val(w):
        r = [(sy @ w) / max(sm @ w, 1e-12) for sy, sm in S]
        return (r[0] / r[1] - 1) if len(r) == 2 else r[0] - 1
    pt = val(np.ones(k))
    out = np.array([val(rng.multinomial(k, np.full(k, 1 / k)).astype(float)) for _ in range(boot)])
    return pt, np.percentile(out, 2.5), np.percentile(out, 97.5)


def f(t, pct=True):
    return '%+6.1f%% [%+6.1f,%+6.1f]' % tuple(100 * x for x in t)


def sig(t):
    return '*' if (t[1] > 0 or t[2] < 0) else ' '


results = {}
for market, (tcol, src, outcol) in SPEC.items():
    rows = cm.eligible_rows(frame, market).copy()
    rows['m'] = mean_of(rows, market, src)
    rows['y'] = rows['y_' + market].to_numpy(float)
    rows['cluster'] = rows.player_id + '|' + rows.season.astype(str)
    if '--all' not in sys.argv:
        rows = rows[rows.played].reset_index(drop=True)  # participants only (books void a player who does not play)
    base = rows[(rows.k >= 4) & rows[tcol].notna()].copy()
    lo, hi = base[tcol].quantile(.15), base[tcol].quantile(.85)
    base['grp'] = np.where(base[tcol] >= hi, 'top', np.where(base[tcol] <= lo, 'bot', 'mid'))
    print(f'\n################ {market}  (mean source: {src}; rows with k>=4 and trend: {len(base)}; trend cut-offs bottom15% <= {lo:+.3f}, top15% >= {hi:+.3f}; ' + ('all rows incl. zero-filled DNP' if '--all' in sys.argv else 'participants only') + ')')
    print(f'  overall mean calibration R (all rows) {f(ratio_ci(rows, [np.ones(len(rows))]))}   (k>=4 rows) {f(ratio_ci(base, [np.ones(len(base))]))}')

    def seg(name, mask_all):
        d = base[mask_all].reset_index(drop=True)
        if len(d) < 200 or (d.grp == 'top').sum() < 40 or (d.grp == 'bot').sum() < 40:
            return
        top, bot = (d.grp == 'top').to_numpy(float), (d.grp == 'bot').to_numpy(float)
        t = ratio_ci(d, [top, bot])
        rt = ratio_ci(d, [top]); rb = ratio_ci(d, [bot]); ra = ratio_ci(d, [np.ones(len(d))])
        print(f'  {name:26s} n={len(d):5d} (top {int(top.sum()):4d}/bot {int(bot.sum()):4d}) | TREND {f(t)} {sig(t)} | R_top {f(rt)} {sig(rt)} | R_bot {f(rb)} {sig(rb)} | R_all {f(ra)} {sig(ra)}')
        return t

    print('  -- all (pooled)')
    seg('ALL', np.ones(len(base), bool))
    print('  -- by season (replication)')
    n_same = 0
    for s in range(2021, 2026):
        t = seg(f'season {s}', (base.season == s).to_numpy())
    print('  -- by position')
    for pos in cm.MARKETS[market]['positions']:
        seg(pos, (base.position == pos).to_numpy())
    print('  -- by role stability: games played this season (k), k>=4 only')
    for lo_k, hi_k, nm in ((4, 5, 'k=4-5'), (6, 8, 'k=6-8'), (9, 12, 'k=9-12')):
        seg(nm, ((base.k >= lo_k) & (base.k <= hi_k)).to_numpy())
    print('  -- by season phase (week)')
    for lo_w, hi_w, nm in ((1, 6, 'weeks 1-6'), (7, 12, 'weeks 7-12'), (13, 18, 'weeks 13-18')):
        seg(nm, ((base.week >= lo_w) & (base.week <= hi_w)).to_numpy())
    print('  -- injury-driven opportunity: share of team ' + ('target' if outcol == 'out_tgt' else 'carry') + ' mass belonging to teammates who did not play')
    thr = 0.10 if outcol == 'out_tgt' else 0.15
    seg(f'teammate out (>= {thr:.2f})', (base[outcol] >= thr).to_numpy())
    seg('no major teammate out', (base[outcol] < thr).to_numpy())
    print('  -- by position x phase (weeks 1-6 vs later)')
    for pos in cm.MARKETS[market]['positions']:
        for lo_w, hi_w, nm in ((1, 6, 'wk1-6'), (7, 18, 'wk7+')):
            seg(f'{pos} {nm}', ((base.position == pos) & (base.week >= lo_w) & (base.week <= hi_w)).to_numpy())
