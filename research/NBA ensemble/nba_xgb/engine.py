"""Point-in-time team-strength engine.

Every feature for a game on calendar date D (America/New_York) is a function of the
completed, verified games with date <= D - lag_days only. State is recorded as a snapshot
after each result date; a game reads the snapshot index `p` = number of result dates
<= D - lag_days. That structure makes future leakage impossible by construction and is
checked by perturbation tests (tests/test_nba_xgb_leakage.py).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import bisect
import numpy as np
import pandas as pd
from scipy import sparse

BUBBLE_START = '2020-07-30'   # NBA restart in Orlando: every game after this date is effectively neutral-site
REST_CAP = 7
POSS_FT = 0.44
FF = ['efg', 'tov', 'orb', 'ftr']   # four-factor net measures (own minus opponent, oriented so higher = better)

DEFAULT = dict(
    lag_days=1,
    elo=dict(k=20.0, hca=65.0, carry=0.75, mov=True),
    adj=dict(lam=30.0, kappa=0.5),
    recent=dict(half_life=20.0, n0=8.0, rho=0.5),
)


def day_number(date_strings) -> np.ndarray:
    return (pd.to_datetime(pd.Series(date_strings)).values.astype('datetime64[D]').astype('int64'))


@dataclass
class Prep:
    games: pd.DataFrame            # all canonical games sorted by tipoff
    teams: list
    g_season: np.ndarray
    g_day: np.ndarray
    g_home: np.ndarray
    g_away: np.ndarray
    g_neutral: np.ndarray
    upd: pd.DataFrame              # verified completed games with box-derived measures, sorted by day
    ud: np.ndarray                 # unique result dates
    slices: list = field(default_factory=list)   # (start, stop) of upd rows for each result date


def possessions(box: pd.DataFrame) -> pd.Series:
    return box.fga + POSS_FT * box.fta - box.oreb + box.tov


def prepare(games: pd.DataFrame, boxes: pd.DataFrame) -> Prep:
    g = games.sort_values(['tipoff_utc', 'game_id']).reset_index(drop=True).copy()
    teams = sorted(set(g.home_id) | set(g.away_id))
    tix = {t: i for i, t in enumerate(teams)}
    g['day'] = day_number(g.game_date)
    g['neutral_eff'] = g.neutral | ((g.season == 2020) & (g.game_date >= BUBBLE_START))
    g['hi'] = g.home_id.map(tix)
    g['ai'] = g.away_id.map(tix)
    u = g[g.completed & g.verified].copy()
    b = boxes.copy()
    b['poss_t'] = possessions(b)
    h = b.add_prefix('h_').rename(columns={'h_game_id': 'game_id', 'h_team_id': 'home_id'})
    a = b.add_prefix('a_').rename(columns={'a_game_id': 'game_id', 'a_team_id': 'away_id'})
    u = u.merge(h, on=['game_id', 'home_id']).merge(a, on=['game_id', 'away_id'])
    u['poss'] = (u.h_poss_t + u.a_poss_t) / 2.0           # one possession count per game, both teams
    u['h_ortg'] = 100.0 * u.h_points / u.poss
    u['a_ortg'] = 100.0 * u.a_points / u.poss
    for side, o in (('h', 'a'), ('a', 'h')):
        u[f'{side}_efg'] = (u[f'{side}_fgm'] + 0.5 * u[f'{side}_fg3m']) / u[f'{side}_fga']
        u[f'{side}_tovr'] = u[f'{side}_tov'] / u[f'{side}_poss_t']
        u[f'{side}_orbr'] = u[f'{side}_oreb'] / (u[f'{side}_oreb'] + u[f'{o}_dreb'])
        u[f'{side}_ftr'] = u[f'{side}_fta'] / u[f'{side}_fga']
    u = u.sort_values(['day', 'tipoff_utc', 'game_id']).reset_index(drop=True)
    ud = np.unique(u.day.values)
    bounds = np.searchsorted(u.day.values, ud, side='left')
    slices = [(int(s), int(e)) for s, e in zip(bounds, list(bounds[1:]) + [len(u)])]
    return Prep(g, teams, g.season.values, g.day.values, g.hi.values, g.ai.values,
                g.neutral_eff.values, u, ud, slices)


def cutoff_index(prep: Prep, lag_days: int) -> np.ndarray:
    """p = number of result dates available when predicting each game (date <= D - lag)."""
    return np.searchsorted(prep.ud, prep.g_day - lag_days, side='right')


# --------------------------------------------------------------------------- Elo
def elo_snapshots(prep: Prep, k=20.0, hca=65.0, carry=0.75, mov=True):
    n = len(prep.teams)
    r = np.full(n, 1500.0)
    stamp = np.zeros(n, dtype=int)
    snaps_r, snaps_s = [r.copy()], [stamp.copy()]
    u = prep.upd
    season = u.season.values
    hi, ai = u.hi.values, u.ai.values
    neutral = u.neutral_eff.values
    hs, as_ = u.home_score.values, u.away_score.values
    for s, e in prep.slices:
        for i in range(s, e):
            for t in (hi[i], ai[i]):
                if stamp[t] < season[i]:
                    if stamp[t] > 0:
                        r[t] = 1500.0 + carry * (r[t] - 1500.0)
                    stamp[t] = season[i]
            home_bonus = 0.0 if neutral[i] else hca
            d = r[hi[i]] + home_bonus - r[ai[i]]
            exp_h = 1.0 / (1.0 + 10.0 ** (-d / 400.0))
            home_won = hs[i] > as_[i]
            m = 1.0
            if mov:
                win_d = d if home_won else -d
                m = (abs(hs[i] - as_[i]) + 3.0) ** 0.8 / (7.5 + 0.006 * win_d)
            delta = k * m * ((1.0 if home_won else 0.0) - exp_h)
            r[hi[i]] += delta
            r[ai[i]] -= delta
        snaps_r.append(r.copy())
        snaps_s.append(stamp.copy())
    return np.array(snaps_r), np.array(snaps_s)


def elo_features(prep: Prep, p: np.ndarray, snaps, carry: float):
    R, S = snaps
    rh = R[p, prep.g_home]
    ra = R[p, prep.g_away]
    # lazy season-transition regression for teams whose last update was in an earlier season
    sh, sa = S[p, prep.g_home], S[p, prep.g_away]
    rh = np.where((sh > 0) & (sh < prep.g_season), 1500.0 + carry * (rh - 1500.0), rh)
    ra = np.where((sa > 0) & (sa < prep.g_season), 1500.0 + carry * (ra - 1500.0), ra)
    return rh - ra


# ------------------------------------------------------------- opponent-adjusted ridge
class AdjustedStrength:
    """Regularised opponent-adjusted offence/defence (points per 100 possessions).

    y(team scoring on opponent) = mu_season + b*home + a_team + d_opp, ridge penalty lam on a, d.
    Current-season games weigh 1, previous-season games weigh kappa, older games are dropped.
    """

    def __init__(self, prep: Prep, lam: float, kappa: float):
        u = prep.upd
        n = len(prep.teams)
        self.n, self.lam, self.kappa = n, lam, kappa
        day = np.repeat(u.day.values, 2)
        order_idx = np.arange(len(u))
        rows = pd.DataFrame({
            'day': np.concatenate([u.day.values, u.day.values]),
            'season': np.concatenate([u.season.values, u.season.values]),
            'team': np.concatenate([u.hi.values, u.ai.values]),
            'opp': np.concatenate([u.ai.values, u.hi.values]),
            'hc': np.concatenate([np.where(u.neutral_eff.values, 0.0, 1.0), np.where(u.neutral_eff.values, 0.0, -1.0)]),
            'y': np.concatenate([u.h_ortg.values, u.a_ortg.values]),
            'ord': np.concatenate([order_idx, order_idx])}).sort_values(['day', 'ord'], kind='stable')
        self.day = rows.day.values
        self.season = rows.season.values
        self.team = rows.team.values.astype(int)
        self.opp = rows.opp.values.astype(int)
        self.hc = rows.hc.values
        self.y = rows.y.values
        self.cache = {}

    def solve(self, cutoff_day: int, season: int):
        key = (cutoff_day, season)
        if key in self.cache:
            return self.cache[key]
        end = int(np.searchsorted(self.day, cutoff_day, side='right'))
        start = int(np.searchsorted(self.season, season - 1, side='left'))
        if end <= start:
            out = (np.zeros(self.n), np.zeros(self.n))
            self.cache[key] = out
            return out
        sl = slice(start, end)
        seas, team, opp, hc, y = self.season[sl], self.team[sl], self.opp[sl], self.hc[sl], self.y[sl]
        w = np.where(seas == season, 1.0, self.kappa)
        m = len(y)
        ncol = 3 + 2 * self.n
        ri = np.arange(m)
        cols = np.stack([np.where(seas == season, 0, 1), np.full(m, 2), 3 + team, 3 + self.n + opp], 1)
        vals = np.stack([np.ones(m), hc, np.ones(m), np.ones(m)], 1)
        X = sparse.csr_matrix((vals.ravel(), (np.repeat(ri, 4), cols.ravel())), shape=(m, ncol))
        W = sparse.diags(w)
        A = (X.T @ W @ X).toarray()
        pen = np.zeros(ncol)
        pen[3:] = self.lam
        pen[:3] = 1e-6
        A[np.diag_indices(ncol)] += pen
        beta = np.linalg.solve(A, X.T @ (w * y))
        out = (beta[3:3 + self.n], beta[3 + self.n:])
        self.cache[key] = out
        return out


def adjusted_features(prep: Prep, p: np.ndarray, adj: AdjustedStrength, rows=None):
    off = np.zeros(len(p))
    de = np.zeros(len(p))
    idx = range(len(p)) if rows is None else rows
    ud = prep.ud
    for i in idx:
        cutoff_day = int(ud[p[i] - 1]) if p[i] > 0 else -10**9
        a, d = adj.solve(cutoff_day, int(prep.g_season[i]))
        h, w = prep.g_home[i], prep.g_away[i]
        off[i] = a[h] - a[w]
        de[i] = d[w] - d[h]
    return off, de


# ------------------------------------------------------------- recency-weighted performance
def recent_snapshots(prep: Prep, half_life=20.0, n0=8.0, rho=0.5):
    """Exponentially weighted (per-game decay) team measures shrunk to a carried-forward prior.

    Columns: 0 weight, 1 net rating, 2 offence (rel. to league), 3 defence (rel.), 4-7 four-factor nets.
    estimate = (sum_w x + n0 * prior) / (sum_w + n0); prior = rho * previous-season final estimate.
    """
    n = len(prep.teams)
    decay = 0.5 ** (1.0 / half_life)
    K = 8
    S = np.zeros((n, K))
    prior = np.zeros((n, K - 1))
    cnt = np.zeros(n, dtype=int)
    stamp = np.zeros(n, dtype=int)
    lg = {'season': 0, 'sum': 0.0, 'n': 0, 'prev': None}
    u = prep.upd
    season = u.season.values
    hi, ai = u.hi.values, u.ai.values
    cols = {}
    for side, o in (('h', 'a'), ('a', 'h')):
        cols[side] = np.stack([
            u[f'{side}_ortg'] - u[f'{o}_ortg'], u[f'{side}_ortg'], u[f'{o}_ortg'],
            u[f'{side}_efg'] - u[f'{o}_efg'], u[f'{o}_tovr'] - u[f'{side}_tovr'],
            u[f'{side}_orbr'] - u[f'{o}_orbr'], u[f'{side}_ftr'] - u[f'{o}_ftr']], 1)
    snaps = [(S.copy(), prior.copy(), stamp.copy(), cnt.copy())]
    for s, e in prep.slices:
        for i in range(s, e):
            if lg['season'] != season[i]:
                if lg['n'] > 0:
                    lg['prev'] = lg['sum'] / lg['n']
                lg.update(season=season[i], sum=0.0, n=0)
            lg['sum'] += cols['h'][i, 1] + cols['a'][i, 1]
            lg['n'] += 2
            mean = lg['sum'] / lg['n'] if lg['prev'] is None else (60 * lg['prev'] + lg['sum']) / (60 + lg['n'])
            for side, t in (('h', hi[i]), ('a', ai[i])):
                if stamp[t] < season[i]:
                    if stamp[t] > 0:
                        est = (S[t, 1:] + n0 * prior[t]) / (S[t, 0] + n0)
                        prior[t] = rho * est
                    S[t] = 0.0
                    cnt[t] = 0
                    stamp[t] = season[i]
                c = cols[side][i]
                x = np.array([1.0, c[0], c[1] - mean, c[2] - mean, c[3], c[4], c[5], c[6]])
                S[t] = decay * S[t] + x
                cnt[t] += 1
        snaps.append((S.copy(), prior.copy(), stamp.copy(), cnt.copy()))
    return snaps, dict(n0=n0, rho=rho)


def recent_features(prep: Prep, p: np.ndarray, snaps, n0: float, rho: float):
    """Pregame recency estimates for home and away teams. Returns dict of home-minus-away arrays."""
    n_games = len(p)
    est_h = np.zeros((n_games, 7))
    est_a = np.zeros((n_games, 7))
    gp = np.zeros((n_games, 2))
    for i in range(n_games):
        S, prior, stamp, cnt = snaps[p[i]]
        for side, t, out in ((0, prep.g_home[i], est_h), (1, prep.g_away[i], est_a)):
            if stamp[t] == 0:
                out[i] = 0.0
                continue
            if stamp[t] < prep.g_season[i]:       # season boundary: prior only
                est = (S[t, 1:] + n0 * prior[t]) / (S[t, 0] + n0)
                out[i] = rho * est
                gp[i, side] = 0
            else:
                out[i] = (S[t, 1:] + n0 * prior[t]) / (S[t, 0] + n0)
                gp[i, side] = cnt[t]
    return est_h, est_a, gp


# ------------------------------------------------------------- schedule context
def rest_features(prep: Prep) -> pd.DataFrame:
    """Rest days from the full published schedule (known before the season), incl. quarantined games."""
    g = prep.games
    last = {}
    rest_h = np.zeros(len(g))
    rest_a = np.zeros(len(g))
    order = np.lexsort((np.arange(len(g)), prep.g_day))
    prev_season = {}
    for i in order:
        for arr, t in ((rest_h, prep.g_home[i]), (rest_a, prep.g_away[i])):
            if t in last and prev_season.get(t) == prep.g_season[i]:
                arr[i] = min(REST_CAP, prep.g_day[i] - last[t])
            else:
                arr[i] = REST_CAP
        last[prep.g_home[i]] = prep.g_day[i]
        last[prep.g_away[i]] = prep.g_day[i]
        prev_season[prep.g_home[i]] = prev_season[prep.g_away[i]] = prep.g_season[i]
    return pd.DataFrame({'rest_home': rest_h, 'rest_away': rest_a})


def build_features(games: pd.DataFrame, boxes: pd.DataFrame, params: dict | None = None) -> pd.DataFrame:
    """One row per canonical game with every pregame feature (labels kept separate in `home_win`)."""
    prm = {**DEFAULT, **(params or {})}
    prep = prepare(games, boxes)
    p = cutoff_index(prep, prm['lag_days'])
    e = prm['elo']
    elo = elo_features(prep, p, elo_snapshots(prep, e['k'], e['hca'], e['carry'], e['mov']), e['carry'])
    adj = AdjustedStrength(prep, prm['adj']['lam'], prm['adj']['kappa'])
    adj_off, adj_def = adjusted_features(prep, p, adj)
    r = prm['recent']
    snaps, _ = recent_snapshots(prep, r['half_life'], r['n0'], r['rho'])
    eh, ea, gp = recent_features(prep, p, snaps, r['n0'], r['rho'])
    rest = rest_features(prep)
    g = prep.games
    out = pd.DataFrame({
        'game_id': g.game_id.values, 'season': g.season.values, 'game_date': g.game_date.values,
        'tipoff_utc': g.tipoff_utc.values, 'home_id': g.home_id.values, 'away_id': g.away_id.values,
        'home': g.home.values, 'away': g.away.values,
        'eligible': (g.completed & g.verified).values, 'home_win': g.home_win.values,
        'data_through_day': np.where(p > 0, prep.ud[np.maximum(p - 1, 0)], -1),
        'elo_diff': elo, 'adj_off_diff': adj_off, 'adj_def_diff': adj_def,
        'adj_net_diff': adj_off + adj_def,
        'recent_net_diff': eh[:, 0] - ea[:, 0],
        'recent_off_diff': eh[:, 1] - ea[:, 1],
        'recent_def_diff': ea[:, 2] - eh[:, 2],
        'rest_diff': rest.rest_home.values - rest.rest_away.values,
        'b2b_home': (rest.rest_home.values == 1).astype(float),
        'b2b_away': (rest.rest_away.values == 1).astype(float),
        'home_court': (~prep.g_neutral).astype(float),
        'gp_min': gp.min(axis=1), 'gp_home': gp[:, 0], 'gp_away': gp[:, 1]})
    for j, name in enumerate(FF):
        out[f'ff_{name}_diff'] = eh[:, 3 + j] - ea[:, 3 + j]
    out['prediction_cutoff_utc'] = (pd.to_datetime(out.game_date).dt.tz_localize('America/New_York')
                                    + pd.Timedelta(hours=6)).dt.tz_convert('UTC')
    return out
