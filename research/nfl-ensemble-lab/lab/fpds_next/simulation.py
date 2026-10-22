"""Shared game copula, empirical role mixtures and fixed conditional intervals."""
import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata, poisson

ORDER=('win','margin','total','pass_yds','pass_tds','rec','rec_yds','rush_yds','anytime_td')


def correlation(histories,decision):
    columns={}
    for stat,d in histories.items():
        d=d[pd.to_datetime(d.available_at,utc=True).lt(decision)]
        if len(d):columns[stat]=(d.actual-d.pred).groupby(d.game_id).mean()
    if len(columns)!=len(ORDER):return np.eye(len(ORDER)),0
    z=pd.DataFrame(columns).reindex(columns=ORDER).dropna()
    if len(z)<100:return np.eye(len(ORDER)),len(z)
    ranks=np.column_stack([norm.ppf((rankdata(z[c])-.5)/len(z)) for c in ORDER])
    corr=np.corrcoef(ranks,rowvar=False)
    if not np.isfinite(corr).all():return np.eye(len(ORDER)),len(z)
    return .5*corr+.5*np.eye(len(ORDER)),len(z)


def draws(stat,mean,u,bank,role=None):
    p=np.asarray(mean,float)[:,None];u=np.clip(u,1e-8,1-1e-8)
    ratio=np.ones_like(u) if role is None else role
    if stat in ('win','anytime_td'):
        probability=-np.expm1(np.log1p(-np.clip(p,0,1-1e-9))*ratio)
        return (u<probability).astype(float)
    if stat in ('rec','pass_tds'):return poisson.ppf(u,np.maximum(p*ratio,1e-9))
    return p*ratio+np.quantile(np.asarray(bank,float),u)


def summaries(target,values):
    y=target.actual.to_numpy(float);ordered=np.sort(values,axis=1);n=values.shape[1]
    correction=ordered@((2*np.arange(1,n+1)-n-1)/n**2)
    out=target.copy();out['pred']=values.mean(1);out['q10'],out['q50'],out['q90']=np.quantile(values,[.1,.5,.9],axis=1)
    out['crps']=np.abs(values-y[:,None]).mean(1)-correction
    return out


def radius(d):
    if len(d)<100:return 0.
    a=np.maximum.reduce([d.q10-d.actual,d.actual-d.q90,np.zeros(len(d))])
    k=min(len(a),int(np.ceil((len(a)+1)*.8)))
    return float(np.partition(a,k-1)[k-1])


def calibrate(current,history,grouped=False):
    out=current.copy();global_radius=radius(history);radii=[]
    for r in current.itertuples():
        group=history
        if grouped and len(history):
            group=history[history.position.eq(r.position)&history.r10_changed.eq(r.r10_changed)]
        radii.append(radius(group) if grouped and len(group)>=200 else global_radius)
    out['q10']=out.q10-np.asarray(radii);out['q90']=out.q90+np.asarray(radii)
    out['calibration_radius']=radii
    return out


def energy(samples,actual,scale):
    """Disjoint sample pairs estimate the independent-copy energy term."""
    z=np.asarray(samples,float)/scale[None,:];y=np.asarray(actual,float)/scale
    n=len(z)//2
    return float(np.linalg.norm(z-y,axis=1).mean()-.5*np.linalg.norm(z[:n]-z[n:2*n],axis=1).mean())
