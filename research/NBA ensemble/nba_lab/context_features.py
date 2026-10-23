"""Independent shadow context; original features are never changed or reset.

Every result enters only strictly after scheduled tipoff plus24hours. Rolling
windows count games, including missing-box games, rather than valid box rows.
"""
from collections import defaultdict, deque
import heapq
import numpy as np
import pandas as pd
from .features import rates


AGE_STATS = ('form_age_days', 'season_history_20', 'prior_season_fraction_20')
SHARED_STATS = ('shared_ortg_20', 'shared_drtg_20')
AGE_COLUMNS = tuple(f'{side}_{stat}' for side in ('home', 'away', 'diff') for stat in AGE_STATS) + (
    'diff_prior_season_margin_interaction', 'diff_prior_season_net_interaction')
SHARED_COLUMNS = tuple(f'{side}_{stat}' for side in ('home', 'away', 'diff') for stat in SHARED_STATS)


def shared_rates(own, opp, home_score, away_score):
    """Unknown if either side is absent, mismatched or lacks valid possessions."""
    empty = (np.nan, np.nan)
    if not own or not opp or own.get('points') != home_score or opp.get('points') != away_score:
        return empty
    hp = rates(own, opp, home_score, away_score)['poss']
    ap = rates(opp, own, away_score, home_score)['poss']
    if not (np.isfinite(hp) and np.isfinite(ap) and hp > 0 and ap > 0):
        return empty
    possessions = (hp + ap) / 2
    return 100 * home_score / possessions, 100 * away_score / possessions


def build(base, games, boxes):
    """Return base plus explicit AGE_COLUMNS/SHARED_COLUMNS and provenance."""
    if base.game_id.astype(str).duplicated().any() or games.game_id.astype(str).duplicated().any():
        raise ValueError('Duplicate context game identity')
    if boxes.duplicated(['game_id', 'team_id']).any():
        raise ValueError('Duplicate context team/game box identity')
    if set((*AGE_COLUMNS, *SHARED_COLUMNS, 'context_latest_available_at')) & set(base.columns):
        raise ValueError('Context fields already present; original columns cannot be replaced')
    context = base.copy()
    context.index = context.game_id.astype(str)
    lookup = {(str(r.game_id), str(r.team_id)): r._asdict() for r in boxes.itertuples(index=False)}
    history = defaultdict(lambda: deque(maxlen=20))
    queue = []
    rows = []
    latest = None
    ordered = games.copy()
    ordered['tipoff'] = pd.to_datetime(ordered.tipoff, utc=True)
    for game in ordered.sort_values(['tipoff', 'game_id']).itertuples(index=False):
        game_id = str(game.game_id)
        if game_id not in context.index:
            continue
        original = context.loc[game_id]
        decision = pd.Timestamp(original.decision_at)
        while queue and queue[0][0] < decision:
            available, _, season, tipoff, home, away, hrate, arate = heapq.heappop(queue)
            history[home].append((season, tipoff, hrate, arate))
            history[away].append((season, tipoff, arate, hrate))
            latest = available
        available_inputs = [pd.Timestamp(v) for v in (latest, original.get('latest_input_available_at')) if pd.notna(v)]
        row = {'game_id': game_id, 'context_latest_available_at': max(available_inputs) if available_inputs else pd.NaT}
        for side, team in (('home', str(game.home_id)), ('away', str(game.away_id))):
            records = list(history[team])
            row[f'{side}_form_age_days'] = min(180., max(0., (decision - records[-1][1]).total_seconds()/86400)) if records else np.nan
            row[f'{side}_season_history_20'] = min(20, sum(r[0] == game.season for r in records))
            row[f'{side}_prior_season_fraction_20'] = sum(r[0] < game.season for r in records)/len(records) if records else np.nan
            for stat, index in (('shared_ortg_20', 2), ('shared_drtg_20', 3)):
                values = [r[index] for r in records if np.isfinite(r[index])]
                row[f'{side}_{stat}'] = float(np.mean(values)) if values else np.nan
        for stat in (*AGE_STATS, *SHARED_STATS):
            row[f'diff_{stat}'] = row[f'home_{stat}'] - row[f'away_{stat}']
        hp, ap = row['home_prior_season_fraction_20'], row['away_prior_season_fraction_20']
        row['diff_prior_season_margin_interaction'] = original.home_margin_20 * hp - original.away_margin_20 * ap
        hnet = original.home_ortg_20 - original.home_drtg_20
        anet = original.away_ortg_20 - original.away_drtg_20
        row['diff_prior_season_net_interaction'] = hnet * hp - anet * ap
        rows.append(row)
        if game.completed:
            home, away = str(game.home_id), str(game.away_id)
            own, opp = lookup.get((game_id, home), {}), lookup.get((game_id, away), {})
            hrate, arate = shared_rates(own, opp, game.home_score, game.away_score)
            heapq.heappush(queue, (game.tipoff + pd.Timedelta(hours=24), game_id, game.season,
                                  game.tipoff, home, away, hrate, arate))
    additions = pd.DataFrame(rows)
    if len(additions) != len(base):
        raise ValueError('Not all base rows have matched context schedules')
    # Positional assignment keeps original index, order, dtypes and identifiers.
    additions = additions.set_index('game_id').loc[base.game_id.astype(str)]
    out = base.copy()
    for column in (*AGE_COLUMNS, *SHARED_COLUMNS, 'context_latest_available_at'):
        out[column] = additions[column].to_numpy()
    available = pd.to_datetime(out.context_latest_available_at, utc=True)
    if (available.notna() & available.ge(pd.to_datetime(out.decision_at, utc=True))).any():
        raise AssertionError('Context availability is not strictly pre-decision')
    return out
