#!/usr/bin/env python3
"""Why is the live receptions calibration slope (~0.20) so far below the point-in-time backtest (~0.8)?

Read-only. Uses data/public_tracker (via scripts/calibration_audit_a.load_frame), research/calibration/A/regrade_all.csv (nflverse no-row flags),
and, for the backtest, scripts/calibration_models (licensed cache is read in-memory only; only aggregates are printed).
    python research/receptions-live/analysis.py [--boot 2000] > out.txt
"""
import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import poisson

warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import calibration_audit_a as A  # noqa: E402

SEED = 20261009
logit = A.logit


def slope(x, y, w=None):
    w = np.ones(len(x)) if w is None else w
    a, b = A.fit_cal(x, y, w)
    return b


def cboot(d, fn, boot, rng, col='game'):
    """Cluster bootstrap (resample games). fn(weights) -> scalar; returns (point, lo, hi, n_valid)."""
    cl, ncl = pd.factorize(d[col])
    k = len(ncl)
    pt = fn(np.ones(len(d)))
    out = []
    for _ in range(boot):
        w = rng.multinomial(k, np.full(k, 1 / k))[cl].astype(float)
        v = fn(w)
        if np.isfinite(v):
            out.append(v)
    out = np.array(out)
    if len(out) < 0.8 * boot:
        return pt, np.nan, np.nan, len(out)
    return pt, np.percentile(out, 2.5), np.percentile(out, 97.5), len(out)


def fmt(t):
    return '%.3f [%.3f, %.3f]' % t[:3]


def slope_ci(d, boot, rng, pcol='p', ycol='y'):
    x = logit(d[pcol].to_numpy(float))
    y = d[ycol].to_numpy(float)
    return cboot(d, lambda w: slope(x, y, w), boot, rng)


def implied_lambda(p_over, line):
    """Poisson mean that reproduces P(X>line)=p_over (model-implied mean; the live legacy model's family is not stored)."""
    p_over = np.clip(p_over, 1e-4, 1 - 1e-4)
    out = np.empty(len(p_over))
    for i, (p, l) in enumerate(zip(p_over, line)):
        out[i] = brentq(lambda lam: poisson.sf(np.floor(l), lam) - p, 1e-3, 60)
    return out


def live_frame():
    df, recs = A.load_frame()
    d = A.settled_universe(df)
    U = d.drop_duplicates('contract')
    R = U[U.market == 'player_receptions'].copy()
    nr = pd.read_csv(ROOT / 'research/calibration/A/regrade_all.csv')
    dnp = set(nr.loc[nr.nflverse_no_row == True, 'id'])  # noqa: E712
    R['dnp'] = R['id'].isin(dnp)
    R['plus_cal'] = R.cohort.str.endswith('+cal')
    R['p_over'] = np.where(R.side == 'Over', R.p, 1 - R.p)
    R['lam'] = implied_lambda(R.p_over.to_numpy(), R.line.to_numpy())
    R['dist'] = R.line - R.lam
    R['absd'] = R.dist.abs()
    R['pfav'] = np.maximum(R.p_over, 1 - R.p_over)
    return df, d, U, R


def part_live(R, d, B, rng, df_all_cal=0):
    allr = d[d.market == 'player_receptions']
    print('== LIVE FRAME ==')
    print('settled receptions rows (pre-dedupe): %d ; contract-dedup: %d ; games %d ; players %d ; families %d' % (len(allr), len(R), R.game.nunique(), R.profile_id.nunique(), R.family.nunique()))
    print('obs window', R.obs_t.min(), R.obs_t.max(), 'weeks', R.week.value_counts().sort_index().to_dict())
    print('baseline slope (contract dedup, all):', fmt(slope_ci(R, B, rng)), 'mean p %.3f rate %.3f' % (R.p.mean(), R.y.mean()))
    print('  pre-dedupe slope (point only):', round(slope(logit(allr.p.to_numpy(float)), allr.y.to_numpy(float)), 3))
    print('  sd logit p: live %.3f ; rows by side %s' % (logit(R.p).std(), R.side.value_counts().to_dict()))

    print('\n== (b) duplicates / clustering ==')
    F = R.sort_values('obs_t').drop_duplicates('family')
    print('one row per family (game/player/market; first obs):', len(F), fmt(slope_ci(F, B, rng)))
    Mn = R.sort_values('absd').drop_duplicates('family')
    print('one row per family, closest to model mean (post-hoc diagnostic):', len(Mn), fmt(slope_ci(Mn, B, rng)))
    sl = []
    for _ in range(200):
        s = R.sample(frac=1, random_state=int(rng.integers(1e9))).drop_duplicates('family')
        sl.append(slope(logit(s.p.to_numpy(float)), s.y.to_numpy(float)))
    print('random one-row-per-family, 200 draws: slope mean %.3f sd %.3f 5-95%% [%.3f, %.3f]' % (np.mean(sl), np.std(sl), *np.percentile(sl, [5, 95])))
    g = R.groupby('family').size()
    print('families with >1 row:', int((g > 1).sum()), 'of', len(g), '; mean rows/family %.2f' % g.mean(), '; rows per game median %d max %d' % (R.groupby('game').size().median(), R.groupby('game').size().max()))
    print('player-cluster bootstrap:', fmt(cboot(R, lambda w, x=logit(R.p.to_numpy(float)), y=R.y.to_numpy(float): slope(x, y, w), B, rng, col='profile_id')))

    print('\n== (c) side ==')
    for s, g in R.groupby('side'):
        print(s, len(g), 'mean p %.3f rate %.3f' % (g.p.mean(), g.y.mean()), 'slope', fmt(slope_ci(g, B, rng)))

    print('iid-row bootstrap (ignores clustering) CI for comparison:', fmt(cboot(R, lambda w, x=logit(R.p.to_numpy(float)), y=R.y.to_numpy(float): slope(x, y, w), B, rng, col='id')))
    print('\n== (d) cohort / +cal ==')
    print('+cal receptions predictions overall (any status):', int(df_all_cal), 'settled in dedup frame:', int(R.plus_cal.sum()))
    for c, g in R.groupby('cohort'):
        print('%-26s n=%4d games=%2d mean p %.3f rate %.3f slope %s' % (c, len(g), g.game.nunique(), g.p.mean(), g.y.mean(), fmt(slope_ci(g, 300, rng)) if len(g) > 40 else 'n/a'))
    print('+cal rows settled:', int(R.plus_cal.sum()), '; raw:', int((~R.plus_cal).sum()))
    print('excluding +cal:', fmt(slope_ci(R[~R.plus_cal], B, rng)))
    R['modern'] = R.proj_mean.notna()
    for m, g in R.groupby('modern'):
        print('has projection_mean=%s n=%d slope %s' % (m, len(g), fmt(slope_ci(g, 500, rng))))

    print('\n== (e) did-not-play (nflverse no stat row) ==')
    print('DNP rows:', int(R.dnp.sum()), 'by side', R[R.dnp].side.value_counts().to_dict(), '; actual==0 total', int((R.actual == 0).sum()), '; win rate on DNP rows %.3f' % R[R.dnp].y.mean())
    r1 = R[~R.dnp]
    print('excluding DNP:', len(r1), fmt(slope_ci(r1, B, rng)), 'rate %.3f mean p %.3f' % (r1.y.mean(), r1.p.mean()))
    print('excluding DNP and +cal:', fmt(slope_ci(R[~R.dnp & ~R.plus_cal], B, rng)))
    print('excluding all actual==0 (biased diagnostic):', fmt(slope_ci(R[R.actual > 0], 500, rng)))

    print('\n== (a) line selection ==')
    q = [.05, .25, .5, .75, .95]
    print('live (line - implied Poisson mean) quantiles', np.round(R.dist.quantile(q).values, 2), '; |dist| mean %.2f ; share |dist|<=1: %.3f ; >2: %.3f' % (R.absd.mean(), (R.absd <= 1).mean(), (R.absd > 2).mean()))
    pm = R[R.proj_mean.notna()]
    print('validation where projection_mean exists n=%d: corr(implied lam, projection_mean)=%.3f, mean(lam-proj) %.3f; line-projection_mean quantiles %s' % (len(pm), np.corrcoef(pm.lam, pm.proj_mean)[0, 1], (pm.lam - pm.proj_mean).mean(), np.round((pm.line - pm.proj_mean).quantile(q).values, 2)))
    print('live pfav quantiles', np.round(R.pfav.quantile(q).values, 3), 'share pfav>0.7: %.3f ; >0.85: %.3f' % ((R.pfav > .7).mean(), (R.pfav > .85).mean()))
    R['dband'] = pd.cut(R.absd, [-.01, .5, 1, 1.5, 2, 99], labels=['<=.5', '.5-1', '1-1.5', '1.5-2', '>2']).astype(str)
    for b, g in R.groupby('dband'):
        print('  |dist| %-6s n=%4d mean p %.3f rate %.3f slope %s sd logit %.2f' % (b, len(g), g.p.mean(), g.y.mean(), fmt(slope_ci(g, 300, rng)) if len(g) > 40 else 'n/a', logit(g.p).std()))
    print('live |dist|<=1:', len((R[R.absd <= 1])), fmt(slope_ci(R[R.absd <= 1], B, rng)))
    print('\n== combined adjustments (live) ==')
    c1 = R.sort_values('obs_t')[lambda x: ~x.dnp].drop_duplicates('family')
    print('family-dedup + no DNP:', len(c1), fmt(slope_ci(c1, B, rng)))
    c2 = c1[c1.absd <= 1]
    print('family-dedup + no DNP + |dist|<=1:', len(c2), fmt(slope_ci(c2, B, rng)))
    c3 = R[~R.dnp & (R.absd <= 1)]
    print('no DNP + |dist|<=1 (contract rows):', len(c3), fmt(slope_ci(c3, B, rng)))


def backtest_frame():
    import calibration_models as cm
    f = cm.load_frame()
    rows, long = cm.build_long(f, 'receptions')
    pr = cm.row_params_long(rows, long, 'receptions', 'v2')
    probs = cm.long_probs(rows, long, 'receptions', ('v1', 'v2'))
    L = long.copy()
    L['lam'] = pr['lam']
    L['p_over'] = probs['v2']
    L['p_over_v1'] = probs['v1']
    L['dist'] = L.line - L.lam
    tm = rows.team.fillna('NA').astype(str).to_numpy()[L.row.to_numpy()]
    op = rows.opponent.fillna('NA').astype(str).to_numpy()[L.row.to_numpy()]
    L['game'] = L.season.astype(str) + '-' + L.week.astype(str) + '-' + np.where(tm < op, tm + op, op + tm)
    return L


def bet_side_view(L, pcol='p_over'):
    """Mirror every ladder line into two bets (Over and Under): the bet-side view used by the live tracker."""
    o = L.assign(side='Over', p=L[pcol], yy=L.y, sdist=L.lam - L.line)
    u = L.assign(side='Under', p=1 - L[pcol], yy=1 - L.y, sdist=L.line - L.lam)
    return pd.concat([o, u], ignore_index=True)  # sdist: model mean minus line from the bet side's view (positive = model favors the bet)


def bt_slope(d, boot, rng, pcol='p', ycol='yy', w=None):
    x = logit(d[pcol].to_numpy(float))
    y = d[ycol].to_numpy(float)
    ww = np.ones(len(d)) if w is None else w
    return cboot(d, lambda k: slope(x, y, k * ww), boot, rng)


def part_backtest(R, B, rng):
    print('\n== BACKTEST (calibration_models.build_long, v2 probabilities; 7 half-integer lines around the model-median main line) ==')
    L = backtest_frame()
    print('long rows %d ; seasons %s ; games(clusters) %d' % (len(L), L.season.value_counts().sort_index().to_dict(), L.game.nunique()))
    for name, sel in (('2025 holdout', L.season == 2025), ('2024', L.season == 2024), ('2021-23', L.season <= 2023), ('all', L.season > 0)):
        s = L[sel]
        o = s.assign(p=s.p_over, yy=s.y)
        m = o[o.is_main]
        print('%-12s Over-view ALL lines: n=%d slope %s | MAIN only: n=%d slope %s | sd logit p main %.3f all %.3f' % (name, len(o), fmt(bt_slope(o, 150, rng)), len(m), fmt(bt_slope(m, 200, rng)), logit(m.p).std(), logit(o.p).std()))
    H = L[L.season >= 2024]
    print('--- rest uses 2024-2025 (out of the 2021-23 development window) ---')
    S = bet_side_view(H)
    a, b = A.fit_cal(logit(S.p.to_numpy(float)), S.yy.to_numpy(float), np.ones(len(S)))
    print('bet-side view (both sides mirrored) n=%d slope %s ; point a=%.3f b=%.3f' % (len(S), fmt(bt_slope(S, 150, rng)), a, b))
    S['absoff'] = S.off.abs()
    print('\n-- by |ladder offset| (receptions from the main line) --')
    for k, g in S.groupby('absoff'):
        print('  |off|=%d n=%6d mean p %.3f rate %.3f slope %s sd logit %.2f' % (k, len(g), g.p.mean(), g.yy.mean(), fmt(bt_slope(g, 100, rng)) if len(g) > 200 else 'n/a', logit(g.p).std()))
    print('  |off|<=1 pooled: n=%d slope %s ; |off|>=2: n=%d %s' % ((S.absoff <= 1).sum(), fmt(bt_slope(S[S.absoff <= 1], 150, rng)), (S.absoff >= 2).sum(), fmt(bt_slope(S[S.absoff >= 2], 150, rng))))
    print('\n-- by |line - model mean| (same bands as the live table) --')
    S['absd'] = S.sdist.abs()
    S['dband'] = pd.cut(S.absd, [-.01, .5, 1, 1.5, 2, 99], labels=['<=.5', '.5-1', '1-1.5', '1.5-2', '>2']).astype(str)
    for k, g in S.groupby('dband'):
        print('  |dist| %-6s n=%6d mean p %.3f rate %.3f slope %s sd logit %.2f' % (k, len(g), g.p.mean(), g.yy.mean(), fmt(bt_slope(g, 100, rng)) if len(g) > 200 else 'n/a', logit(g.p).std()))
    print('\n-- by bet side --')
    for k, g in S.groupby('side'):
        print('  %s n=%d mean p %.3f rate %.3f slope %s' % (k, len(g), g.p.mean(), g.yy.mean(), fmt(bt_slope(g, 100, rng))))
    print('\n-- by bet-side probability band (per-band slope is not identified; gap = rate - mean p) --')
    S['pb'] = pd.cut(S.p, [0, .2, .3, .4, .5, .6, .7, .8, .9, 1.0]).astype(str)
    for k, g in S.groupby('pb', sort=False):
        lo, hi = A.wilson(int(g.yy.sum()), len(g))
        print('  p in %-12s n=%6d games=%4d mean p %.3f rate %.3f (wilson %.3f-%.3f) gap %+.3f' % (k, len(g), g.game.nunique(), g.p.mean(), g.yy.mean(), lo, hi, g.yy.mean() - g.p.mean()))
    print('\n-- favored side only (p>0.5): by side x band --')
    Fv = S[S.p > .5].copy()
    Fv['pb2'] = pd.cut(Fv.p, [.5, .6, .7, .8, .9, 1.0]).astype(str)
    for k, g in Fv.groupby(['side', 'pb2']):
        print('  %-6s %-10s n=%6d mean p %.3f rate %.3f gap %+.3f' % (k[0], k[1], len(g), g.p.mean(), g.yy.mean(), g.yy.mean() - g.p.mean()))
    print('\n-- does the model beat a line-only base rate (fit on 2021-23, scored 2024-25, Over view)? Brier(base) - Brier(model); positive = model better --')
    import calibration_models as cm
    dev = L[L.season <= 2023]
    tab, overall = cm.base_rate_table(dev.line.to_numpy(), dev.y.to_numpy())
    Hh = H.copy()
    Hh['pb_'] = cm.base_rate_apply(Hh.line.to_numpy(), tab, overall)
    Hh['gain'] = (Hh.pb_ - Hh.y) ** 2 - (Hh.p_over - Hh.y) ** 2
    Hh['aoff'] = Hh.off.abs()
    cl_all, _ = pd.factorize(Hh.game)
    for k, g in list(Hh.groupby('aoff')) + [('all', Hh)]:
        cl, ncl = pd.factorize(g.game); kk = len(ncl)
        bs = np.array([np.average(g.gain, weights=rng.multinomial(kk, np.full(kk, 1 / kk))[cl] + 1e-12) for _ in range(150)])
        print('  |off|=%s n=%d model Brier %.4f base-rate Brier %.4f gain %+.4f [%+.4f, %+.4f]' % (k, len(g), ((g.p_over - g.y) ** 2).mean(), ((g.pb_ - g.y) ** 2).mean(), g.gain.mean(), *np.percentile(bs, [2.5, 97.5])))
    return L, S


def part_reweight(R, S, B, rng):
    """Re-score the backtest on the live distribution of (side, model-mean-minus-line), then ask how often live-sized samples show slope <= live."""
    print('\n== BACKTEST RE-WEIGHTED TO THE LIVE LINE-DISTANCE DISTRIBUTION ==')
    R = R.copy()
    R['sdist'] = np.where(R.side == 'Over', R.lam - R.line, R.line - R.lam)
    qq = [.05, .25, .5, .75, .95]
    print('live bet-view sdist quantiles', np.round(R.sdist.quantile(qq).values, 2), 'mean %.2f' % R.sdist.mean())
    print('backtest bet-view sdist quantiles (all lines)', np.round(S.sdist.quantile(qq).values, 2), '; main-line only', np.round(S[S.is_main].sdist.quantile(qq).values, 2))
    edges = np.array([-9, -2, -1.5, -1, -.5, -.25, 0, .25, .5, 1, 1.5, 2, 9])
    R['cb'] = np.digitize(R.sdist, edges)
    S = S.copy()
    S['cb'] = np.digitize(S.sdist, edges)
    key = ['side', 'cb']
    wt = (R.groupby(key).size() / S.groupby(key).size()).rename('w')
    S = S.join(wt, on=key)
    S['w'] = S['w'].fillna(0.0)
    S1 = S[S.w > 0]
    x = logit(S1.p.to_numpy(float)); y = S1.yy.to_numpy(float); w = S1.w.to_numpy(float)
    a, b = A.fit_cal(x, y, w)
    mu = np.average(x, weights=w)
    print('backtest reweighted to live (side x sdist bin): eff n %.0f ; weighted slope %.3f intercept %.3f ; weighted sd logit p %.3f (live %.3f)' % (w.sum() ** 2 / (w ** 2).sum(), b, a, np.sqrt(np.average((x - mu) ** 2, weights=w)), logit(R.p).std()))
    print('   cluster-boot (games) slope of reweighted backtest: %s' % fmt(bt_slope(S1, 150, rng, w=w)))
    Mn = S[S.is_main]
    print('   unweighted main-line-only bet-view slope: %.3f ; sd logit %.3f' % (slope(logit(Mn.p.to_numpy(float)), Mn.yy.to_numpy(float)), logit(Mn.p).std()))
    print('\n-- simulation: if TRUE calibration were as stated, how often does a live-shaped sample (966 rows, same lines, same dependence within a player-game) show slope <= 0.202? --')
    R = R.sort_values(['family', 'line'])
    fam, fidx = np.unique(R.family.to_numpy(), return_inverse=True)
    xo = logit(R.p_over.to_numpy(float))
    isover = R.side.to_numpy() == 'Over'
    xp = logit(R.p.to_numpy(float))
    for label, (aa, bb) in (('reweighted-backtest (a,b)', (a, b)), ('backtest slope, intercept 0', (0.0, b)), ('perfect (0,1)', (0.0, 1.0))):
        # calibrated Over-hit probability: recalibrate in the Over view (the model's own side-neutral probability)
        qo = 1 / (1 + np.exp(-(aa + bb * xo)))
        out = []
        for _ in range(2000):
            u = rng.random(len(fam))[fidx]
            hit = (u < qo).astype(float)
            ysim = np.where(isover, hit, 1 - hit)
            out.append(slope(xp, ysim))
        out = np.array(out)
        print('  %-28s slope mean %.3f sd %.3f 2.5-97.5%% [%.3f, %.3f]  P(slope<=0.202)=%.4f' % (label, out.mean(), out.std(), *np.percentile(out, [2.5, 97.5]), (out <= 0.2025).mean()))


def fit_multi(X, y, w=None, offset=None, iters=60, ridge=1e-8):
    """Weighted logistic regression with design X (n x k, include a constant column yourself) and optional offset. Returns coefficient vector."""
    n, k = X.shape
    w = np.ones(n) if w is None else w
    off = np.zeros(n) if offset is None else offset
    beta = np.zeros(k)
    for _ in range(iters):
        mu = 1 / (1 + np.exp(-np.clip(X @ beta + off, -30, 30)))
        g = X.T @ (w * (y - mu))
        H = (X * (w * mu * (1 - mu))[:, None]).T @ X + ridge * np.eye(k)
        step = np.clip(np.linalg.solve(H, g), -2, 2)
        beta = beta + step
        if np.abs(step).max() < 1e-9:
            break
    return beta


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def part_price(R, B, rng):
    print('\n== (g) THE BOOK PRICE ==')
    R = R.copy()
    R['pr_raw'] = R.impl_raw.clip(1e-4, 1 - 1e-4)
    Rm = R[R.mref.notna()].copy()
    Rm['mref_c'] = Rm.mref.clip(1e-3, 1 - 1e-3)
    print('rows with same-book de-vigged reference: %d, games %d, players %d, cohorts %s' % (len(Rm), Rm.game.nunique(), Rm.profile_id.nunique(), Rm.cohort.value_counts().to_dict()))
    print('  on these rows: mean p %.3f mean mref %.3f mean raw 1/odds %.3f hit rate %.3f ; corr(logit p, logit mref)=%.3f ; sd logit p %.3f sd logit mref %.3f' % (Rm.p.mean(), Rm.mref.mean(), Rm.impl_raw.mean(), Rm.y.mean(), np.corrcoef(logit(Rm.p), logit(Rm.mref_c))[0, 1], logit(Rm.p).std(), logit(Rm.mref_c).std()))
    xp, xm, y = logit(Rm.p.to_numpy(float)), logit(Rm.mref_c.to_numpy(float)), Rm.y.to_numpy(float)
    print('  slope of outcome on logit(model p):      %s' % fmt(cboot(Rm, lambda w: slope(xp, y, w), B, rng)))
    print('  slope of outcome on logit(de-vigged ref): %s' % fmt(cboot(Rm, lambda w: slope(xm, y, w), B, rng)))
    X2 = np.column_stack([np.ones(len(Rm)), xm, xp])
    b2 = lambda w, j: fit_multi(X2, y, w)[j]
    print('  joint y ~ a + b_ref*logit(ref) + b_model*logit(p): b_ref %s ; b_model %s' % (fmt(cboot(Rm, lambda w: b2(w, 1), B, rng)), fmt(cboot(Rm, lambda w: b2(w, 2), B, rng))))
    for nm, pp in (('model p', Rm.p), ('de-vigged ref', Rm.mref_c), ('raw 1/odds (vig in)', Rm.pr_raw), ('50/50', pd.Series(.5, index=Rm.index))):
        print('  %-22s brier %.4f logloss %.4f' % (nm, ((pp - Rm.y) ** 2).mean(), ll(pp.to_numpy(float), y).mean()))
    dll = ll(Rm.p.to_numpy(float), y) - ll(Rm.mref_c.to_numpy(float), y)
    cl, ncl = pd.factorize(Rm.game)
    k = len(ncl)
    bs = np.array([np.average(dll, weights=rng.multinomial(k, np.full(k, 1 / k))[cl] + 1e-12) for _ in range(B)])
    print('  logloss(model) - logloss(ref): %.4f [%.4f, %.4f]  (positive = ref better)' % (dll.mean(), *np.percentile(bs, [2.5, 97.5])))

    print('\n-- same, all 966 rows, price proxy = raw 1/odds (includes vig; shifts the intercept only) --')
    xp, xr, y = logit(R.p.to_numpy(float)), logit(R.pr_raw.to_numpy(float)), R.y.to_numpy(float)
    print('  slope on logit(model p): %s ; slope on logit(1/odds): %s ; corr %.3f' % (fmt(cboot(R, lambda w: slope(xp, y, w), B, rng)), fmt(cboot(R, lambda w: slope(xr, y, w), B, rng)), np.corrcoef(xp, xr)[0, 1]))
    X3 = np.column_stack([np.ones(len(R)), xr, xp])
    print('  joint: b_price %s ; b_model %s' % (fmt(cboot(R, lambda w: fit_multi(X3, y, w)[1], B, rng)), fmt(cboot(R, lambda w: fit_multi(X3, y, w)[2], B, rng))))
    dis = xp - xr
    print('  disagreement dis=logit p - logit(1/odds): mean %.3f sd %.3f' % (dis.mean(), dis.std()))
    R['disq'] = pd.qcut(pd.Series(dis, index=R.index), 5, labels=False)
    for q, g in R.groupby('disq'):
        print('   dis quintile %d: n=%d mean dis %+.2f mean p %.3f mean raw price %.3f hit rate %.3f' % (q, len(g), (logit(g.p) - logit(g.pr_raw)).mean(), g.p.mean(), g.pr_raw.mean(), g.y.mean()))
    # weight on the model relative to price: logit q = c + logit(price) + w*(logit p - logit price)
    for nm, D, base, yy_, dd in (('raw 1/odds, all rows', R, xr, y, dis), ('de-vigged ref, ref rows', Rm, logit(Rm.mref_c.to_numpy(float)), Rm.y.to_numpy(float), logit(Rm.p.to_numpy(float)) - logit(Rm.mref_c.to_numpy(float)))):
        Xo = np.column_stack([np.ones(len(D)), dd])
        f = lambda w_: fit_multi(Xo, yy_, w_, offset=base)[1]
        print('  weight w on model-minus-price disagreement (%s): %s' % (nm, fmt(cboot(D, f, B, rng))))
    return R, Rm


def cv_correction(R, Rm, rng, B):
    """Out-of-sample test of shrinking toward the price. Forward-chaining by observation week and leave-one-game-out."""
    print('\n== OUT-OF-SAMPLE SHRINKAGE TEST (live) ==')
    out = {}
    for nm, D, price in (('raw 1/odds, all rows', R, 'pr_raw'), ('de-vigged ref rows', Rm, 'mref_c')):
        D = D.copy()
        D['xp'] = logit(D.p.to_numpy(float))
        D['xq'] = logit(D[price].to_numpy(float))
        D['dis'] = D.xp - D.xq
        y = D.y.to_numpy(float)

        def fitw(tr):
            X = np.column_stack([np.ones(len(tr)), tr.dis.to_numpy()])
            return fit_multi(X, tr.y.to_numpy(float), offset=tr.xq.to_numpy())

        def fitw_fixed_c(tr, c):  # intercept-free: pure shrink toward the price
            X = tr.dis.to_numpy()[:, None]
            return fit_multi(X, tr.y.to_numpy(float), offset=tr.xq.to_numpy() + c)[0]
        # leave-one-game-out
        pred_c = np.full(len(D), np.nan); pred_w = np.full(len(D), np.nan); ws = []
        for g in D.game.unique():
            te = (D.game == g).to_numpy()
            tr = D[~te]
            c, w = fitw(tr)
            ws.append(w)
            pred_c[te] = 1 / (1 + np.exp(-(c + D.xq[te] + w * D.dis[te])))
            w0 = fitw_fixed_c(tr, 0.0)
            pred_w[te] = 1 / (1 + np.exp(-(D.xq[te] + w0 * D.dis[te])))
        pb = D[price].to_numpy(float)
        print('-- %s : n=%d games=%d' % (nm, len(D), D.game.nunique()))
        print('   leave-one-game-out fitted w: mean %.3f range [%.3f, %.3f]' % (np.mean(ws), min(ws), max(ws)))
        for lab, pp in (('model p (raw)', D.p.to_numpy(float)), ('price', pb), ('shrunk w/ intercept (LOGO)', pred_c), ('shrunk, no intercept (LOGO)', pred_w), ('50/50', np.full(len(D), .5))):
            print('   %-30s brier %.4f logloss %.4f' % (lab, ((pp - y) ** 2).mean(), ll(pp, y).mean()))
        # paired cluster bootstrap of logloss difference model - shrunk
        d_ = ll(D.p.to_numpy(float), y) - ll(pred_w, y)
        cl, ncl = pd.factorize(D.game); k = len(ncl)
        bs = np.array([np.average(d_, weights=rng.multinomial(k, np.full(k, 1 / k))[cl] + 1e-12) for _ in range(B)])
        print('   logloss(model) - logloss(shrunk no-intercept LOGO): %.4f [%.4f, %.4f]' % (d_.mean(), *np.percentile(bs, [2.5, 97.5])))
        d2 = ll(pb, y) - ll(pred_w, y)
        bs2 = np.array([np.average(d2, weights=rng.multinomial(k, np.full(k, 1 / k))[cl] + 1e-12) for _ in range(B)])
        print('   logloss(price) - logloss(shrunk):                    %.4f [%.4f, %.4f]' % (d2.mean(), *np.percentile(bs2, [2.5, 97.5])))
        # forward chaining by week
        wk = sorted(D.week.unique())
        pf = np.full(len(D), np.nan)
        for i in range(1, len(wk)):
            tr = D[D.week.isin(wk[:i])]; te = (D.week == wk[i]).to_numpy()
            if len(tr) < 80:
                continue
            w0 = fitw_fixed_c(tr, 0.0)
            pf[te] = 1 / (1 + np.exp(-(D.xq[te] + w0 * D.dis[te])))
        m = np.isfinite(pf)
        print('   forward-chaining by obs week (test weeks %s, n=%d): logloss model %.4f price %.4f shrunk %.4f' % (wk[1:], m.sum(), ll(D.p.to_numpy(float)[m], y[m]).mean(), ll(pb[m], y[m]).mean(), ll(pf[m], y[m]).mean()))
        print('   fixed-weight sweep, q = expit(logit(price) + w*(logit p - logit price)); logloss and difference vs w=0 (positive = worse than w=0):')
        base0 = ll(pb, y)
        for wfix in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0):
            qq_ = 1 / (1 + np.exp(-(D.xq.to_numpy() + wfix * D.dis.to_numpy())))
            dd_ = ll(qq_, y) - base0
            bsw = np.array([np.average(dd_, weights=rng.multinomial(k, np.full(k, 1 / k))[cl] + 1e-12) for _ in range(B)])
            print('     w=%.2f logloss %.4f brier %.4f diff %+.4f [%+.4f, %+.4f]' % (wfix, ll(qq_, y).mean(), ((qq_ - y) ** 2).mean(), dd_.mean(), *np.percentile(bsw, [2.5, 97.5])))
        out[nm] = (D, pred_w)
    # EV calibration: realized return vs estimated EV
    print('\n-- estimated EV vs realized (unit stake at the recorded odds; wins pay odds-1) --')
    D, pw = out['raw 1/odds, all rows']
    D = D.assign(pw=pw)
    D['ev_model'] = D.p * D.odds - 1
    D['ev_shr'] = D.pw * D.odds - 1
    D['ret'] = np.where(D.y == 1, D.odds - 1, -1.0)
    print('   all rows: mean est EV (model) %+.4f ; mean est EV (shrunk LOGO) %+.4f ; mean realized %+.4f' % (D.ev_model.mean(), D.ev_shr.mean(), D.ret.mean()))
    cl, ncl = pd.factorize(D.game); k = len(ncl)
    bs = np.array([np.average(D.ret, weights=rng.multinomial(k, np.full(k, 1 / k))[cl] + 1e-12) for _ in range(B)])
    print('   realized mean return cluster CI [%.4f, %.4f]' % tuple(np.percentile(bs, [2.5, 97.5])))
    D['evb'] = pd.cut(D.ev_model, [-1, 0, .05, .10, .20, 5]).astype(str)
    for b, g in D.groupby('evb'):
        print('   est EV %-12s n=%4d mean est EV %+.3f shrunk EV %+.3f realized %+.3f' % (b, len(g), g.ev_model.mean(), g.ev_shr.mean(), g.ret.mean()))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--boot', type=int, default=2000)
    a = ap.parse_args()
    rng = np.random.default_rng(SEED)
    df, d, U, R = live_frame()
    part_live(R, d, a.boot, rng, int(((df.market == 'player_receptions') & df.cohort.str.endswith('+cal')).sum()))
    L, S = part_backtest(R, a.boot, rng)
    part_reweight(R, S, a.boot, rng)
    R2, Rm = part_price(R, a.boot, rng)
    cv_correction(R2, Rm, rng, a.boot)
