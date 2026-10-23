"""Seven frozen individual-model changes and one earlier-OOF stacked challenger."""
import copy
import time
import warnings
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.linear_model import LogisticRegression
from .config import ROOT,CACHE,REPORTS,KEYS,SEED,now,read,once
from . import models as M
from .features import feature_columns
from .adjusted import run as feature_run
from .research_io import fingerprint,update

SPECS={'logistic_adjusted':'logistic','logistic_recent':'logistic',
       'random_forest_simple':'random_forest','xgboost_regularized':'xgboost',
       'hist_native_missing':'hist_gradient_boosting','svm_simple':'rbf_svm','mlp_small':'mlp'}
STACK_MEMBERS=('logistic_adjusted','random_forest_simple','xgboost_regularized','hist_native_missing','svm_simple','mlp_small')


def columns(name,d):
    base=[c for c in feature_columns(d) if not c.startswith('diff_adj_')]
    if name=='logistic_adjusted':return base+[f'diff_{s}_20' for s in ('adj_margin','adj_attack','adj_defense')]
    if name in ('random_forest_simple','svm_simple'):
        return [c for c in base if not c.endswith(('_5','_10'))]
    return base


def make(name,threads):
    if name=='hist_native_missing':
        return make_pipeline(StandardScaler(),HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=7,min_samples_leaf=40,l2_regularization=10,early_stopping=False,random_state=SEED))
    model=M.make(SPECS[name],threads)
    params={'random_forest_simple':{'randomforestclassifier__max_depth':6,'randomforestclassifier__min_samples_leaf':40},
            'xgboost_regularized':{'xgbclassifier__n_estimators':300,'xgbclassifier__max_depth':2,'xgbclassifier__learning_rate':.03,'xgbclassifier__min_child_weight':10,'xgbclassifier__reg_lambda':10},
            'svm_simple':{'svc__C':.5,'svc__gamma':.02}}
    return model.set_params(**params.get(name,{}))


def neural(train,cols,max_epochs=400,patience=20):
    validation=train[train.season.eq(train.season.max())];earlier=train[train.season.lt(train.season.max())]
    if len(earlier)<300 or len(validation)<100:raise ValueError('Insufficient chronological neural optimization history')
    if (earlier.tipoff.max()+pd.Timedelta(hours=24))>=validation.tipoff.min():raise ValueError('Neural optimization chronology overlaps')
    prep=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler())
    x=prep.fit_transform(earlier[cols].to_numpy(float));xv=prep.transform(validation[cols].to_numpy(float))
    model=MLPClassifier(hidden_layer_sizes=(32,),alpha=.1,max_iter=1,random_state=SEED)
    best=np.inf;best_epoch=0;stale=0
    for epoch in range(1,max_epochs+1):
        model.partial_fit(x,earlier.home_win.astype(int),classes=np.array([0,1]))
        loss=M.scores(validation.home_win,model.predict_proba(xv)[:,1])['log_loss']
        if loss<best-1e-4:best=loss;best_epoch=epoch;stale=0
        else:stale+=1
        if stale>=patience:break
    # Frozen epoch budget, then learn from the full allowed training set.
    prep=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler())
    full=prep.fit_transform(train[cols].to_numpy(float))
    final=MLPClassifier(hidden_layer_sizes=(32,),alpha=.1,max_iter=1,random_state=SEED)
    for _ in range(best_epoch):final.partial_fit(full,train.home_win.astype(int),classes=np.array([0,1]))
    return make_pipeline(prep.steps[0][1],prep.steps[1][1],final),{'selected_epoch':best_epoch,'optimization_epochs':epoch,'optimizer_cap_reached':stale<patience,'internal_validation_season':int(validation.season.max()),'internal_validation_log_loss':best}


def fit(name,train,cal,cols,threads=1):
    if (train.tipoff.max()+pd.Timedelta(hours=24))>=cal.tipoff.min():raise ValueError('Calibration chronology overlaps')
    optimization={}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        if name=='mlp_small':model,optimization=neural(train,cols)
        else:
            model=make(name,threads);kwargs={}
            if name=='logistic_recent':kwargs['logisticregression__sample_weight']=np.power(.5,(train.season.max()-train.season.to_numpy())/2)
            model.fit(train[cols].to_numpy(float),train.home_win.astype(int),**kwargs)
        calibrator=LogisticRegression(C=1,max_iter=1000).fit(M.raw(model,cal[cols].to_numpy(float)).reshape(-1,1),cal.home_win.astype(int))
    return (model,calibrator),{'optimization':optimization,'warnings':[str(w.message)[:300] for w in caught]}


def load_frame():
    feature_run()
    d=pd.read_parquet(CACHE/'improvement_features.parquet',filters=[('season','<=',2025)])
    return d[d.eligible&d.home_win.notna()&d.season.ge(2016)].sort_values(['tipoff','game_id'])


def run(threads=1,log=print):
    started=time.monotonic();d=load_frame();directory=REPORTS/'individual_v1';directory.mkdir(parents=True,exist_ok=True)
    paths=[ROOT/'docs/IMPROVEMENTS_PREREGISTRATION.md',ROOT/'nba_lab/individual.py',ROOT/'nba_lab/adjusted.py',ROOT/'nba_lab/models.py',ROOT/'nba_lab/research_io.py',CACHE/'improvement_features.parquet']
    paths += [REPORTS/'research'/f'fold_{s}'/'predictions.parquet' for s in (2023,2024,2025)]
    key=fingerprint(paths);manifest=directory/'MANIFEST.json'
    if manifest.exists() and read(manifest)['fingerprint']!=key:raise ValueError('Changed individual-study inputs; refusing overwrite')
    if (directory/'RESULT.json').exists():return read(directory/'RESULT.json')
    if not manifest.exists():once(manifest,{'created_at':now(),'fingerprint':key,'configurations':7})
    failures=[];history=[];folds=[];fit_attempts=0
    for season in (2023,2024,2025):
        original=pd.read_parquet(REPORTS/'research'/f'fold_{season}'/'predictions.parquet')
        train=d[d.season.le(season-2)];cal=d[d.season.eq(season-1)]
        test=d[d.season.eq(season)].set_index('game_id').loc[original.game_id].reset_index()
        if test.home_win.tolist()!=original.home_win.tolist():raise ValueError('Saved original/control labels mismatch')
        out=original[['game_id','season','tipoff','home_win']].copy()
        for name,family in SPECS.items():
            meta=directory/f'{season}_{name}.json';path=directory/f'{season}_{name}.parquet'
            if meta.exists():
                info=read(meta)
                if 'error' in info:failures.append(info);continue
                prob=pd.read_parquet(path);fit_attempts+=1
            else:
                log(f'Individual {season}: {name}');fit_attempts+=1
                try:
                    cols=columns(name,d);bundle,info=fit(name,train,cal,cols,threads)
                    p=bundle[1].predict_proba(M.raw(bundle[0],test[cols].to_numpy(float)).reshape(-1,1))[:,1]
                    prob=pd.DataFrame({'game_id':test.game_id,'probability':p})
                    prob.to_parquet(path,index=False)
                    once(meta,{'name':name,'season':season,'columns':cols,'train_n':len(train),'calibration_n':len(cal),'test_n':len(test),**info})
                except Exception as error:
                    info={'name':name,'season':season,'error':type(error).__name__,'message':str(error)[:300]}
                    once(meta,info);failures.append(info);log(str(info));continue
            if prob.game_id.tolist()!=original.game_id.tolist():raise ValueError('Candidate/control game IDs differ')
            out[name]=prob.probability.to_numpy();out['control_'+name]=original[family].to_numpy()
        if all(name in out for name in STACK_MEMBERS) and all(all(name in h for name in STACK_MEMBERS) for h in history):
            hp=np.concatenate([h[list(STACK_MEMBERS)].to_numpy() for h in history]) if history else None
            hy=np.concatenate([h.home_win.to_numpy(int) for h in history]) if history else None
            combined,_,_=M.combine(out[list(STACK_MEMBERS)].to_numpy(),hp,hy)
            out['new_stacked']=combined['stacked'];out['control_new_stacked']=original.stacked.to_numpy()
        history.append(out)
        if season in (2024,2025):folds.append(out)
    dev=pd.concat(folds,ignore_index=True);results=[]
    for name in (*SPECS,'new_stacked'):
        if name not in dev or dev[name].isna().any():continue
        control='control_'+name;baseline=M.scores(dev.home_win,dev[control]);candidate=M.scores(dev.home_win,dev[name])
        ci=M.paired_ci(dev.home_win.to_numpy(),dev[name].to_numpy(),dev[control].to_numpy(),alpha=.05/8)
        seasonal={str(int(s)):{'control':M.scores(g.home_win,g[control]),'candidate':M.scores(g.home_win,g[name])} for s,g in dev.groupby('season')}
        signs=sum(r['candidate']['log_loss']<r['control']['log_loss'] for r in seasonal.values())
        gain=1-candidate['log_loss']/baseline['log_loss']
        results.append({'name':name,'control':baseline,'candidate':candidate,'delta':ci,'seasons_improving':signs,'relative_gain':gain,'by_season':seasonal,
                        'accepted_exploratory':bool(gain>=.01 and ci['ci_high']<0 and signs==2 and candidate['brier']<=baseline['brier'])})
    result={'created_at':now(),'fingerprint':key,'configurations':7,'final_base_fit_attempts':fit_attempts,'internal_neural_sequences':3,
            'elapsed_seconds':time.monotonic()-started,'results':results,'failures':failures,
            'status':'Reused discovery only. No confirmation/prospective selection, operational model change or promotion.'}
    once(directory/'RESULT.json',result);dev.to_parquet(directory/'DISCOVERY.parquet',index=False)
    update(REPORTS/'INDIVIDUAL_LATEST.json',{'path':str(directory/'RESULT.json')});return result
