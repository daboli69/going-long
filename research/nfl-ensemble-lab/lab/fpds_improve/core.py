"""Chronological combination, task schemas and distribution heads."""
import numpy as np
import pandas as pd
from scipy.stats import poisson, nbinom
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor

from .. import ensemble
from ..fpds_manual import engine as E
from ..fpds_research import models as M


def task_columns(meta, stat, protocol, arm='fpds'):
    game = stat in E.GAME_STATS
    base = list(meta['game_base_columns'] if game else meta['base_columns'])
    if arm == 'control':
        return base
    families = protocol['game_groups' if game else 'target_groups'][stat]
    if game:
        tables = [t for t, g in meta['groups'].items() if g['family'] in families]
        extra = [c for c in meta['game_fp_columns'] if any(c.startswith('fpg__'+t+'__') for t in tables)]
    else:
        extra = [c for g in meta['groups'].values() if g['family'] in families for c in g['columns']]
    return list(dict.fromkeys(base + sorted(set(extra))))


def earlier(frame, decision):
    if frame.empty:
        return frame
    return frame[pd.to_datetime(frame.available_at, utc=True).lt(decision)].copy()


def pipeline(model):
    return Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                     ('scale',StandardScaler()),('model',model)])


def predict_model(model, train, target, cols, y, weights, binary=False):
    model = pipeline(model)
    model.fit(train[cols].to_numpy(np.float32),np.asarray(y,float),model__sample_weight=weights)
    X=target[cols].to_numpy(np.float32)
    return (model.predict_proba(X)[:,1] if binary else model.predict(X)), model


def combine(current, history, stat, kind):
    names=['member_'+m for m in E.members(stat)]
    P=current[names].to_numpy(float);equal=P.mean(axis=1)
    if len(history)<100 or (M.binary(stat) and history.actual.nunique()<2):
        return equal, {'warmup':True,'history_rows':len(history)}
    H=history[names].to_numpy(float);y=history.actual.to_numpy(float)
    if kind=='weighted':
        weights=1/np.maximum([M.loss(stat,y,H[:,i]).mean() for i in range(H.shape[1])],1e-8)
        weights=.5*weights/weights.sum()+.5/len(weights)
        return P@weights, {'weights':weights.tolist(),'history_rows':len(H)}
    if M.binary(stat):
        stack=ensemble.fit_stacker(H,y,C=.1)
        fitted=ensemble.stack_predict(stack,P)
    else:
        stack=Ridge(alpha=100,positive=True).fit(H,y)
        fitted=stack.predict(P)
    p=.5*equal+.5*fitted
    return (p if stat=='margin' else np.clip(p,0,1) if M.binary(stat) else np.maximum(p,0)), {'history_rows':len(H),'shrink_to_equal':.5}


def calibrate(raw, history, kind):
    if len(history)<200 or history.actual.nunique()<2:
        return raw, {'warmup':True,'history_rows':len(history)}
    h=np.clip(history.raw.to_numpy(float),1e-6,1-1e-6);p=np.clip(raw,1e-6,1-1e-6)
    if kind=='sigmoid':
        model=LogisticRegression(C=1,max_iter=1000).fit(np.log(h/(1-h))[:,None],history.actual)
        value=model.predict_proba(np.log(p/(1-p))[:,None])[:,1]
    else:
        model=IsotonicRegression(out_of_bounds='clip').fit(h,history.actual)
        value=model.predict(p)
    return np.clip(value,1e-6,1-1e-6), {'history_rows':len(history)}


def quantiles(train,target,stat,cols,weights,before_fit=lambda _:None):
    values=[]
    for q in (.1,.5,.9):
        before_fit('quantile_'+str(q))
        model=HistGradientBoostingRegressor(loss='quantile',quantile=q,max_iter=80,max_depth=3,l2_regularization=10,random_state=20261021)
        p,_=predict_model(model,train,target,cols,train[stat],weights)
        values.append(p)
    Q=np.sort(np.column_stack(values),axis=1)
    return Q if stat=='margin' else np.maximum(Q,0)


def hurdle(train,target,stat,cols,weights,before_fit=lambda _:None):
    y=train[stat].to_numpy(float);active=y>0
    before_fit('hurdle_gate')
    if len(np.unique(active))<2:
        gate=np.full(len(target),float(active.mean()))
    else:
        gate,_=predict_model(LogisticRegression(C=.1,max_iter=1000),train,target,cols,active,weights,True)
    before_fit('positive_minus_one')
    from sklearn.linear_model import PoissonRegressor
    if active.sum()<20:
        mu=np.full(len(target),max(float(y[active].mean())-1,0) if active.any() else 0)
    elif np.max(y[active])==1:
        mu=np.zeros(len(target))
    else:
        mu,_=predict_model(PoissonRegressor(alpha=1,max_iter=500),train[active],target,cols,y[active]-1,weights[active])
    mu=np.maximum(mu,0)
    return gate*(1+mu),gate,mu


def nb_dispersion(history):
    if len(history)<100:return .001
    y=history.actual.to_numpy(float);mu=np.maximum(history.pred.to_numpy(float),1e-6)
    return float(max(np.sum((y-mu)**2-y)/max(np.sum(mu**2),1e-9),.001))


def count_over(line,mean,kind='poisson',alpha=.001,gate=None,positive_mu=None):
    k=np.floor(np.asarray(line,float));mu=np.maximum(np.asarray(mean,float),1e-9)
    if kind=='hurdle':
        return np.where(k<0,1,np.asarray(gate)*poisson.sf(k-1,np.asarray(positive_mu)))
    if kind=='nb':
        r=1/alpha
        return nbinom.sf(k,r,r/(r+mu))
    return poisson.sf(k,mu)
