"""Descriptive trend labels and the team/matchup context stored with every weekly trend state.

Everything here is DESCRIPTIVE EVIDENCE. Until prospective evidence validates a label's predictive value (research ledger), a label is never a model
input, a rating bonus or a bet trigger. Thresholds are fixed here, in code, before any outcome exists; missing data produces no label (never a
negative one).
"""
import json
from pathlib import Path

from .trends import live_snapshots

# label -> (description, rule). Rules read the derived/weekly/before values of one player's trend record.
THRESHOLDS = {
    'route_participation': {'min_routes': 10, 'relative_change': 0.20, 'absolute_routes': 5.0},
    'target_volume': {'relative_change': 0.25, 'absolute_targets': 2.0},
    'first_read_share': {'min_targets': 4, 'share_change': 0.15},
    'carry_volume': {'relative_change': 0.25, 'absolute_carries': 3.0},
    'goal_line': {'absolute_snaps': 2.0},
    'opportunity': {'relative_change': 0.30, 'absolute_xfp': 3.0},
}
TEAM_METRICS = {'plays': 'Overall.SNAPS', 'pass_plays': 'Overall.PASS', 'neutral_plays': 'Neutral.SNAPS', 'neutral_pass_plays': 'Neutral.PASS',
                'leading_plays': 'Leading By 7+.SNAPS', 'trailing_plays': 'Trailing By 7+.SNAPS'}


def _doc(root, entry):
    return json.loads((Path(root) / entry['normalized_path']).read_text(encoding='utf-8'))


def _team_rows(root, entry, columns):
    out = {}
    for row in _doc(root, entry)['rows']:
        team = row['entity'].get('team')
        if team:
            out[team] = {name: row['metrics'].get(col) for name, col in columns.items()}
            out[team]['_games'] = row['context'].get('games')
            out[team]['_opponent'] = row['context'].get('opponent')
    return out


def team_environment(root, manifest, season, game):
    """Each team's own play mix in week `game` (difference of consecutive run/pass snapshots) and its season-to-date mix before that week."""
    snaps = live_snapshots(manifest, season, 'run_pass_report')
    if game not in snaps or (game - 1) not in snaps:
        return {}, {}
    now, before = _team_rows(root, snaps[game], TEAM_METRICS), _team_rows(root, snaps[game - 1], TEAM_METRICS)
    out = {}
    for team, current in now.items():
        previous = before.get(team)
        if not previous or (current['_games'] or 0) <= (previous['_games'] or 0):
            continue
        week = {k: round(current[k] - previous[k], 4) for k in TEAM_METRICS if current.get(k) is not None and previous.get(k) is not None}
        record = {'week': week, 'before': {k: previous[k] for k in TEAM_METRICS if previous.get(k) is not None}}
        if week.get('plays'):
            record['pass_rate_week'] = round(week['pass_plays'] / week['plays'], 4) if week.get('pass_plays') is not None else None
        if week.get('neutral_plays'):
            record['neutral_pass_rate_week'] = round(week['neutral_pass_plays'] / week['neutral_plays'], 4) if week.get('neutral_pass_plays') is not None else None
        if previous.get('plays') and previous.get('pass_plays') is not None:
            record['pass_rate_before'] = round(previous['pass_plays'] / previous['plays'], 4)
        out[team] = record
    return out, {'run_pass_report': {'now': snaps[game]['sha256'], 'before': snaps[game - 1]['sha256']}}


def matchup_context(root, manifest, season, game):
    """What was known about the NEXT opponent when snapshot `game` was imported: the forward-looking OL/DL table and the opponent's cumulative coverage mix."""
    out, sources = {}, {}
    lm = live_snapshots(manifest, season, 'line_matchups').get(game)
    cov = live_snapshots(manifest, season, 'coverage_matrix').get(game)
    coverage = {}
    if cov:
        sources['coverage_matrix'] = cov['sha256']
        for row in _doc(root, cov)['rows']:
            team = row['entity'].get('team')
            if team:
                coverage[team] = {k.split('.')[-1]: v for k, v in row['metrics'].items() if k.startswith(('Man/Zone.MAN', 'Man/Zone.ZONE', 'Coverages.', 'Middle of Field'))
                                  and 'FP/DB' not in k}
    if lm:
        sources['line_matchups'] = lm['sha256']
        rows = {r['entity'].get('team'): r for r in _doc(root, lm)['rows'] if r['entity'].get('team')}
        for team, row in rows.items():
            opponent = row['context'].get('opponent')
            m, theirs = row['metrics'], (rows.get(opponent) or {}).get('metrics', {})
            out[team] = {'next_opponent': opponent, 'offense_rush_grade': m.get('Offense Stats.RUSH GRADE'), 'offense_pass_grade': m.get('Offense Stats.PASS GRADE'),
                         'own_defense_adj_ybc_per_att': m.get('Defense Stats.ADJ YBC/ATT'), 'own_defense_pressure_pct': m.get('Defense Stats.PRESS %'),
                         'opponent_defense_adj_ybc_per_att': theirs.get('Defense Stats.ADJ YBC/ATT'), 'opponent_defense_pressure_pct': theirs.get('Defense Stats.PRESS %'),
                         'opponent_coverage_mix_season_to_date': coverage.get(opponent)}
    elif coverage:
        out = {team: {'coverage_mix_season_to_date': mix} for team, mix in coverage.items()}
    return out, sources


def detect(record):
    """Descriptive labels for one player's weekly record. Returns a list of {label, detail}; empty when the evidence is missing."""
    week, before, derived = record.get('week') or {}, record.get('before') or {}, record.get('derived') or {}
    gb = (record.get('games_before') or {})
    labels = []

    def add(label, detail):
        labels.append({'label': label, 'detail': detail, 'descriptive_only': True})
    rules = THRESHOLDS['route_participation']
    delta, games = derived.get('routes_vs_season_avg'), gb.get('receiving_routes_run')
    if delta is not None and games and before.get('routes') and week.get('routes', 0) >= rules['min_routes']:
        average = before['routes'] / games
        if delta >= rules['absolute_routes'] and delta / average >= rules['relative_change']:
            add('ROUTE PARTICIPATION UP', f"{week['routes']:g} routes vs {average:.1f} per game before")
        elif -delta >= rules['absolute_routes'] and -delta / average >= rules['relative_change']:
            add('ROUTE PARTICIPATION DOWN', f"{week['routes']:g} routes vs {average:.1f} per game before")
    rules = THRESHOLDS['target_volume']
    delta = derived.get('targets_vs_season_avg')
    if delta is not None and games and before.get('targets') is not None:
        average = before['targets'] / games
        if average > 0 and delta >= rules['absolute_targets'] and delta / average >= rules['relative_change']:
            add('TARGET VOLUME UP', f"{week.get('targets', 0):g} targets vs {average:.1f} per game before")
        elif average > 0 and -delta >= rules['absolute_targets'] and -delta / average >= rules['relative_change']:
            add('TARGET VOLUME DOWN', f"{week.get('targets', 0):g} targets vs {average:.1f} per game before")
    rules = THRESHOLDS['first_read_share']
    if week.get('targets', 0) >= rules['min_targets'] and week.get('first_read_targets') is not None and before.get('first_read_targets') is not None and before.get('targets'):
        share_now = week['first_read_targets'] / week['targets']
        share_before = before['first_read_targets'] / before['targets']
        if share_now - share_before >= rules['share_change']:
            add('FIRST READ UP', f'{share_now:.0%} of targets this week vs {share_before:.0%} before')
        elif share_before - share_now >= rules['share_change']:
            add('FIRST READ DOWN', f'{share_now:.0%} of targets this week vs {share_before:.0%} before')
    rules = THRESHOLDS['carry_volume']
    games_bc = gb.get('rushing_bell_cow')
    if games_bc and before.get('carries') is not None and week.get('carries') is not None and before['carries'] / games_bc > 0:
        average = before['carries'] / games_bc
        delta = week['carries'] - average
        if delta >= rules['absolute_carries'] and delta / average >= rules['relative_change']:
            add('CARRY VOLUME UP', f"{week['carries']:g} carries vs {average:.1f} per game before")
        elif -delta >= rules['absolute_carries'] and -delta / average >= rules['relative_change']:
            add('CARRY VOLUME DOWN', f"{week['carries']:g} carries vs {average:.1f} per game before")
    rules = THRESHOLDS['goal_line']
    games_os = gb.get('offense_snaps')
    if games_os and before.get('snaps_inside_10') is not None and week.get('snaps_inside_10') is not None:
        average = before['snaps_inside_10'] / games_os
        if week['snaps_inside_10'] - average >= rules['absolute_snaps']:
            add('GOAL LINE UP', f"{week['snaps_inside_10']:g} inside-10 snaps vs {average:.1f} per game before")
    rules = THRESHOLDS['opportunity']
    games_ra = gb.get('receiving_advanced')
    if games_ra and before.get('xfp') is not None and week.get('xfp') is not None and before['xfp'] / games_ra > 0:
        average = before['xfp'] / games_ra
        delta = week['xfp'] - average
        if delta >= rules['absolute_xfp'] and delta / average >= rules['relative_change']:
            add('OPPORTUNITY UP', f"{week['xfp']:.1f} expected fantasy points vs {average:.1f} per game before")
        elif -delta >= rules['absolute_xfp'] and -delta / average >= rules['relative_change']:
            add('OPPORTUNITY DOWN', f"{week['xfp']:.1f} expected fantasy points vs {average:.1f} per game before")
    return labels
