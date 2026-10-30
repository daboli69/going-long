"""Explicit prospective lineup scenarios; original v1/v2 archives are untouched."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import pandas as pd
import psutil
from . import weekly as W
from ..config import ARTIFACTS_DIR, LAB_ROOT
from ..fpds_research.common import atomic

ROOT=ARTIFACTS_DIR/'props'/'injury_adjusted'
# Doubtful added 2026-10-30 (Travis approved). On 2021-2024 history, treating Doubtful as unavailable improved the log likelihood of who gets targets
# (+0.0071 nats, 98.75% CI 0.0017 to 0.0125) and carries (+0.0121, 0.0069 to 0.0184), positive in both 2021-2023 and 2024:
# docs/MARKET_NEWS_PREREGISTRATION.md Amendment 3, docs/MARKET_NEWS_RESULTS.md. Questionable and unknown are still never removed.
# To restore the earlier rule, delete 'doubtful' from this set. The preregistered weekly archive (weekly.py) is not affected.
OUT_STATUSES={'out','inactive','ir','pup','doubtful'}
AVAILABILITY_RULE='Out, inactive, IR, PUP and Doubtful treated as unavailable (Doubtful added 2026-10-30, usage evidence in docs/MARKET_NEWS_RESULTS.md); Questionable and unknown are not removed'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def participants(info,a):
    """Report every already-modeled participant; does not change simulation inputs."""
    result=[]
    for team,qb,inputs in info:
        if qb:result.append((team,qb,'pass_yds'))
        for pid in inputs['rush'].index[inputs['rush']['share']>0]:result.append((team,pid,'rush_yds'))
        for pid in inputs['recv'].index[inputs['recv']['share']>0]:
            result.extend((team,pid,stat) for stat in ('rec','rec_yds'))
    return list(dict.fromkeys(result))


def latest_completed(root=None):
    """One immutable completed copy per game; creation timestamp, never file mtime."""
    root=Path(root) if root is not None else ROOT
    selected={}
    for path in root.glob('*/RESULT.json'):
        item=read(path)
        if item.get('state')!='complete':continue
        game=item['game_id']
        if game not in selected or pd.Timestamp(item['created_at'])>pd.Timestamp(selected[game]['created_at']):selected[game]=item
    return selected


def context(game, now, state=None):
    from ..fpds_drop import STATE
    state=Path(state) if state is not None else STATE
    pointer=state/f'CONFIRMATION_W{int(game.week):02d}.json'
    if not pointer.exists():raise ValueError('Refresh injuries with START_HERE option 6 first.')
    metadata=read(pointer)
    created=pd.Timestamp(metadata['created_at'])
    if created>now or now-created>pd.Timedelta(hours=24):raise ValueError('Injury comparison is future-dated or over 24 hours old. Refresh first.')
    path=Path(metadata['path'])/'CONFIRMATION_PRIVATE.parquet'
    body=path.read_bytes()
    rows=pd.read_parquet(path)
    if rows.empty:raise ValueError('No matched injury statuses. Review source errors before simulating.')
    rows=rows[rows.game_id.eq(game.game_id)&rows.team.isin([game.home_team,game.away_team])].copy()
    for team in (game.home_team,game.away_team):
        z=rows[rows.team.eq(team)]
        if z.empty or not z.effective_status.ne('unknown').any():raise ValueError(f'No known matched injury context for {team}; coverage unknown.')
    for row in rows.itertuples():
        if not row.conflict:continue
        sources=json.loads(row.sources) if isinstance(row.sources,str) else row.sources
        known={s['status'] for s in sources.values()}-{'unknown'}
        # Preserve source conflicts; only statuses with the same exclusion effect are compatible.
        if row.effective_status=='unknown' or not known or len({s in OUT_STATUSES for s in known})>1:
            raise ValueError('Injury sources conflict on availability for this game; resolve or refresh before simulating.')
    for row in rows.itertuples():
        if row.effective_status=='unknown':continue
        sources=json.loads(row.sources) if isinstance(row.sources,str) else row.sources
        source=sources.get(row.selected_source)
        if source is None: # unanimous secondary agreement; every contributing source must be timely
            source_times=[pd.Timestamp(s['available_at']) for s in sources.values() if s['status']!='unknown']
        else:source_times=[pd.Timestamp(source['available_at'])]
        if not source_times or any(t>now or now-t>pd.Timedelta(hours=24) for t in source_times):
            raise ValueError('Selected injury evidence is missing, future-dated or stale; refresh first.')
    return rows,{'comparison_created_at':metadata['created_at'],'comparison_sha256':hashlib.sha256(body).hexdigest(),
                 'comparison_path':str(path),'source_errors':metadata.get('source_errors',[])}


def adjuster(rows):
    def apply(game,team,available,qb):
        excluded=set(rows.loc[rows.team.eq(team)&rows.effective_status.isin(OUT_STATUSES),'pid'])
        if not qb or qb in excluded or qb not in set(available.pid):
            raise ValueError(f'{team}: starting QB unavailable/unverified; no replacement guessed.')
        result=available[~available.pid.isin(excluded)].copy()
        if not result.position.isin(['WR','TE','RB']).any() or not result.position.isin(['RB','FB']).any():
            raise ValueError(f'{team}: no eligible receiving/rushing replacement group.')
        return result,f'injury-adjusted shadow: {len(excluded)} known unavailable; existing within-position redistribution'
    return apply


def game_row(game_id,now):
    games=W.load_games()
    match=games[games.game_id.eq(game_id)]
    if len(match)!=1:raise ValueError('Select one known regular-season game.')
    game=next(match.itertuples(index=False))
    if pd.notna(game.home_score) or W.kickoff(game.gameday,game.gametime)<=now:
        raise ValueError('Game has started or finished; no pregame revision permitted.')
    prior=games[games.season.eq(game.season)&games.week.lt(game.week)]
    if prior.home_score.isna().any() or prior.away_score.isna().any():
        raise ValueError('Earlier weeks are not fully complete; refresh data first.')
    if len(prior) and max(W.kickoff(r.gameday,r.gametime) for r in prior.itertuples())+pd.Timedelta(hours=24)>now:
        raise ValueError('Prior-week kickoff +24h gate has not passed.')
    return game


def launch(game_id,root=None):
    root=Path(root) if root is not None else ROOT
    pointer=root/'LATEST_JOB.json'
    if pointer.exists():
        previous=read(pointer)
        if previous.get('pid') and psutil.pid_exists(previous['pid']):
            try:
                if abs(psutil.Process(previous['pid']).create_time()-previous['process_created'])<1:
                    raise ValueError('An injury-adjusted simulation is already running.')
            except psutil.NoSuchProcess:pass
    now=pd.Timestamp.now(tz='UTC');game=game_row(game_id,now)
    rows,info=context(game,now)
    job=root/(now.strftime('%Y%m%dT%H%M%S%fZ')+'_'+uuid.uuid4().hex[:8]);job.mkdir(parents=True,exist_ok=False)
    # Freeze a private copy at click time: later refreshes cannot alter this job's inputs.
    rows.to_parquet(job/'AVAILABILITY.parquet',index=False)
    input_hashes={}
    for name,source in [('ROSTER.parquet',W.RAW_DIR/f'roster_weekly_{game.season}.parquet'),
                        ('INJURIES.parquet',W.RAW_DIR/f'injuries_{game.season}.parquet')]:
        if source.exists():
            body=source.read_bytes()
            with (job/name).open('xb') as stream:stream.write(body)
            input_hashes[name]=hashlib.sha256(body).hexdigest()
    request={'game_id':game_id,'created_at':now.isoformat(),'path':str(job),'n_sims':10000,**info}
    request['availability_input_hashes']=input_hashes
    with (job/'REQUEST.json').open('x',encoding='utf-8') as stream:json.dump(request,stream)
    atomic(job/'STATUS.json',{'state':'queued'})
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    with (job/'RUN.log').open('wb') as stream:
        process=subprocess.Popen([sys.executable,'-m','lab.low_priority','-m','lab.props.injury_adjusted','run',str(job)],
                                 cwd=LAB_ROOT,stdout=stream,stderr=stream,creationflags=flags)
    request.update(pid=process.pid,process_created=psutil.Process(process.pid).create_time())
    atomic(pointer,request)
    return request


def run(job):
    job=Path(job);request=read(job/'REQUEST.json')
    if (job/'RESULT.json').exists():return 0
    try:
        atomic(job/'STATUS.json',{'state':'running','note':'Building existing simulator tables and running 10,000 games.'})
        now=pd.Timestamp.now(tz='UTC');game=game_row(request['game_id'],now)
        # A queued job cannot consume a snapshot which has gone stale since launch.
        if now-pd.Timestamp(request['created_at'])>pd.Timedelta(minutes=30):raise ValueError('Queued injury snapshot expired; start a new run.')
        rows=pd.read_parquet(job/'AVAILABILITY.parquet')
        workload=[]
        roster=pd.read_parquet(job/'ROSTER.parquet')
        names=roster[roster.week.eq(game.week)].drop_duplicates('gsis_id').set_index('gsis_id')['full_name'].to_dict()
        def observe(g,info,history):
            for team,qb,inputs in info:
                if inputs['rush'].empty or inputs['recv'].empty:
                    raise ValueError(f'{team}: no positive-share rushing/receiving allocation; replacement role unknown.')
                for pid in dict.fromkeys(list(inputs['rush'].index)+list(inputs['recv'].index)):
                    workload.append({'team':team,'pid':pid,'player':names.get(pid,pid),
                        'position':roster.loc[roster.gsis_id.eq(pid),'position'].iloc[-1],
                        'carry_share':float(inputs['rush'].loc[pid,'share']) if pid in inputs['rush'].index else 0.0,
                        'target_share':float(inputs['recv'].loc[pid,'share']) if pid in inputs['recv'].index else 0.0,
                        'limited_history':pid not in history.index or float(history.loc[pid].get('games_total',0))<4})
        provenance={'simulation_revision':job.name,'decision_at':now.isoformat(),'anchor_mode':'market-anchored',
                    'simulator_training_through_season':int(game.season)-1,'player_training_through_week':int(game.week)-1,
                    'player_training_season':int(game.season),'availability_snapshot_sha256':request['comparison_sha256']}
        result=W.archive(season=int(game.season),week=int(game.week),now=now,n_sims=10000,out=job/'forecasts',
                         only=[game.game_id],availability_adjuster=adjuster(rows),availability_snapshot=job,
                         revision_metadata=provenance,player_selector=participants,input_observer=observe)
        if game.game_id not in result['archived']:raise ValueError('Selected game was not simulated.')
        if pd.Timestamp.now(tz='UTC')>=W.kickoff(game.gameday,game.gametime):
            raise ValueError('Run finished after kickoff; withheld, not a pregame forecast.')
        forecast=job/'forecasts'/f'{game.season}_w{int(game.week):02d}'/f'{game.game_id}.parquet'
        table=W.projection_table(pd.read_parquet(forecast),keep_pid=True)
        roles=pd.DataFrame(workload)
        if len(roles):
            roles.to_csv(job/'WORKLOAD.csv',index=False,mode='x')
            table=table.merge(roles.drop(columns='player'),left_on=['Team','Player ID'],right_on=['team','pid'],how='left').drop(columns=['team','pid'])
        for key,value in provenance.items():table[key]=value
        table.to_csv(job/'PROJECTIONS.csv',index=False,mode='x')
        excluded=rows[rows.effective_status.isin(OUT_STATUSES)][['team','pid','effective_status']].to_dict('records')
        done={'state':'complete','created_at':pd.Timestamp.now(tz='UTC').isoformat(),'game_id':game.game_id,
              'projection_path':str(job/'PROJECTIONS.csv'),'excluded':excluded,'n_sims':10000,
              'workload_path':str(job/'WORKLOAD.csv') if len(roles) else None,
              'training_cutoff':'Simulator: 2025 season end; player roles: weeks before '+str(game.week)+' of '+str(game.season),
              'availability_rule':AVAILABILITY_RULE,'warning':'Assumption-based market-anchored shadow. V1/v2 workload redistribution; baseline B unchanged. No winner/FPDS/Phase10 sheet update.',
              'source_snapshot':request['comparison_sha256']}
        with (job/'RESULT.json').open('x',encoding='utf-8') as stream:json.dump(done,stream,indent=2)
        atomic(job/'STATUS.json',done)
        return 0
    except Exception as error:
        # Do not expose provider details or credentials in user-visible errors.
        atomic(job/'STATUS.json',{'state':'failed','error':str(error) if isinstance(error,ValueError) else type(error).__name__,
                                 'note':'Original forecasts unchanged. Review private RUN.log or refresh and retry.'})
        return 1


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('action',choices=['run','launch']);parser.add_argument('target')
    args=parser.parse_args()
    if args.action=='run':raise SystemExit(run(args.target))
    print('Started injury-adjusted shadow simulation: '+launch(args.target)['path'])
