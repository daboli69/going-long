"""Separate shadow margin/total targets and paired empirical score uncertainty."""
import time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.multioutput import MultiOutputRegressor
from .config import ROOT,CACHE,REPORTS,MODELS,ARCHIVES,DATA,SEED,now,stamp,digest,read,once
from .models import scores as winner_scores
from .adjusted import run as feature_run
from .research_io import update,fingerprint

METHODS=('league_mean','rolling','ridge','hist')
TARGETS=('margin','total')


def columns(d):
    return ['neutral','elo_diff']+[c for c in d if c.startswith(('home_','away_')) and (c.endswith('_20') or c.endswith(('_rest_days','_back_to_back','_games_last4days')))]+[f'diff_{s}_20' for s in ('adj_margin','adj_attack','adj_defense')]


def targets(d):return d[list(TARGETS)].to_numpy(float)


def load_frame(include_current=False):
    feature_run()
    filters=None if include_current else [('season','<=',2025)]
    d=pd.read_parquet(CACHE/'improvement_features.parquet',filters=filters)
    g=pd.read_parquet(CACHE/'games.parquet',columns=['game_id','home_score','away_score'],filters=filters)
    d=d.merge(g,on='game_id',validate='one_to_one')
    d['margin']=(d.home_score-d.away_score).where(d.home_win.notna())
    d['total']=(d.home_score+d.away_score).where(d.home_win.notna())
    return d[d.eligible&d.season.ge(2016)].sort_values(['tipoff','game_id'])


def raw(bundle,d):
    method=bundle['method']
    if method=='league_mean':return np.tile(bundle['mean'],(len(d),1))
    if method=='rolling':
        home=(d.home_points_20.to_numpy()+d.away_allowed_20.to_numpy())/2
        away=(d.away_points_20.to_numpy()+d.home_allowed_20.to_numpy())/2
        return np.column_stack([home-away,home+away])
    return bundle['model'].predict(d[bundle['columns']].to_numpy(float))


def fit(method,train,cal):
    if (train.tipoff.max()+pd.Timedelta(hours=24))>=cal.tipoff.min():raise ValueError('Score training/calibration chronology overlaps')
    if len(cal)<300 or len(train)<300:raise ValueError('Insufficient score training/calibration history')
    bundle={'method':method,'columns':columns(train),'mean':targets(train).mean(axis=0)}
    if method=='ridge':
        model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),Ridge(alpha=10))
        model.fit(train[bundle['columns']].to_numpy(float),targets(train));bundle['model']=model
    elif method=='hist':
        model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=150,max_leaf_nodes=7,min_samples_leaf=40,l2_regularization=10,early_stopping=False,random_state=SEED)))
        model.fit(train[bundle['columns']].to_numpy(float),targets(train));bundle['model']=model
    elif method not in ('league_mean','rolling'):raise ValueError('Unknown score method')
    residuals=targets(cal)-raw(bundle,cal)
    if not np.isfinite(residuals).all():raise ValueError('Nonfinite calibration scores; no silent sample changes')
    bundle['bias']=residuals.mean(axis=0);bundle['residuals']=residuals-bundle['bias']
    bundle['train_n']=len(train);bundle['calibration_n']=len(cal)
    bundle['trained_through']=train.tipoff.max().isoformat();bundle['calibrated_through']=cal.tipoff.max().isoformat()
    bundle['training_available_through']=(train.tipoff.max()+pd.Timedelta(hours=24)).isoformat()
    bundle['calibration_available_through']=(cal.tipoff.max()+pd.Timedelta(hours=24)).isoformat()
    return bundle


def distribution(bundle,d):
    point=raw(bundle,d)+bundle['bias'];residuals=bundle['residuals']
    if not np.isfinite(point).all():raise ValueError('Nonfinite score prediction')
    if (point[:,1]<np.abs(point[:,0])).any():raise ValueError('Negative implied team score; no silent score repair')
    quantiles=point[:,:,None]+np.quantile(residuals,[.1,.5,.9],axis=0).T[None,:,:]
    margins=point[:,0,None]+residuals[:,0]
    p_home=(margins>0).mean(axis=1)+.5*(margins==0).mean(axis=1)
    return point,quantiles,p_home


def crps(point,actual,residuals):
    residuals=np.sort(np.asarray(residuals));n=len(residuals)
    pair_half=np.dot(2*np.arange(1,n+1)-n-1,residuals)/(n*n)
    return np.abs(np.asarray(point)[:,None]+residuals-np.asarray(actual)[:,None]).mean(axis=1)-pair_half


def loss_ci(delta,alpha=.05/4):
    delta=np.asarray(delta);rng=np.random.default_rng(SEED)
    samples=np.array([delta[rng.integers(0,len(delta),len(delta))].mean() for _ in range(2000)])
    return {'delta':float(delta.mean()),'ci_low':float(np.quantile(samples,alpha/2)),'ci_high':float(np.quantile(samples,1-alpha/2))}


def evaluate_frame(bundle,d):
    point,q,p_home=distribution(bundle,d);actual=targets(d)
    out=d[['game_id','season','tipoff']].copy()
    for j,target in enumerate(TARGETS):
        out[target+'_actual']=actual[:,j];out[target+'_point']=point[:,j]
        out[target+'_abs_error']=np.abs(point[:,j]-actual[:,j]);out[target+'_sq_error']=(point[:,j]-actual[:,j])**2
        out[target+'_crps']=crps(point[:,j],actual[:,j],bundle['residuals'][:,j])
        out[target+'_bias']=point[:,j]-actual[:,j]
        out[target+'_covered']=((actual[:,j]>=q[:,j,0])&(actual[:,j]<=q[:,j,2])).astype(float)
    out['winner_brier']=(p_home-d.home_win.to_numpy())**2
    return out


def summarize(d,target):
    return {'n':len(d),'mae':float(d[target+'_abs_error'].mean()),'rmse':float(np.sqrt(d[target+'_sq_error'].mean())),
            'crps':float(d[target+'_crps'].mean()),'bias':float(d[target+'_bias'].mean()),
            'coverage_80':float(d[target+'_covered'].mean()),'winner_brier':float(d.winner_brier.mean())}


def research(log=print):
    started=time.monotonic();d=load_frame();d=d[d.home_win.notna()]
    directory=REPORTS/'scores_v1';directory.mkdir(parents=True,exist_ok=True)
    key=fingerprint([ROOT/'docs/IMPROVEMENTS_PREREGISTRATION.md',ROOT/'nba_lab/score_models.py',ROOT/'nba_lab/adjusted.py',ROOT/'nba_lab/research_io.py',CACHE/'improvement_features.parquet',CACHE/'games.parquet'])
    manifest=directory/'MANIFEST.json'
    if manifest.exists() and read(manifest)['fingerprint']!=key:raise ValueError('Changed score-study inputs; no overwrite')
    if (directory/'RESULT.json').exists():return read(directory/'RESULT.json')
    if not manifest.exists():once(manifest,{'created_at':now(),'fingerprint':key})
    collected={m:[] for m in METHODS};failures=[]
    for season in (2024,2025):
        train=d[d.season.le(season-2)];cal=d[d.season.eq(season-1)];test=d[d.season.eq(season)]
        for method in METHODS:
            meta=directory/f'{season}_{method}.json';path=directory/f'{season}_{method}.parquet'
            if meta.exists():
                if 'error' in read(meta):failures.append(read(meta));continue
                out=pd.read_parquet(path)
            else:
                log(f'Score distribution {season}: {method}')
                try:
                    bundle=fit(method,train,cal);out=evaluate_frame(bundle,test)
                    out.to_parquet(path,index=False)
                    once(meta,{'created_at':now(),'method':method,'season':season,'train_n':len(train),'calibration_n':len(cal),'test_n':len(test)})
                except Exception as error:
                    failure={'method':method,'season':season,'error':type(error).__name__,'message':str(error)[:300]}
                    once(meta,failure);failures.append(failure);log(str(failure));continue
            collected[method].append(out)
    complete={m:pd.concat(parts,ignore_index=True).sort_values(['tipoff','game_id']) for m,parts in collected.items() if len(parts)==2}
    if 'rolling' not in complete:raise ValueError('Structural score benchmark failed; no comparison possible')
    benchmark=complete['rolling'];rows=[]
    for method,out in complete.items():
        if out.game_id.tolist()!=benchmark.game_id.tolist():raise ValueError('Score comparison samples differ')
        for target in TARGETS:
            summary=summarize(out,target);base=summarize(benchmark,target)
            ci=loss_ci(out[target+'_abs_error'].to_numpy()-benchmark[target+'_abs_error'].to_numpy())
            seasons=sum(g[target+'_abs_error'].mean()<benchmark[benchmark.season.eq(s)][target+'_abs_error'].mean() for s,g in out.groupby('season'))
            gain=1-summary['mae']/base['mae']
            rows.append({'method':method,'target':target,**summary,'control_mae':base['mae'],'mae_delta':ci,
                         'relative_gain':gain,'seasons_improving':seasons,
                         'accepted_exploratory':bool(method in ('ridge','hist') and gain>=.01 and ci['ci_high']<0 and seasons==2 and summary['crps']<=base['crps'])})
    accepted=[m for m in ('ridge','hist') if all(any(r['method']==m and r['target']==t and r['accepted_exploratory'] for r in rows) for t in TARGETS)]
    selected=min(accepted,key=lambda m:sum(r['mae']/r['control_mae'] for r in rows if r['method']==m)) if accepted else 'rolling'
    result={'created_at':now(),'fingerprint':key,'results':rows,'failures':failures,'selected_shadow_method':selected,
            'learned_configurations':2,'scalar_regressor_fit_attempts':8,'elapsed_seconds':time.monotonic()-started,
            'status':'Reused discovery; no market comparison, independent confirmation or promotion.'}
    once(directory/'RESULT.json',result)
    frozen=ROOT/'docs/SCORE_FROZEN_CONFIG.json'
    once(frozen,{'created_at':now(),'selected_method':selected,'research_fingerprint':key,
                 'code_hashes':{p:digest(ROOT/'nba_lab'/p) for p in ('score_models.py','adjusted.py','research_io.py')},
                 'status':'Separate shadow score distribution; never replaces winner ensemble.'})
    return result


def train_shadow():
    config=read(ROOT/'docs/SCORE_FROZEN_CONFIG.json')
    for name,checksum in config['code_hashes'].items():
        if digest(ROOT/'nba_lab'/name)!=checksum:raise ValueError('Frozen score implementation changed; refit refused')
    d=load_frame(include_current=True);known=d[d.home_win.notna()];boundary=known.iloc[-300].tipoff
    train=known[(known.tipoff+pd.Timedelta(hours=24)).lt(boundary)];cal=known[known.tipoff.ge(boundary)]
    bundle=fit(config['selected_method'],train,cal);bundle['created_at']=now();bundle['version']=stamp()
    bundle['config_hash']=digest(ROOT/'docs/SCORE_FROZEN_CONFIG.json');bundle['data_hash']=digest(CACHE/'improvement_features.parquet')
    directory=MODELS/'score_shadow'/bundle['version'];directory.mkdir(parents=True,exist_ok=False)
    joblib.dump(bundle,directory/'bundle.joblib')
    once(directory/'META.json',{k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in bundle.items() if k not in ('model','residuals')})
    update(MODELS/'SCORE_CURRENT.json',{'path':str(directory/'bundle.joblib'),'version':bundle['version']});return bundle,d


def archive(date=None,bundle=None,d=None):
    if bundle is None:bundle,d=train_shadow()
    time_now=pd.Timestamp.now(tz='UTC');date=pd.Timestamp(date).date() if date else time_now.tz_convert('America/New_York').date()
    local=d.tipoff.dt.tz_convert('America/New_York').dt.date
    future=d[local.eq(date)&d.tipoff.gt(time_now)&~d.completed].copy()
    if future.empty:return None
    if pd.Timestamp(bundle['calibration_available_through'])>=time_now:raise ValueError('Score training outcomes are not yet available')
    point,q,p_home=distribution(bundle,future)
    out=future[['game_id','home','away','tipoff']].copy()
    out['home_points']=(point[:,1]+point[:,0])/2;out['away_points']=(point[:,1]-point[:,0])/2
    out['home_margin']=point[:,0];out['total']=point[:,1];out['p_home_score_model']=p_home
    for j,target in enumerate(TARGETS):
        for k,percentile in enumerate((10,50,90)):out[f'{target}_p{percentile}']=q[:,j,k]
    out['spread']=[f'{h} {-m:+.1f}' if m>=0 else f'{a} {m:+.1f}' for h,a,m in zip(out.home,out.away,out.home_margin)]
    out['created_at']=now();out['method']=bundle['method'];out['model_version']=bundle['version']
    for name in ('config_hash','data_hash','training_available_through','calibration_available_through'):out[name]=bundle[name]
    out['warning']='Shadow score distribution; no live injury adjustment, market comparison or props. Winner ensemble remains separate.'
    if out.tipoff.le(pd.Timestamp.now(tz='UTC')).any():raise ValueError('Game started before score archive completed')
    directory=ARCHIVES/'score_forecasts'/(str(date)+'_'+stamp());directory.mkdir(parents=True,exist_ok=False)
    out.to_csv(directory/'predictions.csv',index=False,mode='x');out.to_parquet(directory/'predictions.parquet',index=False)
    future.drop(columns=['home_win','home_score','away_score','margin','total'],errors='ignore').to_parquet(directory/'INPUTS.parquet',index=False)
    meta={'created_at':now(),'path':str(directory),'date':str(date),'games':len(out),'method':bundle['method'],
          'config_hash':bundle['config_hash'],'data_hash':bundle['data_hash'],'source_manifest_hash':digest(DATA/'SOURCES.json'),
          'training_available_through':bundle['training_available_through'],'calibration_available_through':bundle['calibration_available_through']}
    once(directory/'META.json',meta);update(ARCHIVES/'SCORE_LATEST.json',meta);return meta
