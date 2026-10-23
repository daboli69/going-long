"""Three discovery-qualified individual copies; no promotion or new combination."""
import warnings
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPClassifier
from sklearn.linear_model import LogisticRegression
from .config import ROOT,MODELS,ARCHIVES,DATA,SEED,now,stamp,read,once,digest
from . import individual as I,models as M
from .score_models import load_frame
from .research_io import update


def fit_fixed(name,train,cal,config,threads):
    if (train.tipoff.max()+pd.Timedelta(hours=24))>=cal.tipoff.min():raise ValueError('Shadow calibration overlaps training')
    cols=I.columns(name,train)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        if name=='mlp_small':
            prep=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler())
            x=prep.fit_transform(train[cols].to_numpy(float))
            model=MLPClassifier(hidden_layer_sizes=(32,),alpha=.1,max_iter=1,random_state=SEED)
            for _ in range(config['fixed_mlp_epochs']):model.partial_fit(x,train.home_win.astype(int),classes=np.array([0,1]))
            model=make_pipeline(prep.steps[0][1],prep.steps[1][1],model)
        else:
            model=I.make(name,threads);model.fit(train[cols].to_numpy(float),train.home_win.astype(int))
        calibrator=LogisticRegression(C=1,max_iter=1000).fit(M.raw(model,cal[cols].to_numpy(float)).reshape(-1,1),cal.home_win.astype(int))
    return {'model':model,'calibrator':calibrator,'columns':cols,'warnings':[str(w.message)[:300] for w in caught]}


def archive(date=None,threads=1):
    config=read(ROOT/'docs/INDIVIDUAL_SHADOW_CONFIG.json')
    for name,checksum in config['code_hashes'].items():
        if digest(ROOT/'nba_lab'/name)!=checksum:raise ValueError('Frozen individual shadow implementation changed')
    d=load_frame(include_current=True)
    known=d[d.home_win.notna()];boundary=known.iloc[-300].tipoff
    train=known[(known.tipoff+pd.Timedelta(hours=24)).lt(boundary)];cal=known[known.tipoff.ge(boundary)]
    time=pd.Timestamp.now(tz='UTC');date=pd.Timestamp(date).date() if date else time.tz_convert('America/New_York').date()
    future=d[d.tipoff.dt.tz_convert('America/New_York').dt.date.eq(date)&d.tipoff.gt(time)&~d.completed].copy()
    if future.empty:return None
    available=(cal.tipoff.max()+pd.Timedelta(hours=24)).isoformat()
    if pd.Timestamp(available)>=time:raise ValueError('Shadow calibration outcomes not available')
    rows=[];bundles={}
    for name in config['accepted_development_candidates']:
        bundle=fit_fixed(name,train,cal,config,threads);bundles[name]=bundle
        p=bundle['calibrator'].predict_proba(M.raw(bundle['model'],future[bundle['columns']].to_numpy(float)).reshape(-1,1))[:,1]
        for i,row in enumerate(future.itertuples(index=False)):
            rows.append({'game_id':row.game_id,'tipoff':row.tipoff,'home':row.home,'away':row.away,'candidate':name,
                         'p_home':float(p[i]),'winner':row.home if p[i]>.5 else row.away if p[i]<.5 else 'tie',
                         'created_at':now(),'training_available_through':(train.tipoff.max()+pd.Timedelta(hours=24)).isoformat(),
                         'calibration_available_through':available,'config_hash':digest(ROOT/'docs/INDIVIDUAL_SHADOW_CONFIG.json'),
                         'status':'Development-qualified individual shadow; original ensemble unchanged; no live injury adjustment.'})
    out=pd.DataFrame(rows)
    if out.tipoff.le(pd.Timestamp.now(tz='UTC')).any():raise ValueError('Game started before shadow archive')
    version=stamp();directory=ARCHIVES/'individual_forecasts'/(str(date)+'_'+version);directory.mkdir(parents=True,exist_ok=False)
    out.to_parquet(directory/'predictions.parquet',index=False);out.to_csv(directory/'predictions.csv',index=False,mode='x')
    model_dir=MODELS/'individual_shadow'/version;model_dir.mkdir(parents=True,exist_ok=False);joblib.dump(bundles,model_dir/'bundle.joblib')
    meta={'created_at':now(),'path':str(directory),'games':len(future),'rows':len(out),'members':list(bundles),
          'training_games':len(train),'calibration_games':len(cal),'calibration_available_through':available,
          'config_hash':digest(ROOT/'docs/INDIVIDUAL_SHADOW_CONFIG.json'),'data_hash':digest(ROOT/'data/cache/improvement_features.parquet'),
          'source_manifest_hash':digest(DATA/'SOURCES.json'),'model_bundle_hash':digest(model_dir/'bundle.joblib')}
    once(directory/'META.json',meta);update(ARCHIVES/'INDIVIDUAL_LATEST.json',meta);return meta
