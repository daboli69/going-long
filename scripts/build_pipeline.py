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


def pace_factor(team, period):
    early = team.get('periods', {}).get(period, {})
    full, pace = team.get('pace_seconds'), early.get('pace_seconds')
    if not finite(full) or not finite(pace) or min(full, pace) <= 0:
        return 1.0
    n = early.get('pace_n', 0)
    return max(.9, min(1.1, 1 + (full / pace - 1) * n / (n + 100)))


def period_distribution(model, mean_fraction, variance_fraction):
    """Moment-matched baseline, not a claim of independent lognormal increments."""
    if model.get('status') != 'ready' or not finite(model.get('mean')):
        return {'status': 'insufficient', 'n': model.get('n', 0)}
    if model['mean'] < 0 or (model['mean'] == 0 and model.get('sd', 0) > 0):
        return {'status': 'unsupported_nonpositive_mean', 'n': model.get('n', 0)}
    mean = max(0, model['mean'] * mean_fraction)
    sd = model.get('sd', 0) * math.sqrt(variance_fraction)
    out = dict(family=model['family'], mean=mean, sd=sd, n=model['n'], status='ready',
               method='scaled period baseline', mean_fraction=mean_fraction, variance_fraction=variance_fraction)
    if model['family'] == 'poisson':
        out.update({'lambda': mean, 'sd': math.sqrt(mean)})
    elif mean > 0:
        variance = math.log1p((sd / mean)**2)
        out.update(mu_log=math.log(mean)-variance/2, sigma_log=math.sqrt(variance), positive_weight=1, nonpositive=[])
    else:
        out.update(mu_log=None, sigma_log=None, positive_weight=0, nonpositive=[0]*model['n'])
    return out


def competing_first_td(stages):
    """Integrate piecewise constant competing hazards over two unit intervals."""
    probabilities = defaultdict(float)
    survival = 1.0
    for hazards in stages:
        if any(not finite(v) or v < 0 for v in hazards.values()):
            raise ValueError('Hazards must be finite and nonnegative')
        total = sum(hazards.values())
        if total:
            scored = survival * -math.expm1(-total)
            for key, hazard in hazards.items():
                probabilities[key] += scored * hazard / total
            survival *= math.exp(-total)
    probabilities['no_td'] = survival
    return dict(probabilities)


def fair_american(probability):
    if not 0 < probability < 1:
        return None
    return round(-100*probability/(1-probability) if probability >= .5 else 100*(1-probability)/probability)


def first_td_game(game, profiles, features):
    m = game.get('model')
    if not m or not finite(m.get('total_mean')) or not finite(m.get('margin_mean')):
        return None
    stages = [defaultdict(float), defaultdict(float)]
    metadata = {}
    for team, sign in ((game['home'], 1), (game['away'], -1)):
        t = features['nfl']['teams'].get(team, {})
        # 75% of points attributed to offensive TD drives, seven points/drive.
        expected_td = max(0, (m['total_mean'] + sign*m['margin_mean'])/2) * .75 / 7
        available = {pid: p for pid, p in profiles.items() if p['team'] == team and p.get('position') in ('QB','RB','WR','TE','FB') and (datetime.now(timezone.utc).date()-datetime.fromisoformat(p['last_game']).date()).days <= 400}
        scored, opening = {}, {}
        run_mix = 1 - (t.get('opening_pass_rate') if finite(t.get('opening_pass_rate')) else .55)
        for pid, p in available.items():
            f = features['nfl']['players'].get(f'{team}|{pid}', {})
            # Disjoint rush zones; end-zone targets are a separate receiving event.
            carries5 = f.get('goal_line_carries', 0)
            carries10 = max(0, f.get('inside_ten_carries', 0)-carries5)
            carries20 = max(0, f.get('red_zone_carries', 0)-carries5-carries10)
            signal = .4*carries5 + .15*carries10 + .04*carries20 + .3*f.get('end_zone_targets', 0)
            prior = max(0, p.get('stats', {}).get('atd', {}).get('mean', 0))
            scored[pid] = signal/max(1, t.get('games', 12)) + .5*prior
            sh = f.get('shares', {})
            opening[pid] = run_mix*(sh.get('opening_carries') or 0) + (1-run_mix)*(sh.get('opening_targets') or 0)
            metadata[pid] = {'player_id': pid, 'name': p['name'], 'team': team}
        # Reserve mass for unmodeled/new offensive participants; never renormalize
        # only the names offered by the sportsbook.
        total = sum(scored.values())
        open_total = sum(opening.values())
        opening_fraction = max(.15, min(.4, (t.get('opening_snaps', 0)+25)/(t.get('snaps', 0)+100)))
        for stage, share in enumerate((opening_fraction, 1-opening_fraction)):
            offense_mass = expected_td * share
            for pid in available:
                baseline = scored[pid]/total if total else 0
                weight = .65*baseline + .35*opening[pid]/open_total if stage == 0 and open_total and total else baseline
                stages[stage][pid] += offense_mass * .95 * weight
            stages[stage]['other_'+team] += offense_mass * (.05 if total else 1)
            stages[stage]['dst_'+team] += offense_mass * .06/.94
        metadata['other_'+team] = {'name': 'Other offensive scorer', 'team': team}
        metadata['dst_'+team] = {'name': 'Defense / special teams', 'team': team}
    probabilities = competing_first_td(stages)
    return {'status':'ready','method':'two-stage competing hazards baseline','calibrated':False,
            'home':game['home'],'away':game['away'],'kickoff':game['kickoff'],
            'outcomes':{key:dict(metadata.get(key, {'name':'No touchdown'}), probability=p, fair_odds=fair_american(p)) for key,p in probabilities.items()},
            'probability_sum':sum(probabilities.values())}


def build_derivatives(profiles, game_data, features):
    for p in profiles.values():
        team = features['nfl']['teams'].get(p['team'], {})
        for period, suffix, mean_fraction, variance_fraction in (('1H','1h',.49,.5),('Q1','1q',.22,.25)):
            pace = pace_factor(team, period)
            for market in ('pass_yds','rush_yds','rec_yds','receptions','pass_tds','rush_tds','rec_tds'):
                p['stats'][market+'_'+suffix] = period_distribution(p['stats'].get(market, {}), mean_fraction*pace, variance_fraction*pace)
    for sport, games in game_data.items():
        for game in games:
            m = game.get('model')
            if not m:
                continue
            game['period_models'] = {}
            for period, fraction, margin_fraction in (('1H',.52,.5),('Q1',.22,.25)):
                pace = stats.mean(pace_factor(features[sport]['teams'].get(team, {}), period) for team in (game['home'],game['away']))
                game['period_models'][period] = {**m, 'total_mean': m['total_mean']*fraction*pace,
                    'margin_mean':m['margin_mean']*margin_fraction, 'total_sd':m['total_sd']*math.sqrt(fraction*pace) if finite(m.get('total_sd')) else None,
                    'margin_sd':m['margin_sd']*math.sqrt(margin_fraction) if finite(m.get('margin_sd')) else None,
                    'method':'scaled early-pace baseline','calibrated':False,'pace_factor':pace}
    first_td = {g['id']: model for g in game_data['nfl'] if (model := first_td_game(g, profiles, features))}
    features['availability'].update(first_td_probability='baseline: two-stage competing hazards',period_probability='baseline: scaled moments and early pace')
    return {'schema_version':1, 'first_td':first_td,
            'assumptions':{'td_points_fraction':.75,'points_per_td_drive':7,'dst_hazard_share':.06,'other_offense_share':.05,
                           'goal_line_carry_conversion':.4,'inside_ten_carry_conversion':.15,'red_zone_carry_conversion':.04,
                           'end_zone_target_conversion':.3,'opening_usage_weight':.35,'calibrated':False}}


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
    derivatives = build_derivatives(profiles, game_data, features)
    history = load_json(ROOT / 'data/history.json')
    history['betting'] = {'schema_version': 1, 'generated_at': generated, 'window': window, 'minimum_games': minimum,
                          'sources': {'nflreadpy': sources, 'sportsdataverse': 'loaded'}, 'profiles': profiles,
                          'aliases': aliases, 'team_names': team_map, 'games': game_data, 'validation': validation,
                          'features': features, 'derivatives': derivatives}
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
