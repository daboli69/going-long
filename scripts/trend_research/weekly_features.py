"""Point-in-time rolling features for Week N -> Week N+1 experiments.

Every feature at a target game is computed from games STRICTLY BEFORE it (``merge_asof`` with exact matches disallowed). Windows count the player's
own games (L1 / L3 / L6), so byes and missed games cannot misalign them. Sources: Fantasy Points by-game panel, nflverse box scores (raw recency), the free
ffopportunity expected values, and team run/pass tendencies from both nflverse and the Fantasy Points run/pass report.
"""
import numpy as np
import pandas as pd

from . import champion, weekly

WINDOWS = (1, 3, 6)


def _t(frame):
    return (frame['season'].astype(int) * 100 + frame['week'].astype(int)).astype('int64')


def rolling_asof(targets, source, key, cols, prefix, windows=WINDOWS, id_col=None):
    """For each target row, window means of ``cols`` over the last n source rows of the same ``key`` strictly before the target game.

    ``targets`` needs key, season, week. ``source`` needs key, season, week and cols. Adds ``{prefix}{col}__L{n}`` and ``{prefix}__cnt`` (rows in the 6-game window)."""
    src = source.dropna(subset=[key]).drop_duplicates([key, 'season', 'week']).copy()
    src['_t'] = _t(src)
    src = src.sort_values([key, '_t'])
    grouped = src.groupby(key, sort=False)
    parts = {}
    for n in windows:
        rolled = grouped[cols].rolling(n, min_periods=1).mean().reset_index(level=0, drop=True)
        for c in cols:
            parts[f'{prefix}{c}__L{n}'] = rolled[c]
    parts[f'{prefix}__cnt'] = grouped[cols[0]].transform(lambda s: s.notna().astype(float).rolling(max(windows), min_periods=1).sum())
    feats = pd.DataFrame(parts, index=src.index)
    feats[key] = src[key]
    feats['_t'] = src['_t']
    left = targets[[key, 'season', 'week']].copy()
    left['_t'] = _t(left)
    left['_row'] = np.arange(len(left))
    left = left.sort_values('_t')
    merged = pd.merge_asof(left, feats.sort_values('_t'), on='_t', by=key, direction='backward', allow_exact_matches=False)
    merged = merged.sort_values('_row').drop(columns=[key, 'season', 'week', '_t', '_row']).reset_index(drop=True)
    return pd.concat([targets.reset_index(drop=True), merged], axis=1)


def with_trends(frame, prefix, cols):
    """Adds {prefix}{col}__d3 = L3 - L6 and __d1 = L1 - L6 (change versus the player's own recent baseline)."""
    new = {}
    for c in cols:
        new[f'{prefix}{c}__d3'] = frame[f'{prefix}{c}__L3'] - frame[f'{prefix}{c}__L6']
        new[f'{prefix}{c}__d1'] = frame[f'{prefix}{c}__L1'] - frame[f'{prefix}{c}__L6']
    return pd.concat([frame, pd.DataFrame(new, index=frame.index)], axis=1)


NFL_VOLUME = ['targets', 'receptions', 'receiving_yards', 'carries', 'rushing_yards', 'attempts', 'passing_yards', 'passing_tds']
FFO_COLS = ['receptions_exp', 'rec_yards_gained_exp', 'rec_touchdown_exp', 'rush_yards_gained_exp', 'rush_touchdown_exp']


def nfl_recency(frame, root):
    """Raw box-score recency from nflverse: the control every Fantasy Points feature must beat."""
    w = champion.load_weekly(root, list(range(2019, 2026)))
    w = w[w.season_type == 'REG'][['player_id', 'season', 'week'] + NFL_VOLUME].copy()
    w[NFL_VOLUME] = w[NFL_VOLUME].fillna(0)
    return rolling_asof(frame, w, 'player_id', NFL_VOLUME, 'nfl.')


def ffopp_recency(frame, root):
    f = champion.load_ffopp(root, list(range(2019, 2026)))
    f = f[['player_id', 'season', 'week'] + FFO_COLS].copy()
    return rolling_asof(frame, f, 'player_id', FFO_COLS, 'ffo.')


def fp_recency(frame, root, cols):
    panel = weekly.game_panel(root)
    panel = panel[['player_id', 'season', 'week'] + [c for c in cols if c in panel.columns]]
    missing = [c for c in cols if c not in panel.columns]
    if missing:
        raise KeyError(f'Fantasy Points panel lacks {missing[:4]}')
    return rolling_asof(frame, panel, 'player_id', cols, 'fp.')


def team_recency(frame, root):
    """Team run/pass tendency from nflverse (all seasons) and the Fantasy Points run/pass report (2024 not yet downloaded)."""
    w = champion.load_weekly(root, list(range(2019, 2026)))
    w = w[w.season_type == 'REG']
    team = w.groupby(['team', 'season', 'week'], as_index=False).agg(att=('attempts', 'sum'), car=('carries', 'sum'), pyds=('passing_yards', 'sum'))
    team['nfl_pass_rate'] = team.att / (team.att + team.car)
    team['nfl_att'] = team.att
    team['nfl_car'] = team.car
    out = rolling_asof(frame, team, 'team', ['nfl_pass_rate', 'nfl_att', 'nfl_car'], 'tm.')
    rp = weekly.load_table(root, 'run_pass_report_weekly')
    rp = rp.rename(columns={'Overall.PASS %': 'fp_pass_pct', 'Neutral.PASS %': 'fp_neutral_pass_pct', 'Inside 10.PASS %': 'fp_i10_pass_pct',
                            'Trailing By 7+.SNAPS': 'fp_trail_snaps', 'Leading By 7+.SNAPS': 'fp_lead_snaps', 'Overall.SNAPS': 'fp_snaps'})
    rp = rp.dropna(subset=['team'])
    cols = ['fp_pass_pct', 'fp_neutral_pass_pct', 'fp_i10_pass_pct', 'fp_snaps']
    return rolling_asof(out, rp[['team', 'season', 'week'] + cols], 'team', cols, 'rp.')
