"""Backtest pieces of the DFS projection against ARCHIVED actual DraftKings points (PRIVATE archive read-only; aggregates only).

1. component bias (--history data/history.json): actual DK points minus the "core" points computed from the same game's logged stat line (what the projection formula can express).
   The formula omits interceptions, lost fumbles and 2-point conversions, so this isolates the omitted-terms bias by position, split fit (< --split) / validate (>= --split).
2. slate calibration (--pool pool.json from scripts/dfs_headless.cjs --out): GOING's pregame projection vs actual points for one archived slate, by position and by value quartile
   (projection per $1,000), against the platform AvgPointsPerGame baseline. One slate is DESCRIPTIVE only.
Usage: python scripts/dfs_projection_backtest.py --archive <StatApi> --history data/history.json [--pool pool.json --date 2026-10-04] --out <aggregate json outside the repo>
"""
import argparse
import json
import re
import unicodedata

import numpy as np
import pandas as pd


def nk(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower())


def core_points(d):
    return (.04 * d.pass_yds + 4 * d.pass_tds + .1 * (d.rush_yds + d.rec_yds) + 6 * (d.rush_tds + d.rec_tds) + d.receptions
            + 3 * ((d.pass_yds >= 300) * 1 + (d.rush_yds >= 100) * 1 + (d.rec_yds >= 100) * 1))


def component_bias(archive, history, split):
    profiles = json.load(open(history))['betting']['profiles']
    games = []
    for p in profiles.values():
        for g in p['games']:
            games.append(dict(key=nk(p['name']), date=pd.Timestamp(g['date']),
                              **{k: g.get(k, 0) or 0 for k in ['pass_yds', 'pass_tds', 'rush_yds', 'rush_tds', 'rec_yds', 'rec_tds', 'receptions']}))
    games = pd.DataFrame(games)
    games['core'] = core_points(games)
    frame = pd.read_parquet(archive + '/ownership_frame.parquet')
    frame = frame[(frame.game_type == 'classic') & frame.position.isin(['QB', 'RB', 'WR', 'TE'])].drop_duplicates(['slate_id', 'player_key']).copy()
    frame['key'] = frame.name.map(nk)
    frame['date'] = pd.to_datetime(frame.date)
    merged = pd.merge_asof(frame.sort_values('date'), games.sort_values('date')[['key', 'date', 'core']].rename(columns={'date': 'gdate'}),
                           left_on='date', right_on='gdate', by='key', direction='nearest', tolerance=pd.Timedelta('1D'))
    merged = merged[merged.gdate.notna()].copy()
    merged['gap'] = merged.fantasy_points - merged.core
    merged['half'] = np.where(merged.date < split, 'fit', 'validate')
    out = {}
    for (pos, half), g in merged.groupby(['position', 'half']):
        out[f'{pos}/{half}'] = {'n': int(len(g)), 'mean_gap': float(g.gap.mean()), 'se': float(g.gap.std() / np.sqrt(len(g)))}
    return out


def stats(e):
    return {'MAE': float(e.abs().mean()), 'RMSE': float(np.sqrt((e ** 2).mean())), 'bias': float(e.mean())}


def slate_calibration(archive, pool_path, date):
    pool = pd.DataFrame(json.load(open(pool_path))['pool'])
    pool['key'] = pool.name.map(nk)
    frame = pd.read_parquet(archive + '/ownership_frame.parquet')
    act = frame[(frame.date == date) & (frame.game_type == 'classic')].drop_duplicates('player_key').copy()
    act['key'] = act.name.map(nk)
    m = pool.merge(act[['key', 'team', 'fantasy_points']].rename(columns={'team': 't2'}), on='key')
    m = m[(m.team == m.t2) & m.matched & ~m.unavailable & (m.projection > 0)].copy()
    m['err'] = m.projection - m.fantasy_points
    m['value'] = m.projection / m.salary * 1000
    m['vq'] = pd.qcut(m.value, 4, labels=['Q1', 'Q2', 'Q3', 'Q4 high value'])
    return {'n': int(len(m)), 'going': stats(m.err), 'site_avg': stats(m.avgPointsPerGame - m.fantasy_points),
            'by_position': {k: {'n': int(len(g)), **stats(g.err)} for k, g in m.groupby('position')},
            'by_value_quartile': {str(k): {'n': int(len(g)), 'bias': float(g.err.mean()), 'se': float(g.err.std() / np.sqrt(len(g)))} for k, g in m.groupby('vq')}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--archive', required=True)
    ap.add_argument('--history', required=True)
    ap.add_argument('--pool')
    ap.add_argument('--date', default='2026-10-04')
    ap.add_argument('--split', default='2026-01-15')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = {'component_bias': component_bias(args.archive, args.history, args.split)}
    if args.pool:
        out['slate_calibration'] = slate_calibration(args.archive, args.pool, args.date)
    json.dump(out, open(args.out, 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
