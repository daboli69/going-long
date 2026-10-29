"""Point-in-time game states from raw ESPN play-by-play, with real wall-clock times, and walk-forward pregame priors (expected margin and total).

Event time = ESPN wall-clock stamp (repaired with a running maximum; games with an inversion over 10 minutes or a span over 6 hours are flagged and excluded
from any price-versus-state comparison). A state at time w is the score and clock after the last event with wall-clock <= w; nothing later is visible.
"""
from __future__ import annotations
import glob
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from . import data, pbp, avail_study as S
from .avail_study import OUT, ROOT

REG = 2880.0


def load_events(season: int) -> dict:
    f = sorted(glob.glob(str(ROOT / 'data' / 'raw' / 'archive' / f'pbp_{season}' / '*.parquet')))[-1]
    d = pd.read_parquet(f, columns=['game_id', 'season_type', 'game_play_number', 'wallclock', 'period_number',
                                    'clock_display_value', 'home_score', 'away_score'])
    d = d[d.season_type == 2].copy()
    d['game_id'] = d.game_id.astype(str)
    d = d.sort_values(['game_id', 'game_play_number'], kind='stable')
    d['el'] = pbp.elapsed(d.period_number.values.astype(float), pbp.clock_seconds(d.clock_display_value))
    d['wc'] = pd.to_datetime(d.wallclock, utc=True, errors='coerce').astype('int64') // 10**9
    out = {}
    for gid, x in d.groupby('game_id', sort=False):
        wc = x.wc.values.astype(float)
        wc[wc < 0] = np.nan
        ok = ~np.isnan(wc)
        if ok.sum() < 100:
            continue
        inversion = float(np.nanmin(np.diff(wc[ok]))) if ok.sum() > 1 else 0.0
        span = float(wc[ok].max() - wc[ok].min())
        wc = pd.Series(wc).ffill().bfill().values
        wc_fixed = np.maximum.accumulate(wc)
        el = np.maximum.accumulate(x.el.values)
        out[gid] = {'el': el, 'h': x.home_score.values.astype(float), 'a': x.away_score.values.astype(float),
                    'period': x.period_number.values.astype(int), 'wc': wc_fixed,
                    'bad_clock': bool(inversion < -600 or span > 6 * 3600)}
    return out


def state_at_wallclock(ev: dict, w: float):
    """State visible at wall-clock w (epoch seconds). Returns (elapsed, home, away, period) or None before the first event."""
    i = np.searchsorted(ev['wc'], w, side='right') - 1
    if i < 0:
        return None
    return ev['el'][i], ev['h'][i], ev['a'][i], ev['period'][i]


def state_at_elapsed(ev: dict, t: float):
    i = np.searchsorted(ev['el'], t, side='right') - 1
    if i < 0:
        return 0.0, 0.0, 0.0
    return ev['el'][i], ev['h'][i], ev['a'][i]


def regulation_scores(ev: dict):
    i = np.searchsorted(ev['el'], REG, side='right') - 1
    return ev['h'][i], ev['a'][i]


# --------------------------------------------------------------------------------------- pregame priors
def team_totals_ew(games: pd.DataFrame, half_life=15.0, carry=0.5):
    """Pregame expected game total from each team's exponentially weighted (points scored + allowed), lagged one calendar day."""
    g = games[games.completed & games.verified].sort_values(['game_date', 'tipoff_utc']).copy()
    decay = 0.5 ** (1.0 / half_life)
    state, prior, seas = {}, {}, {}
    rows = {}
    by_date = {d: x for d, x in g.groupby('game_date', sort=True)}
    all_games = games.sort_values(['game_date', 'tipoff_utc'])
    dates = sorted(all_games.game_date.unique())
    # process dates in order: predict for the date's games using state before the date, then update with the date's finished games
    for d in dates:
        for r in all_games[all_games.game_date == d].itertuples(index=False):
            vals = []
            for t in (r.home_id, r.away_id):
                s = state.get(t)
                if s is None or seas[t] != r.season:
                    base = prior.get(t, 225.0)
                    vals.append(carry * base + (1 - carry) * 225.0 if s is None or seas[t] != r.season else base)
                else:
                    sw, sx = s
                    vals.append((sx + 8.0 * prior.get(t, 225.0)) / (sw + 8.0))
            rows[r.game_id] = float(np.mean(vals))
        for r in by_date.get(d, pd.DataFrame()).itertuples(index=False):
            tot = float(r.home_score + r.away_score)
            for t in (r.home_id, r.away_id):
                if t not in seas or seas[t] != r.season:
                    if t in state:
                        sw, sx = state[t]
                        prior[t] = (sx + 8.0 * prior.get(t, 225.0)) / (sw + 8.0)
                    state[t] = (0.0, 0.0)
                    seas[t] = r.season
                sw, sx = state[t]
                state[t] = (decay * sw + 1.0, decay * sx + tot)
    return pd.Series(rows, name='ew_total')


def pregame_priors(log=print) -> pd.DataFrame:
    """Walk-forward expected margin (mu) and total (T) for every labelled game: fit on seasons before the target season only."""
    games, _ = data.load(verify=False)
    T = S.load_table()
    ew = team_totals_ew(games[games.season >= 2015])
    X = T.set_index('game_id')
    lab = games.set_index('game_id')
    X['margin'] = lab.home_score - lab.away_score
    X['total'] = lab.home_score + lab.away_score
    X['ew_total'] = ew
    base = [c for c in S.BASE]
    full = base + S.AVAIL
    out = []
    for season in range(2019, 2027):
        tr = X[X.eligible & X.season.between(2017, season - 1)]
        te = X[X.eligible & (X.season == season)]
        res = pd.DataFrame(index=te.index)
        for name, feats in (('mu_base', base), ('mu_avail', full)):
            A = np.nan_to_num(tr[feats].values)
            if name == 'mu_avail':
                A = np.column_stack([A, tr.has_avail.values])
            m = Ridge(alpha=50.0).fit(A, tr.margin.values)
            B = np.nan_to_num(te[feats].values)
            if name == 'mu_avail':
                B = np.column_stack([B, te.has_avail.values])
            res[name] = m.predict(B)
        mt = Ridge(alpha=5.0).fit(tr[['ew_total']].values, tr.total.values)
        res['T_pre'] = mt.predict(te[['ew_total']].values)
        res['season'] = season
        out.append(res)
        log(season, 'prior fitted on', len(tr), 'games')
    P = pd.concat(out)
    P.index.name = 'game_id'
    return P.reset_index()


def live_priors(new: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Pregame expected margin (mu_base, mu_avail) and total (T_pre) for upcoming games, fitted on every labelled game before `new`'s season."""
    T = S.load_table()
    ew = team_totals_ew(games[games.season >= 2015])
    X = T.set_index('game_id')
    lab = games.set_index('game_id')
    X['margin'] = lab.home_score - lab.away_score
    X['total'] = lab.home_score + lab.away_score
    X['ew_total'] = ew
    season = int(new.season.max())
    tr = X[X.eligible & X.season.between(2017, season - 1)]
    N = new.set_index('game_id')
    N['ew_total'] = ew
    res = pd.DataFrame(index=N.index)
    for name, feats in (('mu_base', list(S.BASE)), ('mu_avail', list(S.BASE) + list(S.AVAIL))):
        A, B = np.nan_to_num(tr[feats].values), np.nan_to_num(N[feats].values.astype(float))
        if name == 'mu_avail':
            A, B = np.column_stack([A, tr.has_avail.values]), np.column_stack([B, N.has_avail.values])
        res[name] = Ridge(alpha=50.0).fit(A, tr.margin.values).predict(B)
    res['T_pre'] = Ridge(alpha=5.0).fit(tr[['ew_total']].values, tr.total.values).predict(N[['ew_total']].values)
    assert len(res) > 0 and res.notna().all().all(), 'live priors incomplete'
    return res.reset_index()


if __name__ == '__main__':
    P = pregame_priors()
    games, _ = data.load(verify=False)
    lab = games.set_index('game_id')
    P = P.merge(lab[['home_score', 'away_score']].reset_index(), on='game_id')
    P['margin'] = P.home_score - P.away_score
    P['total'] = P.home_score + P.away_score
    P.drop(columns=['home_score', 'away_score']).to_parquet(OUT / 'pregame_priors.parquet', index=False)
    for s, g in P.groupby('season'):
        print(s, len(g), 'margin RMSE base', round(float(np.sqrt(((g.margin - g.mu_base) ** 2).mean())), 3),
              'avail', round(float(np.sqrt(((g.margin - g.mu_avail) ** 2).mean())), 3),
              '| total RMSE', round(float(np.sqrt(((g.total - g.T_pre) ** 2).mean())), 3),
              'naive', round(float(g.total.std()), 3))
