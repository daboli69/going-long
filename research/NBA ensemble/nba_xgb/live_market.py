"""Join historical Kalshi in-game moneyline quotes (1-minute) to the game state visible at that wall-clock minute.

Rows are sampled every STEP minutes from the first play-by-play event until the final event. For every row we keep what a trader saw: bid and ask of the home and away
winner contracts as of the candle, plus the score and clock from the last play-by-play event stamped at or before (candle end - LAG seconds).
The play-by-play stamp delay is unknown; LAG is a sensitivity parameter, chosen on the development window only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats
from . import data, kalshi, live_state as LS
from .avail_study import OUT

STEP = 2          # minutes between sampled states
LAG = 0           # seconds subtracted from the quote time before looking up the game state


def quotes() -> pd.DataFrame:
    q = pd.read_parquet(OUT / 'kalshi_inplay' / 'moneyline_minutes.parquet')
    q = q.sort_values(['ticker', 'end_ts'])
    for c in ('bid', 'ask', 'last'):
        q[c] = q.groupby('ticker')[c].ffill()
    h = q[q.side == 'home'].set_index(['game_id', 'end_ts'])[['bid', 'ask', 'last', 'volume']].add_prefix('h_')
    a = q[q.side == 'away'].set_index(['game_id', 'end_ts'])[['bid', 'ask', 'last', 'volume']].add_prefix('a_')
    w = h.join(a, how='outer').reset_index()
    res = q.drop_duplicates('game_id').set_index('game_id').result
    w['home_result'] = w.game_id.map(q[q.side == 'home'].drop_duplicates('game_id').set_index('game_id').result)
    return w


def mid_prob(row_bid, row_ask):
    ok = (row_bid >= 0) & (row_ask <= 1) & (row_ask > row_bid)
    return np.where(ok, (row_bid + row_ask) / 2.0, np.nan)


def build(step=STEP, lag=LAG, log=print) -> pd.DataFrame:
    games, _ = data.load(verify=False)
    lab = games[games.season == 2026].set_index('game_id')
    ev_all = LS.load_events(2026)
    priors = pd.read_parquet(OUT / 'pregame_priors.parquet').set_index('game_id')
    snaps = pd.read_parquet(OUT / 'live_snapshots.parquet')
    stints = pd.read_parquet(OUT / 'stints.parquet')
    sgrp = {gid: x.sort_values('t0') for gid, x in stints.groupby('game_id')}
    rat = pd.read_parquet(OUT / 'rapm_ratings.parquet')
    by = {d: dict(zip(g.athlete_id.astype(int), g.net)) for d, g in rat.groupby('refit_day')}
    days = np.array(sorted(by))
    from .market_benchmark import spreads
    spread = spreads().set_index('game_id').home_team_spread
    Q = quotes()
    rows = []
    for gid, qg in Q.groupby('game_id'):
        if gid not in ev_all or gid not in lab.index or gid not in priors.index:
            continue
        ev = ev_all[gid]
        if ev['bad_clock']:
            continue
        info = lab.loc[gid]
        qg = qg.sort_values('end_ts')
        hb, ha = qg.h_bid.values, qg.h_ask.values
        ab, aa = qg.a_bid.values, qg.a_ask.values
        ts = qg.end_ts.values.astype(float)
        first, last = ev['wc'][0], ev['wc'][-1]
        # pregame close: last quote before the first play-by-play event
        pre = qg[qg.end_ts <= first]
        if pre.empty:
            continue
        pre_mid_h = mid_prob(pre.h_bid.values[-1:], pre.h_ask.values[-1:])[0]
        pre_mid_a = mid_prob(pre.a_bid.values[-1:], pre.a_ask.values[-1:])[0]
        day = int(np.datetime64(info.game_date, 'D').astype('int64'))
        k = np.searchsorted(days, day, side='right') - 1
        rating = by[days[k]] if k >= 0 else {}
        st = sgrp.get(gid)
        pr = priors.loc[gid]
        reg_end = None
        for i in range(len(ts)):
            if ts[i] < first + 60 or ts[i] > last + 30:
                continue
            if int((ts[i] - first) // 60) % step:
                continue
            s = LS.state_at_wallclock(ev, ts[i] - lag)
            if s is None:
                continue
            el, h, a, per = s
            if el >= 2880:
                continue                     # regulation states only; overtime is handled as a separate regime
            L = np.nan
            if st is not None and rating:
                x = st[(st.t0 <= el) & (st.t1 > el)]
                if len(x):
                    x = x.iloc[0]
                    L = sum(rating.get(int(p), 0.0) for p in x.home_lineup) - sum(rating.get(int(p), 0.0) for p in x.away_lineup)
            rows.append((gid, info.game_date, ts[i], el, 2880.0 - el, h - a, h + a, per, L, pr.mu_base, pr.mu_avail, pr.T_pre,
                         spread.get(gid, np.nan), pre_mid_h, pre_mid_a, hb[i], ha[i], ab[i], aa[i],
                         float(info.home_score - info.away_score), float(info.home_score + info.away_score)))
    cols = ['game_id', 'game_date', 'ts', 't', 'tau', 'm', 'S', 'period', 'L', 'mu_base', 'mu_avail', 'T_pre', 'mu_close_espn',
            'pre_mid_home', 'pre_mid_away', 'h_bid', 'h_ask', 'a_bid', 'a_ask', 'final_margin', 'final_total']
    d = pd.DataFrame(rows, columns=cols)
    d['y'] = (d.final_margin > 0).astype(float)
    d['mid_h'] = mid_prob(d.h_bid.values, d.h_ask.values)
    d['mid_a'] = mid_prob(d.a_bid.values, d.a_ask.values)
    d['k_mid'] = np.where(np.isnan(d.mid_h) | np.isnan(d.mid_a), np.nan, d.mid_h / (d.mid_h + d.mid_a))   # vig-normalised midpoint
    d['k_pre'] = d.pre_mid_home / (d.pre_mid_home + d.pre_mid_away)
    log('rows', len(d), 'games', d.game_id.nunique(), 'with in-game mid', int(d.k_mid.notna().sum()))
    return d


if __name__ == '__main__':
    d = build()
    d.to_parquet(OUT / 'inplay_states.parquet', index=False)
    print(d.describe().T[['count', 'mean']].round(3).head(30))
