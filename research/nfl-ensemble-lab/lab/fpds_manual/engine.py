"""Same four-member ensemble in both arms; no market inputs or live promotion."""
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
from scipy.stats import poisson,bernoulli
from ..ensemble import equal_average,MODEL_KEYS
from ..props.ensemble.features import eligible
from ..props.ensemble.production import season_weight_map
from ..fpds_research import models as M
from ..fpds_research.features import availability
from ..fpds_research.walkforward import columns_for

MEMBERS=('linear','hist','xgboost','mlp')
GAME_STATS=('win','margin','total')
PROP_STATS=('pass_yds','pass_tds','rec','rec_yds','rush_yds','anytime_td')


def members(stat):return MODEL_KEYS if stat in GAME_STATS else MEMBERS


def fit_member(train,target,stat,cols,key,threads,weights):
    if stat not in GAME_STATS:return M.fit_predict(train,target,stat,cols,key,threads,weights)
    from ..models import make,grid
    if train[stat].nunique()<2:return np.full(len(target),float(train[stat].mean())),{'kind':'constant training-only fallback'}
    kind='clf' if stat=='win' else 'reg'
    model=make(kind,key,grid(kind,key)[0])
    if 'model__n_jobs' in model.get_params():model.set_params(model__n_jobs=threads)
    model.fit(train[cols].to_numpy(np.float32),train[stat].to_numpy(float),model__sample_weight=weights)
    X=target[cols].to_numpy(np.float32)
    pred=model.predict_proba(X)[:,1] if stat=='win' else model.predict(X)
    if stat=='total':pred=np.maximum(pred,0)
    return pred,model


def targets(scope):return GAME_STATS if scope=='games' else PROP_STATS if scope=='props' else GAME_STATS+PROP_STATS


def data_for(stat,players,games):
    if stat in GAME_STATS:
        result=games.copy()
        if stat=='win':result=result[~result.get('tie',pd.Series(False,index=result.index)).fillna(False).astype(bool)]
        return result
    return players[eligible(players,stat)].copy()


def training_rows(data,games,decision,season,week,stat):
    clock=availability(games)
    before=(data.season<season)|((data.season==season)&data.week.lt(week))
    known=np.array([clock.get((s,w),pd.Timestamp.max.tz_localize('UTC'))<decision for s,w in zip(data.season,data.week)])
    return data[data.season.ge(2021)&before&known&data[stat].notna()].sort_values(['season','week','kickoff_utc','game_id'])


def columns(meta,stat,arm):
    return columns_for({'stat':stat,'arm':'all' if arm=='fpds' else 'control','group':'all'},meta)


def history(path,stat,arm,decision):
    files=sorted((Path(path)/'blocks'/stat/arm).glob('*.parquet'))
    if not files:return pd.DataFrame()
    d=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
    return d[pd.to_datetime(d.available_at,utc=True).lt(decision)]


def residuals(train_prediction,train,stat,prior):
    if len(prior)>=100:
        return (prior.actual-prior.pred).to_numpy(float),'earlier emitted out-of-fold residuals'
    return train[stat].to_numpy(float)-train_prediction,'training residual warm-up; not OOF-calibrated'


def fit_matched(train,target,stat,cols,prior,threads=1,fit=None,before_fit=None):
    fit=fit or fit_member
    weights=train.season.map(season_weight_map(train.season.unique(),reference_season=int(target.season.max()))).to_numpy(float)
    weights/=weights.mean()
    predictions=[];train_predictions=[]
    for member in members(stat):
        if before_fit is not None:before_fit(member)
        p,model=fit(train,target,stat,cols,member,threads,weights)
        predictions.append(p)
        if hasattr(model,'predict'):
            X=train[cols].to_numpy(np.float32)
            fitted=model.predict_proba(X)[:,1] if M.binary(stat) else model.predict(X)
            if stat!='margin':fitted=np.clip(fitted,0,1) if M.binary(stat) else np.maximum(fitted,0)
        else:fitted=np.full(len(train),float(train[stat].mean()))
        train_predictions.append(fitted)
    if before_fit is not None:before_fit('equal_average')
    P=np.column_stack(predictions);raw=equal_average(P)
    p,calibrated=M.calibrated(raw,prior) if M.binary(stat) else (raw,False)
    bank,method=residuals(equal_average(np.column_stack(train_predictions)),train,stat,prior)
    bank=bank[np.isfinite(bank)]
    if not len(bank):raise ValueError('No earlier residual history')
    ids=[c for c in ('game_id','pid','name','team','position','home_team','away_team','season','week','kickoff_utc') if c in target]
    out=target[ids].copy().reset_index(drop=True)
    for i,key in enumerate(members(stat)):out['member_'+key]=P[:,i]
    out['raw']=raw;out['pred']=p;out['actual']=target[stat].to_numpy(float)
    out['member_min']=P.min(1);out['member_max']=P.max(1)
    out['mean']=p;out['stat']=stat;out['calibrated']=calibrated;out['interval_method']=method
    out['training_rows']=len(train);out['training_min_season']=int(train.season.min())
    out['training_max_season']=int(train.season.max());out['training_last_week']=int(train.loc[train.season.eq(train.season.max()),'week'].max())
    if M.binary(stat):q=bernoulli.ppf(np.array([.1,.5,.9])[:,None],p[None,:])
    elif stat in ('rec','pass_tds'):q=poisson.ppf(np.array([.1,.5,.9])[:,None],np.maximum(p,1e-9)[None,:])
    else:q=p[None,:]+np.quantile(bank,[.1,.5,.9])[:,None]
    if stat!='margin':q=np.maximum(q,0)
    out['q10'],out['q50'],out['q90']=q;out['median']=q[1]
    out['loss']=M.loss(stat,out.actual,p)
    if stat in ('margin','total'):
        ordered=np.sort(bank);n=len(bank)
        correction=float(np.sum((2*np.arange(1,n+1)-n-1)*ordered)/n**2)
        out['crps']=[float(abs(y-v-ordered).mean()-correction) for y,v in zip(out.actual,p)]
    return out,bank


def simulate(rows,bank,sims=10000,seed=17):
    """Common random numbers across arms; simulated mean may differ after clipping."""
    rows=rows.copy()
    for ix,r in rows.iterrows():
        token=f'{seed}:{r.game_id}:{r.get("pid","")}:{r.stat}'.encode()
        rng=np.random.default_rng(int.from_bytes(hashlib.sha256(token).digest()[:8],'little'))
        if M.binary(r.stat):draws=rng.binomial(1,np.clip(r['mean'],0,1),sims)
        elif r.stat in ('rec','pass_tds'):draws=rng.poisson(max(r['mean'],1e-9),sims)
        else:
            draws=r['mean']+rng.choice(bank,sims,replace=True)
            if r.stat!='margin':draws=np.maximum(draws,0)
        rows.loc[ix,['q10','q50','q90']]=np.quantile(draws,[.1,.5,.9])
        rows.loc[ix,'median']=rows.loc[ix,'q50'];rows.loc[ix,'simulated_mean']=float(draws.mean())
        rows.loc[ix,'monte_carlo_mean_se']=float(np.std(draws)/np.sqrt(sims))
        if r.stat in ('win','anytime_td'):rows.loc[ix,'simulated_probability']=float(draws.mean())
        if r.stat=='margin':rows.loc[ix,'margin_sim_home_win_probability']=float((draws>0).mean())
    rows['sims']=int(sims);rows['simulation_seed']=int(seed)
    rows['simulation_type']='conditional distribution draws; not play-by-play'
    return rows


def paired(delta,games,family_size):
    d=pd.DataFrame({'game_id':games,'delta':np.asarray(delta,float)}).dropna()
    grouped=d.groupby('game_id').delta.agg(['sum','size'])
    if grouped.empty:return {'n':0,'games':0,'delta':None,'ci95':None,'corrected_ci95':None,'p':1.}
    rng=np.random.default_rng(20261021);ix=rng.integers(0,len(grouped),(2000,len(grouped)))
    draws=grouped['sum'].to_numpy()[ix].sum(1)/grouped['size'].to_numpy()[ix].sum(1)
    value=float(d.delta.mean());alpha=.025/family_size
    return {'n':len(d),'games':len(grouped),'delta':value,'ci95':np.quantile(draws,[.025,.975]).tolist(),
            'corrected_ci95':np.quantile(draws,[alpha,1-alpha]).tolist(),'p':float((np.sum(draws-value<=value)+1)/2001)}
