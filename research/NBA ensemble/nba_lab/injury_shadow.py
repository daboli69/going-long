"""Shadow copy of the strength shadow plus today's official injury report; nothing promoted."""
import joblib
import numpy as np
import pandas as pd
import requests
from .config import ROOT,MODELS,ARCHIVES,DATA,CACHE,REPORTS,KEYS,now,stamp,read,once,atomic,digest
from . import models as M
from . import injury_reports as R
from .injury_features import INJURY,build
from .injury_research import OUT,SEASONS,FIRST_TRAIN,CONFIGS,columns
from .strength import run as strength_run
from .research_io import update

CONFIG=ROOT/'docs/INJURY_SHADOW_CONFIG.json';CANDIDATE='strength_injury'


def live_report(day,first_tipoff,at,session=None):
    """Latest official report published by min(now, first tipoff - 1h). Misses are not cached,
    because a slot that is missing now may be published later today."""
    manifest=R._manifest();scratch=dict(manifest);session=session or requests.Session()
    cutoff=min(pd.Timestamp(at),pd.Timestamp(first_tipoff)-pd.Timedelta(hours=1))
    report=R.pregame_report(day,cutoff+pd.Timedelta(hours=1),scratch,session,lead_hours=1.0)
    for url,meta in scratch.items():
        if meta.get('status')==200:manifest[url]=meta
    atomic(R.MANIFEST,manifest);return report


def report_rows(report,season,games,players):
    if not report['url']:return pd.DataFrame(columns=['game_id','team_id','athlete_id','status','not_yet_submitted','available_at'])
    rows=pd.DataFrame(report['rows']).assign(season=season,report_day=report['day'],report_url=report['url'],
        report_sha256=report['sha256'],available_at=report['available_at'])
    rows=rows[rows.game_date.eq(pd.Timestamp(report['day']).strftime('%m/%d/%Y'))].copy()
    rows['player_name']=rows.player_name_raw.map(R.display_name)
    return R.map_rows(rows,games,players)


def stacker():
    oof=pd.concat([pd.read_parquet(OUT/f'{CANDIDATE}_{s}.parquet') for s in SEASONS])
    _,weights,stack=M.combine(oof[list(KEYS)].to_numpy(),oof[list(KEYS)].to_numpy(),oof.home_win.to_numpy(int))
    return weights,stack


def archive(date=None,threads=1):
    config=read(CONFIG)
    for name,checksum in config['code_hashes'].items():
        if digest(ROOT/'nba_lab'/name)!=checksum:raise ValueError('Frozen injury shadow implementation changed')
    time=pd.Timestamp.now(tz='UTC');date=pd.Timestamp(date).date() if date else time.tz_convert('America/New_York').date()
    base=strength_run().sort_values(['tipoff','game_id']);base.tipoff=pd.to_datetime(base.tipoff,utc=True)
    games=pd.read_parquet(CACHE/'games.parquet');players=pd.read_parquet(CACHE/'player_boxes.parquet')
    history=pd.read_parquet(CACHE/'injury_reports.parquet')
    local=base.tipoff.dt.tz_convert('America/New_York').dt.date
    future=base[local.eq(date)&base.tipoff.gt(time)&~base.completed]
    if future.empty:return None
    if not future.eligible.all():raise ValueError('Some future teams have insufficient history; no silent partial slate')
    day=str(date);first=base[local.eq(date)].tipoff.min()
    report=live_report(day,first,time)
    today=report_rows(report,int(future.season.iloc[0]),games,players)
    if not report['url']:
        # No qualifying report yet: every team is unknown, never treated as healthy.
        teams=[(g,t) for g,h,a in future[['game_id','home_id','away_id']].itertuples(index=False) for t in (h,a)]
        today=pd.DataFrame([{'game_id':g,'team_id':t,'athlete_id':None,'player_name':None,'status':R.NYS,'not_yet_submitted':True,
                             'available_at':time-pd.Timedelta(seconds=1)} for g,t in teams])
    # Only unstarted games use today's report; started games keep their original decision time.
    today=today[today.game_id.isin(future.game_id)]
    # The forecast is made now: future rows decide at this time, after the report was published.
    base.loc[future.index,'decision_at']=time
    d=build(base,games,players,pd.concat([history,today],ignore_index=True))
    known=d[d.eligible&d.home_win.notna()&d.season.ge(FIRST_TRAIN)].sort_values(['tipoff','game_id']);boundary=known.iloc[-300].tipoff
    train=known[(known.tipoff+pd.Timedelta(hours=24)).lt(boundary)];cal=known[known.tipoff.ge(boundary)]
    rows=d[d.game_id.isin(future.game_id)].sort_values(['tipoff','game_id'])
    bundle=M.fit(train,cal,columns(d,CONFIGS[CANDIDATE]),threads,log=lambda _:None);weights,stack=stacker()
    p=M.probabilities(bundle,rows);stacked=stack.predict_proba(M.logits(p))[:,1]
    out=rows[['game_id','tipoff','home','away','diff_out_gmsc','diff_questionable_gmsc','home_out_gmsc','away_out_gmsc']].copy()
    for j,key in enumerate(KEYS):out[key]=p[:,j]
    out['p_home']=stacked;out['home_votes']=(p>.5).sum(axis=1);out['away_votes']=(p<.5).sum(axis=1)
    out['winner']=np.where(stacked>.5,out.home,np.where(stacked<.5,out.away,'coin flip'))
    listed=today[today.status.isin(('Out','Doubtful','Questionable'))] if len(today) else today
    out['listed_out']=out.apply(lambda r:', '.join(listed[listed.game_id.eq(r.game_id)&listed.status.isin(('Out','Doubtful'))].player_name.dropna()),axis=1) if len(listed) else ''
    out['injury_report_url']=report['url'];out['injury_report_published_at']=report.get('available_at')
    out['created_at']=now();out['config_hash']=digest(CONFIG)
    out['status']='Injury shadow: passed a fixed retrospective gate; not promoted. Uses one official report published by min(now, first tipoff - 1h); later scratches are not seen.'
    if out.tipoff.le(pd.Timestamp.now(tz='UTC')).any():raise ValueError('Game started before injury shadow archive')
    version=stamp();directory=ARCHIVES/'injury_forecasts'/(day+'_'+version);directory.mkdir(parents=True,exist_ok=False)
    out.to_parquet(directory/'predictions.parquet',index=False);out.to_csv(directory/'predictions.csv',index=False,mode='x')
    model_dir=MODELS/'injury_shadow'/version;model_dir.mkdir(parents=True,exist_ok=False)
    joblib.dump({**bundle,'weights':weights,'stacker':stack},model_dir/'bundle.joblib')
    meta={'created_at':now(),'path':str(directory),'games':len(out),'training_games':bundle['train_n'],'calibration_games':bundle['calibration_n'],
          'calibration_available_through':bundle['calibration_outcomes_available_through'],'config_hash':digest(CONFIG),
          'injury_report_url':report['url'],'injury_report_published_at':report.get('available_at'),'injury_rows':len(today),
          'unmatched_rows':int(today.athlete_id.isna().sum()-today.not_yet_submitted.sum()) if len(today) else 0,
          'not_yet_submitted_teams':int(today.not_yet_submitted.sum()) if len(today) else 0,
          'source_manifest_hash':digest(DATA/'SOURCES.json'),'model_bundle_hash':digest(model_dir/'bundle.joblib')}
    once(directory/'META.json',meta);update(ARCHIVES/'INJURY_LATEST.json',meta);return meta


def freeze():
    if CONFIG.exists():return read(CONFIG)
    result=read(REPORTS/'injury_v1'/'RESULTS.json')
    if not result['comparison']['passed']:raise ValueError('Injury candidate did not pass its gate; nothing to freeze')
    config={'created_at':now(),'candidate':CANDIDATE,'study_protocol':result['protocol'],'result':result['comparison'],
            'code_hashes':{n:digest(ROOT/'nba_lab'/n) for n in ('injury_features.py','injury_shadow.py','injury_reports.py','strength.py','models.py','features.py')},
            'status':'Shadow only. Original ensemble and strength shadow unchanged; promotion needs prospective 2026-27 evidence.'}
    once(CONFIG,config);return config
