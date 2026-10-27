"""Retrospective King of the Court backtest on every 2025-26 Tuesday, run through Codex's unchanged simulator.

Field per team: players with minutes for that team in any released current-season game, plus anyone the
official pregame injury report listed for it. Slates start once every team has 3 released games. Availability: Out/Doubtful on that report -> out. Origin: the day's first
tipoff minus 1 hour. Outcomes come only after the slate is built. Two configurations share every slate:
  codex_minutes  - Codex's own current-team minutes prior (no explicit minutes scenario)
  rotation_minutes - the explicit rotation-aware minutes scenario from kotc.expected_minutes
Retrospective fields are reconstructions, not archived pregame rosters; see docs/KOTC.md.
"""
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from .config import CACHE,REPORTS,now,once
from . import codex_research as CR
from . import kotc as K

OUT=REPORTS/'kotc_backtest_v1';HISTORY=CR.KOTC/'backtest-history-2026.json';SEASON=2026;DRAWS=4000
CONFIGS=('codex_minutes','rotation_minutes')
LAG=36  # Codex retrospective release rule: a result is usable 36 hours after tipoff


def slates():
    history=json.loads(HISTORY.read_text(encoding='utf-8'));games=history['games']
    reports=pd.read_parquet(CACHE/'injury_reports.parquet')
    boxes=pd.read_parquet(CACHE/'player_boxes.parquet',columns=['athlete_id','season','team_id','team_abbreviation'])
    codes={str(r.team_id):K.ALIASES.get(r.team_abbreviation,r.team_abbreviation) for r in boxes[['team_id','team_abbreviation']].drop_duplicates().itertuples()}
    reports=reports.assign(team_code=reports.team_id.astype(str).map(codes))
    debut=boxes.assign(athlete_id='espn:'+boxes.athlete_id.astype(str)).groupby('athlete_id').season.min().astype(int).to_dict()
    by_day=defaultdict(list)
    for g in games:
        if g['season']==SEASON:by_day[pd.Timestamp(g['tipoff']).tz_convert('America/New_York').date()].append(g)
    names={p['player_id']:(p['name'],p.get('position','?')) for g in games for p in g['players']}
    for day in sorted(d for d in by_day if d.weekday()==1):
        target=by_day[day];origin=min(pd.Timestamp(g['tipoff']) for g in target)-pd.Timedelta(hours=1)
        window=[g for g in games if g['season']==SEASON and pd.Timestamp(g['tipoff'])+pd.Timedelta(hours=LAG)<origin]
        if any(sum(code in (w['home'],w['away']) for w in window)<3 for g in target for code in (g['home'],g['away'])):continue
        listed=reports[reports.report_day.eq(str(day))&reports.game_id.notna()&reports.athlete_id.notna()]
        # Current team = the official report's team that day, else the latest team he played for (trades).
        current={}
        for w in sorted(window,key=lambda w:w['tipoff']):
            for p in w['players']:
                if p.get('minutes'):current[p['player_id']]=p['team']
        for r in listed.itertuples():current['espn:'+str(r.athlete_id)]=r.team_code
        players=[];actual={}
        for g in target:
            gid=g['game_id']
            for code in (g['home'],g['away']):
                recent={p['player_id'] for w in window for p in w['players'] if p['team']==code and p.get('minutes')}
                mine=listed[listed.game_id.eq(gid.removeprefix('espn:'))&listed.team_code.eq(code)]
                official={'espn:'+str(r.athlete_id):r.status for r in mine.itertuples()}
                for pid in sorted(p for p in recent|set(official) if current.get(p)==code):
                    name,position=names.get(pid,(pid,'?'))
                    players.append({'player_id':pid,'name':name,'position':position,'team':code,'game_id':gid,
                                    'debut_season':min(debut.get(pid,SEASON),SEASON),
                                    'availability':'out' if official.get(pid) in ('Out','Doubtful') else 'available',
                                    'selectable':True,'known_at':origin.isoformat(),'source':'Reconstructed: recent team boxes + official injury report'})
            for p in g['players']:actual[p['player_id']]=p['pts']+p['reb']+p['ast']
        slate={'date':str(day),'season':SEASON,'origin':origin.isoformat(),'known_at':origin.isoformat(),'regular_season':True,
               'source':'Retrospective reconstruction','evidence_kind':'retrospective_fixture','field_complete':True,'rosters_complete':True,
               'full_terms_verified':False,'eligible_game_ids':[g['game_id'] for g in target],'eligible_player_ids':[p['player_id'] for p in players],
               'games':[{'game_id':g['game_id'],'home':g['home'],'away':g['away'],'tipoff':g['tipoff'],'status':'scheduled'} for g in target],
               'players':players}
        yield slate,actual,games


def run(log=print):
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for slate,actual,games in slates():
        minutes=None
        for config in CONFIGS:
            path=OUT/f'{slate["date"]}_{config}.json'
            if not path.exists():
                s=json.loads(json.dumps(slate))
                if config=='rotation_minutes':
                    minutes=minutes or K.minute_history(HISTORY,pd.Timestamp(slate['origin']),SEASON,LAG)
                    for p in s['players']:
                        scenario=K.expected_minutes(p['player_id'],p['team'],minutes,slate['origin'])
                        if scenario:p['expected_minutes']=scenario
                (OUT/f'{slate["date"]}_{config}_slate.json').write_text(json.dumps(s),encoding='utf-8')
                (OUT/'parameters.json').write_text(json.dumps(K.DEFAULT_PARAMETERS),encoding='utf-8')
                CR.run('-m','scripts.king_court','simulate','--history',str(HISTORY),'--slate',str(OUT/f'{slate["date"]}_{config}_slate.json'),
                       '--research-parameters',str(OUT/'parameters.json'),'--draws',str(DRAWS),'--mode','retrospective','--output',str(path),timeout=3600)
            rows.append(score(slate,actual,config,path));log(rows[-1])
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'slates.csv',index=False)
    return frame


def score(slate,actual,config,path):
    run=json.loads(Path(path).read_text(encoding='utf-8'))
    field={p['player_id'] for p in slate['players']}
    best=max(actual.values());leaders={p for p,v in actual.items() if v==best}
    credit={p['player_id']:p['fractional_leader_credit'] for p in run['players']}
    inclusive={p['player_id']:p['inclusive_leader_probability'] for p in run['players']}
    expected={p['player_id']:p['expected_pra'] for p in run['players']}
    top=max(credit,key=credit.get)
    played=[p for p in field if p in actual]
    season_avg={p['player_id']:p.get('season_average_pra') or 0 for p in run['players']}
    naive=max(season_avg,key=season_avg.get)
    probability=sum(credit.get(p,0.) for p in leaders)
    return {'date':slate['date'],'config':config,'games':len(slate['games']),'field':len(field),
            'leaders':', '.join(sorted(leaders)),'leader_pra':best,'leaders_in_field':len(leaders&field),
            'leader_probability':probability,'log_score':float(np.log(max(probability,1e-4))),
            'brier_inclusive':float(sum((inclusive[p]-(p in leaders))**2 for p in inclusive)),
            'top_pick':top,'top_pick_hit':top in leaders,'top_pick_credit':credit[top],
            'naive_pick_hit':naive in leaders,'pra_mae':float(np.mean([abs(expected[p]-actual[p]) for p in played])) if played else None,
            'missing_leader':bool(leaders-field)}


def summarize(frame):
    out={}
    for config,x in frame.groupby('config'):
        out[config]={'slates':len(x),'mean_log_score':x.log_score.mean(),'mean_leader_probability':x.leader_probability.mean(),
                     'top_pick_hits':int(x.top_pick_hit.sum()),'naive_pick_hits':int(x.naive_pick_hit.sum()),
                     'mean_top_pick_credit':x.top_pick_credit.mean(),'pra_mae':x.pra_mae.mean(),'brier_inclusive':x.brier_inclusive.mean(),
                     'slates_leader_not_in_field':int(x.missing_leader.sum())}
    a=frame[frame.config.eq('rotation_minutes')].set_index('date');b=frame[frame.config.eq('codex_minutes')].set_index('date')
    d=(a.log_score-b.log_score).dropna();rng=np.random.default_rng(20261027)
    boot=[d.sample(len(d),replace=True,random_state=int(rng.integers(1<<30))).mean() for _ in range(2000)]
    out['rotation_minus_codex_log_score']={'mean':float(d.mean()),'ci_low':float(np.quantile(boot,.025)),'ci_high':float(np.quantile(boot,.975)),
                                           'slates_better':int((d>0).sum()),'slates':len(d)}
    return out
