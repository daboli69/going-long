"""Publish all-position NFL weekly rosters and exact injury text, no service required."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from build_pipeline import atomic_json

ROOT = Path(__file__).resolve().parents[1]

def latest_week(roster, season):
    return max((int(r.get('week') or 0) for r in roster if r.get('game_type') == 'REG' and r.get('season') == season), default=0)


def bye_teams_for(schedule, season, week):
    """Teams scheduled in the season but not playing ``week``; empty when the schedule has no such week."""
    rows = [g for g in schedule if g.get('season') == season and g.get('game_type', 'REG') == 'REG']
    playing = {t for g in rows if int(g.get('week') or 0) == week for t in (g.get('home_team'), g.get('away_team'))}
    everyone = {t for g in rows for t in (g.get('home_team'), g.get('away_team'))}
    return sorted(everyone - playing) if playing else []


def normalize(roster, injuries, season, bye_teams=()):
    regular = [r for r in roster if r.get('game_type') == 'REG' and r.get('season') == season]
    week = max((int(r.get('week') or 0) for r in regular), default=0)
    report_week = max((int(r.get('week') or 0) for r in injuries if r.get('season') == season and r.get('season_type') == 'REG'), default=0)
    reports = {}
    for r in injuries:
        if r.get('season') != season or r.get('season_type') != 'REG' or int(r.get('week') or 0) != report_week: continue
        pid = r.get('gsis_id')
        if not pid: continue
        report = { 'report_status': r.get('report_status'), 'practice_status': r.get('practice_status'),
                   'primary_injury': r.get('report_primary_injury') or r.get('practice_primary_injury'),
                   'secondary_injury': r.get('report_secondary_injury') or r.get('practice_secondary_injury'),
                   'week': report_week, 'reported_at': str(r.get('date_modified') or '') or None }
        parts = [str(report.get(k) or '').lower() for k in ('primary_injury','secondary_injury')]
        if not report['report_status'] and all(not p or 'not injury related' in p or p == 'rest' for p in parts):
            continue
        if any(report.get(k) for k in ('report_status','practice_status','primary_injury','secondary_injury')):
            prior=reports.get(pid)
            if not prior or str(report['reported_at'] or '') >= str(prior['reported_at'] or ''): reports[pid]=report
    players={}
    for r in regular:
        if int(r.get('week') or 0)!=week or r.get('status')!='ACT' or not r.get('gsis_id') or not r.get('team'):continue
        pid=r['gsis_id'];players[pid]={'id':pid,'name':r.get('full_name'),'team':r['team'],'position':r.get('position'),
                                    'number':r.get('jersey_number'),'roster_status':r['status'],'week':week,'injury':reports.get(pid)}
    # nflverse omits bye-week teams from that week's file. Carry each one's latest earlier
    # active roster forward (each player keeps its true snapshot week) instead of dropping the team.
    carried = []
    for team in bye_teams:
        earlier = [r for r in regular if r.get('team') == team and r.get('status') == 'ACT' and r.get('gsis_id') and int(r.get('week') or 0) < week]
        if not earlier: continue
        prior = max(int(r.get('week') or 0) for r in earlier)
        for r in earlier:
            if int(r.get('week') or 0) != prior or r['gsis_id'] in players: continue
            pid=r['gsis_id'];players[pid]={'id':pid,'name':r.get('full_name'),'team':team,'position':r.get('position'),
                                        'number':r.get('jersey_number'),'roster_status':r['status'],'week':prior,'injury':None,'bye_carry_forward':True}
        carried.append(team)
    return {'season':season,'week':week,'injury_week':report_week,'players':list(players.values()),'bye_carry_forward_teams':sorted(carried)}

def build():
    import nflreadpy as nfl
    season=int(os.getenv('SEASON',datetime.now().year))
    roster=nfl.load_rosters_weekly([season]).to_dicts()
    bye=bye_teams_for(nfl.load_schedules([season]).to_dicts(),season,latest_week(roster,season))
    result=normalize(roster,nfl.load_injuries([season]).to_dicts(),season,bye)
    if len({p['team'] for p in result['players']})!=32:raise RuntimeError('Incomplete active roster source; previous snapshot retained')
    result.update(schema_version=1,generated_at=datetime.now(timezone.utc).isoformat(),status='FRESH',
                  source='nflverse weekly rosters and injury reports',source_url='https://github.com/nflverse/nflverse-data',
                  note='Active roster at the published weekly snapshot; teams on bye keep their latest earlier active roster (flagged bye_carry_forward, true week per player); game-day inactive status is separate. Injury report week is shown explicitly.')
    atomic_json(ROOT/'data/nfl_roster.json',result)
    print(f"Roster: {len(result['players'])} players, 32 teams, week {result['week']}")

if __name__=='__main__':build()
