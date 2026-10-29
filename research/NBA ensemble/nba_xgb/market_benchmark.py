"""ESPN pregame spread -> home-win probability, used ONLY as a scoring benchmark (never a feature).

The spread comes from the archived ESPN play-by-play files (`home_team_spread`, positive = home favoured). Its capture time is unknown,
so this is an approximate market benchmark, not a verified closing line. Mapping: logistic of the spread fitted on seasons 2022..T-1.
"""
import glob
import stat
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from . import avail_study as S, data

ROOT = S.ROOT


def spreads():
    rows = []
    for s in range(2022, 2027):
        f = sorted(glob.glob(str(ROOT / 'data' / 'raw' / 'archive' / f'pbp_{s}' / '*.parquet')))[-1]
        d = pd.read_parquet(f, columns=['game_id', 'season_type', 'home_team_spread'])
        d = d[d.season_type == 2].drop_duplicates('game_id')
        d['game_id'] = d.game_id.astype(str)
        rows.append(d[['game_id', 'home_team_spread']])
    return pd.concat(rows, ignore_index=True)


def main():
    T = S.load_table().merge(spreads(), on='game_id', how='left')
    out = []
    for f in S.TEST_FOLDS:
        tr = T[T.eligible & T.season.between(2022, f - 1)].dropna(subset=['home_team_spread'])
        ev = T[T.eligible & (T.season == f)]
        m = LogisticRegression(penalty=None, max_iter=500).fit(tr[['home_team_spread']].values, tr.home_win.values)
        p = m.predict_proba(ev[['home_team_spread']].fillna(0).values)[:, 1]
        print(f, 'missing spreads', int(ev.home_team_spread.isna().sum()), 'coef', m.coef_.round(4), m.intercept_.round(4))
        out.append(pd.DataFrame({'game_id': ev.game_id.values, 'season': f, 'game_date': ev.game_date.values,
                                 'prediction_cutoff_utc': ev.prediction_cutoff_utc.astype(str).values, 'model': 'espn_spread',
                                 'p_home_raw': p, 'p_home': p, 'model_version': 'spread_logistic_v1', 'train_seasons': f'2022-{f - 1}'}))
    pred = pd.concat(out, ignore_index=True)
    path = S.OUT / 'benchmark_espn_spread_2025_2026.csv'
    if path.exists():
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
    pred.to_csv(path, index=False)
    path.chmod(stat.S_IREAD)
    print('written', path, len(pred))


if __name__ == '__main__':
    main()
