"""Checkpointed fixed-budget chronological discovery; ONE locked validation."""
from __future__ import annotations
import os
from pathlib import Path
import time
import warnings
import numpy as np
import pandas as pd
import joblib
from scipy.stats import norm,poisson,nbinom
from ..props.ensemble.features import eligible
from ..props.ensemble.production import season_weight_map
from .common import ROOT, REPORT, LAB_ROOT, STATS, SEED, now, stamp, read, atomic, write_once, digest, sha, registered, private_error
from .features import latest_features, availability
from . import models as M


def columns_for(spec,meta):
    stat=spec['stat'];game=stat in ('margin','total','win')
    base=list(meta['game_base_columns'] if game else meta['base_columns'])
    groups=meta['groups']
    if game:
        extra=meta['game_fp_columns'] if spec['arm']!='control' else []
    else:
        extra=[]
        for table,g in groups.items():
            include=spec['arm']=='all' or spec['arm']=='add' and spec['group']==table or spec['arm']=='leave' and spec['group']!=table or spec['arm']=='family' and spec['group']==g['family']
            if spec['arm']=='family' and spec['group']=='H3':
                extra.extend(c for c in g['columns'] if any(k in c for k in ('xtd','i5','i20','ez','td','exp','yac','adot')))
            elif include:extra.extend(g['columns'])
    return base+sorted(set(extra))


def data_for(spec,frame,games):
    stat=spec['stat']
    if stat in ('margin','total','win'):
        valid=games[stat].notna()
        if stat=='win' and 'tie' in games:valid &= ~games.tie.fillna(False).astype(bool)
        return games[valid].copy()
    return frame[eligible(frame,stat)&frame[stat].notna()].copy()


def completed_blocks(directory,spec,season=None):
    path=Path(directory)/'blocks'/spec['id']
    files=sorted(p for p in path.glob(f'{season if season else "*"}_w*.parquet') if '__' not in p.stem)
    return pd.concat([pd.read_parquet(p) for p in files],ignore_index=True) if files else pd.DataFrame()


def earlier_predictions(directory,spec,season,week):
    d=completed_blocks(directory,spec)
    return d[(d.season<season)|((d.season==season)&(d.week<week))] if len(d) else d


def member_predictions(directory,spec,target,season,week):
    result=[];joined=None
    for i,model in enumerate(('linear','hist','xgboost','mlp')):
        member=spec|{'id':f"{spec['stat']}__all__all__{model}",'model':model}
        d=completed_blocks(directory,member)
        if d.empty:raise ValueError('Required registered ensemble member unavailable')
        keys=['game_id','pid'] if 'pid' in target else ['game_id']
        current=d.merge(target[keys],on=keys,validate='one_to_one')
        current=target[keys].merge(current[keys+['raw']],on=keys,validate='one_to_one')
        if current.raw.isna().any():raise ValueError('Incomplete member coverage')
        result.append(current.raw.to_numpy())
        h=d[(d.season<season)|((d.season==season)&(d.week<week))][keys+['season','week','actual','raw']].rename(columns={'raw':f'm{i}'})
        joined=h if joined is None else joined.merge(h[keys+[f'm{i}']],on=keys,validate='one_to_one')
    return result,joined


def residuals(model,train,columns,stat,history):
    if len(history)>=100:
        return (history.actual-history.pred).to_numpy(float),'earlier emitted out-of-fold blocks'
    if hasattr(model,'predict') and not M.binary(stat):
        p=model.predict(train[columns].to_numpy(np.float32))
    else:p=np.full(len(train),float(train[stat].mean()))
    return train[stat].to_numpy(float)-p,'training residual fallback; intervals not OOF-calibrated'


def run_block(directory,spec,data,games,meta,season,week,threads):
    stat=spec['stat'];path=directory/'blocks'/spec['id']/f'{season}_w{week:02d}.parquet'
    if path.exists():return {'status':'checkpoint','rows':len(pd.read_parquet(path,columns=['game_id']))}
    target=data[data.season.eq(season)&data.week.between(week,min(18,week+3))].copy()
    if target.empty:return {'status':'no eligible target rows','rows':0}
    first=games[games.season.eq(season)&games.week.between(week,min(18,week+3))].kickoff_utc.min()
    clock=availability(games)
    train=data[(data.season>=2021)&((data.season<season)|((data.season==season)&(data.week<week)))].copy()
    valid=np.array([clock.get((s,w),pd.Timestamp.max.tz_localize('UTC'))<first for s,w in zip(train.season,train.week)])
    train=train[valid].sort_values(['season','week','kickoff_utc','game_id'])
    if len(train)<100:raise ValueError('Insufficient strictly earlier training rows')
    cols=columns_for(spec,meta)
    if spec['arm'] in ('add','family') and len(cols)==len(meta['base_columns']):
        raise ValueError('Requested FPDS table/family has no eligible predeclared features')
    history=earlier_predictions(directory,spec,season,week)
    weights=train.season.map(season_weight_map(train.season.unique(),reference_season=season)).to_numpy(float)
    weights/=weights.mean();kind=spec['model']
    if kind in ('equal','weighted','stacked'):
        members,h=member_predictions(directory,spec,target,season,week)
        p,model=M.combine(members,h,stat,kind)
    elif kind=='blend':
        source=spec|{'id':f'{stat}__all__all__linear','model':'linear'}
        current=completed_blocks(directory,source,season)
        current=target[['game_id']].merge(current[['game_id','pred']],on='game_id',validate='one_to_one')
        hist=completed_blocks(directory,source)
        hist=hist[hist.season<season].merge(games[['game_id','spread_line','total_line']],on='game_id')
        market='spread_line' if stat=='margin' else 'total_line'
        good=hist.dropna(subset=[market])
        x=(good.pred-good[market]).to_numpy();y=(good.actual-good[market]).to_numpy()
        w=float(np.clip(x@y/(x@x),0,1)) if len(good)>=100 and x@x>0 else 0.
        q=target[market].to_numpy(float);p=q+w*(current.pred.to_numpy()-q)
        if not np.isfinite(p).all():raise ValueError('Missing real closing benchmark line for blend')
        model={'blend_weight':w,'earlier_season_oof_rows':len(good)}
    else:
        p,model=M.fit_predict(train,target,stat,cols,kind,threads,weights)
    raw=np.asarray(p,float)
    calibrated=False
    if M.binary(stat):p,calibrated=M.calibrated(raw,history)
    if not np.isfinite(p).all():raise ValueError('Nonfinite prediction')
    residual,interval_method=residuals(model,train,cols,stat,history)
    q=np.asarray(p)[None,:]+np.quantile(residual,[.1,.5,.9])[:,None]
    if stat!='margin':q=np.maximum(q,0)
    if M.binary(stat):q=np.clip(q,0,1)
    ids=['game_id','season','week']+(['pid','team','position','hist_games'] if 'pid' in target else [])
    out=target[ids].copy();out['actual']=target[stat].to_numpy(float);out['raw']=raw;out['pred']=p
    out['q10'],out['q50'],out['q90']=q
    out['loss']=M.loss(stat,out.actual,p)
    if stat in ('margin','total'):
        r=np.sort(residual[np.isfinite(residual)])
        if len(r):
            correction=float(np.sum((2*np.arange(1,len(r)+1)-len(r)-1)*r)/(len(r)**2))
            out['crps']=np.abs((out.actual.to_numpy()-p)[:,None]-r[None,:]).mean(axis=1)-correction
    out['training_rows']=len(train);out['training_last_season']=int(train.season.max())
    out['training_last_week']=int(train[train.season.eq(train.season.max())].week.max())
    out['training_cutoff']=first.isoformat();out['calibrated']=calibrated
    # Pseudo-line is a prior-games MEDIAN, not the cached rolling mean.
    if 'pseudo_'+stat in target:out['pseudo_line']=target['pseudo_'+stat].to_numpy(float)
    if 'pseudo_line' in out:
        line=out.pseudo_line.to_numpy(float)
        if stat in ('rec','pass_tds'):
            out['p_over_pseudo']=poisson.sf(np.floor(line),np.maximum(p,1e-6))
            mean=float(train[stat].mean());variance=float(train[stat].var())
            alpha=max((variance-mean)/max(mean**2,1e-6),1e-6)
            n=1/alpha;prob=n/(n+np.maximum(p,1e-6))
            out['nb_p_over_pseudo']=nbinom.sf(np.floor(line),n,prob)
            out['nb_dispersion']=alpha
        else:
            out['p_over_pseudo']=(p[:,None]+residual[None,:]>line[:,None]).mean(axis=1)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');out.to_parquet(tmp,index=False);os.replace(tmp,path)
    state={'created_at':now(),'stat':stat,'configuration':spec,'columns':cols,'interval_method':interval_method,
           'training_rows':len(train),'training_last_week':int(out.training_last_week.iloc[0]),
           'training_last_season':int(out.training_last_season.iloc[0]),'first_target_kickoff':first.isoformat(),
           'historical_reconstruction':True,'rows':len(out),'calibrated':calibrated}
    write_once(path.with_suffix('.json'),state)
    # Retain exact fitted state for held-out grouped permutation / audit, never a live model pointer.
    joblib.dump({'model':model,'columns':cols,'state':state},path.with_suffix('.joblib'),compress=3)
    if spec['arm']=='all' and kind=='linear' and stat in STATS:
        permutation=[]
        for table,group in meta['groups'].items():
            selected=[c for c in group['columns'] if c in cols]
            if not selected:continue
            permuted=target.copy();rng=np.random.default_rng(SEED)
            keys=['week','position'] if group['entity_kind']=='player' else ['week']
            for _,idx in target.groupby(keys).groups.items():
                if group['entity_kind']=='team':
                    teams=target.loc[idx,['team']+selected].drop_duplicates('team')
                    values=teams[selected].to_numpy()[rng.permutation(len(teams))]
                    mapping=pd.DataFrame(values,index=teams.team,columns=selected)
                    permuted.loc[idx,selected]=mapping.loc[target.loc[idx,'team']].to_numpy()
                else:permuted.loc[idx,selected]=target.loc[rng.permutation(idx),selected].to_numpy()
            pp=model.predict_proba(permuted[cols].to_numpy(np.float32))[:,1] if M.binary(stat) else model.predict(permuted[cols].to_numpy(np.float32))
            if M.binary(stat):pp,_=M.calibrated(pp,history)
            if stat!='margin':pp=np.clip(pp,0,1) if M.binary(stat) else np.maximum(pp,0)
            diff=M.loss(stat,out.actual,pp)-out.loss.to_numpy()
            permutation.append(pd.DataFrame({'game_id':out.game_id,'table':table,'delta':diff}))
        if permutation:
            pd.concat(permutation,ignore_index=True).to_parquet(path.with_name(path.stem+'__permutation.parquet'),index=False)
    return {'status':'complete','rows':len(out),'train_rows':len(train),'features':len(cols)}


def canaries(meta):
    from .audit import association,latest
    result={'created_at':now(),'same_week_flags':[],'lag_policy':'raw associations diagnostic only; no unlagged observations used'}
    base=pd.read_parquet(Path(meta['path'])/'players.parquet',columns=['season','week','pid']+list(STATS),filters=[('season','<=',2024)])
    for t in latest()['working_tables']:
        if t['entity_kind']!='player':continue
        d=pd.read_parquet(t['private_path'])
        d=d.dropna(subset=['pid']);d=d[~d.duplicated(['season','week','pid'],False)]
        cols=[c['column'] for c in t['columns'] if c['laggable_numeric']]
        if not cols:continue
        numeric=d[['season','week','pid']].copy()
        from ..fpds_ingest import number
        numeric=pd.concat([numeric,pd.DataFrame({c:d[c].map(number) for c in cols},index=d.index)],axis=1)
        j=numeric.merge(base,on=['season','week','pid'])
        for stat in STATS:
            for flag in association(j,stat,cols):result['same_week_flags'].append(dict(table=t['table'],**flag))
    # Independent synthetic canaries execute the actual join implementation.
    from .features import rolling_panel,join_asof
    g=pd.DataFrame({'season':[2021,2021,2021],'week':[1,2,3],
                    'kickoff_utc':pd.to_datetime(['2021-09-13T00:00Z','2021-09-20T00:00Z','2021-09-27T00:00Z'])})
    obs=pd.DataFrame({'season':[2021]*3,'week':[1,2,3],'entity':['synthetic']*3,'metric':[1.,2.,10000.]})
    target=pd.DataFrame({'season':[2021],'week':[2],'pid':['synthetic'],'kickoff_utc':pd.to_datetime(['2021-09-20T00:00Z'])})
    a=join_asof(target,rolling_panel(obs,['metric'],g),['metric__last1'],'pid')[0]
    changed=obs.copy();changed.loc[changed.week>=2,'metric']=-10000
    b=join_asof(target,rolling_panel(changed,['metric'],g),['metric__last1'],'pid')[0]
    if not np.array_equal(a,b):raise AssertionError('Future mutation leakage canary failed')
    result['future_mutation_passed']=True
    for mode in ('shifted','shuffled'):
        z=obs.copy();z['week']=z.week+1 if mode=='shifted' else z.week.sample(frac=1,random_state=SEED).to_numpy()
        _,s,w=join_asof(target,rolling_panel(z,['metric'],g),['metric__last1'],'pid')
        if not all(np.isnan(x) or x<2 for x in w):raise AssertionError('Week-order canary failed')
        result[mode+'_week_passed']=True
    write_once(Path(meta['path'])/'CANARIES.json',result)
    atomic(REPORT/'FPDS_A6_CANARIES.json',result)
    return result


def job_status(directory,state,force=False):
    if force or time.monotonic()-state.get('_last_status',0)>=1800:
        state['_last_status']=time.monotonic()
        clean={k:v for k,v in state.items() if not k.startswith('_')}
        atomic(directory/'STATUS.json',clean)
        with (REPORT/'STATUS.md').open('a',encoding='utf-8') as f:
            f.write(f"\n- {now()}: Amendment6 {clean.get('phase')}; {clean.get('attempted',0)} configurations attempted, {clean.get('blocks',0)} blocks complete; failures={clean.get('failures',0)}. Private checkpoints retained.\n")


def run(args):
    registration=registered();meta=latest_features();protocol=read(LAB_ROOT/'docs/FPDS_AMENDMENT6_TRIALS.json')
    if not (Path(meta['path'])/'CANARIES.json').exists():canaries(meta)
    if args.command=='screen':return {'status':'canaries complete; no extra model fits or feature selection'}
    code=digest({p.name:sha(p) for p in Path(__file__).parent.glob('*.py')})
    identity=digest({'registration':registration,'features':meta['fingerprint'],'code':code})
    directory=ROOT/'research'/identity[:20];directory.mkdir(parents=True,exist_ok=True)
    if not (directory/'JOB.json').exists():write_once(directory/'JOB.json',{'created_at':now(),'feature_metadata':meta,'registration_hash':registration,'code_hash':code,'identity':identity})
    atomic(ROOT/'LATEST_RESEARCH.json',{'path':str(directory),'fingerprint':identity})
    phase=args.phase
    if phase!='discovery':
        from .report import frozen
        selection=frozen(directory)
        selected=selection['configurations']+selection.get('market_informed_configurations',[])
        base=[s for s in protocol['trials'] if s['arm']=='control']
        dependencies=[]
        for s in selected:
            if s['model'] in ('equal','weighted','stacked'):
                dependencies.extend(x for x in protocol['trials'] if x['stat']==s['stat'] and x['arm']=='all' and x['model'] in ('linear','hist','xgboost','mlp'))
            elif s['model']=='blend':
                dependencies.extend(x for x in protocol['trials'] if x['stat']==s['stat'] and x['arm']=='all' and x['model']=='linear')
        specs=list({s['id']:s for s in base+dependencies+selected}.values())
        # First-TD depends on completed ATD predictions in this phase.
        specs=sorted(specs,key=lambda s:s['stat']=='first_td')
        seasons=[2025] if phase=='validation' else [2026]
        if phase=='validation':
            lock=directory/'VALIDATION_LOCK.json'
            if lock.exists() and not args.resume:raise ValueError('Validation already started; exact checkpoint resume only')
            if not lock.exists():write_once(lock,{'created_at':now(),'frozen_hash':digest(selection),'warning':'2025 previously examined for old simulator'})
        elif not (directory/'VALIDATION_COMPLETE.json').exists():raise ValueError('Finish single frozen validation before descriptive scoring')
    else:specs=protocol['trials'];seasons=protocol['discovery']
    max_season=2024 if phase=='discovery' else 2025 if phase=='validation' else 2026
    frame=pd.read_parquet(Path(meta['path'])/'players.parquet',filters=[('season','<=',max_season)])
    games=pd.read_parquet(Path(meta['path'])/'games.parquet',filters=[('season','<=',max_season)])
    frame['kickoff_utc']=pd.to_datetime(frame.kickoff_utc,utc=True);games['kickoff_utc']=pd.to_datetime(games.kickoff_utc,utc=True)
    if phase=='discovery':frame=frame[frame.season<=2024];games=games[games.season<=2024]
    deadline=pd.Timestamp(args.deadline);threads=args.threads or max(1,(os.cpu_count() or 2)-2)
    ledger=read(directory/'LEDGER.json') if (directory/'LEDGER.json').exists() else {}
    state={'started_at':now(),'phase':phase,'attempted':len(ledger),'blocks':0,'failures':0,'trial_ceiling':protocol['trial_budget']}
    job_status(directory,state,True)
    for spec in specs:
        if spec['id'] not in ledger:
            if phase=='discovery' and len(ledger)>=protocol['trial_budget']:raise RuntimeError('Pre-registered trial budget exhausted')
            ledger[spec['id']]={'started_at':now(),'configuration':spec,'blocks':[],'status':'running'}
            atomic(directory/'LEDGER.json',ledger)
        record=ledger[spec['id']]
        if phase!='discovery':record.setdefault('discovery_status',record['status'])
        if record['status'] in ('complete','failed') and phase=='discovery':continue
        state['attempted']=len(ledger)
        try:
            if spec['stat']=='first_td':
                from .first_td import run_config
                run_config(directory,spec,frame,games,seasons,deadline)
            else:
                d=data_for(spec,frame,games)
                for season in seasons:
                    for week in protocol['refit_weeks']:
                        if phase=='descriptive' and week>6:continue
                        if (deadline-pd.Timestamp.now(tz='UTC')).total_seconds()<180:
                            state['status']='deadline checkpoint; resumable';job_status(directory,state,True)
                            return state
                        with warnings.catch_warnings(record=True) as ws:
                            warnings.simplefilter('always')
                            result=run_block(directory,spec,d,games,meta,season,week,threads)
                        record['blocks'].append(dict(season=season,week=week,result=result,warning_count=len(ws)))
                        state['blocks']+=int(result['status']=='complete')
                        atomic(directory/'LEDGER.json',ledger);job_status(directory,state)
            record['status']='complete';record['completed_at']=now()
            record[phase+'_status']='complete'
        except Exception:
            record['status']='failed';record['private_error']=private_error('research');state['failures']+=1
            record[phase+'_status']='failed'
            # Log, skip and continue; no automatic retry or alternative configuration.
        atomic(directory/'LEDGER.json',ledger)
    state['status']='complete';job_status(directory,state,True)
    marker=directory/(phase.upper()+'_COMPLETE.json')
    if not marker.exists():write_once(marker,{k:v for k,v in state.items() if not k.startswith('_')})
    return state
