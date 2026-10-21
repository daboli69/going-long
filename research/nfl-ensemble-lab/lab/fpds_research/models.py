"""Bounded shadow estimators; no champion registry or simulator mutation."""
from __future__ import annotations
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge, PoissonRegressor, LogisticRegression
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.neural_network import MLPRegressor, MLPClassifier
from ..props.ensemble.combine import loss_rows
from .common import SEED


def binary(stat):return stat in ('anytime_td','win')


def loss(stat,y,p):
    return loss_rows('anytime_td' if stat=='win' else stat,y,p)


def estimator(stat,key,threads=1):
    b=binary(stat);count=stat in ('rec','pass_tds')
    if key in ('linear','shrink','distribution'):
        model=LogisticRegression(C=.1,max_iter=1000,random_state=SEED) if b else PoissonRegressor(alpha=1,max_iter=500) if count else Ridge(alpha=100)
    elif key=='hist':
        cls=HistGradientBoostingClassifier if b else HistGradientBoostingRegressor
        model=cls(max_iter=80,max_depth=3,l2_regularization=10,random_state=SEED,
                  **({'loss':'poisson'} if count else {}))
    elif key=='xgboost':
        from xgboost import XGBClassifier,XGBRegressor
        cls=XGBClassifier if b else XGBRegressor
        model=cls(n_estimators=100,max_depth=3,learning_rate=.05,reg_lambda=10,n_jobs=threads,
                  random_state=SEED,objective='binary:logistic' if b else 'count:poisson' if count else 'reg:squarederror')
    elif key=='mlp':
        cls=MLPClassifier if b else MLPRegressor
        model=cls(hidden_layer_sizes=(32,),max_iter=100,alpha=1,random_state=SEED,shuffle=False,early_stopping=False)
    else:raise ValueError('Unregistered model key')
    return Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                     ('scale',StandardScaler()),('model',model)])


def fit_predict(train,test,stat,columns,key,threads=1,weights=None):
    if not columns:raise ValueError('No usable predeclared features')
    if train[stat].nunique()<2:
        value=float(train[stat].mean())
        return np.full(len(test),value),{'kind':'constant training-only fallback','value':value}
    if key=='structural_proxy':
        col='hist_off_td' if stat=='anytime_td' else 'hist_'+stat
        if col not in test:raise ValueError('Analytical structural proxy unavailable for target')
        p=test[col].fillna(float(train[stat].mean())).to_numpy(float)
        if stat=='anytime_td':p=-np.expm1(-np.maximum(p,0)*test.ind_total.fillna(44).to_numpy()/44.)
        return np.maximum(p,0),{'kind':'analytical historical-volume proxy; not PBP simulator'}
    model=estimator(stat,key,threads)
    X=train[columns].to_numpy(np.float32);T=test[columns].to_numpy(np.float32)
    params={'model__sample_weight':weights} if weights is not None else {}
    model.fit(X,train[stat].to_numpy(float),**params)
    p=model.predict_proba(T)[:,1] if binary(stat) else model.predict(T)
    if key=='distribution' and stat in ('rec','pass_tds'):
        gate=estimator('anytime_td','linear',threads)
        active=(train[stat].to_numpy()>0).astype(int)
        if len(np.unique(active))==2:
            gate.fit(X,active,**params)
            positive=train[train[stat]>0]
            conditional=estimator(stat,'linear',threads)
            conditional.fit(positive[columns].to_numpy(np.float32),positive[stat].to_numpy(float),
                            **({'model__sample_weight':weights[active==1]} if weights is not None else {}))
            p=gate.predict_proba(T)[:,1]*conditional.predict(T)
            model={'base':model,'gate':gate,'conditional':conditional}
    if key=='shrink':
        if 'position' in train and 'position' in test:
            prior=test.position.map(train.groupby('position')[stat].mean()).fillna(train[stat].mean()).to_numpy(float)
            n=test.hist_games.fillna(0).to_numpy(float);w=n/(n+4)
            p=w*p+(1-w)*prior
    if stat!='margin':p=np.clip(p,0,1) if binary(stat) else np.maximum(p,0)
    return np.asarray(p,float),model


def combine(current,history,stat,kind):
    P=np.column_stack(current);equal=P.mean(axis=1)
    if len(history)<100:return equal,{'warmup':'equal','history_rows':len(history)}
    H=history[[f'm{i}' for i in range(P.shape[1])]].to_numpy(float);y=history.actual.to_numpy(float)
    if kind=='equal':return equal,{'history_rows':len(H)}
    if kind=='weighted':
        weights=1/np.maximum([loss(stat,y,H[:,i]).mean() for i in range(H.shape[1])],1e-8);weights/=weights.sum()
        return P@weights,{'weights':weights.tolist(),'history_rows':len(H)}
    if binary(stat):
        if len(np.unique(y))<2:return equal,{'warmup':'one-class equal'}
        model=LogisticRegression(C=.1,max_iter=1000).fit(H,y)
        return model.predict_proba(P)[:,1],{'history_rows':len(H)}
    model=Ridge(alpha=100,positive=True).fit(H,y)
    return np.maximum(model.predict(P),0),{'history_rows':len(H)}


def calibrated(p,history):
    if len(history)<100 or history.actual.nunique()<2:return p,False
    raw=np.clip(history.raw.to_numpy(float),1e-6,1-1e-6)
    model=LogisticRegression(C=1,max_iter=1000).fit(np.log(raw/(1-raw))[:,None],history.actual)
    q=np.clip(p,1e-6,1-1e-6)
    return model.predict_proba(np.log(q/(1-q))[:,None])[:,1],True
