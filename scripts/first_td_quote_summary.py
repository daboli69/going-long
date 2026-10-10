"""Exact-game first-TD quote diagnostics, independent of provider/cache access."""
import pandas as pd


def summarize_quotes(quotes, schedule, first_scorers, team_names=None):
    names = team_names or {}
    aliases = {'LAR': 'LA', 'JAC': 'JAX', 'WSH': 'WAS'}

    def team(value):
        value = names.get(value, value)
        return aliases.get(value, value)

    games = schedule[['game_id', 'gameday', 'home_team', 'away_team']].copy()
    games['home'] = games.home_team.map(team)
    games['away'] = games.away_team.map(team)
    keys = ['gameday', 'home', 'away']
    if games.duplicated(keys).any() or games.game_id.duplicated().any():
        raise ValueError('Schedule does not uniquely identify games.')
    first = first_scorers[['game_id', 'td_player_id']].copy()
    if first.game_id.duplicated().any():
        raise ValueError('First-TD outcomes must have one scorer per game.')
    q = quotes.copy()
    q['home'] = q.home.map(team)
    q['away'] = q.away.map(team)
    q = q.merge(games[keys + ['game_id']], on=keys, how='inner', validate='many_to_one')
    q = q.merge(first, on='game_id', how='inner', validate='many_to_one')
    q['hit'] = q.pid == q.td_player_id
    price = pd.to_numeric(q.over, errors='coerce')
    q = q[price.notna() & (price.abs() >= 100)].copy()
    price = price.loc[q.index]
    decimal = price.map(lambda value: 1 + value / 100 if value > 0 else 1 + 100 / -value)
    q['imp'] = 1 / decimal
    q = q.sort_values('upd', kind='stable').groupby(['game_id', 'pid', 'book'], sort=False).tail(1)
    consensus = q.groupby(['game_id', 'pid']).agg(imp=('imp', 'mean'), hit=('hit', 'max'), nb=('book', 'nunique')).reset_index()
    covered = consensus.loc[consensus.hit, 'game_id'].nunique()
    return consensus, {'quoted_games': consensus.game_id.nunique(), 'outcome_games': len(first),
                       'scorer_covered_games': covered, 'scorer_coverage': covered / len(first) if len(first) else None}
