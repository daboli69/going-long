"""Estimate D/ST correlations and spread from archived DraftKings contest points (PRIVATE archive, read-only; aggregates only).

Method: for each (slate date, team) build the team-game's starters from the Classic contests' player pools (role = salary rank within team and position; players with 0 points are
treated as not having played), attach the opposing team through the archive's projection files (team/opponent/date), and compute the normal-score (rank) correlation of the team's
D/ST DraftKings points with each opposing starter. Games dated before 2025 fit; 2025 onward validate. The constants in shared/dfs-sim.js are the all-games estimates shrunk by n/(n+50).
Usage: python scripts/dfs_correlation_estimates.py --archive <StatApi dir> --out <aggregate json outside the repo>
"""
import argparse
import collections
import glob
import gzip
import json

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata

FIX = {'LAR': 'LA', 'JAC': 'JAX', 'WSH': 'WAS'}


def opponents(root):
    seen = collections.defaultdict(set)
    for path in glob.glob(root + '/raw/projections/*.gz'):
        try:
            data = json.loads(gzip.open(path, 'rt', encoding='utf-8').read())
        except Exception:
            continue
        for row in data.get('projections', []):
            p = row.get('player', {})
            if p.get('team') and p.get('opponent') and p.get('slate_date'):
                seen[(p['slate_date'], FIX.get(p['team'], p['team']))].add(FIX.get(p['opponent'], p['opponent']))
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def team_games(root):
    opp = opponents(root)
    frame = pd.read_parquet(root + '/ownership_frame.parquet')
    frame = frame[(frame.game_type == 'classic') & frame.fantasy_points.notna()].copy()
    frame['team'] = frame.team.replace(FIX)
    frame = frame.drop_duplicates(['date', 'name'])
    rows = {}
    for (date, team), g in frame.groupby(['date', 'team']):
        row = {'date': date, 'team': team, 'opp': opp.get((date, team))}
        for pos, names in [('QB', ['QB']), ('RB', ['RB1']), ('WR', ['WR1', 'WR2', 'WR3']), ('TE', ['TE1'])]:
            played = g[(g.position == pos) & (g.fantasy_points != 0)].sort_values('salary', ascending=False)
            for i, name in enumerate(names):
                row[name] = played.fantasy_points.iloc[i] if len(played) > i else np.nan
        d = g[g.position == 'DST']
        row['DST'] = d.fantasy_points.iloc[0] if len(d) else np.nan
        rows[(date, team)] = row
    table = pd.DataFrame(rows.values())
    table = table[table.opp.notna()]
    index = table.set_index(['date', 'team'])
    for col in ['QB', 'RB1', 'WR1', 'WR2', 'WR3', 'TE1', 'DST']:
        table['opp_' + col] = [index.at[(r.date, r.opp), col] if (r.date, r.opp) in index.index else np.nan for r in table.itertuples()]
    table['split'] = np.where(table.date < '2025-01-01', 'fit', 'validate')
    return table


def nscore(x):
    return norm.ppf((rankdata(x) - .5) / len(x))


def corr(table, a, b):
    d = table[[a, b]].dropna()
    if len(d) < 30:
        return (None, int(len(d)))
    return (float(np.corrcoef(nscore(d[a].values), nscore(d[b].values))[0, 1]), int(len(d)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--archive', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    table = team_games(args.archive)
    out = {'team_games': int(len(table)), 'split_counts': {k: int(v) for k, v in table.split.value_counts().items()}, 'pairs': {}, 'dst_points': {}}
    for b in ['opp_QB', 'opp_RB1', 'opp_WR1', 'opp_WR2', 'opp_WR3', 'opp_TE1', 'QB', 'RB1', 'WR1', 'TE1', 'opp_DST']:
        fit = corr(table[table.split == 'fit'], 'DST', b)
        val = corr(table[table.split == 'validate'], 'DST', b)
        allg = corr(table, 'DST', b)
        shrunk = None if allg[0] is None else allg[0] * allg[1] / (allg[1] + 50)
        out['pairs']['DST~' + b] = {'fit': fit, 'validate': val, 'all': allg, 'shrunk_n_over_n_plus_50': shrunk}
    for s, g in table.groupby('split'):
        out['dst_points'][s] = {'n': int(g.DST.notna().sum()), 'mean': float(g.DST.mean()), 'sd': float(g.DST.std())}
    json.dump(out, open(args.out, 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
