"""King of the Court: build tonight's complete Tuesday slate from free sources, run Codex's frozen PRA simulator.

Sources: ESPN scoreboard (games) and team rosters (field, positions, experience), the official NBA injury
report (availability), SportsDataverse boxes via Codex's own history. Raw responses are archived by SHA256.
The simulator itself is Codex's unchanged code, run as a subprocess (see codex_research.py).
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from .config import ROOT,CACHE,RAW,now,stamp,once
from . import codex_research as CR
from . import injury_reports as R

ESPN='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'
OUT=ROOT/'artifacts'/'kotc';ARCHIVE=RAW/'archive'/'kotc'
ALIASES={'GS':'GSW','SA':'SAS','NY':'NYK','NO':'NOP','UTAH':'UTA','WSH':'WAS'}
# Fixed before any backtest: protocol grid member used until a registered selection exists (docs/KOTC.md).
DEFAULT_PARAMETERS={'season_decay':.65,'game_half_life_days':30,'prior_games':15}
# Expected-minutes scenario (fixed before any backtest): blend the current team's rotation this season, where
# games a player missed count as 0, with his own recent played minutes, worth ROTATION_PRIOR games.
# A player with no minutes in 2+ current-team games is outside the rotation.
MINUTE_GAMES,MINUTE_HALF_LIFE,MINUTE_SD_FLOOR,TEAM_GAMES,ROTATION_PRIOR=15,5.,4.,10,3.


def minute_history(path,origin,season,lag_hours=None):
    """Before origin: player -> played minutes (oldest first); team -> list of {player: minutes} this season.
    Live runs use each game's known_at; retrospective runs use tipoff + lag_hours, as Codex's retrospective mode does."""
    games=json.loads(Path(path).read_text(encoding='utf-8'))['games']
    own,team={},{}
    for g in sorted(games,key=lambda g:g['tipoff']):
        released=pd.Timestamp(g['tipoff'])+pd.Timedelta(hours=lag_hours) if lag_hours else pd.Timestamp(g['known_at'])
        if released>=origin:continue
        for p in g['players']:
            if p.get('minutes'):own.setdefault(p['player_id'],[]).append(float(p['minutes']))
        if g['season']==season:
            for code in (g['home'],g['away']):
                team.setdefault(code,[]).append({p['player_id']:float(p.get('minutes') or 0) for p in g['players'] if p['team']==code})
    return {'own':own,'team':team}


def expected_minutes(pid,code,history,known_at):
    """Explicit pregame minutes scenario, or None with no NBA minutes at all (Codex's experience prior applies)."""
    recent=history['own'].get(pid,[])[-MINUTE_GAMES:];rotation=history['team'].get(code,[])[-TEAM_GAMES:]
    if not recent:return None
    w=0.5**(np.arange(len(recent))[::-1]/MINUTE_HALF_LIFE);x=np.array(recent)
    own=float(np.average(x,weights=w));sd=float(np.sqrt(np.average((x-own)**2,weights=w)))
    current=[g.get(pid,0.) for g in rotation]
    if len(current)>=2 and not any(current):return {'mean':0.5,'sd':MINUTE_SD_FLOOR,'known_at':known_at,'source':'No minutes in any current-team game'}
    mean=(sum(current)+ROTATION_PRIOR*own)/(len(current)+ROTATION_PRIOR)
    if mean<=.5:return None if not current else {'mean':0.5,'sd':MINUTE_SD_FLOOR,'known_at':known_at,'source':'Out of current rotation'}
    return {'mean':round(min(mean,48.),2),'sd':round(max(sd,MINUTE_SD_FLOOR),2),'known_at':known_at,
            'source':f'{len(current)} current-team games (missed = 0) blended with last {len(recent)} played games, prior {ROTATION_PRIOR:g} games'}


def archive(name,payload,retrieved):
    raw=json.dumps(payload,sort_keys=True).encode()
    checksum=hashlib.sha256(raw).hexdigest()
    path=ARCHIVE/f'{name}_{retrieved.strftime("%Y%m%dT%H%M%SZ")}_{checksum[:12]}.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():path.write_bytes(raw)
    return {'path':str(path),'sha256':checksum,'retrieved_at':retrieved.isoformat()}


def get(url,session):
    response=session.get(url,timeout=30);response.raise_for_status();return response.json()


def debut_season(years,season):
    """ESPN experience counts the current season (2 = second season) but lists rookies as 0."""
    if years is None:return None
    return season if int(years)==0 else season-int(years)+1


def availability(report,season,games):
    """Official pregame report -> {espn athlete id: status}; teams that have not submitted are flagged."""
    if not report.get('url'):return {},set(),None
    from .injury_shadow import report_rows
    players=pd.read_parquet(CACHE/'player_boxes.parquet')
    rows=report_rows(report,season,games,players)
    status={str(r.athlete_id):r.status for r in rows.itertuples() if r.athlete_id and not r.not_yet_submitted}
    pending={str(r.team_id) for r in rows.itertuples() if r.not_yet_submitted}
    return status,pending,report


def build_slate(date,session=None,at=None,minutes=None):
    """Complete pregame slate manifest in Codex's contract, plus a readable roster table."""
    session=session or requests.Session();at=pd.Timestamp(at or pd.Timestamp.now(tz='UTC'))
    day=pd.Timestamp(date).date()
    if day.weekday()!=1:raise ValueError('King of the Court slates are Tuesdays only')
    board=get(ESPN+'scoreboard?dates='+day.strftime('%Y%m%d'),session)
    receipts={'scoreboard':archive(f'scoreboard_{day:%Y%m%d}',board,at)}
    games=[];teams={}
    for event in board['events']:
        competition=event['competitions'][0]
        if event['status']['type']['name']!='STATUS_SCHEDULED':raise ValueError(f"Game {event['id']} is {event['status']['type']['name']}; the slate must be frozen before the first tipoff")
        sides={c['homeAway']:c['team'] for c in competition['competitors']}
        games.append({'game_id':'espn:'+event['id'],'home':ALIASES.get(sides['home']['abbreviation'],sides['home']['abbreviation']),
                      'away':ALIASES.get(sides['away']['abbreviation'],sides['away']['abbreviation']),
                      'tipoff':pd.Timestamp(event['date']).isoformat(),'status':'scheduled'})
        for side in ('home','away'):teams[sides[side]['id']]=(games[-1]['game_id'],games[-1][side])
    if not games:raise ValueError('No NBA games on this date')
    season=int(board['leagues'][0]['season']['year'])
    first=min(pd.Timestamp(g['tipoff']) for g in games)
    if at>=first:raise ValueError('First game has started; a whole-slate pregame forecast is no longer possible')
    report=CR_report(day,first,at,session)
    schedule=pd.read_parquet(CACHE/'games.parquet')
    status,pending,report=availability(report,season,schedule)
    box_first=pd.read_parquet(CACHE/'player_boxes.parquet',columns=['athlete_id','season']).assign(athlete_id=lambda d:d.athlete_id.astype(str)).groupby('athlete_id').season.min()
    players=[];table=[]
    for team_id,(game_id,code) in teams.items():
        roster=get(ESPN+f'teams/{team_id}/roster',session)
        receipts[f'roster_{code}']=archive(f'roster_{code}',roster,at)
        for a in roster['athletes']:
            pid=str(a['id']);espn_injury=(a.get('injuries') or [{}])[0].get('status')
            debut=debut_season(a.get('experience',{}).get('years'),season)
            if pid in box_first.index and (debut is None or box_first[pid]<debut):debut=int(box_first[pid])  # an earlier NBA box is conclusive
            official=status.get(pid)
            out=official in ('Out','Doubtful') or (official is None and team_id in pending and espn_injury=='Out')
            scenario=expected_minutes('espn:'+pid,code,minutes,at.isoformat()) if minutes else None
            players.append({'player_id':'espn:'+pid,'name':a['displayName'],'position':(a.get('position') or {}).get('abbreviation','?'),
                            'team':code,'game_id':game_id,'debut_season':debut,'availability':'out' if out else 'available',
                            'selectable':True,'known_at':at.isoformat(),
                            'source':'ESPN team roster + official NBA injury report' if report else 'ESPN team roster (no official report yet)',
                            **({'expected_minutes':scenario} if scenario else {})})
            table.append({'player_id':'espn:'+pid,'name':a['displayName'],'team':code,'official_status':official or ('team not submitted' if team_id in pending else 'not listed'),
                          'espn_injury':espn_injury,'availability':players[-1]['availability'],'debut_season':debut})
    missing=[p['name'] for p in players if p['debut_season'] is None]
    if missing:raise ValueError('No experience metadata for: '+', '.join(missing))
    field={'date':str(day),'eligible_game_ids':[g['game_id'] for g in games],'eligible_player_ids':[p['player_id'] for p in players],
           'built_from':{k:v['sha256'] for k,v in receipts.items()}}
    field_receipt=archive(f'field_{day:%Y%m%d}',field,at)
    slate={'date':str(day),'season':season,'origin':at.isoformat(),'known_at':at.isoformat(),'regular_season':True,
           'source':'ESPN scoreboard and rosters; official NBA injury report','evidence_kind':'prospective',
           'field_complete':True,'rosters_complete':True,'full_terms_verified':False,
           'eligible_game_ids':field['eligible_game_ids'],'eligible_player_ids':field['eligible_player_ids'],'games':games,'players':players,
           'field_source_receipt':{'path':field_receipt['path'],'sha256':field_receipt['sha256'],'known_at':at.isoformat(),
                                   'source':'Field list built from archived ESPN scoreboard and roster responses'},
           'availability_source':{'official_report_url':report.get('url') if report else None,
                                  'official_report_published_at':str(report.get('available_at')) if report else None,
                                  'teams_not_submitted':sorted(pending)},'raw_receipts':receipts}
    return slate,pd.DataFrame(table)


def CR_report(day,first,at,session):
    from .injury_shadow import live_report
    try:return live_report(str(day),first,at,session)
    except Exception as error:return {'url':None,'error':type(error).__name__+': '+str(error)[:200]}


def history():
    """Fresh Codex history (current season plus three prior), rebuilt when older than 12 hours."""
    paths=sorted(CR.KOTC.glob('history-*.json'),key=lambda p:p.stat().st_mtime)
    if paths and pd.Timestamp.now().timestamp()-paths[-1].stat().st_mtime<12*3600:return paths[-1]
    version=stamp();sources=f'.cache/king-court/sources-{version}.json';output=f'.cache/king-court/history-{version}.json'
    CR.run('-m','scripts.king_court','fetch','--seasons','2024','2025','2026','2027','--cache','.cache/king-court/raw','--output',sources)
    CR.run('-m','scripts.king_court','ingest','--manifest',sources,'--output',output)
    return CR.PACKAGE/output


def simulate(date,draws=20000,parameters=None,at=None):
    """Builds the slate, runs Codex's simulator, saves a readable result next to its sealed receipt."""
    source=history()  # fetched first: the simulator requires its schedule receipt to predate the slate origin
    at=pd.Timestamp(at or pd.Timestamp.now(tz='UTC'))
    slate,table=build_slate(date,at=at,minutes=minute_history(source,at,int(pd.Timestamp(date).year)+(1 if pd.Timestamp(date).month>=8 else 0)))
    version=stamp();directory=OUT/f'{slate["date"]}_{version}';directory.mkdir(parents=True,exist_ok=False)
    (directory/'slate.json').write_text(json.dumps(slate,indent=2),encoding='utf-8')
    (directory/'parameters.json').write_text(json.dumps(parameters or DEFAULT_PARAMETERS),encoding='utf-8')
    table.to_csv(directory/'field.csv',index=False)
    receipt=directory/'simulation.json'
    CR.run('-m','scripts.king_court','simulate','--history',str(source),'--slate',str(directory/'slate.json'),
           '--research-parameters',str(directory/'parameters.json'),'--draws',str(draws),'--mode','prospective','--output',str(receipt),timeout=3600)
    result=summary(receipt)
    result.to_csv(directory/'players.csv',index=False)
    once(directory/'META.json',{'created_at':now(),'date':slate['date'],'draws':draws,'parameters':parameters or DEFAULT_PARAMETERS,
         'players':len(result),'games':len(slate['games']),'availability_source':slate['availability_source'],
         'receipt':str(receipt),'status':'Research simulation; parameters not selected by registered prospective folds.'})
    return directory


def summary(receipt):
    run=json.loads(Path(receipt).read_text(encoding='utf-8'))
    rows=[]
    for p in run['players']:
        q=p.get('pra_quantiles') or {};c=p.get('expected_components') or {}
        rows.append({'player_id':p['player_id'],'name':p['name'],'team':p['team'],'availability':p['availability'],
                     'experience':p.get('experience'),'minutes':p.get('expected_minutes'),'pts':c.get('points'),'reb':c.get('rebounds'),
                     'ast':c.get('assists'),'pra':p.get('expected_pra'),'pra_p10':q.get('p10'),'pra_p50':q.get('p50'),'pra_p90':q.get('p90'),
                     'sole_leader':p.get('sole_leader_probability'),'tied_leader':p.get('tied_leader_probability'),
                     'inclusive_leader':p.get('inclusive_leader_probability'),'tie_credit':p.get('fractional_leader_credit'),
                     'evidence_games':(p.get('evidence') or {}).get('games'),'prior':(p.get('prior') or {}).get('kind')})
    return pd.DataFrame(rows).sort_values('tie_credit',ascending=False)


def samples(receipt):
    run=json.loads(Path(receipt).read_text(encoding='utf-8'))
    with np.load(run['simulation_artifact']['path'],allow_pickle=False) as arrays:
        return arrays['player_ids'].tolist(),arrays['pra__recency']


def prize_share(ids,pra,ownership,entrants,pool=1_000_000,selectable=None):
    """Expected face-value bonus share for one entry on each player:
    pool * P(player is a leader) * E[1 / (1 + other entrants on every tied leader)].
    Other entrants are spread by the ownership vector (their expected counts; a hypothetical scenario)."""
    ids=list(ids);own=np.array([ownership.get(i,0.) for i in ids]);own=own/own.sum()
    counts=entrants*own
    best=pra.max(axis=1,keepdims=True);leaders=pra==best
    crowd=leaders@counts
    share=np.where(leaders,pool/(1+crowd)[:,None],0.)
    return pd.DataFrame({'player_id':ids,'leader_probability':leaders.mean(axis=0),'expected_share':share.mean(axis=0),
                         'share_if_leader':np.divide(share.sum(axis=0),leaders.sum(axis=0),out=np.zeros(len(ids)),where=leaders.sum(axis=0)>0)})
