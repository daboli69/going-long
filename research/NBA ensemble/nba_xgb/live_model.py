"""Conditional live pricing model: distribution of the remaining game given score, clock, pregame priors and on-court lineups.

Regulation margin and total are modelled jointly:
    final_reg_margin = m + D,  D ~ N(a1*mu*(tau/2880) + aL*L*(tau/2880), s_m(tau)^2)
    final_reg_total  = S + R,  R ~ N(k . features, s_t(tau)^2),  corr(D, R) = rho
Overtime is a mixture: a regulation tie goes to a five-minute period with its own margin and total distribution.
Moneyline, spread and total probabilities all come from the same joint draw or its closed form, so they are mutually consistent.
Parameters are fitted by maximum likelihood on training seasons only. mu and T_pre are either the independent pregame priors (Model A) or
closing-line-implied values (Model B).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from . import data, live_state as LS
from .avail_study import OUT

REG = 2880.0
GRID = 120


# ---------------------------------------------------------------------------------- snapshot table
def _ratings_lookup():
    r = pd.read_parquet(OUT / 'rapm_ratings.parquet')
    by = {d: dict(zip(g.athlete_id.astype(int), g.net)) for d, g in r.groupby('refit_day')}
    return by, np.array(sorted(by))


def build_snapshots(seasons=range(2022, 2027), log=print) -> pd.DataFrame:
    games, _ = data.load(verify=False)
    lab = games.set_index('game_id')
    priors = pd.read_parquet(OUT / 'pregame_priors.parquet').set_index('game_id')
    stints = pd.read_parquet(OUT / 'stints.parquet')
    sgrp = {gid: x.sort_values('t0') for gid, x in stints.groupby('game_id')}
    by, days = _ratings_lookup()
    rows = []
    for season in seasons:
        ev_all = LS.load_events(season)
        for gid, ev in ev_all.items():
            if gid not in lab.index or gid not in priors.index or ev['bad_clock']:
                continue
            info = lab.loc[gid]
            if not (info.completed and info.verified):
                continue
            hreg, areg = LS.regulation_scores(ev)
            fh, fa = float(info.home_score), float(info.away_score)
            ot = fh + fa > hreg + areg + 0.5 or (hreg == areg)
            day = int(np.datetime64(info.game_date, 'D').astype('int64'))
            k = np.searchsorted(days, day, side='right') - 1
            rating = by[days[k]] if k >= 0 else {}
            st = sgrp.get(gid)
            for t in range(GRID, int(REG), GRID):
                el, h, a = LS.state_at_elapsed(ev, float(t))
                L = np.nan
                if st is not None and rating:
                    s = st[(st.t0 <= t) & (st.t1 > t)]
                    if len(s):
                        s = s.iloc[0]
                        L = sum(rating.get(int(p), 0.0) for p in s.home_lineup) - sum(rating.get(int(p), 0.0) for p in s.away_lineup)
                pr = priors.loc[gid]
                rows.append((gid, season, info.game_date, t, REG - t, h - a, h + a, L, pr.mu_base, pr.mu_avail, pr.T_pre,
                             hreg - areg, hreg + areg, fh - fa, fh + fa, float(hreg == areg)))
        log('snapshots built for', season, len(rows))
    cols = ['game_id', 'season', 'game_date', 't', 'tau', 'm', 'S', 'L', 'mu_base', 'mu_avail', 'T_pre',
            'reg_margin', 'reg_total', 'final_margin', 'final_total', 'tied_reg']
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------------- model
@dataclass
class Params:
    a1: float = 1.0
    aL: float = 0.0
    am: float = 0.0            # lead-dependent drift: leaders ease off, trailing teams close gaps
    av: float = 0.0            # variance inflation with the size of the lead (|m|/10)
    sm: tuple = (1.0, 1.0)         # log variance parameters for margin sigma^2 = exp(p0) + exp(p1) * x, x = tau/2880
    k: tuple = (0.0, 0.0, 0.0, 0.0, 0.0)
    st: tuple = (1.0, 1.0)
    rho: float = 0.0
    ot_margin_sd: float = 5.5
    ot_total_mean: float = 11.0
    ot_total_sd: float = 4.0
    p_home_ot: float = 0.5
    nu_m: float = 1e6          # Student-t degrees of freedom (large = Gaussian)
    nu_t: float = 1e6
    use_lineup: bool = False
    mu_col: str = 'mu_base'
    fitted_on: str = ''


def margin_sd(p: Params, x):
    return np.sqrt(np.exp(p.sm[0]) + np.exp(p.sm[1]) * x)


def total_sd(p: Params, x):
    return np.sqrt(np.exp(p.st[0]) + np.exp(p.st[1]) * x)


def total_features(df, mu_col=None):
    x = df.tau.values / REG
    ps = df.S.values - df.T_pre.values * (df.t.values / REG)
    late = (df.tau.values < 300).astype(float) * (df.tau.values / 300.0)
    return np.column_stack([x, x * df.T_pre.values, x * ps, late, np.ones(len(df)) * 0.0])


def fit(df: pd.DataFrame, mu_col='mu_base', use_lineup=False, T_col='T_pre') -> Params:
    d = df.dropna(subset=[mu_col, T_col]).copy()
    if T_col != 'T_pre':
        d['T_pre'] = d[T_col]
    if use_lineup:
        d = d.dropna(subset=['L'])
    x = d.tau.values / REG
    D = d.reg_margin.values - d.m.values
    mu = d[mu_col].values
    L = d.L.values if use_lineup else np.zeros(len(d))

    def nll(th):
        a1, aL, p0, p1, q, am, av = th
        mean = a1 * mu * x + am * mm_ * x + (aL * L * x if use_lineup else 0.0)
        sd = np.sqrt((np.exp(p0) + np.exp(p1) * x) * (1.0 + np.exp(av) * (np.abs(mm_) / 10.0) ** 2 * x))
        return -stats.t.logpdf(D, 2.0 + np.exp(q), mean, sd).mean()
    mm_ = d.m.values
    th0 = np.array([1.0, 0.0, np.log(4.0), np.log(150.0), np.log(10.0), 0.0, np.log(0.05)])
    r = minimize(nll, th0, method='L-BFGS-B')
    a1, aL, p0, p1, q, am, av = r.x
    nu_m = 2.0 + float(np.exp(q))
    # remaining regulation total by OLS then variance by MLE
    Xt = total_features(d)[:, :4]
    R = d.reg_total.values - d.S.values
    beta, *_ = np.linalg.lstsq(Xt, R, rcond=None)
    res = R - Xt @ beta

    def nll_t(th):
        sd = np.sqrt(np.exp(th[0]) + np.exp(th[1]) * x)
        return -stats.t.logpdf(res, 2.0 + np.exp(th[2]), 0, sd).mean()
    rt = minimize(nll_t, np.array([np.log(4.0), np.log(150.0), np.log(10.0)]), method='L-BFGS-B')
    nu_t = 2.0 + float(np.exp(rt.x[2]))
    zs = (D - (a1 * mu * x + am * mm_ * x + (aL * L * x if use_lineup else 0))) / np.sqrt((np.exp(p0) + np.exp(p1) * x) * (1.0 + np.exp(av) * (np.abs(mm_) / 10.0) ** 2 * x))
    zt = res / np.sqrt(np.exp(rt.x[0]) + np.exp(rt.x[1]) * x)
    mask = x > 0.15
    rho = float(np.corrcoef(zs[mask], zt[mask])[0, 1])
    ot = d[d.tied_reg == 1].drop_duplicates('game_id')
    otm = float(ot.final_margin.std()) if len(ot) > 30 else 5.5
    ott = (ot.final_total - ot.reg_total)
    return Params(a1=float(a1), aL=float(aL), am=float(am), av=float(np.exp(av)), sm=(float(p0), float(p1)), k=tuple(float(b) for b in beta) + (0.0,), st=(float(rt.x[0]), float(rt.x[1])),
                  rho=rho, nu_m=nu_m, nu_t=nu_t, ot_margin_sd=otm, ot_total_mean=float(ott.mean()) if len(ot) > 30 else 11.0,
                  ot_total_sd=float(ott.std()) if len(ot) > 30 else 4.0, p_home_ot=float((ot.final_margin > 0).mean()) if len(ot) > 30 else 0.5,
                  use_lineup=use_lineup, mu_col=mu_col, fitted_on=f'{int(d.season.min())}-{int(d.season.max())}')


def moments(p: Params, df: pd.DataFrame):
    x = df.tau.values / REG
    mu = df[p.mu_col].values
    L = df.L.fillna(0.0).values if p.use_lineup else np.zeros(len(df))
    mean_m = df.m.values + p.a1 * mu * x + p.am * df.m.values * x + p.aL * L * x
    sd_m = margin_sd(p, x) * np.sqrt(1.0 + p.av * (np.abs(df.m.values) / 10.0) ** 2 * x)
    mean_t = df.S.values + total_features(df)[:, :4] @ np.array(p.k[:4])
    sd_t = total_sd(p, x)
    return mean_m, sd_m, mean_t, sd_t


def p_home_win(p: Params, df: pd.DataFrame) -> np.ndarray:
    """Closed form with integer-score continuity correction; a regulation tie is decided in overtime."""
    mm, sm, _, _ = moments(p, df)
    cdf = lambda z: stats.t.cdf(z, p.nu_m)
    win = 1 - cdf((0.5 - mm) / sm)
    tie = cdf((0.5 - mm) / sm) - cdf((-0.5 - mm) / sm)
    return win + tie * p.p_home_ot


def simulate(p: Params, row: pd.Series, n=200_000, seed=0):
    """Joint draw of final (home margin, total) including overtime, for spread and total probabilities."""
    rng = np.random.default_rng(seed)
    d1 = pd.DataFrame([row])
    mm, sm, mt, st_ = (v[0] for v in moments(p, d1))
    g1 = rng.standard_normal(n)
    g2 = p.rho * g1 + np.sqrt(1 - p.rho ** 2) * rng.standard_normal(n)
    w1 = np.sqrt(p.nu_m / rng.chisquare(p.nu_m, n))
    w2 = np.sqrt(p.nu_t / rng.chisquare(p.nu_t, n))
    margin = np.rint(mm + sm * g1 * w1)
    total = np.rint(mt + st_ * g2 * w2)
    tie = margin == 0
    if tie.any():
        k = int(tie.sum())
        margin[tie] = np.rint(rng.normal(0, p.ot_margin_sd, k))
        total[tie] += np.rint(rng.normal(p.ot_total_mean, p.ot_total_sd, k))
        z = margin == 0
        margin[z] = np.where(rng.random(int(z.sum())) < p.p_home_ot, 1, -1)
    return margin, total


# ---------------------------------------------------------------------------------- scoring
def logloss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def crps_normal(y, mu, sd):
    z = (y - mu) / sd
    return sd * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))
