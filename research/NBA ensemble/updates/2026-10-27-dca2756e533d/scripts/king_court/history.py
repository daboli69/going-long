"""Two-level recency, experience priors and separate role/production evidence."""
from collections import defaultdict
import math
import numpy as np

from .common import utc


def weighted(values, weights, fallback=0.):
    total = float(np.sum(weights))
    return float(np.average(values, weights=weights)) if total > 0 else float(fallback)


def effective_n(weights):
    w = np.array(weights, dtype=float)
    return float(w.sum() ** 2 / np.dot(w, w)) if len(w) and np.dot(w, w) else 0.


def recency_weights(rows, origin, season, parameters, variant='recency'):
    if variant not in ('recency', 'current_only', 'equal_history'):
        raise ValueError('Unknown history variant')
    anchors = {}
    for row in rows:
        s, tip = row['season'], utc(row['tipoff'])
        if not season-3<=s<=season or tip>=origin:
            continue
        anchors[s] = max(anchors.get(s, tip), tip)
    anchors[season] = origin
    result = []
    for row in rows:
        s, tip = row['season'], utc(row['tipoff'])
        if not season - 3 <= s <= season or tip >= origin:
            result.append(0.)
        elif variant == 'current_only':
            result.append(float(s == season))
        elif variant == 'equal_history':
            result.append(1.)
        else:
            days = max(0., (anchors[s] - tip).total_seconds() / 86400)
            result.append(parameters['season_decay'] ** (season - s) * 2 ** (-days / parameters['game_half_life_days']))
    return np.array(result)


def flatten(games):
    rows = []
    for g in games:
        for p in g['players']:
            rows.append(dict(p, season=g['season'], tipoff=g['tipoff'], game_id=g['game_id']))
    return rows


def _summary(rows, w):
    total = float(w.sum())
    seasons = defaultdict(float)
    for row, weight in zip(rows, w):
        seasons[str(row['season'])] += float(weight)
    return dict(games=len(rows), effective_sample_size=effective_n(w),
                season_weight_shares={s: v / total for s, v in sorted(seasons.items())} if total else {})


def _aggregate(rows, weights):
    keys = ('minutes', 'pts', 'reb', 'ast', 'fgm', 'fga', 'tpm', 'tpa', 'ftm', 'fta', 'oreb', 'dreb')
    return {k: float(sum(row[k] * w for row, w in zip(rows, weights))) for k in keys}


def player_profile(player, rows, origin, season, parameters, debut_seasons, variant='recency'):
    own = [r for r in rows if r['player_id'] == player['player_id']]
    if any(r['season']<player['debut_season'] for r in own):
        raise ValueError('Player history predates verified NBA debut')
    w = recency_weights(own, origin, season, parameters, variant)
    current_own = [r for r in own if r['season'] == season]
    experience = season - player['debut_season']
    appearance = sum(r['minutes'] > 0 for r in current_own)
    # Stage-matched historical experience cohorts. Missing debut metadata stays unknown.
    stage_width = 5
    stage = appearance // stage_width
    counts = defaultdict(int)
    cohort = []
    for row in sorted(rows, key=lambda r: r['tipoff']):
        key = row['player_id'], row['season']
        index = counts[key]
        if row['minutes'] > 0:
            counts[key] += 1
        debut = debut_seasons.get(row['player_id'])
        if (row['player_id'] != player['player_id'] and debut is not None
                and ((experience<2 and row['season']-debut==experience) or (experience>=2 and row['season']-debut>=2))
                and (row['position'] == player['position'] or player['position'] == 'UNKNOWN')
                and (experience >= 2 or index // stage_width == stage)):
            cohort.append(row)
    prior_kind = 'experience_position_stage_matched'
    if len(cohort) < 20:
        cohort = [r for r in rows if r['player_id'] != player['player_id'] and r['position'] == player['position']]
        prior_kind = 'position_league_fallback_insufficient_experience_cohort'
    if not cohort:
        cohort = [r for r in rows if r['player_id'] != player['player_id']]
        prior_kind = 'league_fallback_no_position_cohort'
    cw = recency_weights(cohort, origin, season, parameters, variant)
    if not cw.sum():
        raise ValueError('No eligible league/cohort evidence for player prior')
    base = _aggregate(cohort, cw / cw.sum())
    own_stats = _aggregate(own, w)
    strength = parameters['prior_games']
    combined = {k: own_stats[k] + strength * base[k] for k in base}
    if combined['minutes'] <= 0:
        raise ValueError('No minutes exposure in player prior')
    positive = [r for r in own if r['team'] == player['team'] and r['season'] == season]
    role_w = recency_weights(positive, origin, season, parameters, variant)
    # Past-team minutes never set the current-team rotation.
    role_prior_mean = base['minutes']
    role_total = float(role_w.sum()) + strength
    mean_minutes = (sum(r['minutes'] * v for r, v in zip(positive, role_w)) + strength * role_prior_mean) / role_total
    cohort_variance = weighted([(r['minutes'] - role_prior_mean) ** 2 for r in cohort], cw, 0)
    variance = (sum(v * (r['minutes'] - mean_minutes) ** 2 for r, v in zip(positive, role_w)) + strength * cohort_variance) / role_total
    minutes_source = 'shrunk_current_team_current_season_role'
    if 'expected_minutes' in player:
        mean_minutes, variance = player['expected_minutes']['mean'], player['expected_minutes']['sd'] ** 2
        minutes_source = 'explicit_pregame_scenario:' + player['expected_minutes']['source']
    if player['availability'] == 'out':
        mean_minutes = variance = 0.

    def fraction(a, b, fallback):
        return combined[a] / combined[b] if combined[b] > 0 else fallback

    two_a = combined['fga'] - combined['tpa']
    two_m = combined['fgm'] - combined['tpm']
    rates = {k: combined[k] / combined['minutes'] for k in ('fga', 'fta', 'oreb', 'dreb', 'ast')}
    probabilities = dict(three_share=fraction('tpa', 'fga', .3),
                         p2=two_m / two_a if two_a else .5,
                         p3=fraction('tpm', 'tpa', .33), pft=fraction('ftm', 'fta', .75))
    exposures = dict(fga=combined['fga'], fta=combined['fta'],
                     three_share=combined['fga'], p2=two_a, p3=combined['tpa'], pft=combined['fta'])
    recent = positive[-5:]
    previous = positive[-20:-5]

    def trend_sample(rs):
        minutes = sum(r['minutes'] for r in rs)
        return dict(n=len(rs), minutes_per_game=float(np.mean([r['minutes'] for r in rs])) if rs else None,
                    attempts_per_minute=sum(r['fga'] + .44*r['fta'] for r in rs)/minutes if minutes else None,
                    pra_per_minute=sum(r['pts'] + r['reb'] + r['ast'] for r in rs)/minutes if minutes else None,
                    field_goal_pct=sum(r['fgm'] for r in rs)/sum(r['fga'] for r in rs) if sum(r['fga'] for r in rs) else None)
    trend = dict(recent=trend_sample(recent), earlier=trend_sample(previous),
                 interpretation='Descriptive role/opportunity/conversion changes; no extra trend multiplier')
    trend['status'] = 'insufficient_comparison_games'
    if len(recent) >= 3 and len(previous) >= 3:
        trend['status'] = 'minutes_up' if trend['recent']['minutes_per_game'] > trend['earlier']['minutes_per_game'] else 'minutes_flat_or_down'
    season_average = np.mean([r['pts']+r['reb']+r['ast'] for r in current_own]) if current_own else None
    return dict(player_id=player['player_id'], name=player['name'], team=player['team'], game_id=player['game_id'],
                availability=player['availability'], selectable=player.get('selectable', False),
                experience='rookie' if experience == 0 else 'second_year' if experience == 1 else 'established',
                minutes_mean=float(mean_minutes), minutes_sd=math.sqrt(max(0, variance)),
                minutes_source=minutes_source, rates=rates, probabilities=probabilities, exposures=exposures,
                weighted_pra_per_minute=(combined['pts'] + combined['reb'] + combined['ast']) / combined['minutes'],
                evidence=_summary(own, w), role_evidence=_summary(positive, role_w),
                prior=dict(kind=prior_kind, cohort_player_games=len(cohort), pseudo_games=strength,
                           own_rate_evidence_share=own_stats['minutes']/combined['minutes']),
                trend=trend, season_average_pra=float(season_average) if season_average is not None else None)


def team_features(g, code):
    opponent = g['away'] if code == g['home'] else g['home']
    a, b = g['teams'][code], g['teams'][opponent]
    poss_a = a['fga'] - a['oreb'] + a['tov'] + .44*a['fta']
    poss_b = b['fga'] - b['oreb'] + b['tov'] + .44*b['fta']
    possessions = .5 * (poss_a + poss_b)
    if possessions <= 0:
        raise ValueError('Invalid possession proxy')
    own_misses = a['fga'] - a['fgm'] + a['fta'] - a['ftm']
    opp_misses = b['fga'] - b['fgm'] + b['fta'] - b['ftm']
    return dict(pace48=possessions * 48 / g['game_minutes'], fga_poss=a['fga']/possessions,
                fta_poss=a['fta']/possessions, p2=(a['fgm']-a['tpm'])/max(1,a['fga']-a['tpa']),
                p3=a['tpm']/max(1,a['tpa']), pft=a['ftm']/max(1,a['fta']),
                ast_fgm=a['ast']/max(1,a['fgm']), oreb_miss=a['oreb']/max(1,own_misses),
                dreb_oppmiss=a['dreb']/max(1,opp_misses),
                allowed_fga_poss=b['fga']/possessions, allowed_fta_poss=b['fta']/possessions,
                allowed_p2=(b['fgm']-b['tpm'])/max(1,b['fga']-b['tpa']),
                allowed_p3=b['tpm']/max(1,b['tpa']), allowed_pft=b['ftm']/max(1,b['fta']),
                allowed_ast_fgm=b['ast']/max(1,b['fgm']), offensive_rating=100*a['pts']/possessions,
                defensive_rating=100*b['pts']/possessions)


def context_profiles(games, origin, season, parameters, variant='recency'):
    records = []
    for g in games:
        for code in (g['home'], g['away']):
            records.append(dict(season=g['season'], tipoff=g['tipoff'], team=code, **team_features(g, code)))
    all_w = recency_weights(records, origin, season, parameters, variant)
    if not all_w.sum():
        raise ValueError('No team context history')
    keys = list(team_features(games[0], games[0]['home']))
    league = {k: weighted([r[k] for r in records], all_w) for k in keys}
    league_var = weighted([(r['pace48']-league['pace48'])**2 for r in records], all_w)
    result = {}
    for code in {r['team'] for r in records}:
        selected = [r for r in records if r['team'] == code]
        w = recency_weights(selected, origin, season, parameters, variant)
        prior = parameters['prior_games']
        values = {k: (sum(r[k]*v for r,v in zip(selected,w)) + prior*league[k])/(w.sum()+prior) for k in keys}
        values['pace_sd'] = math.sqrt((sum(v*(r['pace48']-values['pace48'])**2 for r,v in zip(selected,w)) + prior*league_var)/(w.sum()+prior))
        values['evidence'] = _summary(selected,w)
        result[code] = values
    game_rows = [dict(season=g['season'], tipoff=g['tipoff']) for g in games]
    gw = recency_weights(game_rows,origin,season,parameters,variant)
    ot_distribution = defaultdict(float)
    for g,w in zip(games,gw):
        ot_distribution[(g['game_minutes']-48)//5] += float(w)
    return result, {int(k): v/sum(ot_distribution.values()) for k,v in ot_distribution.items()}


def build_profiles(slate, games, parameters, debut_seasons=None, variant='recency'):
    origin, season = utc(slate['origin']), slate['season']
    rows = flatten(games)
    debut_seasons = dict(debut_seasons or {})
    for p in slate['players']:
        debut_seasons[p['player_id']] = p['debut_season']
    profiles = [player_profile(p,rows,origin,season,parameters,debut_seasons,variant) for p in slate['players']]
    teams, overtime = context_profiles(games,origin,season,parameters,variant)
    for g in slate['games']:
        if g['home'] not in teams or g['away'] not in teams:
            raise ValueError('Missing team history; no numerical matchup invented')
    return profiles, teams, overtime
