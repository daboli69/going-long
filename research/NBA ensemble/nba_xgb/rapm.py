"""Regularized adjusted plus-minus from reconstructed stints, refit on a fixed weekly schedule.

Row = one stint seen from one offence: y = 100 * points / possessions, weight = possessions x time decay.
Columns = intercept, home-court sign, offence indicator per player, defence indicator per player.
Ridge penalty on player columns. A refit at date R uses only stints from games dated <= R - 1.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.linalg import cho_factor, cho_solve
from . import data

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_nba_xgb'
REFIT_DAYS = 7


class Design:
    def __init__(self, stints: pd.DataFrame, games: pd.DataFrame):
        g = games.set_index('game_id')
        st = stints.copy()
        st['day'] = pd.to_datetime(st.game_id.map(g.game_date)).values.astype('datetime64[D]').astype('int64')
        st['neutral'] = st.game_id.map(g.neutral).astype(bool)
        st['poss'] = (st.home_poss + st.away_poss) / 2.0
        st = st[st.poss > 0.5].reset_index(drop=True)
        players = sorted({int(p) for col in ('home_lineup', 'away_lineup') for lu in st[col] for p in lu})
        self.pid = {p: i for i, p in enumerate(players)}
        self.players = players
        P = len(players)
        self.P = P
        n = len(st)
        hl = np.array([[self.pid[int(p)] for p in lu] for lu in st.home_lineup])
        al = np.array([[self.pid[int(p)] for p in lu] for lu in st.away_lineup])
        rows = np.arange(2 * n)
        # rows 0..n-1: home offence; rows n..2n-1: away offence
        ro = np.concatenate([hl, al])           # offensive players per row
        rd = np.concatenate([al, hl])           # defensive players per row
        hc = np.concatenate([np.where(st.neutral, 0.0, 1.0), np.where(st.neutral, 0.0, -1.0)])
        r_idx = np.concatenate([rows, rows, np.repeat(rows, 5), np.repeat(rows, 5)])
        c_idx = np.concatenate([np.zeros(2 * n, int), np.ones(2 * n, int), (2 + ro).ravel(), (2 + P + rd).ravel()])
        vals = np.concatenate([np.ones(2 * n), hc, np.ones(10 * n), np.ones(10 * n)])
        self.X = sparse.csr_matrix((vals, (r_idx, c_idx)), shape=(2 * n, 2 + 2 * P))
        pts = np.concatenate([st.home_pts.values, st.away_pts.values])
        pos = np.concatenate([st.poss.values, st.poss.values])
        self.y = 100.0 * pts / pos
        self.poss = pos
        self.day = np.concatenate([st.day.values, st.day.values])
        self.game = np.concatenate([st.game_id.values, st.game_id.values])

    def fit(self, cut_day: int, lam: float, half_life: float):
        """Fit using rows with day <= cut_day (callers pass refit_day - 1)."""
        sel = np.where(self.day <= cut_day)[0]
        age = cut_day - self.day[sel]
        w = self.poss[sel] * 0.5 ** (age / half_life)
        X = self.X[sel]
        Xw = X.T @ sparse.diags(w)
        A = (Xw @ X).toarray()
        pen = np.full(A.shape[0], lam)
        pen[:2] = 1e-6
        A[np.diag_indices_from(A)] += pen
        b = Xw @ self.y[sel]
        beta = cho_solve(cho_factor(A), b)
        exposure = np.asarray(X[:, 2:2 + self.P].T @ w).ravel()     # decayed offensive possessions seen per player
        return beta, exposure

    def score(self, beta, lo_day: int, hi_day: int):
        """Weighted squared error on rows with lo_day <= day < hi_day (strictly after the fit data)."""
        m = (self.day >= lo_day) & (self.day < hi_day)
        pred = self.X[m] @ beta
        w = self.poss[m]
        return float(np.sum(w * (self.y[m] - pred) ** 2)), float(w.sum())


def day_num(s: str) -> int:
    return int(np.datetime64(s, 'D').astype('int64'))


def refit_days(start: str, end: str):
    d = day_num(start)
    e = day_num(end)
    out = []
    while d <= e:
        out.append(d)
        d += REFIT_DAYS
    return out


def tune(design: Design, season_start='2022-11-01', season_end='2023-04-05', log=print):
    """Chronological tuning: fit at each weekly refit date, score on the following week."""
    grid = [(lam, hl) for lam in (300, 1000, 3000, 10000) for hl in (180, 365, 730)]
    res = {}
    days = refit_days(season_start, season_end)
    for lam, hl in grid:
        se = wsum = 0.0
        for d in days:
            beta, _ = design.fit(d - 1, lam, hl)
            s, w = design.score(beta, d, d + REFIT_DAYS)
            se += s
            wsum += w
        res[(lam, hl)] = se / wsum
        log('rapm tune', lam, hl, round(res[(lam, hl)], 3))
    # reference: intercept-only (no player information)
    base_se = base_w = 0.0
    for d in days:
        beta, _ = design.fit(d - 1, 1e12, 365)
        s, w = design.score(beta, d, d + REFIT_DAYS)
        base_se += s
        base_w += w
    best = min(res, key=res.get)
    return {'grid': {f'{k[0]}_{k[1]}': v for k, v in res.items()}, 'best': {'lam': best[0], 'half_life': best[1]},
            'intercept_only_mse': base_se / base_w, 'best_mse': res[best], 'n_refits': len(days)}


def ratings_table(design: Design, lam: float, half_life: float, start='2021-12-01', end='2026-10-31', log=print, leak_days=0):
    rows = []
    for d in refit_days(start, end):
        beta, expo = design.fit(d - 1 + leak_days, lam, half_life)   # leak_days > 0 only in the mutation test
        P = design.P
        off, de = beta[2:2 + P], beta[2 + P:]
        rows.append(pd.DataFrame({'refit_day': d, 'athlete_id': design.players, 'off': off, 'def': de,
                                  'net': off - de, 'exposure': expo}))
        if len(rows) % 25 == 0:
            log('rapm refit', len(rows), pd.Timestamp(d * 86400, unit='s').date())
    return pd.concat(rows, ignore_index=True)


def main(log=print):
    games, _ = data.load()
    stints = pd.read_parquet(OUT / 'stints.parquet')
    stints = stints[stints.season >= 2021]
    design = Design(stints, games)
    log('design', design.X.shape)
    t = tune(design, log=log)
    (ROOT / 'docs' / 'NBA_AVAIL_RAPM_TUNING.json').write_text(json.dumps(t, indent=2), encoding='utf-8')
    log('best', t['best'], 'mse', t['best_mse'], 'vs intercept-only', t['intercept_only_mse'])
    tab = ratings_table(design, t['best']['lam'], t['best']['half_life'], log=log)
    tab.to_parquet(OUT / 'rapm_ratings.parquet', index=False)
    log('saved', tab.shape)


if __name__ == '__main__':
    main()
