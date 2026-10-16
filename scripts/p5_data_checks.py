#!/usr/bin/env python3
"""Real-data checks for P5-2 inputs (needs the private FantasyPoints cache). Aggregates only.

    python scripts/p5_data_checks.py --root <FantasyPoints>

1. hashes of the games.csv inputs; 2. independent re-computation of every lagged rolling feature with plain loops (same-season, completed games only, strictly before the game);
3. every prior game used had a final score and started before the target game; 4. which games.csv rows changed between two cache files and whether any is <= 2025.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trend_research import experiments14 as e14  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_lag(tg):
    """Recompute r_pf / r_pa / r_fp_snaps for every team-game from raw prior games and compare with the vectorised feature."""
    problems = {'value_mismatch': 0, 'prior_not_before': 0, 'cross_season_use': 0}
    n = 0
    for (team, season), g in tg.sort_values(['team', 'season', 'week']).groupby(['team', 'season']):
        g = g.reset_index(drop=True)
        for i, row in g.iterrows():
            prior = g.iloc[:i]
            for col in ('pf', 'pa', 'fp_snaps', 'nfl_plays'):
                vals = prior[col].tail(e14.WINDOW)
                vals = vals.dropna()
                expect = vals.mean() if len(vals) >= e14.MIN_PRIOR else np.nan
                got = row['r_' + col]
                n += 1
                if not ((np.isnan(expect) and np.isnan(got)) or abs(expect - got) < 1e-9):
                    problems['value_mismatch'] += 1
            if len(prior):
                if not (prior.kick < row.kick).all():
                    problems['prior_not_before'] += 1
            if (prior.season != season).any():
                problems['cross_season_use'] += 1
    return {'feature_cells_checked': n, **problems}


def games_diff(old_path, new_path):
    o, n = pd.read_csv(old_path).set_index('game_id'), pd.read_csv(new_path).set_index('game_id')
    cols = [c for c in o.columns if c in n.columns]
    changed = (o[cols].fillna(-999).astype(str) != n.loc[o.index, cols].fillna(-999).astype(str)).any(axis=1)
    return {'rows_old': len(o), 'rows_new': len(n), 'rows_added_or_removed': len(set(o.index) ^ set(n.index)), 'rows_changed': int(changed.sum()),
            'changed_by_season_week': {f'{s}-{w}': int(c) for (s, w), c in o[changed].groupby(['season', 'week']).size().items()}, 'changed_rows_season_le_2025': int((o[changed].season <= 2025).sum())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--old-games', type=Path)
    a = p.parse_args()
    cache = a.root / 'research' / 'cache'
    games, tg = e14.team_games(a.root)
    out = {'games_csv_sha256': sha(cache / 'games.csv'), 'rolling_feature_recomputation': check_lag(tg)}
    if a.old_games:
        out['old_games_csv_sha256'] = sha(a.old_games)
        out['games_csv_change'] = games_diff(a.old_games, cache / 'games.csv')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
