"""Shadow copy of the six members with the gate-passing strength inputs; original ensemble unchanged."""
import joblib
import numpy as np
import pandas as pd
from .config import ROOT,MODELS,ARCHIVES,DATA,REPORTS,KEYS,now,stamp,read,once,digest
from . import models as M
from .features import feature_columns
from .strength import RATING,TRAVEL,ROSTER,run as feature_run
from .strength_research import OUT,STUDIES
from .research_io import update

CONFIG=ROOT/'docs/STRENGTH_SHADOW_CONFIG.json';CANDIDATE='all'


def columns(d):
    extra=RATING+TRAVEL+ROSTER
    return feature_columns(d.drop(columns=[c for c in extra if c in d]))+list(extra)


def stacker():
    """Refit only from the study's out-of-fold predictions, never from operational fits."""
    oof=pd.concat([pd.read_parquet(OUT/f'B_{CANDIDATE}_{s}.parquet') for s in STUDIES['B']['seasons']])
    _,weights,stack=M.combine(oof[list(KEYS)].to_numpy(),oof[list(KEYS)].to_numpy(),oof.home_win.to_numpy(int))
    return weights,stack


def archive(date=None,threads=1):
    config=read(CONFIG)
    for name,checksum in config['code_hashes'].items():
        if digest(ROOT/'nba_lab'/name)!=checksum:raise ValueError('Frozen strength shadow implementation changed')
    d=feature_run().sort_values(['tipoff','game_id']);d.tipoff=pd.to_datetime(d.tipoff,utc=True)
    known=d[d.eligible&d.home_win.notna()&d.season.ge(STUDIES['B']['first_train'])];boundary=known.iloc[-300].tipoff
    train=known[(known.tipoff+pd.Timedelta(hours=24)).lt(boundary)];cal=known[known.tipoff.ge(boundary)]
    time=pd.Timestamp.now(tz='UTC');date=pd.Timestamp(date).date() if date else time.tz_convert('America/New_York').date()
    future=d[d.tipoff.dt.tz_convert('America/New_York').dt.date.eq(date)&d.tipoff.gt(time)&~d.completed].copy()
    if future.empty:return None
    if not future.eligible.all():raise ValueError('Some future teams have insufficient history; no silent partial slate')
    bundle=M.fit(train,cal,columns(d),threads,log=lambda _:None);weights,stack=stacker()
    p=M.probabilities(bundle,future);stacked=stack.predict_proba(M.logits(p))[:,1]
    out=future[['game_id','tipoff','home','away']].copy()
    for j,key in enumerate(KEYS):out[key]=p[:,j]
    out['p_home']=stacked;out['home_votes']=(p>.5).sum(axis=1);out['away_votes']=(p<.5).sum(axis=1)
    out['winner']=np.where(stacked>.5,out.home,np.where(stacked<.5,out.away,'coin flip'))
    for c in ('diff_mov_elo','diff_ridge_net','diff_roster_gmsc','diff_absent_gmsc'):out[c]=future[c].to_numpy()
    out['created_at']=now();out['training_available_through']=bundle['training_outcomes_available_through']
    out['calibration_available_through']=bundle['calibration_outcomes_available_through']
    out['config_hash']=digest(CONFIG)
    out['status']='Strength shadow: passed fixed retrospective gate; not promoted. Roster uses earlier released boxes, not today\'s injury report.'
    if out.tipoff.le(pd.Timestamp.now(tz='UTC')).any():raise ValueError('Game started before strength shadow archive')
    version=stamp();directory=ARCHIVES/'strength_forecasts'/(str(date)+'_'+version);directory.mkdir(parents=True,exist_ok=False)
    out.to_parquet(directory/'predictions.parquet',index=False);out.to_csv(directory/'predictions.csv',index=False,mode='x')
    model_dir=MODELS/'strength_shadow'/version;model_dir.mkdir(parents=True,exist_ok=False)
    joblib.dump({**bundle,'weights':weights,'stacker':stack},model_dir/'bundle.joblib')
    meta={'created_at':now(),'path':str(directory),'games':len(out),'training_games':bundle['train_n'],'calibration_games':bundle['calibration_n'],
          'calibration_available_through':bundle['calibration_outcomes_available_through'],'config_hash':digest(CONFIG),
          'data_hash':digest(ROOT/'data/cache/strength_features.parquet'),'source_manifest_hash':digest(DATA/'SOURCES.json'),
          'model_bundle_hash':digest(model_dir/'bundle.joblib'),'warnings':bundle['warnings'][:20]}
    once(directory/'META.json',meta);update(ARCHIVES/'STRENGTH_LATEST.json',meta);return meta


def freeze():
    if CONFIG.exists():return read(CONFIG)
    result=read(REPORTS/'strength_v1'/'RESULTS.json')
    passed=[c for c in result['comparisons'] if c['candidate']==CANDIDATE and c['passed']]
    if not passed:raise ValueError('Strength candidate did not pass its gate; nothing to freeze')
    config={'created_at':now(),'candidate':CANDIDATE,'study_protocol':result['protocol'],'result':passed[0],
            'code_hashes':{n:digest(ROOT/'nba_lab'/n) for n in ('strength.py','strength_shadow.py','models.py','features.py')},
            'status':'Shadow only. Original frozen ensemble and forecasts unchanged; promotion needs prospective 2026-27 evidence.'}
    once(CONFIG,config);return config
