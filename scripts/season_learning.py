"""Current-season completeness and conservative NFL defensive-memory learning.

This module deliberately keeps two concerns together because both are daily
integrity checks over already-built snapshots.  It does not create a betting
probability.  Defensive estimates are opponent-adjusted role residuals and may
only become a matchup signal when verified current usage maps to the role.
"""
from __future__ import annotations

import json
import math
import os
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from build_pipeline import atomic_json, normalize_games

ROOT = Path(__file__).resolve().parents[1]
ROLE_SPECS = {
    'WR_RECEIVING': ('defense_receiving', 'WR', 'targets', 'adjusted_extra_yards_per_target'),
    'TE_RECEIVING': ('defense_receiving', 'TE', 'targets', 'adjusted_extra_yards_per_target'),
    'RB_RECEIVING': ('defense_receiving', 'RB', 'targets', 'adjusted_extra_yards_per_target'),
    'RB_RUSHING': ('defense_rushing', 'RB', 'carries', 'adjusted_extra_yards_per_carry'),
    'QB_RUSHING': ('defense_rushing', 'QB', 'carries', 'adjusted_extra_yards_per_carry'),
}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def div(a, b):
    return a / b if b else None


def _stamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def completeness(games, results, models, sport, now=None, pbp_game_ids=None, aggregate_teams=None):
    """Compare the authoritative current schedule with durable result/model rows."""
    now = now or datetime.now(timezone.utc)
    expected = [g for g in games if g.get('sport') == sport and g.get('completed') and (_stamp(g.get('kickoff')) or now) < now]
    result_rows = [r for r in (results.get('games') or {}).values() if r.get('sport') == sport]
    actual = {str(r.get('id')): r for r in result_rows}
    ids = [str(g.get('id')) for g in games if g.get('sport') == sport]
    duplicates = sorted({gid for gid in ids if ids.count(gid) > 1})
    missing, source_lag, partial = [], [], []
    for game in expected:
        gid = str(game['id']); row = actual.get(gid)
        if not row:
            age = (now - _stamp(game['kickoff'])).total_seconds() if _stamp(game['kickoff']) else math.inf
            (source_lag if age <= 12 * 3600 else missing).append(gid)
        elif not all(finite(row.get(key)) for key in ('homeScore', 'awayScore')):
            partial.append(gid)
    pbp_ids = {str(x) for x in (pbp_game_ids or [])}
    trace = []
    for game in sorted(expected, key=lambda g: g['kickoff'], reverse=True)[:3]:
        gid = str(game['id'])
        downstream = next((model for model in models if model.get('model') and ({game['home'], game['away']} & {model.get('home'), model.get('away')})), None)
        aggregate = all(team in set(aggregate_teams or []) for team in (game['home'], game['away'])) if aggregate_teams is not None else bool(downstream)
        feature_present = gid in pbp_ids if pbp_game_ids is not None else aggregate
        trace.append({
            'game_id': gid, 'game': f"{game['away']} @ {game['home']}", 'kickoff': game['kickoff'],
            'raw_schedule': True, 'normalized_completed': True, 'result_persisted': gid in actual,
            'play_by_play_present': (gid in pbp_ids) if pbp_game_ids is not None else None,
            'current_aggregate_present': aggregate, 'features_built': feature_present,
            'downstream_team_model_present': bool(downstream), 'model_input_present': aggregate and bool(downstream),
        })
    latest = max((_stamp(g['kickoff']) for g in expected), default=None)
    generated = _stamp(results.get('generated_at'))
    stale = bool(latest and generated and generated < latest)
    status = 'FAILED' if not games else 'PARTIAL' if missing or partial or source_lag else 'STALE' if stale else 'FRESH'
    return {
        'status': status, 'expected_completed': len(expected), 'actually_ingested': len([g for g in expected if str(g['id']) in actual]),
        'missing_game_ids': missing, 'source_lag_game_ids': source_lag, 'partial_game_ids': partial,
        'duplicate_schedule_game_ids': duplicates, 'latest_completed_kickoff': latest.isoformat() if latest else None,
        'results_generated_at': results.get('generated_at'), 'trace': trace,
    }


def dynamic_blend(history_value, current_value, history_n, current_n, stability,
                  recency=.85, structural_decay=1.0, max_current_weight=.90):
    """Evidence-weighted shrinkage; current evidence rises continuously with n."""
    if not all(finite(x) for x in (history_value, current_value, history_n, current_n, stability, recency, structural_decay)):
        raise ValueError('Dynamic blend requires finite inputs')
    if min(history_n, current_n) < 0 or not 0 <= stability <= 1 or not 0 < recency <= 1 or not 0 < structural_decay <= 1:
        raise ValueError('Invalid evidence weight')
    # Historical observations are capped so a large old season cannot swamp
    # accumulating current evidence.  Predictive carryover and verified change
    # determine how much of that prior remains relevant.
    prior_effective = max(6.0, min(history_n, 100.0) * max(.10, stability) * recency * structural_decay)
    current_weight = min(max_current_weight, current_n / (current_n + prior_effective)) if current_n else 0.0
    return {
        'estimate': history_value * (1 - current_weight) + current_value * current_weight,
        'historical_weight': 1 - current_weight, 'current_weight': current_weight,
        'historical_effective_sample': prior_effective,
        'method': 'sample-size shrinkage with OOS carryover, recency and verified structural-change decay',
    }


def _correlation(xs, ys):
    if len(xs) < 8 or len(xs) != len(ys):
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    dx, dy = [x - mx for x in xs], [y - my for y in ys]
    denom = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return sum(x*y for x, y in zip(dx, dy)) / denom if denom else None


def carryover_validation(scopes, family, metric, position=None, max_test_year=None):
    """Chronological prior-season predictions compared with a zero league prior."""
    years = sorted(int(y) for y in scopes)
    pairs, errors_prior, errors_zero = [], [], []
    for prior_year, next_year in zip(years, years[1:]):
        if max_test_year is not None and next_year > max_test_year:
            continue
        prior, nxt = scopes[str(prior_year)].get(family, {}), scopes[str(next_year)].get(family, {})
        common = sorted(k for k in set(prior) & set(nxt) if position is None or k.endswith('|'+position))
        xs = [prior[k].get(metric) for k in common]; ys = [nxt[k].get(metric) for k in common]
        clean = [(x, y) for x, y in zip(xs, ys) if finite(x) and finite(y)]
        if not clean:
            continue
        x, y = zip(*clean); corr = _correlation(x, y)
        pairs.append({'train_season': prior_year, 'test_season': next_year, 'roles': len(clean), 'correlation': corr})
        errors_prior.extend(abs(a-b) for a,b in clean);errors_zero.extend(abs(b) for _,b in clean)
    correlations = [p['correlation'] for p in pairs if finite(p['correlation'])]
    mae_prior = statistics.mean(errors_prior) if errors_prior else None
    mae_zero = statistics.mean(errors_zero) if errors_zero else None
    predictive = finite(mae_prior) and finite(mae_zero) and mae_prior < mae_zero
    raw = statistics.mean(correlations) if correlations else 0
    stability = max(.10, min(.85, raw if predictive else .10))
    return {'pairs': pairs, 'mae_historical_prior': mae_prior, 'mae_league_prior': mae_zero,
            'historical_prior_outperformed': predictive, 'stability': stability,
            'method': 'season N role residual predicts season N+1; chronological only'}


def _standard_error(row, sample_key, metric_key):
    n = row.get(sample_key, 0)
    if n < 2:
        return None
    # Raw residual variance is retained separately from the shrunk mean.
    residual_sum = row.get('residual', 0); residual_sq = row.get('residual_sq', 0)
    variance = max(0, (residual_sq - residual_sum * residual_sum / n) / (n - 1))
    return math.sqrt(variance / n) if variance else max(.20, abs(row.get(metric_key, 0)) / math.sqrt(n))


def classify_status(history, current, blend, sample_key, metric_key):
    """Classify change only after at least two games and a usable role sample."""
    n, games = current.get(sample_key, 0), current.get('games', 0)
    minimum = 20 if sample_key == 'targets' else 15
    se = _standard_error(current, sample_key, metric_key)
    if games < 2 or n < minimum or se is None:
        return 'uncertain', 'low'
    cur, hist, weighted = current[metric_key], history[metric_key], blend['estimate']
    margin = 1.64 * se
    if cur - hist > margin:
        status = 'worsening'
    elif hist - cur > margin:
        status = 'changed' if weighted <= 0 and cur + margin <= 0 else 'improving'
    elif weighted - margin > 0:
        status = 'persisting'
    else:
        status = 'uncertain'
    confidence = 'high' if games >= 6 and n >= minimum * 3 else 'medium' if games >= 3 and n >= minimum * 2 else 'low'
    return status, confidence


def _latest_head_coaches(schedule, season):
    out = {}
    for row in schedule:
        if row.get('season') != season or row.get('game_type') != 'REG':
            continue
        for team, field in ((row.get('home_team'), 'home_coach'), (row.get('away_team'), 'away_coach')):
            if team and row.get(field):
                out[team] = row[field]
    return out


def build_defensive_memory(context, schedule):
    season = int(context['season']); scopes = context.get('scopes', {})
    historical, current = scopes.get(str(season-1), {}), scopes.get(str(season), {})
    previous_coaches = _latest_head_coaches(schedule, season-1)
    staff = context.get('coaches', {}).get('teams', {})
    validations, weaknesses = {}, []
    for role, (family, position, sample_key, metric_key) in ROLE_SPECS.items():
        validations[role] = carryover_validation(scopes, family, metric_key, position, season-1)
        validation = validations[role]
        for key, hist in historical.get(family, {}).items():
            defense, observed_position = key.split('|', 1)
            if observed_position != position or not finite(hist.get(metric_key)) or hist.get(sample_key, 0) < (35 if sample_key == 'carries' else 40) or hist[metric_key] <= 0:
                continue
            cur = current.get(family, {}).get(key, {sample_key: 0, 'games': 0, metric_key: 0, 'residual': 0, 'residual_sq': 0})
            old_hc, new_hc = previous_coaches.get(defense), staff.get(defense, {}).get('head_coach')
            structural_change = bool(old_hc and new_hc and old_hc != new_hc)
            blend = dynamic_blend(hist[metric_key], cur.get(metric_key, 0), hist[sample_key], cur.get(sample_key, 0), validation['stability'], structural_decay=.55 if structural_change else 1)
            status, confidence = classify_status(hist, cur, blend, sample_key, metric_key)
            weaknesses.append({
                'id': f'{defense}|{role}', 'defense': defense, 'historical_weakness': role,
                'current_status': status, 'confidence': confidence,
                'historical': {'season': season-1, 'sample': hist[sample_key], 'games': hist.get('games'), 'value': hist[metric_key],
                               'yards_per_opportunity': hist.get('yards_per_target', hist.get('yards_per_carry')),
                               'explosive_rate': hist.get('explosive_rate'), 'redzone_rate': hist.get('redzone_target_rate', hist.get('redzone_carry_rate')), 'depth': hist.get('depth')},
                'current': {'season': season, 'sample': cur.get(sample_key, 0), 'games': cur.get('games', 0), 'value': cur.get(metric_key, 0),
                            'yards_per_opportunity': cur.get('yards_per_target', cur.get('yards_per_carry')),
                            'explosive_rate': cur.get('explosive_rate'), 'redzone_rate': cur.get('redzone_target_rate', cur.get('redzone_carry_rate')), 'depth': cur.get('depth')},
                'weighted_estimate': blend['estimate'], 'weights': blend,
                'opponent_adjustment': 'same player versus other defenses; 20-opportunity player prior and 50-opportunity defense shrinkage',
                'structural_change': {'verified': structural_change, 'prior_head_coach': old_hc, 'current_head_coach': new_hc,
                                      'prior_decay': .55 if structural_change else 1, 'source': context.get('coaches', {}).get('source')},
                'oos_validation': validation,
                'lineage': ['football_context.scopes', f'{season-1}.{family}.{key}', f'{season}.{family}.{key}'],
            })
    return weaknesses, validations


def build_matchups(context, weaknesses):
    current = context.get('scopes', {}).get(str(context['season']), {})
    as_of = _stamp(context.get('as_of')) or datetime.now(timezone.utc)
    slate_end = as_of + timedelta(days=8)
    by_defense = {}
    for row in weaknesses:
        by_defense.setdefault(row['defense'], []).append(row)
    output = []
    for game in context.get('games', []):
        kickoff = _stamp(game.get('kickoff'))
        if not kickoff or not as_of <= kickoff <= slate_end:
            continue
        for offense, defense in ((game['away'], game['home']), (game['home'], game['away'])):
            for player in current.get('players', {}).values():
                if player.get('team') != offense:
                    continue
                for weakness in by_defense.get(defense, []):
                    role = weakness['historical_weakness']; pos = role.split('_')[0]
                    if player.get('position') != pos:
                        continue
                    receiving = role.endswith('RECEIVING')
                    count = player.get('targets', 0) if receiving else player.get('rush_attempts', 0)
                    share = player.get('target_share') if receiving else player.get('rush_share')
                    mapped = count >= (2 if receiving else 2 if pos == 'QB' else 3) and finite(share) and share >= (.08 if receiving else .05)
                    if not mapped:
                        continue
                    active = weakness['current_status'] in ('persisting', 'worsening') and weakness['confidence'] in ('medium', 'high')
                    output.append({
                        'id': f"{game['id']}|{player['player_id']}|{weakness['id']}", 'game_id': game['id'], 'kickoff': game['kickoff'],
                        'player_id': player['player_id'], 'player': player.get('name'), 'team': offense, 'opponent': defense,
                        'role': role, 'usage': {'games': player.get('games'), 'opportunities': count, 'share': share,
                                              'snap_share': player.get('share'), 'snap_share_type': player.get('share_type')},
                        'status': weakness['current_status'], 'confidence': weakness['confidence'], 'active_signal': active,
                        'plain_language': f"MATCHUP EDGE — {role.replace('_', ' ')}: struggled in {context['season']-1}; {weakness['current_status']} through {context['season']} observations; {player.get('name')}'s current usage maps to the role.",
                        'weakness_id': weakness['id'],
                        'lineage': ['season_learning.matchup_signals', weakness['id'], f"football_context.scopes.{context['season']}.players.{player['player_id']}"]
                    })
    return output


def _coverage_state_from_margin(defense_margin):
    if not finite(defense_margin):
        return None
    if defense_margin >= 8:
        return 'leading_8_plus'
    if defense_margin >= 1:
        return 'leading_1_7'
    if defense_margin <= -8:
        return 'trailing_8_plus'
    if defense_margin <= -1:
        return 'trailing_1_7'
    return 'tied'


def _starting_qb(offense, current, injury):
    depth = [row for row in (injury.get('current_players') or {}).values()
             if row.get('team') == offense and row.get('position') == 'QB'
             and row.get('roster_status') not in ('RES', 'RET', 'DEV')]
    depth.sort(key=lambda row: (row.get('depth_rank') != 1, row.get('role_order', 99), -(row.get('snap_share') or 0)))
    if depth and depth[0].get('gsis_id'):
        return depth[0]['gsis_id'], depth[0].get('name')
    qbs = [row for row in current.get('players', {}).values()
           if row.get('team') == offense and row.get('position') == 'QB']
    qbs.sort(key=lambda row: (-(row.get('pass_snaps') or 0), -(row.get('share') or 0)))
    return (qbs[0].get('player_id'), qbs[0].get('name')) if qbs else (None, None)


def build_coverage_matchups(context, weaknesses, game_models, injury):
    """Create a conditional coverage chain without inferring uncharted shells.

    The projected first-half margin selects a historical score-state bucket.
    Exact participation labels then link the defense's shell tendency, the
    starting QB's positional target split and the already opponent-adjusted
    role weakness.  This affects GOING Score matchup ranking only; it is not
    promoted into a hard yardage/probability projection before OOS validation.
    """
    season = int(context['season']);scopes = context.get('scopes', {})
    current = scopes.get(str(season), {});as_of = _stamp(context.get('as_of')) or datetime.now(timezone.utc)
    slate_end = as_of + timedelta(days=8);by_defense = {}
    for row in weaknesses:
        if row['historical_weakness'].endswith('RECEIVING'):
            by_defense.setdefault(row['defense'], []).append(row)
    models = {str(row.get('id')): row for row in game_models if row.get('id')}
    chart_years = sorted((int(year) for year,scope in scopes.items()
                          if int(year) < season and scope.get('defense_coverage_game_states')), reverse=True)
    output = []
    for game in context.get('games', []):
        kickoff = _stamp(game.get('kickoff'))
        if not kickoff or not as_of <= kickoff <= slate_end:
            continue
        modeled = models.get(str(game.get('id')))
        if not modeled:
            modeled = next((row for row in game_models if row.get('home') == game.get('home') and row.get('away') == game.get('away')
                            and abs((_stamp(row.get('kickoff'))-kickoff).total_seconds()) < 6*3600), None)
        model = (modeled or {}).get('model') or {}
        first_half = ((modeled or {}).get('period_models') or {}).get('1H', {}).get('margin_mean')
        if not finite(first_half) and finite(model.get('margin_mean')):
            first_half = .5*model['margin_mean']
        for offense, defense in ((game['away'],game['home']),(game['home'],game['away'])):
            defense_margin = first_half if defense == game['home'] else -first_half if finite(first_half) else None
            state = _coverage_state_from_margin(defense_margin)
            qb_id, qb_name = _starting_qb(offense,current,injury)
            if not state or not qb_id:
                continue
            chart_year = next((year for year in chart_years
                               if scopes[str(year)].get('defense_coverage_game_states',{}).get(defense,{}).get(state)), None)
            if chart_year is None:
                continue
            scope = scopes[str(chart_year)]
            tendency = scope['defense_coverage_game_states'][defense][state]
            overall = scope.get('defenses',{}).get(defense,{})
            candidates = []
            for shell, values in tendency.get('shells',{}).items():
                if values.get('plays',0) < 15 or not finite(values.get('rate')):
                    continue
                baseline = div(overall.get('shell_'+shell,0),overall.get('shell_n',0))
                candidates.append((values['rate']-(baseline or 0),values['rate'],shell,values,baseline))
            if not candidates:
                continue
            uplift, shell_rate, shell, shell_values, baseline_rate = max(candidates)
            qb_year = next((year for year in chart_years
                            if scopes[str(year)].get('qb_coverage',{}).get(qb_id,{}).get(shell)), None)
            if qb_year is None:
                continue
            qb_scope = scopes[str(qb_year)].get('qb_coverage',{}).get(qb_id,{})
            split, all_split = qb_scope[shell], qb_scope.get('ALL',{})
            for weakness in by_defense.get(defense,[]):
                position = weakness['historical_weakness'].split('_')[0]
                target_rate = split.get('target_rate_by_position',{}).get(position)
                overall_rate = all_split.get('target_rate_by_position',{}).get(position)
                if not finite(target_rate):
                    continue
                allowed = scope.get('defense_coverage_receiving',{}).get(f'{defense}|{shell}|{position}',{})
                beneficiaries = [p for p in current.get('players',{}).values()
                                 if p.get('team') == offense and p.get('position') == position
                                 and p.get('targets',0) >= 2 and finite(p.get('target_share')) and p['target_share'] >= .08]
                base_active = weakness['current_status'] in ('persisting','worsening') and weakness['confidence'] in ('medium','high')
                state_supported = tendency.get('status') == 'observed' and shell_values.get('plays',0) >= 15
                qb_supported = split.get('status') == 'observed'
                coverage_weak = allowed.get('status') == 'observed' and allowed.get('adjusted_extra_yards_per_target',0) > .15
                target_lift = target_rate-(overall_rate if finite(overall_rate) else target_rate)
                active = base_active and state_supported and qb_supported and (target_lift >= .02 or coverage_weak)
                conditional = None
                if active:
                    conditional = max(-2,min(2,weakness['weighted_estimate']+4*target_lift+.25*(allowed.get('adjusted_extra_yards_per_target') or 0)))
                state_label = state.replace('_',' ')
                output.append({
                    'id': f"{game['id']}|{qb_id}|{defense}|{shell}|{position}", 'game_id': game['id'], 'kickoff': game['kickoff'],
                    'player_id': qb_id, 'qb_id': qb_id, 'qb': qb_name, 'team': offense, 'opponent': defense, 'role': weakness['historical_weakness'],
                    'projected_game_state': {'period':'1H','defense_margin':defense_margin,'bucket':state},
                    'coverage_tendency': {'season':chart_year,'shell':shell,'rate':shell_rate,'plays':shell_values['plays'],
                                          'state_dropbacks':tendency['dropbacks'],'state_games':tendency['games'],
                                          'overall_rate':baseline_rate,'rate_lift':uplift,'status':tendency['status']},
                    'qb_tendency': {'season':qb_year,'shell':shell,'position':position,'target_rate':target_rate,
                                    'overall_target_rate':overall_rate,'rate_lift':target_lift,'dropbacks':split.get('dropbacks',0),
                                    'targets':split.get('targets',0),'games':split.get('games',0),'status':split.get('status')},
                    'defense_role_weakness': {'id':weakness['id'],'status':weakness['current_status'],'confidence':weakness['confidence'],
                                              'weighted_estimate':weakness['weighted_estimate']},
                    'coverage_role_results': {'season':chart_year,'targets':allowed.get('targets',0),'games':allowed.get('games',0),
                                              'yards_per_target':allowed.get('yards_per_target'),
                                              'adjusted_extra_yards_per_target':allowed.get('adjusted_extra_yards_per_target'),
                                              'status':allowed.get('status','unavailable')},
                    'beneficiaries': [{'player_id':p.get('player_id'),'player':p.get('name'),'targets':p.get('targets'),
                                       'target_share':p.get('target_share')} for p in beneficiaries],
                    'active_signal':active,'confidence':'high' if active and tendency['dropbacks']>=80 and split.get('dropbacks',0)>=60 else 'medium' if active else 'low',
                    'conditional_strength':conditional,
                    'plain_language': f"{defense} used {shell.replace('_',' ')} on {shell_rate:.0%} of charted {chart_year} snaps while {state_label}; GOING projects a {defense_margin:+.1f} first-half margin. {qb_name} targeted {position}s on {target_rate:.0%} of charted {shell.replace('_',' ')} targets in {qb_year}. {defense}'s {position} weakness is {weakness['current_status']}.",
                    'projection_adjustment':'not_promoted: conditional coverage signal awaits chronological OOS validation',
                    'weakness_id':weakness['id'],
                    'lineage':[f'football_context.scopes.{chart_year}.defense_coverage_game_states.{defense}.{state}',
                               f'football_context.scopes.{qb_year}.qb_coverage.{qb_id}.{shell}',
                               f'football_context.scopes.{chart_year}.defense_coverage_receiving.{defense}|{shell}|{position}',
                               f'season_learning.defensive_weaknesses.{weakness["id"]}']})
    return output


def update_evaluation_log(previous, matchups, context):
    now = datetime.now(timezone.utc); current_ids = {row['id'] for row in matchups}
    # Keep current-slate forecasts plus any already-started or settled historical
    # record.  Superseded future schedule projections are not OOS observations.
    log = {key: value for key, value in dict((previous or {}).get('evaluation_log', {})).items()
           if key in current_ids or value.get('outcome') is not None or ((_stamp(value.get('prediction', {}).get('kickoff')) or now) <= now)}
    completed = context.get('scopes', {}).get(str(context['season']), {}).get('player_game_usage', {})
    for row in matchups:
        log.setdefault(row['id'], {'prediction': row, 'model_version': 'defensive-memory-1', 'recorded_at': datetime.now(timezone.utc).isoformat(), 'outcome': None})
    for entry in log.values():
        prediction = entry.get('prediction', {}); key = f"{prediction.get('game_id')}|{prediction.get('player_id')}"
        if entry.get('outcome') is None and key in completed:
            entry['outcome'] = completed[key]
    return log


def build():
    import nflreadpy as nfl
    import sportsdataverse.cfb as cfb
    season = int(os.getenv('SEASON', datetime.now().year)); now = datetime.now(timezone.utc)
    context = json.loads((ROOT/'data/football_context.json').read_text())
    results = json.loads((ROOT/'data/results.json').read_text())
    history = json.loads((ROOT/'data/history.json').read_text()).get('betting', {})
    path = ROOT/'data/season_learning.json'; previous = json.loads(path.read_text()) if path.exists() else {}
    injury_path = ROOT/'data/injury_context.json'; injury = json.loads(injury_path.read_text()) if injury_path.exists() else {}
    schedules, raw_schedule, sources = {}, {}, {}
    for sport, loader in (('nfl', nfl.load_schedules), ('ncaa', cfb.load_cfb_schedule)):
        try:
            raw = loader([season]).to_dicts();raw_schedule[sport] = raw;schedules[sport] = normalize_games(raw, sport)
            sources[sport] = {'status': 'loaded', 'rows': len(raw), 'checked_at': now.isoformat()}
        except Exception as exc:
            schedules[sport] = [];raw_schedule[sport] = []
            sources[sport] = {'status': 'failed', 'reason': type(exc).__name__, 'checked_at': now.isoformat()}
    nfl_models = history.get('games', {}).get('nfl', []); ncaa_models = history.get('games', {}).get('ncaa', [])
    pbp_ids = {key.split('|', 1)[0] for key in context.get('scopes', {}).get(str(season), {}).get('player_game_usage', {})}
    audits = {
        'nfl': completeness(schedules['nfl'], results, nfl_models, 'nfl', now, pbp_ids, context.get('scopes', {}).get(str(season), {}).get('teams', {}).keys()),
        'ncaa': completeness(schedules['ncaa'], results, ncaa_models, 'ncaa', now),
    }
    audits['ncaa']['supported_universe'] = 'FBS regular-season games only'
    weaknesses, validation = build_defensive_memory(context, raw_schedule['nfl'])
    matchups = build_matchups(context, weaknesses)
    coverage_matchups = build_coverage_matchups(context, weaknesses, nfl_models, injury)
    result = {
        'schema_version': 2, 'model_version': 'defensive-memory-coverage-2', 'generated_at': now.isoformat(), 'season': season,
        'sources': sources, 'completeness': audits, 'carryover_validation': validation,
        'defensive_weaknesses': weaknesses, 'matchup_signals': matchups, 'coverage_matchup_signals': coverage_matchups,
        'unsupported_granularity': ['WR slot/outside', 'TE slot/inline', 'current-season exact coverage shells'],
        'unsupported_reason': 'Current public participation/alignment charting is unavailable in-season. Conditional shell signals use the latest exact historical charting and never infer a current shell.',
        'evaluation_log': update_evaluation_log(previous, matchups, context),
        'coverage_evaluation_log': update_evaluation_log({'evaluation_log':previous.get('coverage_evaluation_log',{})}, coverage_matchups, context),
        'method': 'Historical weaknesses use opponent-adjusted role production. Current observations gain weight continuously with real opportunities and OOS carryover stability. A single game cannot change status. Conditional coverage selects an exact historical defensive shell bucket from the projected first-half score state, then requires a supported QB positional target split and a persisting role weakness. It changes matchup ranking only until chronological OOS validation supports a projection adjustment.',
    }
    atomic_json(path, result)
    print('Season learning', {k: (v['expected_completed'], v['actually_ingested'], v['status']) for k,v in audits.items()}, f'{len(weaknesses)} weaknesses, {sum(x["active_signal"] for x in matchups)} active role signals, {sum(x["active_signal"] for x in coverage_matchups)} active coverage signals')
    if any(v['status'] == 'FAILED' for v in audits.values()):
        raise RuntimeError('A current-season schedule source failed; report retained with explicit failure state')


if __name__ == '__main__':
    build()
