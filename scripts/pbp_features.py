"""Public PBP feature store. Neutral observations are not full-game projections.

All training aggregates use pre-snap offensive WP in [0.20, 0.80]. Opening
play numbers are assigned BEFORE that filter. Missing charting is never zero.
"""
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def ratio(a, b):
    return a / b if b else None


def player_ids(value):
    """nflverse publishes semicolon strings; accept array representations too."""
    if isinstance(value, str):
        value = value.split(';')
    return set(x.strip() for x in (value or []) if isinstance(x, str) and x.strip())


def canonical(row, sport):
    if sport == 'nfl':
        return dict({k: row.get(k) for k in ('wp', 'drive', 'xpass', 'air_yards', 'passing_yards', 'rushing_yards', 'qb_scramble', 'was_pressure')}, gid=row.get('game_id'), pid=row.get('play_id'), team=row.get('posteam'),
                    defense=row.get('defteam'), date=str(row.get('game_date') or '')[:10],
                    quarter=row.get('qtr'), clock=row.get('quarter_seconds_remaining'),
                    dropback=row.get('qb_dropback'), rush=row.get('rush_attempt'),
                    target=row.get('receiver_player_id'), runner=row.get('rusher_player_id'),
                    yards=row.get('receiving_yards'), goal=row.get('yardline_100'),
                    excluded=any(row.get(k) == 1 for k in ('no_play', 'play_deleted', 'qb_kneel', 'qb_spike', 'aborted_play')) or row.get('play_type') == 'no_play')
    minutes, seconds = row.get('clock_minutes'), row.get('clock_seconds')
    return dict(gid=row.get('game_id'), pid=row.get('game_play_number'), team=row.get('pos_team'),
                defense=row.get('def_pos_team'), date=str(row.get('start_date') or '')[:10],
                quarter=row.get('period'), clock=minutes * 60 + seconds if number(minutes) and number(seconds) else None,
                drive=row.get('drive_id'), wp=row.get('wp_before'), dropback=row.get('pass'), rush=row.get('rush'),
                passing_yards=row.get('completion_yds'), rushing_yards=row.get('rush_yds'),
                excluded=row.get('penalty_no_play') == 1 or 'kneel' in str(row.get('play_type')).lower() or 'spike' in str(row.get('play_type')).lower())


def aggregate(rows, sport='nfl', charting=(), window=12, as_of=None):
    cutoff = as_of or datetime.now(timezone.utc).date().isoformat()
    charts = {(str(r.get('nflverse_game_id')), r.get('play_id')): r for r in charting}
    unique = {}
    for raw in rows:
        r = canonical(raw, sport)
        if (not r['gid'] or r['pid'] is None or not r['team'] or not r['date'] or r['date'] >= cutoff
                or r['excluded'] or r['quarter'] not in (1, 2, 3, 4)
                or not (r.get('dropback') == 1 or r.get('rush') == 1)):
            continue
        unique[(str(r['gid']), r['pid'])] = r
    ordered = sorted(unique.values(), key=lambda r: (r['date'], str(r['gid']), r['pid']))
    games = defaultdict(dict)
    for r in ordered:
        games[r['team']][str(r['gid'])] = r['date']
    selected = {team: set(sorted(g, key=lambda gid: (g[gid], gid))[-window:]) for team, g in games.items()}
    teams, players, defenses = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    coverage, player_coverage = defaultdict(lambda: defaultdict(Counter)), defaultdict(lambda: defaultdict(Counter))
    opening = Counter()
    previous = None
    pace = defaultdict(list)
    periods = defaultdict(lambda: defaultdict(Counter))
    last_dates, chart_dates = {}, {}
    for r in ordered:
        gid, team, pid = str(r['gid']), r['team'], r['pid']
        opening[(gid, team)] += 1
        wp = r.get('wp')
        neutral = number(wp) and .2 <= wp <= .8
        active = gid in selected[team]
        if neutral and active:
            t = teams[team]
            last_dates[team] = max(last_dates.get(team, ''), r['date'])
            t['snaps'] += 1
            t['dropbacks'] += int(r.get('dropback') == 1)
            t['rushes'] += int(r.get('rush') == 1 and r.get('dropback') != 1)
            if number(r.get('xpass')):
                t['proe_sum'] += int(r.get('dropback') == 1) - r['xpass']
                t['proe_n'] += 1
            first = opening[(gid, team)] <= 15
            if first:
                t['opening_snaps'] += 1
                t['opening_dropbacks'] += int(r.get('dropback') == 1)
            for period in ('FT',) + (('Q1',) if r['quarter'] == 1 else ()) + (('1H',) if r['quarter'] <= 2 else ()):
                periods[team][period]['snaps'] += 1
                periods[team][period]['dropbacks'] += int(r.get('dropback') == 1)
                for stat in ('passing_yards', 'rushing_yards'):
                    if number(r.get(stat)):
                        periods[team][period][stat] += r[stat]
            # Adjacent neutral snaps within the same possession and quarter only.
            if previous and previous.get('neutral') and previous['gid'] == r['gid'] and previous['team'] == team and previous['quarter'] == r['quarter'] and r.get('drive') is not None and previous.get('drive') == r.get('drive'):
                if number(previous.get('clock')) and number(r.get('clock')):
                    gap = previous['clock'] - r['clock']
                    if 0 < gap <= 60:
                        pace[team].append(gap)
                        if r['quarter'] <= 2:
                            periods[team]['1H']['pace_sum'] += gap
                            periods[team]['1H']['pace_n'] += 1
                        if r['quarter'] == 1:
                            periods[team]['Q1']['pace_sum'] += gap
                            periods[team]['Q1']['pace_n'] += 1
            ch = charts.get((gid, pid), {})
            if r.get('dropback') == 1:
                ids = player_ids(ch.get('offense_players'))
                # Missing charting is excluded from both numerator and denominator.
                if ids:
                    chart_dates[team] = max(chart_dates.get(team, ''), r['date'])
                    t['charted_dropbacks'] += 1
                    for player in ids:
                        players[f'{team}|{player}']['pass_snaps_proxy'] += 1
                    if r.get('target') in ids:
                        players[f"{team}|{r['target']}"]['charted_targets'] += 1
                pressure = ch.get('was_pressure', r.get('was_pressure'))
                if isinstance(pressure, bool):
                    t['pressure_dropbacks'] += 1
                    t['pressures_allowed'] += int(pressure)
                    defenses[r['defense']]['pressure_dropbacks'] += 1
                    defenses[r['defense']]['pressures_generated'] += int(pressure)
                    bucket = 'pressured' if pressure else 'clean'
                    t[bucket + '_dropbacks'] += 1
                    t[bucket + '_pass_yards'] += r.get('passing_yards') if number(r.get('passing_yards')) else 0
                    t[bucket + '_scramble_yards'] += (r.get('rushing_yards') or 0) if r.get('qb_scramble') == 1 else 0
            labels = [ch.get('defense_man_zone_type')]
            shell = ch.get('defense_coverage_type')
            labels += ['single_high' if shell in ('COVER_1', 'COVER_3') else 'two_high' if shell in ('COVER_2', 'COVER_4', '2_MAN') else None]
            if r.get('dropback') == 1:
                for label in filter(None, labels):
                    coverage[r.get('defense')][label]['dropbacks'] += 1
            target, runner, goal = r.get('target'), r.get('runner'), r.get('goal')
            for player, kind in ((target, 'targets'), (runner, 'carries')):
                if not player or (kind == 'carries' and r.get('rush') != 1):
                    continue
                key = f'{team}|{player}'
                p = players[key]
                p[kind] += 1
                if first:
                    p['opening_' + kind] += 1
                    t['opening_' + kind] += 1
                for zone, maximum in (('red_zone', 20), ('inside_ten', 10), ('goal_line', 5)):
                    if number(goal) and goal <= maximum:
                        p[zone + '_' + kind] += 1
                        t[zone + '_' + kind] += 1
                if kind == 'targets':
                    air = r.get('air_yards')
                    if number(air):
                        p['air_yards'] += air
                        p['air_yards_targets'] += 1
                        if number(goal) and air >= goal:
                            p['end_zone_targets'] += 1
                            t['end_zone_targets'] += 1
                    p['receiving_yards'] += r.get('yards') if number(r.get('yards')) else 0
                    for label in filter(None, labels):
                        pc = player_coverage[key][label]
                        pc['targets'] += 1
                        pc['yards'] += r.get('yards') if number(r.get('yards')) else 0
        previous = dict(r, neutral=neutral)
    team_out = {}
    for team, t in teams.items():
        for field in ('opening_snaps', 'opening_dropbacks', 'charted_dropbacks', 'pressure_dropbacks', 'pressures_allowed'):
            t.setdefault(field, 0)
        team_out[team] = dict(t, last_game=last_dates[team], games=len(selected[team]),
                             last_participation_game=chart_dates.get(team),
                             pressure_rate_allowed=ratio(t['pressures_allowed'], t['pressure_dropbacks']),
                             participation_coverage=ratio(t['charted_dropbacks'], t['dropbacks']),
                             pass_rate=ratio(t['dropbacks'], t['snaps']), proe=ratio(t['proe_sum'], t['proe_n']),
                             pace_seconds=statistics.mean(pace[team]) if pace[team] else None, pace_pairs=len(pace[team]),
                             opening_pass_rate=ratio(t['opening_dropbacks'], t['opening_snaps']),
                             periods={k: dict(v, snap_fraction=ratio(v['snaps'], t['snaps']),
                                              dropback_fraction=ratio(v['dropbacks'], t['dropbacks']),
                                              pace_seconds=ratio(v['pace_sum'], v['pace_n'])) for k, v in periods[team].items()})
    player_out = {}
    for key, p in players.items():
        team, player = key.split('|', 1)
        t = teams[team]
        player_out[key] = dict(p, player_id=player, team=team, last_game=last_dates[team],
                               last_participation_game=chart_dates.get(team),
                               adot=ratio(p['air_yards'], p['air_yards_targets']),
                               routes_run=None, route_participation=None, tprr=None,
                               pass_snap_participation_proxy=ratio(p['pass_snaps_proxy'], t['charted_dropbacks']),
                               targets_per_pass_snap_proxy=ratio(p['charted_targets'], p['pass_snaps_proxy']),
                               participation_charted_dropbacks=t['charted_dropbacks'],
                               route_expansion_flag=(p['pass_snaps_proxy'] >= 50 and p['charted_targets'] / p['pass_snaps_proxy'] >= .25 and p['pass_snaps_proxy'] / t['charted_dropbacks'] < .7) if t['charted_dropbacks'] else None,
                               shares={k: ratio(p[k], t[k]) for k in ('red_zone_carries', 'inside_ten_carries', 'goal_line_carries', 'red_zone_targets', 'inside_ten_targets', 'goal_line_targets', 'end_zone_targets', 'opening_carries', 'opening_targets')},
                               coverage={k: dict(v, yards_per_target=ratio(v['yards'], v['targets']), status='observed' if v['targets'] >= 20 else 'insufficient') for k, v in player_coverage[key].items()})
    return {'teams': team_out, 'players': player_out,
            'defenses': {team: dict(v, pressure_rate_generated=ratio(v['pressures_generated'], v['pressure_dropbacks'])) for team, v in defenses.items() if team},
            'defense_coverage': {team: {label: dict(v) for label, v in labels.items()} for team, labels in coverage.items() if team},
            'eligible_snaps': len(ordered), 'neutral_snaps': sum(t['snaps'] for t in teams.values())}


def build_public_features(seasons, window=12):
    import nflreadpy as nfl
    import sportsdataverse.cfb as cfb
    import polars as pl
    cache = Path(os.environ['FEATURE_INPUT_DIR']) if os.getenv('FEATURE_INPUT_DIR') else None
    sources, output = {}, {}
    for sport, loader, cache_name in (('nfl', nfl.load_pbp, 'nfl'), ('ncaa', cfb.load_cfb_pbp_r, 'cfbfastR')):
        frames, participation = [], []
        if cache:
            frames = [pl.read_parquet(cache / (cache_name + '.parquet'))]
            sources[sport] = {'status': 'loaded', 'input': 'local public-source cache'}
            if sport == 'nfl':
                participation = pl.read_parquet(cache / 'participation.parquet').to_dicts()
        else:
            years = {}
            for year in seasons:
                try:
                    frame = loader([year])
                    frames.append(frame)
                    years[str(year)] = 'loaded' if len(frame) else 'not_published'
                except Exception as exc:
                    if '404' not in str(exc):
                        raise
                    years[str(year)] = 'not_published'
                if sport == 'nfl':
                    try:
                        participation.extend(nfl.load_participation([year]).to_dicts())
                    except Exception as exc:
                        if '404' not in str(exc) and not (year == max(seasons) and 'Season must be between' in str(exc)):
                            raise
            sources[sport] = years
        # Iterate one frame at a time: do not materialize the entire wide CFB archive.
        output[sport] = aggregate((row for frame in frames for row in frame.iter_rows(named=True)), sport, participation, window)
    return dict(schema_version=2, generated_at=datetime.now(timezone.utc).isoformat(), sources=sources,
                definition={'wp': 'pre-snap offensive win probability, inclusive 0.20–0.80', 'window_games': window,
                            'opening': 'first 15 offensive snaps, indexed before WP filtering',
                            'pace': 'clock seconds between adjacent neutral snaps in the same drive and quarter; gaps 1–60 seconds',
                            'use': 'public proxies; bounded pressure sensitivity, not causal or calibrated win-rate estimates',
                            'pass_snap_proxy': 'player pass snaps / team dropbacks with offense_players charting; targets use the same charted snaps',
                            'route_expansion_flag': 'at least 50 pass snaps, targets/pass snap >=25%, participation <70%; heuristic flag'},
                availability={'routes': 'proxy: pass snaps on charted dropbacks; not routes run', 'trench': 'proxy: charted pressure rates; not PRWR/PBWR',
                              'play_caller': 'inactive: verified OC assignment history unavailable',
                              'slot_alignment': 'inactive: alignment unavailable',
                              'coverage_adjustment': 'inactive: historical splits exported; matchup calibration pending',
                              'first_td_probability': 'inactive: competing-scorer calibration pending',
                              'period_probability': 'inactive: period calibration pending'}, **output)


def pressure_matchup(offense, defense):
    """Conservative sensitivity from observed pressured/clean production.

    Blend the opposing defense and offense pressure rates, shrink the difference,
    and use the offense's conditional production difference. Association is not
    causation. Hard limits bound extrapolation; they are policy, not fitted values.
    """
    off, opp = offense.get('pressure_rate_allowed'), defense.get('pressure_rate_generated')
    if not number(off) or not number(opp) or min(offense.get('pressure_dropbacks', 0), defense.get('pressure_dropbacks', 0)) < 100:
        return {'status': 'insufficient', 'pass_scale': 1, 'scramble_yards_delta': 0}
    pressure_n, clean_n = offense.get('pressured_dropbacks', 0), offense.get('clean_dropbacks', 0)
    if min(pressure_n, clean_n) < 30:
        return {'status': 'insufficient', 'pass_scale': 1, 'scramble_yards_delta': 0}
    sample = min(offense['pressure_dropbacks'], defense['pressure_dropbacks'])
    delta = (opp - off) / 2 * sample / (sample + 100)
    # Only activate the requested adverse-pressure scenario.
    delta = max(0, delta)
    clean_pass = offense.get('clean_pass_yards', 0) / clean_n
    pressure_pass = offense.get('pressured_pass_yards', 0) / pressure_n
    baseline = clean_pass * (1 - off) + pressure_pass * off
    scale = max(.85, min(1, 1 + delta * (pressure_pass - clean_pass) / baseline)) if baseline > 0 else 1
    scramble_diff = offense.get('pressured_scramble_yards', 0) / pressure_n - offense.get('clean_scramble_yards', 0) / clean_n
    return {'status': 'proxy', 'pressure_rate_delta': delta, 'pass_scale': scale,
            'scramble_yards_delta': max(0, delta * scramble_diff * offense['dropbacks'] / max(1, offense['games'])),
            'sample': sample, 'method': 'shrunk pressure mismatch; conditional production sensitivity'}


def matchup_adjustments(features, games):
    data = features['nfl']
    result = {}
    for g in games:
        for team, opponent in ((g['home'], g['away']), (g['away'], g['home'])):
            result[f'{team}|{opponent}'] = pressure_matchup(data['teams'].get(team, {}), data['defenses'].get(opponent, {}))
    features['pressure_matchups'] = result
