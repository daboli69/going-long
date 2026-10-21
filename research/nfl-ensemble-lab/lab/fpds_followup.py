"""Bounded Amendment9 shadow tests. Private rows, aggregate reports only."""
import argparse
import json
import os
import subprocess
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import roc_auc_score

from .fpds_improve import storage as S, core as C
from .fpds_improve.run import weights, identifiers, diagnostics
from .fpds_manual import engine as E, jobs
from .fpds_research import models as M
from .fpds_research.common import read, write_once, now, digest

ROOT = S.ROOT.parent / 'followup9'
PROTOCOL = S.LAB_ROOT / 'docs/FPDS_A9_PROTOCOL.json'
COUNTS = {'matched_quantile': 4, 'residual': 3, 'soft_coherence': 12,
          'conformal': 2, 'probability': 4}


def registered():
    files = [PROTOCOL, Path(__file__), S.LAB_ROOT/'docs/PHASE10_PREREGISTRATION.md']
    for p in files:
        rel = subprocess.check_output(['git','ls-files','--full-name',str(p)],cwd=S.LAB_ROOT,text=True).strip()
        if not rel:
            raise ValueError('Commit Amendment9 before fits')
        old = subprocess.check_output(['git','show','HEAD:'+rel],cwd=S.LAB_ROOT).decode('utf-8').replace('\r\n','\n')
        if old != p.read_text(encoding='utf-8'):
            raise ValueError('Uncommitted Amendment9 changes; no fit permitted')
    return read(PROTOCOL), digest({str(p):S.sha(p) for p in files})


def load_blocks(path, variant):
    files = sorted((path/'blocks'/variant).glob('*.parquet'))
    return pd.concat([pd.read_parquet(p) for p in files],ignore_index=True) if files else pd.DataFrame()


def keys(frame):
    return ['game_id'] + (['pid'] if 'pid' in frame else [])


def align(new, reference):
    k = keys(new)
    if new.duplicated(k).any() or reference.duplicated(k).any():
        raise ValueError('Duplicate comparison keys')
    d = new.merge(reference[k+['actual','pred']],on=k,suffixes=('','_reference'),validate='one_to_one')
    if len(d)!=len(new) or len(d)!=len(reference) or not np.allclose(d.actual,d.actual_reference):
        raise ValueError('Incomplete or changed evaluation sample/targets')
    return d


def interval_score(frame):
    y=frame.actual.to_numpy(float);lo=frame.q10.to_numpy(float);hi=frame.q90.to_numpy(float)
    return hi-lo+10*np.maximum(lo-y,0)+10*np.maximum(y-hi,0)


def conformal_radius(history):
    if len(history)<100:
        return 0.
    score=np.maximum.reduce([history.q10-history.actual,history.actual-history.q90,np.zeros(len(history))])
    rank=min(len(score),int(np.ceil((len(score)+1)*.8)))
    return float(np.partition(score,rank-1)[rank-1])


def soft(original, coherent):
    return .75*np.asarray(original,float)+.25*np.asarray(coherent,float)


def probability_diagnostics(d):
    p=np.clip(d.pred.to_numpy(float),1e-6,1-1e-6);y=d.actual.to_numpy(float)
    bins=np.minimum((p*10).astype(int),9);base=float(y.mean())
    rel=res=within=0.;rows=[]
    for b in range(10):
        take=bins==b
        if not take.any():continue
        pb=p[take];yb=y[take];a=float(pb.mean());o=float(yb.mean());w=float(take.mean())
        rel+=w*(a-o)**2;res+=w*(o-base)**2
        within+=w*(float(np.mean((pb-yb)**2))-(a-o)**2-o*(1-o))
        rows.append({'low':b/10,'n':int(take.sum()),'predicted':a,'observed':o})
    brier=float(np.mean((p-y)**2));uncertainty=base*(1-base)
    return {'brier':brier,'log_loss':float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p))),
            'accuracy':float(np.mean((p>.5)==y)),
            'auc':float(roc_auc_score(y,p)) if len(np.unique(y))>1 else None,
            'reliability':rel,'resolution':res,'uncertainty':uncertainty,
            'within_bin_residual':within,'decomposition_error':brier-(rel-res+uncertainty+within),'bins':rows}


def shrink_probabilities(current, earlier, stat):
    p=current.pred.to_numpy(float)
    if len(earlier)<100:return p
    if stat=='win':
        prior=np.full(len(current),float(earlier.actual.mean()))
        n=np.full(len(current),4*earlier.game_id.nunique())
    else:
        prior=current.position.map(earlier.groupby('position').actual.mean()).fillna(earlier.actual.mean()).to_numpy(float)
        n=current.hist_games.fillna(0).clip(lower=0).to_numpy(float)
    w=n/(n+20)
    return np.clip(w*p+(1-w)*prior,1e-6,1-1e-6)


def audit_targets(path, players):
    from .config import RAW_DIR
    from .props.ensemble.features import aggregate, PBP_COLS
    records=[];observations=[]
    for season in (2021,2022,2023,2024):
        plays=pd.read_parquet(RAW_DIR/f'play_by_play_{season}.parquet',columns=PBP_COLS)
        roster=pd.read_parquet(RAW_DIR/f'roster_weekly_{season}.parquet',columns=['season','week','team','gsis_id','status','position'])
        reg=aggregate(plays,roster)
        # Reuse the observation aggregator without changing its production semantics.
        # This local audit copy maps overtime quarters into its accepted range only.
        full=plays.copy();full.loc[full.qtr.gt(4),'qtr']=4
        inclusive=aggregate(full,roster)
        k=['game_id','pid'];cols=['pass_yds','pass_tds','rec','rec_yds','rush_yds','anytime_td']
        j=reg[k+cols].merge(inclusive[k+cols],on=k,suffixes=('_reg','_full'),validate='one_to_one')
        records.append({'season':season,'reg_rows':len(reg),'full_rows':len(inclusive),
                        'overtime_games':int(plays.loc[plays.qtr.gt(4),'game_id'].nunique()),
                        'changed_targets':{c:int((j[c+'_reg']!=j[c+'_full']).sum()) for c in cols}})
        observations.append(inclusive[['game_id','pid','posteam','season','week']].rename(columns={'posteam':'team'}))
    obs=pd.concat(observations,ignore_index=True)
    same=players.merge(obs[['game_id','pid','team']],on=['game_id','pid','team'],how='left',indicator=True)
    missing=same[same['_merge'].eq('left_only')]
    pair=set(zip(obs.game_id,obs.pid));otherteam=sum((g,p) in pair for g,p in zip(missing.game_id,missing.pid))
    result={'created_at':now(),'seasons':records,'candidate_rows':len(players),
            'candidate_exact_observation_missing':len(missing),'missing_but_same_player_game_on_other_team':int(otherteam),
            'unresolved_missing':int(len(missing)-otherteam),
            'definition':'regular-time v overtime-inclusive; still excludes kneels/spikes/two-point plays; not official settlement validation',
            'decision':'target mismatch verified if changes>0; no targets, IDs or old forecasts changed; official box-score/kneel settlement audit remains necessary'}
    write_once(path/'TARGET_AUDIT.json',result)
    return result


def comparison(variant,family,stat,new,ref,interval=False):
    d=align(new,ref)
    if interval:
        base=interval_score(ref.set_index(keys(ref)).loc[pd.MultiIndex.from_frame(d[keys(d)])].reset_index())
        loss=interval_score(d)
    else:
        base=M.loss(stat,d.actual,d.pred_reference);loss=M.loss(stat,d.actual,d.pred)
    effect=E.paired(loss-base,d.game_id,COUNTS[family])
    seasons={str(s):float(np.asarray(loss-base)[d.season.eq(s)].mean()) for s in (2022,2023,2024)}
    diag=diagnostics(new,stat)
    if interval:diag.update(interval_score=float(np.mean(loss)),mean_width=float((new.q90-new.q10).mean()))
    if M.binary(stat):diag.update(probability_diagnostics(new))
    return {'variant':variant,'family':family,'stat':stat,**effect,'control_loss':float(np.mean(base)),
            'new_loss':float(np.mean(loss)),'seasons':seasons,'diagnostics':diag,
            'baseline_diagnostics':diagnostics(ref,stat)}


def run(path,hours=2):
    protocol,signature=registered();deadline=time.monotonic()+hours*3600
    parent=S.ROOT/protocol['parent'];repair=S.ROOT/protocol['repair']
    source=jobs.directory(read(parent/'RUN.json')['protocol']['source_job'])
    meta=read(source/'INPUT.json');oldprotocol=read(parent/'RUN.json')['protocol']
    inputs=S.audit_source(source)
    # Fingerprint all reused fitted outputs and metadata before reading them.
    for folder in (parent,repair):
        for p in sorted(folder.glob('blocks/**/*.parquet')):inputs[str(p)]=S.sha(p)
    for name in ('players.parquet','strong_games.parquet','STRONG_FEATURES.json'):
        inputs[str(parent/name)]=S.sha(parent/name)
    from .config import RAW_DIR
    for season in (2021,2022,2023,2024):
        for prefix in ('play_by_play','roster_weekly'):
            p=RAW_DIR/f'{prefix}_{season}.parquet';inputs[str(p)]=S.sha(p)
    if (path/'RUN.json').exists():
        saved=read(path/'RUN.json')
        if saved['signature']!=signature or saved['inputs']!=inputs:raise ValueError('Resume source/configuration mismatch')
        if (path/'SUMMARY.json').exists():raise ValueError('Completed study is immutable')
    else:
        path.mkdir(parents=True,exist_ok=True)
        write_once(path/'RUN.json',{'created_at':now(),'signature':signature,'inputs':inputs,'protocol':protocol})
    players=pd.read_parquet(parent/'players.parquet');games=pd.read_parquet(parent/'strong_games.parquet')
    for frame in (players,games):frame['kickoff_utc']=pd.to_datetime(frame.kickoff_utc,utc=True)
    meta=dict(meta,game_base_columns=list(dict.fromkeys(meta['game_base_columns']+read(parent/'STRONG_FEATURES.json')['columns'])))
    if not (path/'TARGET_AUDIT.json').exists():
        S.status(path,'running',step='target audit')
        try:audit_targets(path,players)
        except Exception:
            (path/'target_audit.PRIVATE.log').write_text(traceback.format_exc(),encoding='utf-8')
            write_once(path/'TARGET_AUDIT.json',{'status':'failed; retained private diagnostic; no source changes'})
    variants=[]
    for stat in ('rec_yds','rush_yds'):variants.append(('matched_quantile',stat,'control'))
    for stat in E.GAME_STATS:variants.append(('residual',stat,'fpds'))
    for stat in E.PROP_STATS:
        for arm in ('control','fpds'):variants.append(('soft_coherence',stat,arm))
    for stat in ('rec_yds','rush_yds'):variants.append(('conformal',stat,'fpds'))
    for stat in ('win','anytime_td'):
        for arm in ('control','fpds'):variants.append(('probability',stat,arm))
    def ledger(variant,head):
        f=path/'TRIALS.json';v=read(f) if f.exists() else {'outputs':[],'fit_calls':0,'heads':[]}
        v['outputs']=sorted(set(v['outputs'])|{variant})
        if head is not None:v['fit_calls']+=1;v['heads']=sorted(set(v['heads'])|{variant+'/'+head})
        if len(v['outputs'])>25 or v['fit_calls']>400:raise ValueError('Preregistered budget exceeded')
        S.atomic(f,v)
    for family,stat,arm in variants:
        variant=f'{family}__{stat}__{arm}'
        data=E.data_for(stat,players,games)
        if family=='residual':ref=load_blocks(parent,f'strong_games__{stat}__control__equal')
        elif family=='conformal':ref=load_blocks(parent,f'distribution__{stat}__fpds__quantile')
        else:ref=S.source_blocks(source,stat,arm)
        reference=ref.merge(data[keys(ref)+[c for c in ('hist_games','position') if c in data and c not in ref]],on=keys(ref),validate='one_to_one')
        hierarchy=load_blocks(repair,f'opportunity__{stat}__{arm}__hierarchy') if family=='soft_coherence' else None
        for season in protocol['discovery']:
            for week in protocol['refit_weeks']:
                file=S.block_path(path,variant,season,week);failed=file.with_suffix('.FAILED.json')
                if file.exists() or failed.exists():continue
                if time.monotonic()>deadline-300:
                    S.status(path,'checkpoint',step=variant);return
                S.status(path,'running',step=f'{variant}/{season}/w{week}');ledger(variant,None)
                try:
                    current=reference[reference.season.eq(season)&reference.week.between(week,min(week+3,18))].copy()
                    if current.empty:continue
                    decision=pd.to_datetime(current.kickoff_utc,utc=True).min();past=C.earlier(reference,decision)
                    if family=='matched_quantile':
                        target=current[keys(current)].merge(data,on=keys(current),validate='one_to_one')
                        train=E.training_rows(data,games,decision,season,week,stat)
                        q=C.quantiles(train,target,stat,C.task_columns(meta,stat,oldprotocol,'control'),weights(train,season),lambda h:ledger(variant,h))
                        out=identifiers(target,stat,games,q[:,1]);out['q10'],out['q50'],out['q90']=q.T
                    elif family=='residual':
                        out=current.copy();out['correction']=0.
                        cols=[c for c in C.task_columns(meta,stat,oldprotocol,'fpds') if c not in meta['game_base_columns']]
                        if len(past)>=100:
                            train=past[keys(past)+['actual','pred']].merge(data[keys(data)+cols],on=keys(data),validate='one_to_one')
                            target=current[keys(current)].merge(data[keys(data)+cols],on=keys(data),validate='one_to_one')
                            ledger(variant,'ridge_residual')
                            delta,_=C.predict_model(Ridge(alpha=100),train,target,cols,train.actual-train.pred,np.ones(len(train)))
                            out['correction']=.5*delta;out['pred']=current.pred.to_numpy()+.5*delta
                            if stat=='win':out['pred']=out.pred.clip(1e-6,1-1e-6)
                            elif stat=='total':out['pred']=out.pred.clip(lower=0)
                    elif family=='soft_coherence':
                        j=current.merge(hierarchy[keys(current)+['pred']],on=keys(current),suffixes=('','_coherent'),validate='one_to_one')
                        if len(j)!=len(current):raise ValueError('Incomplete hierarchy sample')
                        out=j.copy();out['pred']=soft(j.pred,j.pred_coherent)
                        out=out.drop(columns=[c for c in ('q10','q50','q90') if c in out])
                    elif family=='conformal':
                        out=current.copy();radius=conformal_radius(past)
                        out['q10']=(out.q10-radius).clip(lower=0);out['q90']=out.q90+radius;out['radius']=radius
                        out['calibration_rows']=len(past)
                    else:
                        out=current.copy();out['pred']=shrink_probabilities(current,past,stat)
                    S.save(path,variant,season,week,out)
                except Exception:
                    file.parent.mkdir(parents=True,exist_ok=True)
                    file.with_suffix('.PRIVATE.log').write_text(traceback.format_exc(),encoding='utf-8')
                    write_once(failed,{'status':'failed/logged/skipped; family ineligible'})
    results=[]
    for family,stat,arm in variants:
        variant=f'{family}__{stat}__{arm}';new=load_blocks(path,variant)
        if new.empty:continue
        try:
            if family=='residual':ref=load_blocks(parent,f'strong_games__{stat}__control__equal')
            elif family=='conformal':ref=load_blocks(parent,f'distribution__{stat}__fpds__quantile')
            else:ref=S.source_blocks(source,stat,arm)
            results.append(comparison(variant,family,stat,new,ref,interval=family=='conformal'))
            if family=='matched_quantile':
                fp=load_blocks(parent,f'distribution__{stat}__fpds__quantile')
                results.append(comparison(variant+'__provider_effect',family,stat,fp,new))
        except Exception:
            (path/(variant+'.SUMMARY_PRIVATE.log')).write_text(traceback.format_exc(),encoding='utf-8')
    failures=[str(p.relative_to(path)) for p in path.glob('**/*.FAILED.json')]
    summary_failures=[p.name for p in path.glob('*.SUMMARY_PRIVATE.log')]
    for family,count in COUNTS.items():
        rows=sorted([r for r in results if r['family']==family],key=lambda r:r['p']);prev=0.
        for i,r in enumerate(rows):
            prev=max(prev,min(1,r['p']*(count-i)));r['holm_p']=prev
            r['relative_reduction']=-r['delta']/max(r['control_loss'],1e-9)
            r['seasons_agreeing']=sum(x<0 for x in r['seasons'].values())
            complete=len(rows)==count and not any(family in f for f in failures+summary_failures)
            gate=complete and r['games']>=200 and r['relative_reduction']>=.01 and r['corrected_ci95'][1]<0 and prev<.05 and r['seasons_agreeing']>=2
            if family=='conformal':gate=gate and r['diagnostics']['coverage80']>=.78
            r['nomination']=bool(gate);r['decision']='exploratory nominee; prospective confirmation needed' if gate else 'no gate passed'
    integrity=all(Path(p).exists() and S.sha(p)==v for p,v in inputs.items())
    summary={'created_at':now(),'rows':results,'failures':failures,'summary_failures':summary_failures,
             'target_audit':read(path/'TARGET_AUDIT.json'),'trials':read(path/'TRIALS.json'),'inputs_unchanged':integrity,
             'exact_champion_residual':'blocked: stored calibration/config choices selected on later examined seasons; strict earlier-OOF A8 control tested as labelled surrogate',
             'limitations':protocol['limitations']}
    if not integrity:raise ValueError('Source changed; quarantine results')
    write_once(path/'SUMMARY.json',summary)
    publish(path,summary)
    S.status(path,'complete',comparisons=len(results),failures=len(failures)+len(summary_failures),nominations=sum(r['nomination'] for r in results))


def publish(path,summary):
    dest=S.LAB_ROOT/'reports/run_20261021'/('A9_'+path.name);dest.mkdir(parents=True,exist_ok=False)
    write_once(dest/'AGGREGATE_RESULTS.json',summary)
    lines=['# Six follow-up tests — Amendment9','',
           'Previously examined 2022–24 discovery; local shadow only. No new2025/2026 evaluation, promotion or forecast replacement.',
           '', '|Test / target|n / games|Control → new loss|Delta [corrected95% CI]|Decision|','|---|---|---|---|---|']
    for r in summary['rows']:
        lo,hi=r['corrected_ci95'];lines.append(f"|{r['variant']}|{r['n']}/{r['games']}|{r['control_loss']:.5f} → {r['new_loss']:.5f}|{r['delta']:+.5f} [{lo:+.5f},{hi:+.5f}]|{r['decision']}|")
    lines+=['', 'Losses: MAE for yards/margin/total; Poisson deviance for counts; Brier for probabilities; interval score for conformal. Negative delta improves.',
            '', 'Interval calibration preserves medians; width changes do not improve MAE. Shrunk probabilities are new probabilities, not vote agreement.',
            '', summary['exact_champion_residual'], '', 'Target audit: '+json.dumps(summary['target_audit']),
            '', 'Trials: '+json.dumps(summary['trials']), '',f"Failed blocks: {len(summary['failures'])}; summary failures: {len(summary['summary_failures'])}; inputs unchanged: {summary['inputs_unchanged']}.",
            '',summary['limitations']]
    (dest/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('action',choices=['run','resume','status'])
    parser.add_argument('--run');parser.add_argument('--hours',type=float,default=2);args=parser.parse_args()
    if args.run and not args.run.isalnum():raise SystemExit('Invalid run ID')
    if not .2<=args.hours<=3:raise SystemExit('Runtime must be0.2–3hours')
    if args.action=='status':
        for p in sorted(ROOT.glob('*/STATUS.json')):
            d=read(p);print(p.parent.name,d.get('phase'),d.get('step',''))
        return
    from datetime import datetime,timezone
    path=ROOT/(args.run or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    if args.action=='run' and path.exists():raise SystemExit('Existing run immutable')
    if args.action=='resume' and not (path/'RUN.json').exists():raise SystemExit('Exact snapshot required')
    import psutil
    if jobs.active():raise SystemExit('A manual model job is active; wait before this study')
    for pattern in ('ACTIVE.json',):
        lock=S.ROOT/pattern
        if lock.exists():
            info=read(lock)
            if psutil.pid_exists(info['pid']):raise SystemExit('Another improvement job is active')
    for status in ROOT.glob('*/OWNER*.json'):
        owner=read(status)
        if psutil.pid_exists(owner['pid']):
            other=psutil.Process(owner['pid'])
            if abs(other.create_time()-owner['process_created'])<1:raise SystemExit('Another follow-up job is active')
    process=psutil.Process();process.nice(psutil.IDLE_PRIORITY_CLASS if os.name=='nt' else 19)
    cpus=process.cpu_affinity();process.cpu_affinity(cpus[:max(1,len(cpus)-2)])
    from threadpoolctl import threadpool_limits
    try:
        from .fpds_worker import install
        install()
        path.mkdir(parents=True,exist_ok=args.action=='resume')
        write_once(path/('OWNER.json' if not (path/'OWNER.json').exists() else 'OWNER_RESUME_'+str(os.getpid())+'.json'),
                   {'pid':os.getpid(),'process_created':process.create_time()})
        with threadpool_limits(limits=max(1,(os.cpu_count() or 2)-2)):
            run(path,args.hours)
        print('Amendment9',path.name,read(path/'STATUS.json')['phase'],'; private rows retained locally')
    except Exception:
        path.mkdir(parents=True,exist_ok=True)
        (path/'ERROR_PRIVATE.log').write_text(traceback.format_exc(),encoding='utf-8')
        S.status(path,'failed',message='Private diagnostic retained; no promotion')
        raise SystemExit('Failed; private diagnostic saved; no raw rows printed')


if __name__=='__main__':main()
