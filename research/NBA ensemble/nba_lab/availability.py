"""Prospective ESPN availability context; never adjusts model probabilities.

Only selected injury/roster fields are retained. Empty responses are unknown,
not a healthy lineup. ESPN athlete IDs are used without inferred name joins.
"""
import hashlib
import json
import uuid
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from .config import CACHE,DATA,RAW,now,stamp,once,digest
from .research_io import update

BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'
STATUSES={'out','doubtful','questionable','probable','available','day-to-day'}


def identity(value):
    text=str(value).strip()
    return text if text.isdigit() else None


def injury_row(injury,athlete,game,team,retrieved,source):
    player=identity(athlete.get('id'))
    if player is None:return None
    status=str(injury.get('status','Unknown')).strip()
    published=pd.to_datetime(injury.get('date'),utc=True,errors='coerce')
    future=bool(pd.notna(published) and published>retrieved)
    stale=bool(pd.notna(published) and retrieved-published>pd.Timedelta(hours=24))
    return {'game_id':str(game.game_id),'tipoff':pd.Timestamp(game.tipoff).isoformat(),
        'team_id':team,'team':game.home if str(game.home_id)==team else game.away,
        'player_id':player,'player':str(athlete.get('displayName') or athlete.get('fullName') or ''),
        'status':'Unknown' if future or status.lower() not in STATUSES else status,
        'provider_status':status,'injury_published_at':published.isoformat() if pd.notna(published) else None,
        'retrieved_at':retrieved.isoformat(),'source':source,
        'source_url':BASE+('summary?event='+str(game.game_id) if source=='ESPN game injury summary' else 'teams/'+team+'/roster'),
        'future_dated':future,
        'injury_update_older_than_24h':stale,'conflict':False,
        'verification':'future_timestamp' if future else ('publication_time_missing' if pd.isna(published) else 'current_source_entry'),
        'warning':'Source entry only; an old injury update is not a stale retrieval or a confirmed lineup.'}


def parse_summary(payload,game,retrieved):
    rows=[];reports=[]
    for team in (str(game.home_id),str(game.away_id)):
        groups=[r for r in payload.get('injuries',[]) if str(r.get('team',{}).get('id'))==team]
        entries=[i for g in groups for i in g.get('injuries',[])]
        valid=0
        for injury in entries:
            row=injury_row(injury,injury.get('athlete',{}),game,team,retrieved,'ESPN game injury summary')
            if row:rows.append(row);valid+=1
        reports.append({'game_id':str(game.game_id),'team_id':team,
                        'report_status':'entries_returned' if entries else 'unknown_no_entries',
                        'entries':len(entries),'invalid_player_id_entries':len(entries)-valid,
                        'source_url':BASE+'summary?event='+str(game.game_id),'retrieved_at':retrieved.isoformat()})
    return rows,reports


def parse_roster(payload,team,retrieved):
    if str(payload.get('team',{}).get('id'))!=team:raise ValueError('Roster team ID mismatch')
    published=pd.to_datetime(payload.get('timestamp'),utc=True,errors='coerce')
    if pd.notna(published) and published>retrieved:raise ValueError('Future roster timestamp')
    athletes=[];invalid=0
    for a in payload.get('athletes',[]):
        aid=identity(a.get('id'))
        if aid is None:invalid+=1;continue
        athletes.append({'id':aid,'displayName':str(a.get('displayName','')),
                         'injuries':[{'status':i.get('status'),'date':i.get('date')} for i in a.get('injuries',[])]})
    ids=[a['id'] for a in athletes]
    if not ids or len(set(ids))!=len(ids):raise ValueError('Empty or duplicate roster IDs')
    return {'team_id':team,'source_url':BASE+'teams/'+team+'/roster','invalid_player_id_entries':invalid,
            'provider_timestamp':published.isoformat() if pd.notna(published) else None,
            'retrieved_at':retrieved.isoformat(),'athletes':athletes}


def reconcile(rows):
    grouped={}
    for row in rows:
        key=(row['game_id'],row['team_id'],row['player_id'])
        grouped.setdefault(key,[]).append(row)
    result=[]
    for entries in grouped.values():
        chosen=entries[0].copy();statuses={r['status'].lower() for r in entries}
        chosen['source']='; '.join(sorted({r['source'] for r in entries}))
        chosen['source_url']='; '.join(sorted({r['source_url'] for r in entries}))
        if len(statuses)>1:
            chosen['status']='Unknown';chosen['conflict']=True;chosen['verification']='source_conflict'
        chosen['future_dated']=any(r['future_dated'] for r in entries)
        result.append(chosen)
    return result


def continuity(players,team,roster_ids,retrieved,season,out_ids=None):
    d=players[players.team_id.astype(str).eq(team)].copy()
    available=pd.to_datetime(d.available_at,utc=True)
    d=d[available.lt(retrieved)]
    # Rows with zero/missing/negative minutes carry no denominator mass.
    minutes=pd.to_numeric(d.minutes,errors='coerce')
    d['usable_minutes']=minutes.where(np.isfinite(minutes)&minutes.gt(0),0.)
    games=d[['game_id','tipoff']].drop_duplicates().sort_values('tipoff').tail(20).game_id
    hist=d[d.game_id.isin(games)];total=float(hist.usable_minutes.sum())
    retained=float(hist[hist.athlete_id.astype(str).isin(roster_ids or set())].usable_minutes.sum())
    out_minutes=float(hist[hist.athlete_id.astype(str).isin(out_ids or set())].usable_minutes.sum())
    return {'team_id':team,'released_current_season_games':int(d[d.season.eq(season)].game_id.nunique()),
            'history_games':int(len(games)),'last20_minutes':total,
            'roster_retained_minutes_share':retained/total if total>0 and roster_ids is not None else None,
            'known_out_last20_minutes_share':out_minutes/total if total>0 and out_ids is not None else None,
            'diagnostic_only':True,'warning':'Roster membership is not confirmed playing availability; no probability adjustment.'}


def _get(path,session):
    response=session.get(BASE+path,timeout=(5,15),headers={'User-Agent':'NBA-Ensemble-Local-Research/1.0'})
    response.raise_for_status()
    if len(response.content)>5_000_000:raise ValueError('Availability source too large')
    return response.json()


def collect(date=None,session=None):
    session=session or requests
    started=pd.Timestamp(now());date=pd.Timestamp(date or started.tz_convert('America/New_York').date()).date()
    games=pd.read_parquet(CACHE/'games.parquet')
    tip=pd.to_datetime(games.tipoff,utc=True)
    slate=games[tip.dt.tz_convert('America/New_York').dt.date.eq(date)&tip.gt(started)&~games.completed]
    rows=[];reports=[];issues=[];rosters={};teams=[]
    players=pd.read_parquet(CACHE/'player_boxes.parquet') if (CACHE/'player_boxes.parquet').exists() else None
    for game in slate.itertuples(index=False):
        if pd.Timestamp(game.tipoff)<=pd.Timestamp(now()):continue
        try:
            payload=_get('summary?event='+str(game.game_id),session);retrieved=pd.Timestamp(now())
            if retrieved>=pd.Timestamp(game.tipoff):raise ValueError('Game started during availability retrieval')
            selected,status=parse_summary(payload,game,retrieved);rows.extend(selected);reports.extend(status)
            del payload
        except Exception as e:
            issues.append({'game_id':str(game.game_id),'source':'summary','error':type(e).__name__})
            reports.extend({'game_id':str(game.game_id),'team_id':team,'report_status':'source_unavailable',
                            'entries':None,'retrieved_at':now(),'error':type(e).__name__}
                           for team in (str(game.home_id),str(game.away_id)))
        for team in (str(game.home_id),str(game.away_id)):
            if pd.Timestamp(game.tipoff)<=pd.Timestamp(now()):
                issues.append({'game_id':str(game.game_id),'team_id':team,'source':'roster','error':'GameAlreadyStarted'})
                continue
            if team not in rosters:
                try:
                    payload=_get('teams/'+team+'/roster',session);retrieved=pd.Timestamp(now())
                    if retrieved>=pd.Timestamp(game.tipoff):raise ValueError('Game started during roster retrieval')
                    rosters[team]=parse_roster(payload,team,retrieved);del payload
                except Exception as e:
                    rosters[team]=None;issues.append({'game_id':str(game.game_id),'team_id':team,'source':'roster','error':type(e).__name__})
            roster=rosters[team]
            if roster:
                for a in roster['athletes']:
                    for injury in a['injuries']:
                        row=injury_row(injury,a,game,team,pd.Timestamp(roster['retrieved_at']),'ESPN current roster')
                        if row:rows.append(row)
    rows=reconcile(rows)
    for game in slate.itertuples(index=False):
        for team in (str(game.home_id),str(game.away_id)):
            roster=rosters.get(team);roster_ids={a['id'] for a in roster['athletes']} if roster else None
            report=next((r for r in reports if r['game_id']==str(game.game_id) and r['team_id']==team),None)
            known_out={r['player_id'] for r in rows if r['game_id']==str(game.game_id) and r['team_id']==team and r['status'].lower()=='out'}
            # Unknown report/roster source must not imply zero missing-player mass.
            out_ids=known_out if known_out or (roster and report and report['report_status']=='entries_returned') else None
            if players is not None:
                retrieved=pd.Timestamp(roster['retrieved_at']) if roster else pd.Timestamp(now())
                metric=continuity(players,team,roster_ids,retrieved,int(game.season),out_ids)
            else:
                metric={'team_id':team,'released_current_season_games':None,'history_games':None,'last20_minutes':None,
                        'roster_retained_minutes_share':None,'known_out_last20_minutes_share':None,'diagnostic_only':True}
            metric.update({'game_id':str(game.game_id),'team':game.home if team==str(game.home_id) else game.away,
                'retrieved_at':roster['retrieved_at'] if roster else None,
                'continuity_status':'available' if roster and players is not None and metric['last20_minutes']>0 else
                    ('roster_unavailable' if not roster else 'player_history_unavailable'),
                'warning':'Roster/out-minute diagnostics only; missing sources remain unknown. No probability adjustment.'})
            teams.append(metric)
    result={'created_at':now(),'date':str(date),'games':int(len(slate)),'rows':rows,
        'teams':teams,'reports':reports,'rosters':list(r for r in rosters.values() if r),'issues':issues,
        'games_sha256':digest(CACHE/'games.parquet'),
        'player_history_sha256':digest(CACHE/'player_boxes.parquet') if (CACHE/'player_boxes.parquet').exists() else None,
        'model_input':False,'lineup_verified':False,
        'warning':'Availability context only. Empty reports are unknown; no probability adjustment or confirmed lineup.'}
    body=json.dumps(result,sort_keys=True,default=str,allow_nan=False).encode();checksum=hashlib.sha256(body).hexdigest()
    directory=RAW/'archive'/'availability'/(stamp()+'_'+uuid.uuid4().hex[:8]);directory.mkdir(parents=True,exist_ok=False)
    snapshot=directory/(checksum[:16]+'.json')
    with snapshot.open('xb') as f:f.write(body)
    once(directory/'META.json',{'created_at':result['created_at'],'sha256':checksum,'path':str(snapshot),'source':'ESPN filtered injury/roster fields only'})
    result['snapshot_path']=str(snapshot);result['sha256']=checksum
    CACHE.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(result['rows'],columns=['game_id','tipoff','team_id','team','player_id','player','status','provider_status',
        'injury_published_at','retrieved_at','source','source_url','future_dated','injury_update_older_than_24h','conflict','verification','warning']).to_csv(CACHE/'availability.csv',index=False)
    update(DATA/'AVAILABILITY.json',result)
    return result
