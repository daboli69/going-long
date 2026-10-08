"""DraftKings fantasy scoring for the NFL offense and the player-game frame used by the DFS research.

Scoring (DraftKings Classic/Showdown offense): passing yards 0.04 (+3 at 300), passing TD 4, interception -1, rushing/receiving yards 0.1 (+3 at 100 each), reception 1,
rushing/receiving TD 6, fumble lost -1, two-point conversion 2. Defence/special teams are not modelled here. The modelled-component partial score leaves out interceptions,
fumbles, conversions and bonuses so that projections and outcomes can be compared like for like.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from . import champion

COLUMNS = ['player_id', 'player_display_name', 'position', 'team', 'opponent_team', 'season', 'week', 'season_type', 'passing_yards', 'passing_tds', 'passing_interceptions',
           'rushing_yards', 'rushing_tds', 'receptions', 'targets', 'receiving_yards', 'receiving_tds', 'rushing_fumbles_lost', 'receiving_fumbles_lost', 'sack_fumbles_lost',
           'passing_2pt_conversions', 'rushing_2pt_conversions', 'receiving_2pt_conversions', 'carries', 'attempts', 'special_teams_tds']


def load(root, seasons):
    frames = []
    for s in seasons:
        path = champion._download(champion.WEEKLY_URL.format(season=s), champion.cache(root) / f'stats_player_week_{s}.csv')
        frames.append(pd.read_csv(path, usecols=COLUMNS, low_memory=False))
    out = pd.concat(frames, ignore_index=True)
    return out[out.season_type == 'REG']


def dk_points(df):
    """Full DraftKings offensive points and the modelled-component partial score."""
    f = df.fillna(0)
    partial = (0.04 * f.passing_yards + 4 * f.passing_tds + 0.1 * f.rushing_yards + 6 * f.rushing_tds + f.receptions + 0.1 * f.receiving_yards + 6 * f.receiving_tds)
    bonus = 3 * (f.passing_yards >= 300) + 3 * (f.rushing_yards >= 100) + 3 * (f.receiving_yards >= 100)
    other = (-1 * f.passing_interceptions - f.rushing_fumbles_lost - f.receiving_fumbles_lost - f.sack_fumbles_lost
             + 2 * (f.passing_2pt_conversions + f.rushing_2pt_conversions + f.receiving_2pt_conversions) + 6 * f.special_teams_tds)
    return partial + bonus + other, partial


def player_games(root, seasons):
    df = load(root, seasons)
    df = df[df.position.isin(['QB', 'RB', 'WR', 'TE'])].copy()
    df['dk'], df['dk_partial'] = dk_points(df)
    return df[['player_id', 'season', 'week', 'team', 'opponent_team', 'position', 'dk', 'dk_partial'] + [c for c in COLUMNS if c in ('targets', 'carries', 'attempts', 'receptions', 'passing_yards', 'rushing_yards', 'receiving_yards', 'passing_tds', 'rushing_tds', 'receiving_tds')]]
