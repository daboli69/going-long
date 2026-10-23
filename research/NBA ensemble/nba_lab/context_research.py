"""Two prespecified context challengers; cached discovery and separate archives."""
import time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from .config import ROOT,CACHE,REPORTS,MODELS,ARCHIVES,DATA,now,stamp,digest,read,once
from .features import feature_columns
from .context_features import build,AGE_COLUMNS,SHARED_COLUMNS
from . import models as M
from .research_io import update,fingerprint

METHODS=('season_continuity','shared_possessions')
PROTOCOL=ROOT/'docs/PREGAME_CONTEXT_PREREGISTRATION.md'


def frame():
    inputs={str(p):digest(p) for p in (CACHE/'features.parquet',CACHE/'games.parquet',CACHE/'team_boxes.parquet',ROOT/'nba_lab/context_features.py')}
    path=CACHE/'pregame_context_features.parquet';meta=CACHE/'PREGAME_CONTEXT_FEATURES.json'
    if path.exists() and meta.exists() and read(meta)['inputs']==inputs:
        return pd.read_parquet(path),read(meta)['base_columns']
    base=pd.read_parquet(CACHE/'features.parquet');cols=feature_columns(base)
    d=build(base,pd.read_parquet(CACHE/'games.parquet'),pd.read_parquet(CACHE/'team_boxes.parquet'))
    d.to_parquet(path,index=False);update(meta,{'created_at':now(),'inputs':inputs,'base_columns':cols})
    return d,cols


def columns(method,base):
    if method=='season_continuity':return list(base)+list(AGE_COLUMNS)
    if method=='shared_possessions':return list(base)+[c for c in SHARED_COLUMNS if c.startswith('diff_')]
    raise ValueError('Unknown context challenger')


def fit(train,cal,cols):
    if (train.tipoff.max()+pd.Timedelta(hours=24))>=cal.tipoff.min():raise ValueError('Context train/calibration overlap')
    if len(train)<300 or len(cal)<100:raise ValueError('Insufficient chronological context samples')
    model=M.make('logistic',1);model.fit(train[cols].to_numpy(float),train.home_win.astype(int))
    calibrator=LogisticRegression(C=1,max_iter=1000).fit(M.raw(model,cal[cols].to_numpy(float)).reshape(-1,1),cal.home_win.astype(int))
    return {'model':model,'calibrator':calibrator,'columns':cols}


def probability(bundle,d):return bundle['calibrator'].predict_proba(M.raw(bundle['model'],d[bundle['columns']].to_numpy(float)).reshape(-1,1))[:,1]


def result(d):
    control=M.scores(d.home_win,d.control);candidate=M.scores(d.home_win,d.probability)
    ci=M.paired_ci(d.home_win.to_numpy(),d.probability.to_numpy(),d.control.to_numpy(),alpha=.05/2)
    by_season={str(int(s)):{'control':M.scores(g.home_win,g.control),'candidate':M.scores(g.home_win,g.probability)} for s,g in d.groupby('season')}
    signs=sum(r['candidate']['log_loss']<r['control']['log_loss'] for r in by_season.values())
    gain=1-candidate['log_loss']/control['log_loss']
    early=d[d.home_season_history_20.lt(10)|d.away_season_history_20.lt(10)]
    return {'control':control,'candidate':candidate,'delta':ci,'by_season':by_season,'relative_gain':gain,'seasons_improving':signs,
        'accepted_exploratory':bool(gain>=.01 and ci['ci_high']<0 and signs==2 and candidate['brier']<=control['brier']),
        'early_season_descriptive':{'n':len(early),'control':M.scores(early.home_win,early.control),'candidate':M.scores(early.home_win,early.probability)} if len(early) else {'n':0}}


def research(log=print):
    started=time.monotonic();d,base=frame();d=d[d.eligible&d.home_win.notna()&d.season.between(2016,2025)].sort_values(['tipoff','game_id'])
    directory=REPORTS/'pregame_context_v1';directory.mkdir(parents=True,exist_ok=True)
    files=[PROTOCOL,ROOT/'nba_lab/context_research.py',ROOT/'nba_lab/context_features.py',ROOT/'nba_lab/models.py',ROOT/'nba_lab/research_io.py',CACHE/'pregame_context_features.parquet']
    files += [REPORTS/'research'/f'fold_{s}'/'predictions.parquet' for s in (2024,2025)]
    key=fingerprint(files);manifest=directory/'MANIFEST.json'
    if manifest.exists() and read(manifest)['fingerprint']!=key:raise ValueError('Context study inputs changed; no repeated search')
    if (directory/'RESULT.json').exists():return read(directory/'RESULT.json')
    if not manifest.exists():once(manifest,{'created_at':now(),'fingerprint':key})
    output=[];failures=[]
    deadline=pd.Timestamp('2026-10-23T15:30:00',tz='America/New_York')
    for method in METHODS:
        folds=[]
        for season in (2024,2025):
            path=directory/f'{method}_{season}.parquet';meta=directory/f'{method}_{season}.json'
            if meta.exists():
                if 'error' in read(meta):failures.append(read(meta));continue
                folds.append(pd.read_parquet(path));continue
            if pd.Timestamp.now(tz='UTC')>=deadline:raise ValueError('Pregame research cutoff passed; no new fit')
            log(f'Context hypothesis {method}, target{season}')
            try:
                original=pd.read_parquet(REPORTS/'research'/f'fold_{season}'/'predictions.parquet')
                test=d[d.season.eq(season)].set_index('game_id').loc[original.game_id].reset_index()
                if test.home_win.tolist()!=original.home_win.tolist():raise ValueError('Control outcomes mismatch')
                bundle=fit(d[d.season.le(season-2)],d[d.season.eq(season-1)],columns(method,base))
                out=test[['game_id','tipoff','season','home_win','home_season_history_20','away_season_history_20']].copy()
                out['control']=original.logistic.to_numpy();out['probability']=probability(bundle,test)
                out.to_parquet(path,index=False);once(meta,{'created_at':now(),'method':method,'season':season,'n':len(out)})
                folds.append(out)
            except Exception as error:
                failure={'method':method,'season':season,'error':type(error).__name__,'message':str(error)[:300]}
                once(meta,failure);failures.append(failure);log(str(failure))
        if len(folds)==2:output.append({'method':method,**result(pd.concat(folds,ignore_index=True))})
    out={'created_at':now(),'fingerprint':key,'results':output,'failures':failures,'configurations':2,'base_fit_attempts':4,
         'elapsed_seconds':time.monotonic()-started,'status':'Reused discovery only; no confirmation or current-season outcome selection. No promotion.'}
    once(directory/'RESULT.json',out)
    config={'created_at':now(),'methods':list(METHODS),'base_columns':base,'development_gate':{r['method']:r['accepted_exploratory'] for r in output},
            'research_fingerprint':key,'code_hashes':{name:digest(ROOT/'nba_lab'/name) for name in ('context_research.py','context_features.py','models.py','research_io.py')},
            'status':'Both fixed candidates archived for prospective comparison; never replace original forecasts.'}
    once(ROOT/'docs/PREGAME_CONTEXT_FROZEN.json',config);return out


def archive(date=None):
    config=read(ROOT/'docs/PREGAME_CONTEXT_FROZEN.json')
    for name,checksum in config['code_hashes'].items():
        if digest(ROOT/'nba_lab'/name)!=checksum:raise ValueError('Frozen context implementation changed')
    d,_=frame();d=d[d.eligible&d.season.ge(2016)].sort_values(['tipoff','game_id']);known=d[d.home_win.notna()]
    time_now=pd.Timestamp.now(tz='UTC');date=pd.Timestamp(date).date() if date else time_now.tz_convert('America/New_York').date()
    future=d[d.tipoff.dt.tz_convert('America/New_York').dt.date.eq(date)&d.tipoff.gt(time_now)&~d.completed]
    if future.empty:return None
    boundary=known.iloc[-300].tipoff;train=known[(known.tipoff+pd.Timedelta(hours=24)).lt(boundary)];cal=known[known.tipoff.ge(boundary)]
    available=(cal.tipoff.max()+pd.Timedelta(hours=24)).isoformat()
    if pd.Timestamp(available)>=time_now:raise ValueError('Calibration outcomes not yet available')
    rows=[];bundles={}
    for method in config['methods']:
        if method not in config['development_gate']:continue
        bundle=fit(train,cal,columns(method,config['base_columns']));bundles[method]=bundle;p=probability(bundle,future)
        for i,g in enumerate(future.itertuples(index=False)):
            rows.append({'game_id':g.game_id,'tipoff':g.tipoff,'home':g.home,'away':g.away,'method':method,'p_home':float(p[i]),
                'home_current_season_games':int(g.home_season_history_20),'away_current_season_games':int(g.away_season_history_20),
                'home_prior_season_fraction':float(g.home_prior_season_fraction_20),'away_prior_season_fraction':float(g.away_prior_season_fraction_20),
                'created_at':now(),'training_available_through':(train.tipoff.max()+pd.Timedelta(hours=24)).isoformat(),
                'calibration_available_through':available,'development_gate_passed':config['development_gate'][method],
                'config_hash':digest(ROOT/'docs/PREGAME_CONTEXT_FROZEN.json'),
                'warning':'Prespecified research copy, including rejected configurations; no current injury adjustment or promotion.'})
    out=pd.DataFrame(rows)
    if out.empty:return None
    if out.tipoff.le(pd.Timestamp.now(tz='UTC')).any():raise ValueError('Game started before context archive')
    version=stamp();directory=ARCHIVES/'context_forecasts'/(str(date)+'_'+version);directory.mkdir(parents=True,exist_ok=False)
    out.to_parquet(directory/'predictions.parquet',index=False);out.to_csv(directory/'predictions.csv',index=False,mode='x')
    model_dir=MODELS/'context_shadow'/version;model_dir.mkdir(parents=True,exist_ok=False);joblib.dump(bundles,model_dir/'bundle.joblib')
    meta={'created_at':now(),'path':str(directory),'games':len(future),'rows':len(out),'methods':list(bundles),'config_hash':digest(ROOT/'docs/PREGAME_CONTEXT_FROZEN.json'),
          'data_hash':digest(CACHE/'pregame_context_features.parquet'),'source_manifest_hash':digest(DATA/'SOURCES.json'),
          'model_hash':digest(model_dir/'bundle.joblib'),'calibration_available_through':available}
    once(directory/'META.json',meta);update(ARCHIVES/'CONTEXT_LATEST.json',meta);return meta
