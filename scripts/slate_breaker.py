"""DraftKings Slate Breaker research.

Combines the existing First TD probabilities (who) with a chronologically
trained distribution for elapsed game time of the first touchdown (when).
Kickoff timestamps never enter the competition calculation.
"""
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'slate-breaker-1'
BIN_SECONDS = 60
MAX_SECONDS = 4200
PRIOR_PER_BIN = .25


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def elapsed_game_seconds(row):
    """Elapsed game clock, independent of wall-clock kickoff time."""
    quarter, clock = row.get('qtr'), row.get('quarter_seconds_remaining')
    if finite(quarter) and finite(clock) and quarter >= 1 and clock >= 0:
        quarter = int(quarter)
        length = 900 if quarter <= 4 else 600
        if clock <= length:
            return min(MAX_SECONDS - 1, (quarter - 1) * 900 + (length - clock) if quarter <= 4
                       else 3600 + (quarter - 5) * 600 + (600 - clock))
    remaining = row.get('game_seconds_remaining')
    if finite(remaining) and 0 <= remaining <= 3600:
        return int(3600 - remaining)
    return None


def first_td_event(row):
    """One real TD event with every selection it can credit under the rules."""
    if (row.get('touchdown') != 1 or row.get('no_play') == 1 or row.get('play_type') == 'no_play'
            or row.get('play_deleted') == 1 or row.get('two_point_attempt') == 1):
        return None
    elapsed, team, player = elapsed_game_seconds(row), row.get('td_team'), row.get('td_player_id')
    if elapsed is None or not team:
        return None
    if row.get('kickoff_attempt') == 1 or row.get('punt_attempt') == 1:
        kind, owners = 'return', [x for x in (player, 'dst_' + team) if x]
    elif team != row.get('posteam'):
        kind, owners = 'defense', ['dst_' + team]
    else:
        kind, owners = 'offense', [player] if player else []
    return {'event_id': f"{row.get('game_id')}:{row.get('play_id')}", 'game_id': str(row.get('game_id')),
            'elapsed_seconds': int(elapsed), 'team': team, 'player_id': player, 'kind': kind,
            'eligible_selection_ids': owners}


def game_records(rows, schedules):
    """Return one chronological first-TD observation per completed REG game."""
    games = {str(g.get('game_id')): g for g in schedules if g.get('game_type') == 'REG'}
    first = {}
    seen = set()
    for row in rows:
        gid = str(row.get('game_id'))
        if gid not in games:
            continue
        seen.add(gid)
        event = first_td_event(row)
        if event and (gid not in first or (event['elapsed_seconds'], str(event['event_id'])) <
                      (first[gid]['elapsed_seconds'], str(first[gid]['event_id']))):
            first[gid] = event
    output = []
    for gid in seen:
        game = games[gid]
        if not finite(game.get('home_score')) or not finite(game.get('away_score')):
            continue
        output.append({'game_id': gid, 'date': str(game.get('gameday'))[:10],
                       'total': game.get('total_line') if finite(game.get('total_line')) else None,
                       'event': first.get(gid), 'elapsed_seconds': first.get(gid, {}).get('elapsed_seconds')})
    return sorted(output, key=lambda r: (r['date'], r['game_id']))


def empirical_bins(times):
    bins = MAX_SECONDS // BIN_SECONDS
    counts = [PRIOR_PER_BIN] * bins
    for value in times:
        counts[min(bins - 1, max(0, int(value) // BIN_SECONDS))] += 1
    total = sum(counts)
    return [x / total for x in counts]


def adjusted_bins(base, total, mean_total, beta):
    alpha = (total / mean_total) ** beta if finite(total) and finite(mean_total) and min(total, mean_total) > 0 else 1
    survival, output = 1.0, []
    tail = 1.0
    for probability in base:
        next_tail = max(0.0, tail - probability)
        current = survival
        survival = next_tail ** alpha if next_tail else 0.0
        output.append(max(0.0, current - survival))
        tail = next_tail
    output[-1] += 1 - sum(output)
    return output


def seconds_pmf(bins):
    return [p / BIN_SECONDS for p in bins for _ in range(BIN_SECONDS)]


def cdf_probability(bins, seconds):
    complete, partial = divmod(max(0, seconds), BIN_SECONDS)
    return sum(bins[:complete]) + (bins[complete] * partial / BIN_SECONDS if complete < len(bins) else 0)


def percentile_seconds(bins, target=.5):
    running = 0.0
    for index, probability in enumerate(bins):
        if running + probability >= target:
            fraction = (target - running) / probability if probability else 0
            return round((index + fraction) * BIN_SECONDS)
        running += probability
    return MAX_SECONDS


def evaluate_time_models(records, minimum_training=400):
    """Walk forward without letting a game inform its own prediction."""
    candidates = {'empirical': 0.0, 'total_adjusted': 1.0}
    metrics = {name: {'log_loss': 0.0, 'brier': 0.0, 'n': 0,
                      'calibration': {str(t): {'predicted': 0.0, 'actual': 0} for t in (300, 600, 900)}}
               for name in candidates}
    prior_times, prior_totals = [], []
    first_test_date = None
    for record in sorted(records, key=lambda r: (r['date'], r['game_id'])):
        observed = record.get('elapsed_seconds')
        if observed is None:
            continue
        if len(prior_times) >= minimum_training:
            first_test_date = first_test_date or record['date']
            base, mean_total = empirical_bins(prior_times), sum(prior_totals) / len(prior_totals) if prior_totals else None
            observed_bin = min(len(base) - 1, int(observed) // BIN_SECONDS)
            for name, beta in candidates.items():
                forecast = adjusted_bins(base, record.get('total'), mean_total, beta)
                metric = metrics[name]
                metric['log_loss'] += -math.log(max(1e-12, forecast[observed_bin]))
                for threshold in (300, 600, 900):
                    probability = cdf_probability(forecast, threshold)
                    actual = int(observed <= threshold)
                    metric['brier'] += (probability - actual) ** 2 / 3
                    metric['calibration'][str(threshold)]['predicted'] += probability
                    metric['calibration'][str(threshold)]['actual'] += actual
                metric['n'] += 1
        prior_times.append(observed)
        if finite(record.get('total')):
            prior_totals.append(record['total'])
    for metric in metrics.values():
        n = metric['n']
        if n:
            metric['log_loss'] /= n
            metric['brier'] /= n
            for item in metric['calibration'].values():
                item['predicted'] /= n
                item['observed'] = item.pop('actual') / n
            metric['calibration_error'] = sum(abs(x['predicted'] - x['observed']) for x in metric['calibration'].values()) / 3
    baseline, adjusted = metrics['empirical'], metrics['total_adjusted']
    # Complexity must earn its place on both sharpness and calibration.
    selected = ('total_adjusted' if adjusted['n'] and adjusted['log_loss'] < baseline['log_loss'] - .002
                and adjusted['brier'] <= baseline['brier'] + .001 else 'empirical')
    return {'method': 'chronological expanding-window conditional first-TD time', 'first_test_date': first_test_date,
            'last_test_date': max((r['date'] for r in records), default=None), 'models': metrics,
            'selected': selected, 'selection_rule': 'Adjusted must improve log loss by >0.002 without worsening Brier by >0.001.'}


def fastest_factors(game_forecasts):
    """P(game has the fastest first TD | that game has a first TD); ties win."""
    survivals = {}
    for game_id, forecast in game_forecasts.items():
        running, survival = 0.0, [0.0] * len(forecast['pmf'])
        for second in range(len(forecast['pmf']) - 1, -1, -1):
            running += forecast['pmf'][second]
            survival[second] = running
        survivals[game_id] = survival
    factors = {}
    for game_id, forecast in game_forecasts.items():
        target = forecast['pmf']
        value = 0.0
        for second, probability in enumerate(target):
            if not probability:
                continue
            competitors = 1.0
            for other_id, other in game_forecasts.items():
                if other_id == game_id:
                    continue
                no_td = other['no_td_probability']
                competitors *= no_td + (1 - no_td) * survivals[other_id][second]
            value += probability * competitors
        factors[game_id] = value
    return factors


def position_priors(events, rosters):
    positions = {}
    for row in rosters:
        if row.get('gsis_id') and row.get('position'):
            positions[row['gsis_id']] = row['position']
    counts = Counter(positions.get(e.get('player_id')) for e in events if e.get('kind') == 'offense')
    eligible = ('QB', 'RB', 'FB', 'WR', 'TE')
    total = sum(counts[p] + 1 for p in eligible)
    return {p: (counts[p] + 1) / total for p in eligible}


def recent_return_shares(rows, teams, active_ids):
    games = defaultdict(dict)
    for row in rows:
        team, gid, date = row.get('return_team'), str(row.get('game_id')), str(row.get('game_date') or '')[:10]
        if team in teams and gid and date:
            games[team][gid] = date
    windows = {team: set(sorted(team_games, key=team_games.get)[-12:]) for team, team_games in games.items()}
    counts = defaultdict(Counter)
    for row in rows:
        team, gid = row.get('return_team'), str(row.get('game_id'))
        player = row.get('kickoff_returner_player_id') or row.get('punt_returner_player_id')
        if team in teams and gid in windows.get(team, set()) and player in active_ids:
            counts[team][player] += 1
    return counts


def build_selections(games, first_td, roster, events, return_counts, priors):
    latest = {}
    for row in roster:
        pid = row.get('gsis_id')
        if pid:
            latest[(row.get('team'), pid)] = row
    positions = {'QB', 'RB', 'FB', 'WR', 'TE'}
    active = {team: {pid: row for (club, pid), row in latest.items() if club == team and row.get('status') == 'ACT'
                     and row.get('position') in positions} for team in {t for g in games for t in (g['home'], g['away'])}}
    inactive = sorted({row.get('full_name') for row in latest.values() if row.get('team') in active
                       and row.get('position') in positions and row.get('status') != 'ACT' and row.get('full_name')})
    dst_events = [e for e in events if e['kind'] in ('return', 'defense')]
    return_fraction = ((sum(e['kind'] == 'return' for e in dst_events) + 2) / (len(dst_events) + 10)) if dst_events else .2
    selections, components = [], {}
    for game in games:
        model = first_td[game['id']]
        outcomes = model['outcomes']
        for team in (game['away'], game['home']):
            team_active = active.get(team, {})
            missing = [row for pid, row in team_active.items() if pid not in outcomes]
            other_probability = outcomes.get('other_' + team, {}).get('probability', 0)
            position_counts = Counter(row.get('position') for row in missing)
            weights = {row['gsis_id']: priors.get(row.get('position'), 0) / position_counts[row.get('position')]
                       for row in missing if position_counts[row.get('position')]}
            scale = sum(weights.values())
            for pid, row in team_active.items():
                probability = outcomes.get(pid, {}).get('probability')
                source = 'existing_first_td'
                evidence = ['Existing two-stage competing-hazards First TD estimate.']
                if probability is None:
                    probability = other_probability * weights.get(pid, 0) / scale if scale else 0
                    source = 'reserved_other_mass'
                    evidence = ['Allocated from the existing team other-scorer reserve using league first-TD position frequency; no individual NFL usage history is available.']
                component_id = f"{game['id']}:offense:{pid}"
                components[component_id] = {'probability': probability, 'owners': [pid], 'kind': source}
                selections.append({'id': pid, 'name': row.get('full_name') or outcomes.get(pid, {}).get('name') or pid,
                                   'team': team, 'position': row.get('position'), 'kind': 'player', 'game_id': game['id'],
                                   'game': f"{game['away']}-{game['home']}", 'component_ids': [component_id],
                                   'first_td_probability': probability, 'evidence': evidence,
                                   'profile_source': source})
            dst_id, dst_key = 'dst_' + team, f"{game['id']}:dst:{team}"
            dst_probability = outcomes.get(dst_id, {}).get('probability', 0)
            shares, total_returns = return_counts.get(team, {}), sum(return_counts.get(team, {}).values())
            return_probability = dst_probability * return_fraction
            defense_id = dst_key + ':defense'
            components[defense_id] = {'probability': dst_probability - return_probability, 'owners': [dst_id], 'kind': 'defense'}
            dst_components = [defense_id]
            allocated = 0.0
            for pid, count in shares.items():
                if pid not in team_active or not total_returns:
                    continue
                probability = return_probability * count / total_returns
                component_id = f"{dst_key}:return:{pid}"
                components[component_id] = {'probability': probability, 'owners': [dst_id, pid], 'kind': 'return'}
                dst_components.append(component_id); allocated += probability
                selection = next(x for x in selections if x['game_id'] == game['id'] and x['id'] == pid)
                selection['component_ids'].append(component_id)
                selection['first_td_probability'] += probability
                selection['evidence'].append(f"Also receives {count}/{total_returns} of recent active-player return opportunities; a return TD credits both the returner and {team} D/ST.")
            if allocated < return_probability:
                component_id = dst_key + ':return:unassigned'
                components[component_id] = {'probability': return_probability - allocated, 'owners': [dst_id], 'kind': 'return_unassigned'}
                dst_components.append(component_id)
            selections.append({'id': dst_id, 'name': team + ' D/ST', 'team': team, 'position': 'D/ST', 'kind': 'dst',
                               'game_id': game['id'], 'game': f"{game['away']}-{game['home']}",
                               'component_ids': dst_components, 'first_td_probability': dst_probability,
                               'profile_source': 'existing_first_td',
                               'evidence': ['Existing First TD defense/special-teams estimate.',
                                            'Return touchdowns are represented once and can credit both D/ST and the individual returner.']})
    return selections, components, inactive, return_fraction


def grade_slate(snapshot, rows):
    game_ids = {g['id'] for g in snapshot['games']}
    first = {}
    for row in rows:
        if str(row.get('game_id')) not in game_ids:
            continue
        event = first_td_event(row)
        if event and (event['game_id'] not in first or event['elapsed_seconds'] < first[event['game_id']]['elapsed_seconds']):
            first[event['game_id']] = event
    if not first:
        return {'winner_selection_ids': [], 'winning_elapsed_seconds': None, 'games': []}
    fastest = min(event['elapsed_seconds'] for event in first.values())
    winners = sorted({owner for event in first.values() if event['elapsed_seconds'] == fastest
                      for owner in event['eligible_selection_ids']})
    return {'winner_selection_ids': winners, 'winning_elapsed_seconds': fastest,
            'games': [{'game_id': game['id'], 'actual_first_td': first.get(game['id'])} for game in snapshot['games']]}


def build_payload(config, history, schedules, rows, roster, as_of):
    first_td = history['derivatives']['first_td']
    pairs = {frozenset(pair) for pair in config['games']}
    games = []
    for game_id, model in first_td.items():
        if str(model.get('kickoff', ''))[:10] == config['date'] and frozenset((model['away'], model['home'])) in pairs:
            source = next((g for g in history['games']['nfl'] if g['id'] == game_id), {})
            games.append({'id': game_id, 'away': model['away'], 'home': model['home'], 'kickoff': model['kickoff'],
                          'total': source.get('total'), 'model_total': (source.get('model') or {}).get('total_mean')})
    if len(games) != len(config['games']):
        raise RuntimeError(f"Slate Breaker found {len(games)} of {len(config['games'])} configured games")
    games.sort(key=lambda g: config['games'].index([g['away'], g['home']]))
    records = [r for r in game_records(rows, schedules) if r['date'] < config['date']]
    td_records = [r for r in records if r['elapsed_seconds'] is not None]
    if len(td_records) < 400:
        raise RuntimeError('Insufficient prior first-touchdown games for Slate Breaker')
    validation = evaluate_time_models(td_records)
    beta = 1.0 if validation['selected'] == 'total_adjusted' else 0.0
    base = empirical_bins([r['elapsed_seconds'] for r in td_records])
    totals = [r['total'] for r in td_records if finite(r.get('total'))]
    mean_total = sum(totals) / len(totals) if totals else None
    forecasts = {}
    for game in games:
        total, total_source = (game['total'], 'pregame_total') if finite(game.get('total')) else (game.get('model_total'), 'Going Long scoring model')
        bins = adjusted_bins(base, total, mean_total, beta)
        no_td = first_td[game['id']]['outcomes'].get('no_td', {}).get('probability', 0)
        forecasts[game['id']] = {'pmf': seconds_pmf(bins), 'no_td_probability': no_td, 'bins': bins,
                                  'feature_snapshot': {'total': total, 'total_source': total_source,
                                                       'median_first_td_seconds_given_td': percentile_seconds(bins),
                                                       'first_td_by_5m_given_td': cdf_probability(bins, 300),
                                                       'first_td_by_10m_given_td': cdf_probability(bins, 600)}}
    factors = fastest_factors(forecasts)
    events = [first_td_event(row) for row in rows]
    events = [event for event in events if event]
    teams = {team for game in games for team in (game['away'], game['home'])}
    current_roster = [r for r in roster if int(r.get('season') or 0) == int(config['date'][:4])]
    active_ids = {r.get('gsis_id') for r in current_roster if r.get('status') == 'ACT' and r.get('team') in teams}
    return_counts = recent_return_shares(rows, teams, active_ids)
    priors = position_priors([record['event'] for record in records if record.get('event')], roster)
    selections, components, inactive, return_fraction = build_selections(games, first_td, current_roster, events, return_counts, priors)
    profiles = history.get('profiles', {})
    for selection in selections:
        game = next(g for g in games if g['id'] == selection['game_id'])
        selection['slate_breaker_probability'] = selection['first_td_probability'] * factors[selection['game_id']]
        profile = profiles.get(selection['id'], {})
        sample = profile.get('stats', {}).get('atd', {}).get('n', 0)
        low = selection['kind'] == 'dst' or selection['profile_source'] != 'existing_first_td' or sample < 8
        selection['confidence'] = {'label': 'Low' if low else 'Moderate', 'probability_is_confidence': False,
                                   'reason': ('Rare D/ST or unproven individual role' if low else
                                              f'{sample} recorded player games plus pooled clock history')}
        selection['feature_snapshot'] = {**forecasts[game['id']]['feature_snapshot'],
                                         'fastest_game_factor_given_game_td': factors[game['id']],
                                         'first_td_model': first_td[game['id']]['method'],
                                         'first_td_profile_games': sample,
                                         'active_roster_status': 'ACT'}
    selections.sort(key=lambda x: (-x['slate_breaker_probability'], x['game'], x['name']))
    for rank, selection in enumerate(selections, 1):
        selection['rank'] = rank
    model = {'version': VERSION, 'first_td_version': history['derivatives'].get('schema_version'),
             'time_method': validation['selected'], 'conditional_independence': 'scorer identity and first-TD clock within game',
             'bin_seconds': BIN_SECONDS, 'maximum_seconds': MAX_SECONDS, 'training_cutoff': config['date'],
             'training_games_with_td': len(td_records), 'training_games_no_td': len(records) - len(td_records),
             'mean_pregame_total': mean_total, 'total_beta': beta, 'base_time_bins': base,
             'position_priors': priors, 'dst_return_fraction': return_fraction}
    public_games = [{**game, **forecasts[game['id']]['feature_snapshot'],
                     'no_td_probability': forecasts[game['id']]['no_td_probability'],
                     'fastest_factor_given_td': factors[game['id']]} for game in games]
    return {'schema_version': 1, 'generated_at': as_of, 'date': config['date'], 'offer_id': config['offer_id'],
            'games': public_games, 'selections': selections, 'event_components': components,
            'model': model, 'validation': validation, 'excluded_inactive': inactive,
            'eligibility_note': config['note'], 'source': config['source']}


def main():
    import nflreadpy as nfl
    import polars as pl
    from build_pipeline import atomic_json
    config = json.loads((ROOT / 'config/slate-breaker.json').read_text(encoding='utf-8'))
    history = json.loads((ROOT / 'data/history.json').read_text(encoding='utf-8'))['betting']
    year = int(config['date'][:4]); years = list(range(year - 3, year + 1))
    schedules = nfl.load_schedules(years).to_dicts()
    columns = ['game_id', 'game_date', 'play_id', 'qtr', 'quarter_seconds_remaining', 'game_seconds_remaining',
               'posteam', 'touchdown', 'play_type', 'play_deleted', 'two_point_attempt', 'td_team',
               'td_player_id', 'kickoff_attempt', 'punt_attempt', 'return_team', 'kickoff_returner_player_id',
               'punt_returner_player_id']
    rows = pl.concat([nfl.load_pbp([y]).select(columns) for y in years], how='diagonal_relaxed').to_dicts()
    roster = nfl.load_rosters(years).to_dicts()
    as_of = datetime.now(timezone.utc).isoformat()
    payload = build_payload(config, history, schedules, rows, roster, as_of)
    archive = ROOT / 'data/jackpot/slate-breaker'; archive.mkdir(parents=True, exist_ok=True)
    snapshot_path = archive / f"{config['date']}.json"
    if not snapshot_path.exists():
        snapshot_path.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    results = []
    schedule_by_id = {str(g.get('game_id')): g for g in schedules}
    for path in sorted(archive.glob('*.json')):
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        slate_games = [schedule_by_id.get(game['id'], {}) for game in snapshot['games']]
        if not slate_games or any(not finite(g.get('home_score')) or not finite(g.get('away_score')) for g in slate_games):
            continue
        game_ids = {game['id'] for game in snapshot['games']}
        complete = {str(row.get('game_id')) for row in rows if str(row.get('game_id')) in game_ids
                    and finite(row.get('game_seconds_remaining')) and row.get('game_seconds_remaining') == 0
                    and finite(row.get('qtr')) and row.get('qtr') >= 4}
        if complete != game_ids:
            continue
        result = grade_slate(snapshot, rows)
        result.update(date=snapshot['date'], model_version=snapshot['model']['version'],
                      predictions=[{'id': x['id'], 'game_id': x['game_id'],
                                    'slate_breaker_probability': x['slate_breaker_probability'],
                                    'first_td_probability': x['first_td_probability'],
                                    'won': x['id'] in result['winner_selection_ids']} for x in snapshot['selections']],
                      status='Chronological out-of-sample saved forecast; sportsbook settlement not verified')
        results.append(result)
    atomic_json(ROOT / 'data/slate-breaker.json', {'generated_at': as_of, 'slate': payload, 'results': results})
    print(f"[slate-breaker] {len(payload['selections'])} selections across {len(payload['games'])} games; "
          f"time model={payload['model']['time_method']}")


if __name__ == '__main__':
    main()
