"""Frozen Amendment8 discovery; no holdout scoring or forecast replacement."""
import json
import sys
import time
import traceback
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import poisson,nbinom

from . import storage as S,core as C,features as F,opportunity as O
from ..fpds_manual import engine as E,jobs
from ..fpds_research import models as M
from ..props.ensemble.production import season_weight_map
from ..fpds_research.common import read,write_once,now


def weights(frame,season):
    w=frame.season.map(season_weight_map(frame.season.unique(),reference_season=season)).to_numpy(float)
    return w/w.mean()


def identifiers(target,stat,games,pred,raw=None):
    cols=[c for c in ('game_id','pid','team','position','season','week','kickoff_utc') if c in target]
    out=target[cols].reset_index(drop=True).copy();out['actual']=target[stat].to_numpy(float)
    out['pred']=np.asarray(pred,float);out['raw']=out.pred if raw is None else raw
    clock=E.availability(games)
    out['available_at']=[clock.loc[(s,w)] for s,w in zip(out.season,out.week)]
    return out


def add_intervals(out,stat,history,train=None):
    if len(history)>=100:
        bank=(history.actual-history.pred).to_numpy(float);method='earlier emitted OOF residuals'
    elif train is not None:
        bank=(train[stat]-train[stat].mean()).dropna().to_numpy(float);method='training constant-mean residual warmup'
    else:
        bank=np.array([0.]);method='not calibrated; no earlier residual bank'
    if not len(bank):bank=np.array([0.])
    if M.binary(stat):
        out['q10']=(out.pred>.9).astype(float);out['q50']=(out.pred>.5).astype(float);out['q90']=(out.pred>.1).astype(float)
    elif stat in ('rec','pass_tds'):
        for q in (.1,.5,.9):out['q'+str(int(q*100))]=poisson.ppf(q,np.maximum(out.pred,1e-9))
    else:
        for q in (.1,.5,.9):out['q'+str(int(q*100))]=out.pred+np.quantile(bank,q)
        if stat!='margin':out[['q10','q50','q90']]=out[['q10','q50','q90']].clip(lower=0)
        ordered=np.sort(bank);n=len(ordered)
        correction=float(np.sum((2*np.arange(1,n+1)-n-1)*ordered)/(n*n))
        out['crps']=[float(np.abs(y-p-ordered).mean()-correction) for y,p in zip(out.actual,out.pred)]
    out['interval_method']=method
    return out,bank


def pseudo_lines(players,observations,games):
    clock=E.availability(games);obs=observations.copy()
    if {'snap_share','targets','carries','dropbacks'}<=set(obs):
        played=obs.snap_share.fillna(0).gt(0)|obs[['targets','carries','dropbacks']].fillna(0).sum(axis=1).gt(0)
        obs=obs[played].copy()
    obs['available_at']=[clock.get((s,w),pd.NaT) for s,w in zip(obs.season,obs.week)]
    obs=obs.dropna(subset=['available_at']).sort_values('available_at').drop_duplicates(['game_id','pid'])
    panels={pid:d for pid,d in obs.groupby('pid')}
    result={}
    for stat in ('pass_yds','pass_tds','rec','rec_yds','rush_yds'):
        values=[]
        for r in players.itertuples():
            panel=panels.get(r.pid)
            if panel is None:values.append(np.nan);continue
            prior=panel[panel.available_at.lt(r.kickoff_utc)].tail(8)[stat]
            values.append(np.floor(float(prior.median()))+.5 if len(prior) else np.nan)
        result['pseudo_'+stat]=values
    return pd.concat([players.drop(columns=list(result),errors='ignore').reset_index(drop=True),pd.DataFrame(result)],axis=1)


def probability_columns(out,stat,target,bank,kind='poisson',alpha=.001,gate=None,mu=None):
    col='pseudo_'+stat
    if col not in target:return out
    line=target[col].to_numpy(float);out['pseudo_line']=line
    if stat in ('rec','pass_tds'):
        out['p_over']=C.count_over(line,out.pred,kind,alpha,gate,mu)
    else:
        out['p_over']=[float(np.mean(v+bank>l)) if np.isfinite(l) else np.nan for v,l in zip(out.pred,line)]
    return out


def specs():
    entries=[]
    def add(family,stat,arm,kind,reference):
        entries.append(dict(id=f'{family}__{stat}__{arm}__{kind}',family=family,stat=stat,arm=arm,kind=kind,reference=reference))
    for stat in E.GAME_STATS:
        for arm in ('control','fpds'):
            add('strong_games',stat,arm,'equal',f'A7/{stat}/control' if arm=='control' else f'strong_games__{stat}__control__equal')
    for stat in E.PROP_STATS:add('target_features',stat,'fpds','equal',f'A7/{stat}/fpds')
    for stat in E.GAME_STATS+E.PROP_STATS:
        for arm in ('control','fpds'):
            for kind in ('weighted','stacked'):add('combination',stat,arm,kind,f'A7/{stat}/{arm}')
    for stat in E.PROP_STATS:
        for arm in ('control','fpds'):add('opportunity',stat,arm,'hierarchy',f'A7/{stat}/{arm}')
    for stat in ('margin','total','pass_yds','rec_yds','rush_yds'):
        ref=f'strong_games__{stat}__fpds__equal' if stat in E.GAME_STATS else f'target_features__{stat}__fpds__equal'
        add('distribution',stat,'fpds','quantile',ref)
    for stat in ('rec','pass_tds'):
        for kind in ('hurdle','nb'):add('distribution',stat,'fpds',kind,f'target_features__{stat}__fpds__equal')
    for stat in ('win','anytime_td'):
        for arm in ('control','fpds'):
            for kind in ('sigmoid','isotonic'):add('distribution',stat,arm,kind,f'A7/{stat}/{arm}')
    return entries


def selected_specs(repair_parent=None):
    return [s for s in specs() if not repair_parent or s['family']=='opportunity']


def run(path,hours=3,repair_parent=None):
    protocol,signature=S.registered();deadline=time.monotonic()+hours*3600
    source=jobs.directory(protocol['source_job'])
    audit=S.audit_source(source)
    if (path/'RUN.json').exists():
        saved=read(path/'RUN.json')
        if saved['signature']!=signature or saved['source_hashes']!=audit:raise ValueError('Resume refused: source or code changed')
        repair_parent=saved.get('repair_parent')
    else:
        path.mkdir(parents=True,exist_ok=False)
        selected=selected_specs(repair_parent)
        write_once(path/'RUN.json',{'created_at':now(),'signature':signature,'source_hashes':audit,'protocol':protocol,'specs':selected,'repair_parent':repair_parent})
        if repair_parent:
            import shutil
            parent=S.ROOT/repair_parent;old=read(parent/'RUN.json');repair=read(S.LAB_ROOT/'docs/FPDS_A8_REPAIR_PROTOCOL.json')
            if repair_parent!=repair['parent_run'] or old['source_hashes']!=audit:raise ValueError('Repair parent/data mismatch')
            write_once(path/'REPAIR.json',repair)
            for name in ('strong_games.parquet','STRONG_FEATURES.json','players.parquet','PLAYER_FEATURES.json'):
                shutil.copyfile(parent/name,path/name)
    meta=read(source/'INPUT.json');players,games=__import__('lab.fpds_manual.run',fromlist=['load']).load(meta)
    players=players[players.season.le(2024)].copy();games=games[games.season.le(2024)].copy()
    observations=pd.read_parquet(Path(meta['base_source']).with_name('observations_production.parquet'))
    observations=observations[observations.season.between(2020,2024)].copy()
    from ..data_pipeline import GAMES_TABLE,TEAM_GAMES,QB_GAMES,INJURY_VALID
    feature_path=path/'strong_games.parquet'
    if feature_path.exists():
        games=pd.read_parquet(feature_path);strong_cols=read(path/'STRONG_FEATURES.json')['columns']
    else:
        S.status(path,'preparing',step='source-week-clock team/QB/efficiency/pace/rating reconstruction')
        injuries=pd.read_parquet(INJURY_VALID);injuries['available_at']=pd.to_datetime(injuries.available_at,utc=True)
        games,strong_cols=F.strong_games(games,pd.read_parquet(GAMES_TABLE),pd.read_parquet(TEAM_GAMES),pd.read_parquet(QB_GAMES),injuries,
                                      before_fit=lambda head:S.ledger(path,'feature_reconstruction',head,output=False))
        games.to_parquet(feature_path,index=False)
        write_once(path/'STRONG_FEATURES.json',{'columns':strong_cols,'sha256':S.sha(feature_path),'rule':'available source weeks only; last-known QB; unknown injuries retained as unknown'})
    if S.sha(feature_path)!=read(path/'STRONG_FEATURES.json')['sha256']:raise ValueError('Prepared strong-feature snapshot changed')
    games['kickoff_utc']=pd.to_datetime(games.kickoff_utc,utc=True)
    # The opponent/pace/QB information is common to both enhanced game arms.
    meta=dict(meta,game_base_columns=list(dict.fromkeys(meta['game_base_columns']+strong_cols)))
    if (path/'players.parquet').exists():players=pd.read_parquet(path/'players.parquet')
    else:
        players=pseudo_lines(players,observations,games)
        players.to_parquet(path/'players.parquet',index=False)
        write_once(path/'PLAYER_FEATURES.json',{'sha256':S.sha(path/'players.parquet')})
    if S.sha(path/'players.parquet')!=read(path/'PLAYER_FEATURES.json')['sha256']:raise ValueError('Prepared player snapshot changed')
    team_all_columns=list(dict.fromkeys(meta['game_base_columns']+meta['game_fp_columns']))
    teams,obs=O.team_frame(games,observations,team_all_columns)
    obs_cols=['game_id','pid','team']+[c for c in ('targets','carries','dropbacks','off_td') if c in obs]
    aug=obs[obs_cols].rename(columns={c:'actual_'+c for c in obs_cols if c not in ('game_id','pid','team')})
    players=players.merge(aug,on=['game_id','pid','team'],how='left',validate='one_to_one')
    total_cols=[c for c in teams if c.startswith('actual_team_')]
    players=players.merge(teams[['game_id','team']+total_cols],on=['game_id','team'],how='left',validate='many_to_one')
    originals={(stat,arm):S.source_blocks(source,stat,arm) for stat in E.GAME_STATS+E.PROP_STATS for arm in ('control','fpds')}
    failures=[]
    for spec in read(path/'RUN.json')['specs']:
        stat,arm,variant=spec['stat'],spec['arm'],spec['id']
        data=E.data_for(stat,players,games);data=data[data[stat].notna()]
        for season in protocol['discovery']:
            for week in protocol['refit_weeks']:
                output=S.block_path(path,variant,season,week);failed=output.with_suffix('.FAILED.json')
                if failed.exists():failures.append(str(failed.relative_to(path)));continue
                if output.exists():continue
                if time.monotonic()>deadline-600 or (path/'STOP_REQUESTED.json').exists():
                    S.status(path,'checkpoint',step=variant,message='Resume exact frozen study; no result-dependent changes')
                    return
                target=data[data.season.eq(season)&data.week.between(week,min(week+3,18))].copy()
                if target.empty:continue
                decision=target.kickoff_utc.min();train=E.training_rows(data,games,decision,season,week,stat)
                prior=S.history(path,variant,decision);w=weights(train,season)
                S.status(path,'running',step=f'{variant} / {season} w{week}',failed_blocks=len(failures))
                try:
                    out=execute(path,spec,meta,protocol,train,target,games,teams,originals,prior,w,decision,season,week)
                    clock=E.availability(games)
                    out['available_at']=[clock.loc[(s,w)] for s,w in zip(out.season,out.week)]
                    S.save(path,variant,season,week,out)
                except Exception:
                    output.parent.mkdir(parents=True,exist_ok=True)
                    output.with_suffix('.PRIVATE.log').write_text(traceback.format_exc(),encoding='utf-8')
                    write_once(failed,{'at':now(),'status':'failed/logged/skipped; no silent exclusion from nomination'})
                    failures.append(str(failed.relative_to(path)))
    summarize(path,source,originals,protocol,failures)


def get_reference(path,reference,originals):
    if reference.startswith('A7/'):
        _,stat,arm=reference.split('/')
        return originals[(stat,arm)].copy()
    files=sorted((path/'blocks'/reference).glob('*.parquet'))
    return pd.concat([pd.read_parquet(p) for p in files],ignore_index=True) if files else pd.DataFrame()


def execute(path,spec,meta,protocol,train,target,games,teams,originals,prior,w,decision,season,week):
    stat,arm,variant,kind=spec['stat'],spec['arm'],spec['id'],spec['kind']
    keys=['game_id']+(['pid'] if stat not in E.GAME_STATS else [])
    current=target[keys].merge(originals[(stat,arm)],on=keys,validate='one_to_one')
    if len(current)!=len(target):raise ValueError('Saved source eligibility differs')
    current.index=target.index
    past=C.earlier(originals[(stat,arm)],decision)
    cols=C.task_columns(meta,stat,protocol,arm)
    bank=None
    if spec['family'] in ('strong_games','target_features'):
        def before(member):S.ledger(path,variant+'/'+member,None if member=='equal_average' else member)
        out,bank=E.fit_matched(train,target,stat,cols,prior,max(1,(__import__('os').cpu_count() or 2)-2),before_fit=before)
        return probability_columns(out,stat,target,bank)
    if kind!='quantile':S.ledger(path,variant)
    before=lambda head:S.ledger(path,variant,head)
    if spec['family']=='combination':
        before(kind)
        raw,detail=C.combine(current,past,stat,kind)
        p,_=M.calibrated(raw,prior) if M.binary(stat) else (raw,False)
        out=identifiers(target,stat,games,p,raw);out['meta_history_rows']=len(past)
    elif spec['family']=='opportunity':
        team_data=teams.copy();team_data[stat]=team_data['actual_team_off_td' if stat=='anytime_td' else 'actual_team_'+('pass_yds' if stat=='rec_yds' else stat)]
        tt=E.training_rows(team_data,games,decision,season,week,stat)
        ttarget=team_data[team_data.game_id.isin(target.game_id)].copy()
        # Common team feature set keeps passing/receiving team totals identical.
        team_cols=C.task_columns(meta,'total',protocol,arm)
        p,raw,diag=O.predict(train,target,tt,ttarget,stat,cols,team_cols,w,weights(tt,season),before)
        out=identifiers(target,stat,games,p);out['unreconciled']=raw
        folder=path/'coherence'/variant;folder.mkdir(parents=True,exist_ok=True)
        diag.to_parquet(folder/f'{season}_w{week:02d}.parquet',index=False)
    elif kind=='quantile':
        quantile_fit=lambda head:S.ledger(path,variant+'/'+head,head)
        Q=C.quantiles(train,target,stat,cols,w,quantile_fit)
        out=identifiers(target,stat,games,Q[:,1]);out['q10'],out['q50'],out['q90']=Q.T
        out['interval_method']='direct quantile heads; sorted; nonnegative except margin'
    elif kind=='hurdle':
        p,gate,mu=C.hurdle(train,target,stat,cols,w,before)
        out=identifiers(target,stat,games,p);out,bank=add_intervals(out,stat,prior,train)
        for q in (.1,.5,.9):
            conditional=np.clip((q-(1-gate))/np.maximum(gate,1e-9),0,1-1e-9)
            out['q'+str(int(q*100))]=np.where(q<=1-gate,0,1+poisson.ppf(conditional,mu))
        out['interval_method']='hurdle gate + positive shifted Poisson'
        return probability_columns(out,stat,target,bank,'hurdle',gate=gate,mu=mu)
    elif kind=='nb':
        reference=get_reference(path,spec['reference'],originals)
        refcurrent=target[keys].merge(reference,on=keys,validate='one_to_one')
        history=C.earlier(reference,decision);alpha=C.nb_dispersion(history)
        out=identifiers(target,stat,games,refcurrent.pred);before('earlier_OOF_dispersion')
        for q in (.1,.5,.9):out['q'+str(int(q*100))]=nbinom.ppf(q,1/alpha,(1/alpha)/(1/alpha+np.maximum(out.pred,1e-9)))
        out['interval_method']='negative binomial, earlier OOF dispersion';out['dispersion']=alpha
        return probability_columns(out,stat,target,np.array([0.]),'nb',alpha=alpha)
    else:
        # Explicit sigmoid/isotonic experiment on original raw ensemble probabilities.
        before(kind)
        p,_=C.calibrate(current.raw.to_numpy(float),past,kind)
        out=identifiers(target,stat,games,p,current.raw.to_numpy(float));out['meta_history_rows']=len(past)
    if 'q10' not in out:out,bank=add_intervals(out,stat,prior,train)
    elif bank is None:
        bank=(prior.actual-prior.pred).to_numpy(float) if len(prior)>=100 else (train[stat]-train[stat].mean()).to_numpy(float)
    return probability_columns(out,stat,target,bank)


def diagnostics(frame,stat):
    y=frame.actual.to_numpy(float);p=frame.pred.to_numpy(float)
    result={'n':len(frame),'games':int(frame.game_id.nunique()),'primary_loss':float(M.loss(stat,y,p).mean())}
    if M.binary(stat):
        p=np.clip(p,1e-6,1-1e-6)
        result['log_loss']=float(-(y*np.log(p)+(1-y)*np.log1p(-p)).mean())
        bins=np.minimum((p*10).astype(int),9)
        result['reliability']=[{'low':i/10,'n':int((bins==i).sum()),'predicted':float(p[bins==i].mean()),'observed':float(y[bins==i].mean())} for i in range(10) if (bins==i).any()]
    else:
        result['mae']=float(np.abs(y-p).mean());result['rmse']=float(np.sqrt(np.square(y-p).mean()))
        if 'crps' in frame:result['crps']=float(frame.crps.mean())
        if all(c in frame for c in ('q10','q50','q90')):
            result['pinball']={str(q):float(np.maximum(q*(y-frame[c]),(q-1)*(y-frame[c])).mean()) for q,c in ((.1,'q10'),(.5,'q50'),(.9,'q90'))}
            result['coverage80']=float(((y>=frame.q10)&(y<=frame.q90)).mean())
    if 'pseudo_line' in frame:
        valid=frame.pseudo_line.notna()&frame.p_over.notna()
        if valid.any():
            event=(frame.loc[valid,'actual']>frame.loc[valid,'pseudo_line']).astype(float)
            result['pseudo_line']={'n':int(valid.sum()),'brier':float(np.square(frame.loc[valid,'p_over']-event).mean()),'mean_p_over':float(frame.loc[valid,'p_over'].mean()),'observed_over':float(event.mean())}
    return result


def summarize(path,source,originals,protocol,failures):
    rows=[]
    family_counts={'strong_games':42,'target_features':30,'combination':36,'opportunity':12,'distribution':27}
    for spec in read(path/'RUN.json')['specs']:
        files=sorted((path/'blocks'/spec['id']).glob('*.parquet'))
        if not files:continue
        d=pd.concat([pd.read_parquet(f) for f in files],ignore_index=True)
        ref=get_reference(path,spec['reference'],originals)
        if ref.empty:continue
        keys=['game_id']+(['pid'] if 'pid' in d else [])
        joined=d.merge(ref[keys+['pred','actual']],on=keys,suffixes=('','_reference'),validate='one_to_one')
        if len(joined)==0:continue
        if not np.allclose(joined.actual,joined.actual_reference):raise ValueError('Comparison actual labels differ')
        base=M.loss(spec['stat'],joined.actual,joined.pred_reference);new=M.loss(spec['stat'],joined.actual,joined.pred)
        effect=E.paired(new-base,joined.game_id,family_counts[spec['family']])
        seasons={str(s):float((new-base)[joined.season.eq(s)].mean()) for s in protocol['discovery'] if joined.season.eq(s).any()}
        rows.append(dict(spec,**effect,control_loss=float(base.mean()),new_loss=float(new.mean()),seasons=seasons,
                         identical_sample=len(joined)==len(d)==len(ref),diagnostics=diagnostics(d,spec['stat']),
                         baseline_diagnostics=diagnostics(ref,spec['stat'])))
    for family,count in family_counts.items():
        subset=sorted([r for r in rows if r['family']==family],key=lambda r:r['p']);previous=0
        for i,r in enumerate(subset):
            previous=max(previous,min(1,r['p']*(count-i)));r['holm_p']=previous
            r['relative_reduction']=-r['delta']/max(r['control_loss'],1e-9)
            r['seasons_agreeing']=sum(v<0 for v in r['seasons'].values())
            r['discovery_nomination']=bool(not failures and r['identical_sample'] and r['games']>=200 and r['relative_reduction']>=.01 and r['corrected_ci95'][1]<0 and r['holm_p']<.05 and r['seasons_agreeing']>=2)
            r['decision']='exploratory nominee; future confirmation required' if r['discovery_nomination'] else 'no discovery gate passed'
    coherence=[]
    for folder in sorted((path/'coherence').glob('*')):
        files=sorted(folder.glob('*.parquet'))
        if not files:continue
        d=pd.concat([pd.read_parquet(f) for f in files],ignore_index=True)
        coherence.append({'variant':folder.name,'team_games':len(d),'max_abs_coherence_error':float(d.coherence_error.abs().max()),'mean_other_fraction':float((d.other_players/d.team_projection.clip(lower=1e-9)).mean())})
    S.audit_source(source)  # Caller also verifies equality to the frozen hash manifest.
    integrity=S.audit_source(source)==read(path/'RUN.json')['source_hashes']
    summary={'created_at':now(),'split':'2022-24 previously examined discovery only; no holdout pass or2026 selection','rows':rows,'failures':failures,
             'coherence':coherence,'trials':read(path/'TRIALS.json'),'source_integrity_unchanged':integrity,'status':'shadow only; no promotion'}
    summary['repair_parent']=read(path/'RUN.json').get('repair_parent')
    write_once(path/'SUMMARY.json',summary)
    if not integrity:raise ValueError('Source snapshot changed during study; results quarantined')
    S.status(path,'complete',comparisons=len(rows),failures=len(failures),nominations=sum(r['discovery_nomination'] for r in rows))
