"""Publish all-position NFL weekly rosters and exact injury text, no service required."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from build_pipeline import atomic_json

ROOT = Path(__file__).resolve().parents[1]

def normalize(roster, injuries, season):
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
    return {'season':season,'week':week,'injury_week':report_week,'players':list(players.values())}

def build():
    import nflreadpy as nfl
    season=int(os.getenv('SEASON',datetime.now().year))
    result=normalize(nfl.load_rosters_weekly([season]).to_dicts(),nfl.load_injuries([season]).to_dicts(),season)
    if len({p['team'] for p in result['players']})!=32:raise RuntimeError('Incomplete active roster source; previous snapshot retained')
    result.update(schema_version=1,generated_at=datetime.now(timezone.utc).isoformat(),status='FRESH',
                  source='nflverse weekly rosters and injury reports',source_url='https://github.com/nflverse/nflverse-data',
                  note='Active roster at the published weekly snapshot; game-day inactive status is separate. Injury report week is shown explicitly.')
    atomic_json(ROOT/'data/nfl_roster.json',result)
    print(f"Roster: {len(result['players'])} players, 32 teams, week {result['week']}")

if __name__=='__main__':build()
