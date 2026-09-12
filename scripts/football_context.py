"""Dated NFL opportunity, team scheme and opponent context; no betting lift claims.

All observations precede as_of. Snap share is not route share. The stronger
passing-snap proxy also includes blocking. Personnel/coverage are charted facts,
not inferred receiver alignment or run-blocking concepts.
"""
import json
import os
import re
import statistics as st
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from build_pipeline import atomic_json, finite, nfl_kickoff
from pbp_features import player_ids

ROOT = Path(__file__).resolve().parents[1]


def div(a, b):
    return a / b if b else None


def build_scope(rows, snaps, roster, charting, season, cutoff):
    positions = {r['gsis_id']: r.get('position') for r in roster if r.get('gsis_id')}
    names = {r['gsis_id']: r.get('full_name') for r in roster if r.get('gsis_id')}
    pfr = {r['pfr_id']: r['gsis_id'] for r in roster if r.get('pfr_id') and r.get('gsis_id')}
    charts = {(str(r['nflverse_game_id']), r['play_id']): r for r in charting}
    valid = [r for r in rows if r.get('season') == season and r.get('season_type') == 'REG'
             and str(r.get('game_date', ''))[:10] < cutoff and r.get('posteam') and r.get('qtr') in (1, 2, 3, 4)
             and r.get('play_type') in ('pass', 'run') and not any(r.get(k) == 1 for k in ('no_play', 'qb_kneel', 'qb_spike', 'play_deleted'))]
    dates = {r['game_id']: str(r['game_date'])[:10] for r in valid}
    games_by_team = defaultdict(set)
    for r in valid:
        games_by_team[r['posteam']].add(r['game_id'])
    selected = {t: set(sorted(ids, key=lambda g: (dates[g], g))[-6:]) for t, ids in games_by_team.items()}
    players, teams, defenses = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    player_games, team_games, player_teams = defaultdict(set), defaultdict(set), defaultdict(set)
    target_log, runner_log = [], []
    opening, previous = Counter(), {}
    for r in sorted(valid, key=lambda x: (x['game_date'], x['game_id'], x['play_id'])):
        gid, team, defense = r['game_id'], r['posteam'], r['defteam']
        if gid not in selected[team]:
            continue
        t = teams[team];team_games[team].add(gid)
        t['plays'] += 1
        opening[(gid, team)] += 1
        close = finite(r.get('wp')) and .2 <= r['wp'] <= .8
        if close:
            t['close_plays'] += 1;t['close_dropbacks'] += int(r.get('qb_dropback') == 1)
            if finite(r.get('xpass')):
                t['pass_expected'] += r['xpass'];t['pass_expected_n'] += 1;t['pass_actual'] += int(r.get('qb_dropback') == 1)
            key = (gid, team, r.get('drive'), r['qtr'])
            prev = previous.get(key)
            if prev and finite(r.get('quarter_seconds_remaining')):
                gap = prev - r['quarter_seconds_remaining']
                if 0 < gap <= 60:t['pace_sum'] += gap;t['pace_n'] += 1
            previous[key] = r.get('quarter_seconds_remaining')
            if opening[(gid, team)] <= 15:
                t['opening_plays'] += 1;t['opening_passes'] += int(r.get('qb_dropback') == 1)
        if not close:previous.pop((gid, team, r.get('drive'), r['qtr']), None)
        c = charts.get((str(gid), r['play_id']), {})
        personnel = c.get('offense_personnel')
        if personnel:
            t['personnel_n'] += 1
            counts = {pos: int(n) for n, pos in re.findall(r'(\d+)\s+(RB|TE|WR)\b', personnel)}
            if counts.get('RB') == 1 and counts.get('TE') == 1 and counts.get('WR') == 3:t['personnel_11'] += 1
        if r.get('qb_dropback') == 1:
            t['dropbacks'] += 1
            ids = player_ids(c.get('offense_players'))
            if ids:
                t['charted_dropbacks'] += 1
                for pid in ids:
                    players[pid]['pass_snaps'] += 1;player_games[pid].add(gid);player_teams[pid].add(team)
            rushers = c.get('number_of_pass_rushers')
            if finite(rushers):
                defenses[defense]['rushers_n'] += 1;defenses[defense]['five_plus_rushers'] += int(rushers >= 5)
            shell = c.get('defense_coverage_type')
            if shell:
                defenses[defense]['shell_n'] += 1;defenses[defense]['shell_' + str(shell)] += 1
        pid = r.get('receiver_player_id')
        if pid:
            player_teams[pid].add(team)
            p = players[pid];p['targets'] += 1;p['yards'] += r.get('receiving_yards') or 0
            p['air_yards'] += r.get('air_yards') or 0
            if finite(r.get('cp')):
                p['expected_catches'] += r['cp'];p['actual_catches'] += r.get('complete_pass') or 0;p['catch_model_targets'] += 1
            player_games[pid].add(gid)
            pos = positions.get(pid)
            if pos in ('RB', 'WR', 'TE'):
                t['targets_' + pos] += 1;t['targets'] += 1
                target_log.append((defense, pid, pos, gid, r.get('receiving_yards') or 0))
        runner = r.get('rusher_player_id')
        if r.get('rush_attempt') == 1 and r.get('qb_dropback') != 1 and runner:
            runner_log.append((defense, runner, gid, r.get('rushing_yards') or 0))
            defenses[defense]['carries'] += 1;defenses[defense]['rush_yards'] += r.get('rushing_yards') or 0
            if finite(r.get('epa')):defenses[defense]['run_success_n'] += 1;defenses[defense]['run_success'] += int(r['epa'] > 0)
    # PFR offensive percentages use actual team offensive snaps; reconstruct counts
    # from supplied percentages rather than treating the maximum player as the team.
    for s in snaps:
        pid = pfr.get(s.get('pfr_player_id'));gid = s.get('game_id')
        if not pid or gid not in selected.get(s.get('team'), set()) or not finite(s.get('offense_pct')) or s['offense_pct'] <= 0:
            continue
        player_teams[pid].add(s['team'])
        p = players[pid];p['offense_snaps'] += s.get('offense_snaps') or 0
        p['team_snaps'] += round(s['offense_snaps'] / s['offense_pct']);player_games[pid].add(gid)
    output = {}
    for pid, p in players.items():
        pos = positions.get(pid)
        if pos not in ('WR', 'TE', 'RB', 'QB'):continue
        gids = player_games[pid]
        team = next(iter(player_teams[pid])) if len(player_teams[pid]) == 1 else None
        t = teams.get(team, {})
        passing_coverage = div(t.get('charted_dropbacks', 0), t.get('dropbacks', 0))
        strong = passing_coverage is not None and passing_coverage >= .8 and p['pass_snaps'] >= 50
        share = div(p['pass_snaps'], t.get('charted_dropbacks', 0)) if strong else div(p['offense_snaps'], p['team_snaps'])
        output[pid] = dict(p, name=names.get(pid), position=pos, team=team, games=len(gids), season=season,
                           first_game=min((dates[g] for g in gids), default=None), last_game=max((dates[g] for g in gids), default=None),
                           share=share, share_type='passing_snap_proxy' if strong else 'offensive_snap_share',
                           charting_coverage=passing_coverage, catches_short=round(p['expected_catches']-p['actual_catches'], 2),
                           routes=None, opportunity_flag=False)
    benchmarks = {}
    for pos in ('WR', 'TE'):
        for kind in ('passing_snap_proxy', 'offensive_snap_share'):
            peers = [p for p in output.values() if p['team'] and p['position'] == pos and p['share_type'] == kind and p['games'] >= 3 and finite(p['share']) and p['share'] >= .2]
            avg = st.mean(p['share'] for p in peers) if len(peers) >= 10 else None
            benchmarks[pos + '|' + kind] = {'players': len(peers), 'average_share': avg}
            for p in peers:
                p['position_average'] = avg;p['peer_count'] = len(peers)
                p['opportunity_flag'] = avg is not None and p['share'] >= avg + .05 and p['catch_model_targets'] >= 20 and p['catches_short'] >= 2
    # Compare each defense with the same receivers' production against OTHER
    # defenses. Twenty pseudo-targets stabilize player estimates; fifty stabilize
    # the defensive residual. These are policy shrinkage strengths, not fitted lift.
    totals, versus, league = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for d, pid, pos, gid, yards in target_log:
        for bucket in (totals[pid], versus[(pid, d)], league[pos]):bucket['n'] += 1;bucket['yards'] += yards
    buckets, defensive_games = defaultdict(Counter), defaultdict(set)
    for d, pid, pos, gid, yards in target_log:
        base = league[pos]['yards'] / league[pos]['n']
        other_n = totals[pid]['n']-versus[(pid,d)]['n'];other_y = totals[pid]['yards']-versus[(pid,d)]['yards']
        expected = (other_y+20*base)/(other_n+20)
        b = buckets[(d,pos)];b['targets'] += 1;b['yards'] += yards;b['residual'] += yards-expected;defensive_games[(d,pos)].add(gid)
    allowed = {}
    for (d,pos), b in buckets.items():
        allowed[d+'|'+pos] = dict(b, games=len(defensive_games[(d,pos)]), yards_per_target=b['yards']/b['targets'], adjusted_extra_yards_per_target=b['residual']/(b['targets']+50), status='observed' if b['targets']>=40 and len(defensive_games[(d,pos)])>=4 else 'too_few_plays')
    team_out = {}
    for t, b in teams.items():
        team_out[t] = dict(b, games=len(team_games[t]), first_game=min(dates[g] for g in team_games[t]),last_game=max(dates[g] for g in team_games[t]),
                           plays_per_game=div(b['plays'],len(team_games[t])),pass_over_expected=div(b['pass_actual']-b['pass_expected'],b['pass_expected_n']),pace_seconds=div(b['pace_sum'],b['pace_n']),opening_pass_rate=div(b['opening_passes'],b['opening_plays']),personnel_11_share=div(b['personnel_11'],b['personnel_n']),rb_target_share=div(b['targets_RB'],b['targets']),te_target_share=div(b['targets_TE'],b['targets']))
    return {'season':season,'players':output,'teams':team_out,'position_benchmarks':benchmarks,'defense_receiving':allowed,'defenses':{t:dict(b,run_yards_per_carry=div(b['rush_yards'],b['carries']),five_plus_rusher_rate=div(b['five_plus_rushers'],b['rushers_n'])) for t,b in defenses.items()}}


def coach_meetings(schedule, cutoff):
    pairs = defaultdict(list)
    for g in schedule:
        if g.get('game_type') != 'REG' or str(g.get('gameday',''))>=cutoff or not finite(g.get('home_score')) or not finite(g.get('away_score')):continue
        h,a = g.get('home_coach'),g.get('away_coach')
        if not h or not a:continue
        margin=g['home_score']-g['away_score'];line=g.get('spread_line')
        for coach,opp,sign in ((h,a,1),(a,h,-1)):
            pairs[coach+'|'+opp].append({'date':str(g['gameday']),'margin':sign*margin,'versus_closing_spread':sign*(margin-line) if finite(line) else None})
    out={}
    for pair, meetings in pairs.items():
        covered=[r['versus_closing_spread'] for r in meetings if finite(r['versus_closing_spread'])]
        out[pair]={'games':len(meetings),'wins':sum(r['margin']>0 for r in meetings),'ties':sum(r['margin']==0 for r in meetings),'priced_games':len(covered),'covers':sum(x>0 for x in covered),'refunds':sum(x==0 for x in covered),'average_vs_spread':st.mean(covered) if covered else None,'last_meeting':max(r['date'] for r in meetings),'historically_behind':len(covered)>=6 and sum(x>0 for x in covered)/len(covered)<=1/3 and st.mean(covered)<=-3}
    return out


def build():
    import nflreadpy as nfl
    season=int(os.getenv('SEASON',datetime.now().year));cutoff=datetime.now(timezone.utc).date().isoformat()
    rows=[];snaps=[];roster=[];charts=[];sources={}
    keep=['season','season_type','game_date','game_id','posteam','defteam','qtr','play_type','no_play','qb_kneel','qb_spike','play_deleted','play_id','wp','qb_dropback','xpass','drive','quarter_seconds_remaining','receiver_player_id','receiving_yards','air_yards','cp','complete_pass','rusher_player_id','rushing_yards','rush_attempt','epa','passer_player_id']
    for year in (season-1,season):
        for kind,fn,destination in [('pbp',nfl.load_pbp,rows),('snaps',nfl.load_snap_counts,snaps),('roster',nfl.load_rosters,roster),('participation',nfl.load_participation,charts)]:
            try:
                frame=fn([year]);frame=frame.select([k for k in keep if k in frame.columns]) if kind=='pbp' else frame
                destination.extend(frame.to_dicts());sources[f'{kind}_{year}']={'status':'loaded','rows':len(frame)}
            except Exception as exc:
                sources[f'{kind}_{year}']={'status':'unavailable','reason':type(exc).__name__}
    if not rows or not roster:raise RuntimeError('No verified public play data; retaining previous context')
    schedule=nfl.load_schedules(list(range(season-5,season+1))).to_dicts()
    staff_path=ROOT/f'config/coaches-{season}.json';staff=json.loads(staff_path.read_text()) if staff_path.exists() else {'teams':{},'source':None}
    scopes={str(y):build_scope(rows,snaps,roster,charts,y,cutoff) for y in (season-1,season)}
    upcoming=[dict(id=g['game_id'],home=g['home_team'],away=g['away_team'],home_coach=g.get('home_coach'),away_coach=g.get('away_coach'),kickoff=nfl_kickoff(g),roof=g.get('roof')) for g in schedule if g['season']==season and str(g['gameday'])>=cutoff and g.get('game_type')=='REG']
    result={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'as_of':cutoff,'season':season,'sources':sources,'scopes':scopes,'coaches':staff,'coach_meetings':coach_meetings(schedule,cutoff),'games':upcoming,
            'method':'Last six regular-season games per team, separately by season; future dates excluded. Snap opportunity is not measured routes. Defensive position residuals use other-opponent receiver production, shrunk by 20/50 targets. Coach records are associations, not causal advantages.'}
    atomic_json(ROOT/'data/football_context.json',result)
    print('Football context', {y:len(v['players']) for y,v in scopes.items()},sources)


if __name__=='__main__':build()
