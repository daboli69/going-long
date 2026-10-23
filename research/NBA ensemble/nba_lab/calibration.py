"""Bounded, checkpointed discovery-only post-calibration; no operational changes."""
import hashlib
import json
import time
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from .config import ROOT,REPORTS,SEED,now,digest,read,once,atomic
from .models import logits,scores,paired_ci

CANDIDATES=tuple((method,window) for method in ('platt','isotonic') for window in (300,600,1200))


def load_history():
    # Deliberately enumerate only development files: never open the spent confirmation.
    frames=[]
    for season in (2023,2024,2025):
        path=REPORTS/'research'/f'fold_{season}'/'predictions.parquet'
        d=pd.read_parquet(path,columns=['game_id','season','tipoff','home_win','stacked'])
        if not d.season.eq(season).all():raise ValueError('Wrong development season in checkpoint')
        frames.append(d)
    d=pd.concat(frames,ignore_index=True).sort_values(['tipoff','game_id']).reset_index(drop=True)
    d.tipoff=pd.to_datetime(d.tipoff,utc=True)
    if d.game_id.duplicated().any() or not d.home_win.isin([0,1]).all():raise ValueError('Invalid development identities/labels')
    if not np.isfinite(d.stacked).all() or not d.stacked.between(0,1,inclusive='neither').all():raise ValueError('Invalid probabilities')
    return d


def walkforward(d,method,window):
    target=d[d.season.isin([2024,2025])].copy()
    target['month']=target.tipoff.dt.strftime('%Y-%m')
    outputs=[];fits=0
    for month,test in target.groupby('month',sort=True):
        boundary=pd.Timestamp(month+'-01',tz='UTC')
        available=d.tipoff+pd.Timedelta(hours=24)
        history=d[available.lt(boundary)].tail(window)
        if len(history)!=window or history.home_win.nunique()!=2:raise ValueError('Insufficient earlier calibration history')
        if not (history.tipoff+pd.Timedelta(hours=24)).lt(test.tipoff.min()).all():raise AssertionError('Calibration leakage')
        if method=='platt':
            model=LogisticRegression(C=1,max_iter=1000).fit(logits(history.stacked.to_numpy()).reshape(-1,1),history.home_win)
            p=model.predict_proba(logits(test.stacked.to_numpy()).reshape(-1,1))[:,1]
        elif method=='isotonic':
            model=IsotonicRegression(out_of_bounds='clip').fit(history.stacked.to_numpy(),history.home_win.to_numpy())
            p=model.predict(test.stacked.to_numpy())
        else:raise ValueError('Unknown calibration method')
        test=test.copy();test['candidate']=np.clip(p,1e-6,1-1e-6)
        test['calibration_n']=len(history)
        test['calibration_outcomes_available_through']=(history.tipoff.max()+pd.Timedelta(hours=24)).isoformat()
        test['calibrator_fit_at']=boundary.isoformat()
        outputs.append(test.drop(columns='month'));fits+=1
    return pd.concat(outputs,ignore_index=True).sort_values(['tipoff','game_id']),fits


def reliability(y,p):
    bins=np.minimum((np.asarray(p)*10).astype(int),9)
    result=[]
    for j in range(10):
        mask=bins==j
        if mask.any():result.append({'low':j/10,'high':(j+1)/10,'n':int(mask.sum()),
            'forecast':float(np.asarray(p)[mask].mean()),'observed':float(np.asarray(y)[mask].mean())})
    return result


def brier_ci(y,p,control,draws=2000):
    delta=(np.asarray(p)-y)**2-(np.asarray(control)-y)**2
    rng=np.random.default_rng(SEED)
    samples=np.array([delta[rng.integers(0,len(delta),len(delta))].mean() for _ in range(draws)])
    return {'delta':float(delta.mean()),'ci_low':float(np.quantile(samples,.05/12)),
            'ci_high':float(np.quantile(samples,1-.05/12))}


def evaluate(d,fit_count):
    control=scores(d.home_win,d.stacked);candidate=scores(d.home_win,d.candidate)
    ci=paired_ci(d.home_win.to_numpy(),d.candidate.to_numpy(),d.stacked.to_numpy(),draws=2000,alpha=.05/6)
    by_season={str(int(season)):{'control':scores(g.home_win,g.stacked),'candidate':scores(g.home_win,g.candidate)} for season,g in d.groupby('season')}
    improved=sum(r['candidate']['log_loss']<r['control']['log_loss'] for r in by_season.values())
    gain=1-candidate['log_loss']/control['log_loss']
    accepted=bool(gain>=.01 and ci['ci_high']<0 and improved==2 and candidate['brier']<=control['brier'])
    return {'control':control,'candidate':candidate,'log_loss_delta':ci,
            'brier_delta':brier_ci(d.home_win.to_numpy(),d.candidate.to_numpy(),d.stacked.to_numpy()),
            'relative_log_loss_reduction':gain,'seasons_improving':improved,'by_season':by_season,
            'reliability':reliability(d.home_win,d.candidate),'calibrator_fits':fit_count,'accepted_exploratory':accepted}


def fingerprint():
    files=[ROOT/'docs/CALIBRATION_PREREGISTRATION.md',ROOT/'nba_lab/calibration.py',ROOT/'nba_lab/models.py',ROOT/'nba_lab/config.py']
    files += [REPORTS/'research'/f'fold_{s}'/'predictions.parquet' for s in (2023,2024,2025)]
    from importlib.metadata import version
    payload={'files':{str(p):digest(p) for p in files},'runtime':{k:version(k) for k in ('numpy','pandas','scikit-learn')}}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def run(log=print,max_seconds=1200):
    started=time.monotonic();key=fingerprint();directory=REPORTS/'calibration_v1'
    directory.mkdir(parents=True,exist_ok=True)
    lock=directory/'RUN_LOCK.json';manifest=directory/'MANIFEST.json';result=directory/'RESULT.json'
    if manifest.exists() and read(manifest)['fingerprint']!=key:raise ValueError('Calibration inputs/config changed; no overwrite or new search under this protocol')
    if result.exists():return read(result)
    if max_seconds<=0 or max_seconds>1200:raise ValueError('Bounded run requires 0<seconds<=1200')
    # Exclusive lock: a second app/launcher must not duplicate the experiment.
    try:once(lock,{'created_at':now(),'fingerprint':key})
    except FileExistsError:raise ValueError('Calibration is already running or was interrupted; review RUN_LOCK.json before resuming')
    trials=[];failures=[];stopped=False
    try:
        if not manifest.exists():once(manifest,{'created_at':now(),'fingerprint':key,'maximum_candidates':6,'maximum_seconds':1200})
        d=load_history();baseline=d[d.season.isin([2024,2025])]
        for method,window in CANDIDATES:
            name=f'{method}_{window}';checkpoint=directory/(name+'.json')
            if checkpoint.exists():
                cached=read(checkpoint)
                (failures if 'error' in cached else trials).append(cached);continue
            if time.monotonic()-started>max_seconds-30:stopped=True;break
            log('Chronological post-calibration: '+name)
            atomic(directory/'STATUS.json',{'at':now(),'state':'running','candidate':name,'completed':len(trials),'failures':len(failures)})
            try:
                predictions,count=walkforward(d,method,window)
                if predictions.game_id.tolist()!=baseline.game_id.tolist():raise AssertionError('Candidate/control samples differ')
                record={'name':name,'method':method,'window':window,**evaluate(predictions,count)}
                predictions.to_parquet(directory/(name+'.parquet'),index=False)
                once(checkpoint,record);trials.append(record)
            except Exception as error:
                failure={'name':name,'error':type(error).__name__,'message':str(error)[:400]}
                once(checkpoint,failure);failures.append(failure);log(str(failure))
        out={'created_at':now(),'fingerprint':key,'elapsed_seconds':time.monotonic()-started,
             'trial_count':len(trials)+len(failures),'successful_candidates':len(trials),
             'calibrator_fits':sum(t['calibrator_fits'] for t in trials),'trials':trials,'failures':failures,
             'control':scores(baseline.home_win,baseline.stacked),
             'control_reliability':reliability(baseline.home_win,baseline.stacked),
             'stopped_for_budget':stopped,'status':'Exploratory reused discovery only; confirmation/prospective outcomes not read.'}
        accepted=[t for t in trials if t['accepted_exploratory']]
        out['selected_shadow_candidate']=min(accepted,key=lambda t:(t['candidate']['log_loss'],t['name']))['name'] if accepted else None
        out['decision']='Shadow candidate only; requires new prospective validation' if accepted else 'Retain existing forecast method; no candidate passed the fixed gate.'
        write_report(directory/'REPORT.md',out)
        if not stopped:
            once(result,out);atomic(REPORTS/'CALIBRATION_LATEST.json',{'path':str(result),'created_at':now()})
        atomic(directory/'STATUS.json',{'at':now(),'state':'budget paused' if stopped else 'complete','trials':out['trial_count']})
        return out
    finally:lock.unlink(missing_ok=True)


def write_report(path,result):
    control=result['control']
    lines=['# Bounded NBA winner calibration','',result['decision'],'',
           f"Discovery only: n={control['n']}; {result['trial_count']}/6 candidates; {result['calibrator_fits']} monthly calibrator fits; {result['elapsed_seconds']:.1f}s elapsed. No base-model refits, network, confirmation/prospective outcomes or operational forecast changes.",'',
           '| Candidate | Log loss | Brier | Accuracy | LL delta [corrected CI] | Better seasons | Decision |',
           '|---|---:|---:|---:|---|---:|---|',
           f"| Existing stacked control | {control['log_loss']:.5f} | {control['brier']:.5f} | {control['accuracy']:.2%} | reference | — | unchanged |"]
    for t in result['trials']:
        m=t['candidate'];ci=t['log_loss_delta']
        lines.append(f"| {t['name']} | {m['log_loss']:.5f} | {m['brier']:.5f} | {m['accuracy']:.2%} | {ci['delta']:+.5f} [{ci['ci_low']:+.5f},{ci['ci_high']:+.5f}] | {t['seasons_improving']}/2 | {'Exploratory pass' if t['accepted_exploratory'] else 'Rejected for adoption'} |")
    lines+=['','Negative loss delta is better. Paired whole-game bootstrap2000draws; Bonferroni across6candidates, familywise95%. Required >=1%relative LL improvement, corrected CI<0, both seasons improving and Brier no worse.',
            '',result['status'],'Saved2023OOF is calibration history;2024/2025are already-examined discovery. This is not fresh validation. Monthly fitting uses strictly earlier tipoff+24h outcomes.',
            '', 'Stopping: six fixed candidates or20minute cap; no extra search to fill time. Repeating deterministic winner calculations or drawing more simulated wins does not improve the underlying probability. Current injuries/lineups remain unmodeled. Nothing promoted.']
    if result['failures']:lines+=['', 'Failures: '+json.dumps(result['failures'])]
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
