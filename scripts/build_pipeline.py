#!/usr/bin/env python3
"""NFL/nflreadpy and NCAA/sportsdataverse historical betting baselines.
Preserves history.players for fantasy; see docs/BETTING_MODEL.md.
"""
from __future__ import annotations
import json
import math
import os
import re
import statistics as stats
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
MARKETS = {
    'pass_yds': ('passing_yards', 'lognormal'),
    'rush_yds': ('rushing_yards', 'lognormal'),
    'rec_yds': ('receiving_yards', 'lognormal'),
    'receptions': ('receptions', 'poisson'),
    'pass_tds': ('passing_tds', 'poisson'),
    'rush_tds': ('rushing_tds', 'poisson'),
    'rec_tds': ('receiving_tds', 'poisson'),
    'atd': ('touchdowns', 'poisson'),
}


def normalize_name(name):
    name = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode().lower()
    name = re.sub(r'[^a-z0-9 ]', '', name)
    return re.sub(r'\s+(jr|sr|ii|iii|iv|v)$', '', ' '.join(name.split()))


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def fit_stat(values, family, minimum=5):
    values = [float(v) for v in values if finite(v)]
    n = len(values)
    if not n:
        return {'n': 0, 'status': 'missing'}
    mean, sd = stats.mean(values), stats.stdev(values) if n > 1 else 0.0
    out = {'family': family, 'n': n, 'mean': mean, 'sd': sd,
           'status': 'ready' if n >= minimum else 'insufficient'}
    if family == 'poisson':
        if any(v < 0 or not v.is_integer() for v in values):
            out['status'] = 'invalid_counts'
        out.update({'lambda': mean, 'dispersion': sd * sd / mean if mean > 0 else None})
    else:
        # Preserve zero/negative games as empirical mass; fit positive yards.
        positive = [v for v in values if v > 0]
        out.update(nonpositive=sorted(v for v in values if v <= 0), positive_weight=len(positive) / n)
        if positive:
            pm, ps = stats.mean(positive), stats.stdev(positive) if len(positive) > 1 else 0.0
            out.update(mu_log=math.log(pm) - math.log1p((ps / pm) ** 2) / 2,
                       sigma_log=math.sqrt(math.log1p((ps / pm) ** 2)))
        else:
            out.update(mu_log=None, sigma_log=None)
    return out


def build_profiles(rows, roster, snaps, schedule, window=12, minimum=5):
    metadata = {r['gsis_id']: r for r in roster if r.get('gsis_id')}
    pfr = {r['pfr_id']: r['gsis_id'] for r in roster if r.get('pfr_id') and r.get('gsis_id')}
    dates = {(r.get('season'), r.get('week'), r.get(side)): str(r.get('gameday', ''))
             for r in schedule for side in ('home_team', 'away_team')}
    games = {(r['player_id'], r['season'], r['week']): dict(r) for r in rows
             if r.get('season_type') == 'REG' and r.get('position') in {'QB', 'RB', 'WR', 'TE', 'FB'}}
    for snap in snaps:
        pid = pfr.get(snap.get('pfr_player_id'))
        if not pid or snap.get('game_type') != 'REG' or (snap.get('offense_snaps') or 0) <= 0:
            continue
        meta = metadata[pid]
        if meta.get('position') not in {'QB', 'RB', 'WR', 'TE', 'FB'}:
            continue
        key = (pid, snap['season'], snap['week'])
        if key not in games:
            games[key] = {'player_id': pid, 'season': snap['season'], 'week': snap['week'],
                          'team': snap.get('team'), 'player_display_name': meta.get('full_name'),
                          **{col: 0 for col, _ in MARKETS.values()}, 'special_teams_tds': 0}
    grouped = defaultdict(list)
    for (pid, season, week), r in games.items():
        r['date'] = dates.get((season, week, r.get('team') or r.get('recent_team')), '')
        if not r['date'] or r['date'] > datetime.now(timezone.utc).date().isoformat():
            continue
        tds = [r.get(k) for k in ('rushing_tds', 'receiving_tds', 'special_teams_tds')]
        tds += [r.get(k, 0) for k in ('def_tds', 'fumble_recovery_tds')]
        r['touchdowns'] = sum(tds) if all(finite(v) for v in tds) else None
        grouped[pid].append(r)
    profiles = {}
    for pid, player_games in grouped.items():
        recent = sorted(player_games, key=lambda r: (r['season'], r['week']))[-window:]
        last, meta = recent[-1], metadata.get(pid, {})
        name = meta.get('full_name') or last.get('player_display_name')
        if not name:
            continue
        profiles[pid] = {'id': pid, 'name': name, 'name_key': normalize_name(name),
                         'team': meta.get('team') or last.get('team') or last.get('recent_team'),
                         'position': meta.get('position') or last.get('position'), 'last_game': last['date'],
                         'stats': {market: fit_stat([r.get(column) for r in recent], family, minimum)
                                   for market, (column, family) in MARKETS.items()},
                         'games': [{'season': r['season'], 'week': r['week'], 'date': r['date'],
                                    **{market: r.get(col) for market, (col, _) in MARKETS.items()}} for r in recent]}
    return profiles


def match_player(name, profiles, teams=None):
    from thefuzz.fuzz import ratio
    key = normalize_name(name)
    pool = [p for p in profiles.values() if not teams or p.get('team') in teams]
    ranked = sorted(((ratio(key, p['name_key']), p['id']) for p in pool), reverse=True)
    if not key or not ranked or ranked[0][0] < 92:
        return {'status': 'unmatched', 'player_id': None}
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 7:
        return {'status': 'ambiguous', 'player_id': None}
    return {'status': 'exact' if ranked[0][0] == 100 else 'fuzzy', 'player_id': ranked[0][1], 'score': ranked[0][0]}


def nfl_kickoff(row):
    day, time = str(row.get('gameday') or ''), str(row.get('gametime') or '')
    if not day or not time:
        return None
    return datetime.fromisoformat(f'{day}T{time}').replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc).isoformat()


def normalize_games(rows, sport):
    result = []
    for r in rows:
        if sport == 'nfl':
            if r.get('game_type') != 'REG':
                continue
            hs, aws = r.get('home_score'), r.get('away_score')
            g = {'id': str(r.get('game_id')), 'home': r.get('home_team'), 'away': r.get('away_team'),
                 'kickoff': nfl_kickoff(r), 'spread': -r['spread_line'] if finite(r.get('spread_line')) else None,
                 'total': r.get('total_line'), 'mlHome': r.get('home_moneyline'), 'mlAway': r.get('away_moneyline'),
                 'homeSpreadOdds': r.get('home_spread_odds'), 'awaySpreadOdds': r.get('away_spread_odds'),
                 'overOdds': r.get('over_odds'), 'underOdds': r.get('under_odds')}
        else:
            if r.get('season_type') != 'regular' or not r.get('fbs_game'):
                continue
            hs, aws = r.get('home_points'), r.get('away_points')
            if not r.get('completed'):
                hs = aws = None
            g = {'id': str(r.get('game_id')), 'home': r.get('home_team'), 'away': r.get('away_team'),
                 'kickoff': r.get('start_date'), 'spread': None, 'total': None, 'mlHome': None, 'mlAway': None}
        if not g['kickoff'] or not g['home'] or not g['away']:
            continue
        g.update(sport=sport, season=r.get('season'), homeScore=hs, awayScore=aws,
                 completed=finite(hs) and finite(aws))
        result.append(g)
    return result


def build_game_models(games, window=12, minimum=5):
    history, buckets = defaultdict(list), defaultdict(list)
    errors, output = {'margin': [], 'total': []}, []
    for game in games:
        buckets[game['kickoff']].append(game)
    for kickoff in sorted(buckets):
        pending = []
        for g in buckets[kickoff]:
            h, a = history[g['home']][-window:], history[g['away']][-window:]
            model = None
            if len(h) >= minimum and len(a) >= minimum:
                home = (stats.mean(x[0] for x in h) + stats.mean(x[1] for x in a)) / 2
                away = (stats.mean(x[0] for x in a) + stats.mean(x[1] for x in h)) / 2
                model = {'margin_mean': home - away, 'total_mean': home + away,
                         'home_n': len(h), 'away_n': len(a), 'residual_n': len(errors['margin'])}
                for key in errors:
                    prior = errors[key][-1000:]
                    model[key + '_sd'] = stats.stdev(prior) if len(prior) >= 30 else None
            if not g['completed']:
                output.append({**g, 'model': model})
            else:
                pending.append((g, model))
        # No same-kickoff outcomes influence a prediction in this bucket.
        for g, model in pending:
            if model:
                errors['margin'].append(g['homeScore'] - g['awayScore'] - model['margin_mean'])
                errors['total'].append(g['homeScore'] + g['awayScore'] - model['total_mean'])
            history[g['home']].append((g['homeScore'], g['awayScore']))
            history[g['away']].append((g['awayScore'], g['homeScore']))
    return output, {key: {'n': len(v), 'rmse': math.sqrt(stats.mean(x*x for x in v)) if v else None}
                    for key, v in errors.items()}


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False, default=str), encoding='utf-8')
    temporary.replace(path)


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def build():
    import nflreadpy as nfl
    import sportsdataverse.cfb as cfb
    season = int(os.getenv('SEASON', datetime.now().year))
    window, minimum = int(os.getenv('PROJECTION_WINDOW', '12')), int(os.getenv('PROJECTION_MIN_GAMES', '5'))
    if not 2 <= minimum <= window <= 50:
        raise ValueError('Require 2 <= PROJECTION_MIN_GAMES <= PROJECTION_WINDOW <= 50')
    seasons = list(range(season - 2, season + 1))
    rows, roster, snaps, sources = [], [], [], {}
    for year in seasons:
        try:
            yearly = nfl.load_player_stats([year], summary_level='week').to_dicts()
        except Exception as exc:
            if year != season or not ('404' in str(exc) or 'Season must be between' in str(exc)):
                raise
            sources[str(year)] = 'not_published'
            print(f'[nflreadpy] {year} player stats not published')
            continue
        # Wait for snap counts before using a week's box scores: otherwise
        # zero-stat appearances disappear and bias the trailing mean upward.
        try:
            yearly_snaps = nfl.load_snap_counts([year]).to_dicts()
        except Exception as exc:
            if year != season or '404' not in str(exc):
                raise
            yearly_snaps = []
            print(f'[nflreadpy] {year} snap counts not published; retaining completed prior windows')
        covered_weeks = {r.get('week') for r in yearly_snaps if r.get('game_type') == 'REG'}
        rows.extend(r for r in yearly if r.get('week') in covered_weeks)
        roster.extend(nfl.load_rosters([year]).to_dicts())
        snaps.extend(yearly_snaps)
        sources[str(year)] = 'loaded' if yearly_snaps else 'awaiting_snap_counts'
    if not rows:
        raise RuntimeError('No NFL player statistics loaded')
    if sources.get(str(season)) == 'not_published':
        roster.extend(nfl.load_rosters([season]).to_dicts())
    schedule = nfl.load_schedules(seasons).to_dicts()
    profiles = build_profiles(rows, roster, snaps, schedule, window, minimum)
    if not profiles:
        raise RuntimeError('No profiles built; refusing to replace history')
    # Teams dictionary uses LAR while schedules, rosters and stats use LA.
    codes = {'LAR': 'LA', 'JAC': 'JAX', 'WSH': 'WAS'}
    team_map = {r['team_name']: codes.get(r['team_abbr'], r['team_abbr']) for r in nfl.load_teams().to_dicts()}
    aliases = {}
    odds_snapshot = load_json(ROOT / 'data/nfl_betting.json')
    for prop in odds_snapshot.get('props', []):
        teams = [team_map.get(prop.get(k)) for k in ('homeName', 'awayName')]
        aliases[f"{prop['eventId']}|{normalize_name(prop['player'])}"] = match_player(
            prop['player'], profiles, teams if all(teams) else None)
    for event in load_json(ROOT / 'data/nfl_betting.json').get('props_raw', []):
        teams = [team_map.get(event.get(side)) for side in ('home_team', 'away_team')]
        for book in event.get('bookmakers', []):
            for market in book.get('markets', []):
                for outcome in market.get('outcomes', []):
                    name = outcome.get('description')
                    if name:
                        aliases[f"{event['id']}|{normalize_name(name)}"] = match_player(name, profiles, teams if all(teams) else None)
    game_data, validation = {}, {}
    for sport, games in (('nfl', normalize_games(schedule, 'nfl')),
                         ('ncaa', normalize_games(cfb.load_cfb_schedule(seasons).to_dicts(), 'ncaa'))):
        game_data[sport], validation[sport] = build_game_models(games, window, minimum)
    generated = datetime.now(timezone.utc).isoformat(timespec='seconds')
    from pbp_features import build_public_features, matchup_adjustments
    features = build_public_features(seasons, window)
    matchup_adjustments(features, game_data['nfl'])
    history = load_json(ROOT / 'data/history.json')
    history['betting'] = {'schema_version': 1, 'generated_at': generated, 'window': window, 'minimum_games': minimum,
                          'sources': {'nflreadpy': sources, 'sportsdataverse': 'loaded'}, 'profiles': profiles,
                          'aliases': aliases, 'team_names': team_map, 'games': game_data, 'validation': validation,
                          'features': features}
    config = load_json(ROOT / 'data/data.json')
    config.update(schema_version=1, generated_at=generated, season=season,
                  betting={'window': window, 'minimum_games': minimum, 'kelly_fraction': 0.25,
                           'max_stake_fraction': 0.02, 'max_quote_age_hours': 24,
                           'max_profile_age_days': 400, 'fuzzy_min_score': 92, 'fuzzy_min_margin': 7})
    atomic_json(ROOT / 'data/history.json', history)
    atomic_json(ROOT / 'data/data.json', config)
    print(f'[projections] {len(profiles)} NFL profiles; {sum(len(v) for v in game_data.values())} upcoming games')
    print(f'[walk-forward] {validation}')


if __name__ == '__main__':
    build()
