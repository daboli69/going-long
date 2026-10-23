"""Checkpointed development, frozen one-pass confirmation, prospective forecasts."""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np
import pandas as pd
import joblib
from .config import ROOT,DATA,CACHE,MODELS,REPORTS,ARCHIVES,KEYS,NAMES,now,stamp,digest,read,atomic,once
from . import models as M
from .features import feature_columns


def frame():
    d=pd.read_parquet(CACHE/'features.parquet')
    return d[d.eligible&d.home_win.notna()&d.season.ge(2016)].sort_values(['tipoff','game_id'])


def fingerprint():
    payload={name:digest(ROOT/name) for name in ['docs/PREREGISTRATION.md','nba_lab/config.py','nba_lab/models.py','nba_lab/features.py','nba_lab/engine.py']}
    from importlib.metadata import version
    payload['runtime']={name:version(name) for name in ['numpy','pandas','scikit-learn','xgboost']}
    payload['data']=digest(CACHE/'features.parquet')
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def checkpoint(season,d,columns,history,threads=1,log=print):
    directory=REPORTS/'research'/f'fold_{season}';directory.mkdir(parents=True,exist_ok=True)
    path=directory/'predictions.parquet';meta=directory/'META.json';key=fingerprint()
    if meta.exists():
        if read(meta)['fingerprint']!=key:raise ValueError('Completed fold source/config changed; new preregistration required, no overwrite')
        return pd.read_parquet(path)
    train=d[d.season.le(season-2)];cal=d[d.season.eq(season-1)];test=d[d.season.eq(season)]
    if test.empty:raise ValueError(f'No eligible target games for {season}')
    bundle=M.fit(train,cal,columns,threads,log)
    p=M.probabilities(bundle,test)
    hp=np.concatenate([h[list(KEYS)].to_numpy() for h in history]) if history else None
    hy=np.concatenate([h.home_win.to_numpy(int) for h in history]) if history else None
    combined,w,stack=M.combine(p,hp,hy)
    out=test[['game_id','season','tipoff','home','away','home_win','elo_probability']].copy()
    for j,key_model in enumerate(KEYS):out[key_model]=p[:,j]
    for method,prob in combined.items():out[method]=prob
    out['home_frequency']=float(train.home_win.mean())
    out.to_parquet(path,index=False)
    once(meta,{'fingerprint':key,'target_season':season,'train_n':len(train),'calibration_n':len(cal),'test_n':len(test),
               'base_fit_attempts':6,'warnings':bundle['warnings'],'weights':w.tolist(),
               'stacking_fallback':not history,'training_cutoff':bundle['trained_through'],
               'calibration_cutoff':bundle['calibrated_through'],'created_at':now()})
    return out


def metric_table(d,corrected=False):
    result=[]
    for name in (*KEYS,'equal','weighted','stacked','elo_probability','home_frequency'):
        row={'method':name,**M.scores(d.home_win,d[name])}
        if name not in ('elo_probability','home_frequency'):
            row.update(M.paired_ci(d.home_win.to_numpy(),d[name].to_numpy(),d.elo_probability.to_numpy(),alpha=.05/9 if corrected else .05))
            row['relative_loss_reduction']=1-row['log_loss']/M.scores(d.home_win,d.elo_probability)['log_loss']
            row['seasons_improving']=sum(M.scores(z.home_win,z[name])['log_loss']<M.scores(z.home_win,z.elo_probability)['log_loss'] for _,z in d.groupby('season'))
        result.append(row)
    return result


def develop(threads=1,log=print):
    frozen=ROOT/'docs/FROZEN_CONFIG.json'
    if frozen.exists():return read(frozen)
    d=frame();columns=feature_columns(d);history=[]
    for season in (2023,2024,2025):
        log(f'Development fold {season}: earlier training and calibration only')
        history.append(checkpoint(season,d,columns,history,threads,log))
    dev=pd.concat(history[1:],ignore_index=True)
    table=metric_table(dev,corrected=True)
    candidates=[r for r in table if r['method'] in ('equal','weighted','stacked')]
    selected=min(candidates,key=lambda r:(r['log_loss'],r['method']))
    hp=pd.concat(history,ignore_index=True)
    _,weights,stack=M.combine(hp[list(KEYS)].to_numpy(),hp[list(KEYS)].to_numpy(),hp.home_win.to_numpy(int))
    MODELS.mkdir(parents=True,exist_ok=True);joblib.dump({'weights':weights,'stacker':stack},MODELS/'FROZEN_ENSEMBLE.joblib')
    config={'created_at':now(),'selected_method':selected['method'],'fingerprint':fingerprint(),'columns':columns,
            'ensemble_hash':digest(MODELS/'FROZEN_ENSEMBLE.joblib'),
            'model_keys':list(KEYS),'fixed_model_configurations':6,'base_fit_attempts':18,'calibrator_fits':18,
            'discovery_seasons':[2024,2025],'confirmation_season':2026,'discovery_metrics':table,
            'discovery_gate_passed':bool(selected['relative_loss_reduction']>=.01 and selected['ci_high']<0 and selected['seasons_improving']==2),
            'status':'Frozen shadow; commit this file before one-pass confirmation. No promotion.'}
    once(frozen,config)
    atomic(REPORTS/'DISCOVERY.json',config)
    log('Development complete. Commit docs/FROZEN_CONFIG.json BEFORE running confirm.')
    return config


def confirm(threads=1,log=print):
    result=REPORTS/'CONFIRMATION.json'
    if result.exists():return read(result)
    config=read(ROOT/'docs/FROZEN_CONFIG.json')
    if config['fingerprint']!=fingerprint():raise ValueError('Frozen configuration/data mismatch; confirmation refused')
    if config['ensemble_hash']!=digest(MODELS/'FROZEN_ENSEMBLE.joblib'):raise ValueError('Frozen ensemble artifact changed')
    # Require reviewable frozen selection in Git before examining the later season.
    subprocess.run(['git','ls-files','--error-unmatch','docs/FROZEN_CONFIG.json'],cwd=ROOT,check=True,capture_output=True)
    dirty=subprocess.check_output(['git','status','--porcelain','--','docs/FROZEN_CONFIG.json'],cwd=ROOT,text=True)
    if dirty.strip():raise ValueError('Commit the frozen selection before confirmation')
    history=[pd.read_parquet(REPORTS/'research'/f'fold_{season}'/'predictions.parquet') for season in (2023,2024,2025)]
    test=checkpoint(2026,frame(),config['columns'],history,threads,log)
    table=metric_table(test)
    chosen=next(r for r in table if r['method']==config['selected_method'])
    verdict='Shadow qualified; not promoted' if config['discovery_gate_passed'] and chosen['relative_loss_reduction']>0 and chosen['ci_high']<0 else 'Exploratory; did not pass all preregistered gates'
    out={'created_at':now(),'selected_method':config['selected_method'],'season':2026,'metrics':table,
         'decision':verdict,'fixed_configurations':6,'total_base_fit_attempts':24,
         'warning':'Reconstructed revised history; no historical injury snapshots, no market comparison or betting-return claim.'}
    once(result,out);write_report(config,out);return out


def write_report(config,result):
    lines=['# NBA winner ensemble — initial local research','',result['decision'],'',
           'NBA seasons are labelled by ending year. Discovery2024–25; one-pass confirmation2026. Six fixed configurations;24base fits. No NFL models/data were used.','',
           '| Method | n | Log loss | Brier | Accuracy | Log-loss delta vs Elo [95% CI] |',
           '|---|---:|---:|---:|---:|---|']
    for r in result['metrics']:
        delta=f"{r['delta']:+.4f} [{r['ci_low']:+.4f}, {r['ci_high']:+.4f}]" if 'delta' in r else 'benchmark'
        lines.append(f"| {r['method']} | {r['n']} | {r['log_loss']:.4f} | {r['brier']:.4f} | {r['accuracy']:.1%} | {delta} |")
    lines+=['','Negative delta is better. Only the discovery-selected ensemble is tested for confirmation qualification; other rows are descriptive.',
            '',result['warning'],'','Next: prospective injury archives and lineup-impact validation; then separate margin/total and player-stat targets. No model promoted.']
    path=REPORTS/'INITIAL_RESEARCH.md'
    with path.open('x',encoding='utf-8') as stream:stream.write('\n'.join(lines))


def train(threads=1,log=print):
    config=read(ROOT/'docs/FROZEN_CONFIG.json')
    d=frame();boundary=d.iloc[-300].tipoff
    cal=d[d.tipoff.ge(boundary)];base=d[(d.tipoff+pd.Timedelta(hours=24)).lt(boundary)]
    bundle=M.fit(base,cal,config['columns'],threads,log)
    combined=joblib.load(MODELS/'FROZEN_ENSEMBLE.joblib')
    bundle.update(combined);bundle['selected_method']=config['selected_method'];bundle['created_at']=now()
    bundle['config_hash']=digest(ROOT/'docs/FROZEN_CONFIG.json');bundle['data_hash']=digest(CACHE/'features.parquet')
    bundle['version']=stamp();directory=MODELS/bundle['version'];directory.mkdir(parents=True,exist_ok=False)
    joblib.dump(bundle,directory/'bundle.joblib')
    once(directory/'META.json',{k:bundle[k] for k in ['created_at','version','selected_method','trained_through','calibrated_through','training_outcomes_available_through','calibration_outcomes_available_through','train_n','calibration_n','config_hash','data_hash','warnings']})
    atomic(MODELS/'CURRENT.json',{'version':bundle['version'],'path':str(directory/'bundle.joblib')})
    return bundle


def load():return joblib.load(read(MODELS/'CURRENT.json')['path'])


def combine_bundle(bundle,p):
    return {'equal':p.mean(axis=1),'weighted':p@bundle['weights'],
            'stacked':bundle['stacker'].predict_proba(M.logits(p))[:,1] if bundle['stacker'] is not None else p.mean(axis=1)}


def predict(date=None,save=True):
    bundle=load();d=pd.read_parquet(CACHE/'features.parquet');time=pd.Timestamp.now(tz='UTC')
    date=date or time.tz_convert('America/New_York').date()
    local=pd.to_datetime(d.tipoff,utc=True).dt.tz_convert('America/New_York').dt.date
    future=d[local.eq(pd.Timestamp(date).date())&pd.to_datetime(d.tipoff,utc=True).gt(time)&~d.completed].copy()
    if future.empty:return pd.DataFrame(),None
    if not future.eligible.all():raise ValueError('Some future teams have insufficient history; no silent partial slate')
    p=M.probabilities(bundle,future);combined=combine_bundle(bundle,p)
    out=future[['game_id','tipoff','home','away','home_history','away_history','home_box_history','away_box_history','latest_input_available_at']].copy()
    for j,key in enumerate(KEYS):out[key]=p[:,j]
    for key,value in combined.items():out[key]=value
    out['p_home']=out[bundle['selected_method']];out['p_away']=1-out.p_home
    out['home_votes']=(p>.5).sum(axis=1);out['away_votes']=(p<.5).sum(axis=1)
    out['vote']=np.where(out.home_votes.eq(out.away_votes),'tie',np.where(out.home_votes>out.away_votes,out.home,out.away))
    out['winner']=np.where(np.isclose(out.p_home,.5,atol=1e-8),'coin flip',np.where(out.p_home>.5,out.home,out.away))
    out['member_min']=p.min(axis=1);out['member_max']=p.max(axis=1)
    out['created_at']=now();out['trained_through']=bundle['trained_through'];out['calibrated_through']=bundle['calibrated_through']
    out['training_outcomes_available_through']=bundle['training_outcomes_available_through']
    out['calibration_outcomes_available_through']=bundle['calibration_outcomes_available_through']
    out['model_version']=bundle['version'];out['config_hash']=bundle['config_hash']
    out['warning']='Shadow/unvalidated lineup effects; no current injury adjustment; no market prices used.'
    if not save:return out,None
    if pd.to_datetime(out.tipoff,utc=True).le(pd.Timestamp.now(tz='UTC')).any():raise ValueError('A game started during prediction; save refused')
    directory=ARCHIVES/'forecasts'/(str(date)+'_'+stamp());directory.mkdir(parents=True,exist_ok=False)
    out.to_csv(directory/'predictions.csv',index=False,mode='x');out.to_parquet(directory/'predictions.parquet',index=False)
    future.to_parquet(directory/'INPUTS.parquet',index=False)
    meta={'created_at':now(),'date':str(date),'path':str(directory),'n':len(out),'model_version':bundle['version'],
          'trained_through':bundle['trained_through'],'calibrated_through':bundle['calibrated_through'],
          'training_outcomes_available_through':bundle['training_outcomes_available_through'],
          'calibration_outcomes_available_through':bundle['calibration_outcomes_available_through'],
          'config_hash':bundle['config_hash'],'source_manifest_hash':digest(DATA/'SOURCES.json'),'status':'shadow only'}
    once(directory/'META.json',meta);atomic(ARCHIVES/'LATEST.json',meta)
    return out,meta


def sensitivities(bundle,row):
    """Actual model response to replacing one input with its training median; not causal."""
    cols=bundle['columns'];baseline=M.probabilities(bundle,row)[0]
    records=[]
    for j,col in enumerate(cols):
        modified=row.copy();modified[col]=bundle['medians'][j]
        changed=M.probabilities(bundle,modified)[0]
        records.append({'feature':col,'value':float(row[col].iloc[0]),'training_median':bundle['medians'][j],
                        **{key:float(baseline[k]-changed[k]) for k,key in enumerate(KEYS)}})
    return pd.DataFrame(records)
