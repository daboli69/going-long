"""Manual orchestration. No source rows/logs are printed or uploaded."""
from pathlib import Path
import json
import subprocess
import sys
import traceback
import numpy as np
import pandas as pd
from . import jobs
from . import engine as E
from ..fpds_research.common import read,write_once,atomic,digest,now
from ..fpds_research import models as M


def remaining(deadline):return (deadline-pd.Timestamp.now(tz='UTC')).total_seconds()


def score_diagnostics(frame,stat):
    from ..fpds_research.report import diagnostics
    result=diagnostics(frame,stat)
    if M.binary(stat):
        p=frame.pred.to_numpy(float);y=frame.actual.to_numpy(float)
        bins=np.minimum((np.clip(p,0,1)*10).astype(int),9)
        result['reliability']=[{'low':i/10,'n':int((bins==i).sum()),'predicted':float(p[bins==i].mean()),'observed':float(y[bins==i].mean())} for i in range(10) if (bins==i).any()]
    return result


def admitted(path,deadline):
    return remaining(deadline)>=180 and not (path/'STOP_REQUESTED.json').exists()


def prepare(path,config,deadline):
    if (path/'INPUT.json').exists():return read(path/'INPUT.json')
    from ..fpds_worker import install
    install()
    from ..data_pipeline import FEATURE_STORE
    from ..fpds_weekly_guard import next_week
    from ..fpds_research.features import latest_features,run as fpfeatures
    from ..fpds_research.ingest import run as ingest
    from ..fpds_research.audit import run as audit
    from .features import build
    week=config['week']
    if config['refresh']:
        for name,args,budget in [('fetch',['git','fetch','origin','main'],120),
             ('quotes',[sys.executable,'-m','lab.phase10_archive','--remote-main'],300),
             ('nfl',[sys.executable,'-m','lab.cli','refresh'],1200)]:
            if remaining(deadline)<budget+180:raise TimeoutError('Insufficient runtime for data refresh; retry with a longer budget')
            jobs.state(path,'preparing',step=name)
            with (path/(name+'_'+pd.Timestamp.now(tz='UTC').strftime('%Y%m%dT%H%M%S%f')+'.PRIVATE.log')).open('x',encoding='utf-8') as log:
                subprocess.run(args,cwd=jobs.LAB_ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=budget,check=True)
    g=pd.read_parquet(FEATURE_STORE);g['kickoff_utc']=pd.to_datetime(g.kickoff_utc,utc=True)
    week=week or next_week(g,pd.Timestamp.now(tz='UTC'))
    if config['refresh']:
        from ..props.ensemble.production import completed_cutoff
        from ..props.weekly10 import outputs
        from ..props.ensemble.data import prepare as nfl_prepare
        manifest=ingest();audit(manifest)
        jobs.state(path,'preparing',step='as-of features')
        base=path/'base';base.mkdir(exist_ok=True)
        cutoff=completed_cutoff(g)
        with outputs(base):nfl_prepare(prospective_week=week,production=True,completed_week=cutoff['training_last_completed_week'],log=lambda _:None)
        original=fpfeatures(base=base/'features_production.parquet')
    else:
        original=latest_features()
        from ..fpds_sources import select_sources
        from ..fpds_research.ingest import sha
        manifest=read(Path(original['import_manifest_path'])/'MANIFEST.json')
        actual=sorted((str(p),sha(p)) for p in select_sources())
        recorded=sorted((x['source_path'],x['sha256']) for x in manifest['files'])
        if actual!=recorded:raise ValueError('Prepared cache does not match authoritative source selection; enable refresh')
    meta=build(original,path/'features'/pd.Timestamp.now(tz='UTC').strftime('%Y%m%dT%H%M%S%fZ'))
    meta['requested_week']=week
    write_once(path/'INPUT.json',meta)
    return meta


def load(meta):
    from ..fpds_research.common import sha
    if any(sha(Path(meta['path'])/name)!=value for name,value in meta['files'].items()):raise ValueError('Prepared feature files changed; exact data resume refused')
    frames=[pd.read_parquet(Path(meta['path'])/name) for name in ('players.parquet','games.parquet')]
    for d in frames:d['kickoff_utc']=pd.to_datetime(d.kickoff_utc,utc=True)
    return frames


def save_block(path,stat,arm,season,week,out,bank,games):
    folder=path/'blocks'/stat/arm;folder.mkdir(parents=True,exist_ok=True)
    name=f'{season}_w{week:02d}'
    out['arm']=arm;out['available_at']=[E.availability(games).get((s,w),pd.NaT) for s,w in zip(out.season,out.week)]
    with (folder/(name+'.npy.pending')).open('wb') as f:np.save(f,bank,allow_pickle=False)
    (folder/(name+'.npy.pending')).replace(folder/(name+'.npy'))
    out.to_parquet(folder/(name+'.parquet.pending'),index=False)
    (folder/(name+'.parquet.pending')).replace(folder/(name+'.parquet'))


def trials(path,stat,arm,method):
    dest=path/'TRIALS.json';records=read(dest) if dest.exists() else {'configurations':[],'fit_calls':0}
    records['configurations']=sorted(set(records['configurations'])|{f'{stat}/{arm}/{method}'})
    records['fit_calls']+=int(method!='equal_average')
    if len(records['configurations'])>104:raise ValueError('Preregistered configuration budget exceeded')
    atomic(dest,records)


def compare(path,config,meta,deadline):
    players,games=load(meta);protocol=read(jobs.PROTOCOL)
    # Never score a new2025 confirmation or select on2026.
    if config['scope']!='games':players=players[players.season.le(2024)]
    games=games[games.season.le(2024)]
    failures=[str(p.relative_to(path)) for p in path.glob('blocks/**/*.FAILED.json')];blocks=0
    for stat in E.targets(config['scope']):
        data=E.data_for(stat,players,games)
        data=data[data[stat].notna()]
        for season in protocol['discovery_seasons']:
            for week in protocol['refit_weeks']:
                target=data[data.season.eq(season)&data.week.between(week,min(week+3,18))]
                if target.empty:continue
                decision=target.kickoff_utc.min()
                train=E.training_rows(data,games,decision,season,week,stat)
                if len(train)<100:raise ValueError('Insufficient earlier training rows for fixed discovery split')
                for arm in ('control','fpds'):
                    output=path/'blocks'/stat/arm/f'{season}_w{week:02d}.parquet'
                    failed=output.with_suffix('.FAILED.json')
                    if output.exists() or failed.exists():continue
                    if not admitted(path,deadline) or remaining(deadline)<600:
                        jobs.state(path,'checkpoint',blocks=blocks,message='Exact resume available; no split or configuration change')
                        return
                    jobs.state(path,'running',step=f'{stat} / {arm} / {season} w{week}',blocks=blocks)
                    try:
                        prior=E.history(path,stat,arm,decision)
                        out,bank=E.fit_matched(train,target,stat,E.columns(meta,stat,arm),prior,max(1,(__import__('os').cpu_count() or 2)-2),
                                                before_fit=lambda method:trials(path,stat,arm,method))
                        save_block(path,stat,arm,season,week,out,bank,games);blocks+=1
                    except Exception:
                        failures.append(str(output.relative_to(path)))
                        with output.with_suffix('.PRIVATE.log').open('w',encoding='utf-8') as log:traceback.print_exc(file=log)
                        write_once(failed,{'created_at':now(),'status':'failed; logged/skipped, no automatic model retry'})
    if not admitted(path,deadline) or remaining(deadline)<300:jobs.state(path,'checkpoint',message='Resume for saved-output aggregation');return
    rows=[]
    for stat in E.targets(config['scope']):
        arms=[]
        for arm in ('control','fpds'):
            files=list((path/'blocks'/stat/arm).glob('*.parquet'))
            arms.append(pd.concat([pd.read_parquet(p) for p in files],ignore_index=True) if files else pd.DataFrame())
        a,b=arms
        if a.empty or b.empty:continue
        keys=['game_id']+(['pid'] if 'pid' in a else [])
        joined=a.merge(b,on=keys,suffixes=('_control','_fpds'),validate='one_to_one')
        for method in E.members(stat)+('equal_average',):
            col='pred' if method=='equal_average' else 'member_'+method
            control=M.loss(stat,joined.actual_control,joined[col+'_control']);new=M.loss(stat,joined.actual_fpds,joined[col+'_fpds'])
            effect=E.paired(new-control,joined.game_id,21 if stat in E.GAME_STATS else 30)
            byseason={str(s):float(np.mean((new-control)[joined.season_control.eq(s)])) for s in sorted(joined.season_control.unique())}
            diag=b.copy();diag['pred']=diag[col]
            control_diag=a.copy();control_diag['pred']=control_diag[col]
            if method!='equal_average':
                diag=diag.drop(columns=['q10','q50','q90','crps'],errors='ignore')
                control_diag=control_diag.drop(columns=['q10','q50','q90','crps'],errors='ignore')
            expected=E.data_for(stat,players,games)
            expected=expected[expected.season.isin(protocol['discovery_seasons'])&expected[stat].notna()]
            row={'stat':stat,'method':method,'control_loss':float(control.mean()),'fpds_loss':float(new.mean()),**effect,
                 'seasons':byseason,'seasons_agreeing':sum(v<0 for v in byseason.values()),'identical_sample':len(joined)==len(a)==len(b)==len(expected),
                 'diagnostics_control':score_diagnostics(control_diag,stat),'diagnostics_fpds':score_diagnostics(diag,stat),'primary_metric':'Brier' if M.binary(stat) else 'Poisson deviance' if stat in ('rec','pass_tds') else 'MAE'}
            if method=='equal_average' and not M.binary(stat):
                row['secondary_paired']={}
                for quantile,key in ((.1,'q10'),(.5,'q50'),(.9,'q90')):
                    x=joined.actual_control-joined[key+'_control'];y=joined.actual_fpds-joined[key+'_fpds']
                    delta=np.maximum(quantile*y,(quantile-1)*y)-np.maximum(quantile*x,(quantile-1)*x)
                    row['secondary_paired']['pinball_'+str(quantile)]=E.paired(delta,joined.game_id,21 if stat in E.GAME_STATS else 30)
            if stat in E.GAME_STATS:
                benchmark='market_p_home_novig' if stat=='win' else 'spread_line' if stat=='margin' else 'total_line'
                z=b.merge(games[['game_id',benchmark]],on='game_id',validate='one_to_one').dropna(subset=[benchmark])
                if len(z):row['closing_benchmark']=E.paired(M.loss(stat,z.actual,z[col])-M.loss(stat,z.actual,z[benchmark]),z.game_id,21)
            rows.append(row)
    for family in ('games','props'):
        group=sorted([r for r in rows if (r['stat'] in E.GAME_STATS)==(family=='games')],key=lambda x:x['p'])
        count=21 if family=='games' else 30;running=0.
        for i,r in enumerate(group):running=max(running,min(1.,r['p']*(count-i)));r['holm_p']=running
    for r in rows:
        r['relative_reduction']=-r['delta']/max(r['control_loss'],1e-12)
        r['discovery_nomination']=bool(not failures and r['identical_sample'] and r['games']>=200 and r['relative_reduction']>=.01 and r['corrected_ci95'][1]<0 and r['seasons_agreeing']>=2 and r['holm_p']<.05)
        r['decision']='exploratory discovery only; prospective confirmation required; no promotion'
    first_scores=[]
    if config['scope']!='games':
        from ..fpds_research.first_td import labels
        actual=labels(range(2021,2025)).set_index('game_id').scorer
        for season in protocol['discovery_seasons']:
            for week in protocol['refit_weeks']:
                files=[path/'blocks'/'anytime_td'/arm/f'{season}_w{week:02d}.parquet' for arm in ('control','fpds')]
                if not all(f.exists() for f in files):continue
                atd=pd.concat([pd.read_parquet(f) for f in files],ignore_index=True)
                decision=pd.to_datetime(atd.kickoff_utc,utc=True).min()
                scored=first_td(atd,players,games,decision,config['seed'],100)
                for (game,arm),z in scored.groupby(['game_id','arm']):
                    label=actual.get(game,'NO_OFFENSIVE_TD')
                    if label not in set(z.pid):label='OTHER_PLAYERS'
                    truth=z.pid.eq(label).to_numpy(float);prob=z['mean'].to_numpy(float)
                    first_scores.append({'game_id':game,'arm':arm,'loss':float(-np.log(max(float(prob[truth.astype(bool)][0]),1e-12))),
                                         'brier':float(np.sum((prob-truth)**2))})
    derived=[]
    if first_scores:
        fs=pd.DataFrame(first_scores);j=fs[fs.arm.eq('control')].merge(fs[fs.arm.eq('fpds')],on='game_id',suffixes=('_control','_fpds'),validate='one_to_one')
        for key in ('loss','brier'):derived.append({'metric':'multiclass log loss' if key=='loss' else 'multiclass Brier',**E.paired(j[key+'_fpds']-j[key+'_control'],j.game_id,2),'decision':'secondary only; no selection or promotion'})
        fs.to_parquet(path/'first_td_scores.parquet',index=False)
        trial=read(path/'TRIALS.json');trial['configurations']=sorted(set(trial['configurations'])|{'first_td/control/hazard','first_td/fpds/hazard'});atomic(path/'TRIALS.json',trial)
    summary={'created_at':now(),'action':'compare','split':'2022–24 development, already examined; no2025 pass/no2026 selection','rows':rows,'failures':failures,
             'first_td_secondary':derived,'trials':read(path/'TRIALS.json'),'signature':config['signature'],'source_policy':'full-history-authority-v1','history_windows':meta['history_windows']}
    write_once(path/'SUMMARY.json',summary);jobs.state(path,'complete',blocks=blocks,message='Matched development comparison saved; no promotion')


def first_td(players,frame,games,decision,seed,sims):
    from ..fpds_research.first_td import labels,probabilities
    from ..props.ensemble.features import eligible
    actual=labels(range(2021,int(games.season.max())+1));clock=E.availability(games)
    prior=games[games.completed & games.kickoff_utc.lt(decision)].merge(actual,on='game_id')
    prior=prior[[clock.get((r.season,r.week),pd.Timestamp.max.tz_localize('UTC'))<decision for r in prior.itertuples()]]
    scope=set(map(tuple,frame[eligible(frame,'anytime_td')][['game_id','pid']].to_numpy()))
    td=prior[prior.scorer.ne('NO_OFFENSIVE_TD')];no_td=(len(prior)-len(td)+1)/(len(prior)+2)
    other=(sum((r.game_id,r.scorer) not in scope for r in td.itertuples())+1)/(len(td)+2)
    result=[]
    for (game,arm),z in players[players.stat.eq('anytime_td')].groupby(['game_id','arm']):
        ids,p=probabilities(z.pid,z['mean'],no_td,other)
        rng=np.random.default_rng(seed);counts=np.bincount(rng.choice(len(ids),sims,p=p),minlength=len(ids))/sims
        for i,(pid,value) in enumerate(zip(ids,p)):
            row=z.iloc[0].to_dict() if pid in ('OTHER_PLAYERS','NO_OFFENSIVE_TD') else z[z.pid.eq(pid)].iloc[0].to_dict()
            row.update(stat='first_td',pid=pid,mean=float(value),median=float(value),q10=np.nan,q50=np.nan,q90=np.nan,
                       simulated_probability=float(counts[i]),simulated_mean=float(counts[i]),monte_carlo_mean_se=float(np.sqrt(value*(1-value)/sims)),
                       interval_method='not applicable: categorical scorer probability',simulation_type='categorical offensive first scorer; not play-by-play',
                       member_min=np.nan,member_max=np.nan,first_td_definition='first regulation offensive rushing/receiving scorer; passing/defensive/ST excluded')
            for key in list(row):
                if key.startswith('member_'):row[key]=np.nan
            if pid in ('OTHER_PLAYERS','NO_OFFENSIVE_TD'):row.update(name=pid,team='GAME')
            result.append(row)
    return pd.DataFrame(result)


def project(path,config,meta,deadline):
    from ..props.ensemble.production import completed_cutoff
    from ..fpds_weekly_guard import check
    from ..fpds_research.weekly import quote_comparison,game_comparison
    from ..fpds_sheets import correct_comparisons
    players,games=load(meta);decision=pd.Timestamp.now(tz='UTC');week=meta['requested_week']
    check(games,week,decision);cutoff=completed_cutoff(games,decision)
    # A fully completed week must also clear the source-week+24h clock.
    clock=E.availability(games);available=cutoff['training_last_completed_week']
    while available and clock.get((2026,available),pd.Timestamp.max.tz_localize('UTC'))>=decision:available-=1
    if not available:raise ValueError('No available completed2026 source week')
    cutoff['schedule_last_completed_week']=cutoff['training_last_completed_week']
    cutoff['training_last_completed_week']=available
    cutoff['training_cutoff_date']=str(games.loc[games.season.eq(2026)&games.week.le(available),'gameday'].max())
    if pd.Timestamp(meta['source_observed_at'])>=decision:raise ValueError('Source observation must precede forecast creation')
    targetgames=games[games.season.eq(2026)&games.week.eq(week)&~games.completed&games.kickoff_utc.gt(decision)]
    player_targets=(players[players.game_id.isin(targetgames.game_id)].merge(targetgames[['game_id','home_team','away_team']],on='game_id',suffixes=('','_schedule'))
                    if config['scope']!='games' else pd.DataFrame())
    for c in ('home_team','away_team'):
        if c+'_schedule' in player_targets:player_targets[c]=player_targets[c+'_schedule']
    if config['scope']!='games' and player_targets.empty:raise ValueError('No prepared player rows for this future week; enable refresh')
    rows=[];banks={};trained=[]
    for stat in E.targets(config['scope']):
        data=E.data_for(stat,players,games)
        target=targetgames if stat in E.GAME_STATS else E.data_for(stat,player_targets,targetgames)
        if target.empty:continue
        train=E.training_rows(data,games,decision,2026,cutoff['training_last_completed_week']+1,stat)
        if len(train)<100:raise ValueError('Insufficient earlier production history')
        for arm in ('control','fpds'):
            file=path/'blocks'/stat/arm/f'2026_w{week:02d}.parquet'
            if not admitted(path,deadline):jobs.state(path,'checkpoint',message='Projection checkpoint; exact resume available');return
            if file.exists():out=pd.read_parquet(file);bank=np.load(file.with_suffix('.npy'),allow_pickle=False)
            else:
                if remaining(deadline)<600:jobs.state(path,'checkpoint',message='Insufficient budget for next model block; exact resume available');return
                jobs.state(path,'running',step=f'production {stat} / {arm}')
                prior=pd.DataFrame()
                for candidate in jobs.list_jobs():
                    if candidate['action']!='compare' or candidate['phase']!='complete':continue
                    source=jobs.directory(candidate['job'])
                    oldconfig=read(source/'JOB.json');oldmeta=read(source/'INPUT.json')
                    if oldconfig['signature']==config['signature'] and oldmeta.get('discovery_fingerprint')==meta['discovery_fingerprint']:
                        prior=E.history(source,stat,arm,decision)
                        if len(prior):break
                out,bank=E.fit_matched(train,target,stat,E.columns(meta,stat,arm),prior,max(1,(__import__('os').cpu_count() or 2)-2),
                                        before_fit=lambda method:trials(path,stat,arm,method))
                save_block(path,stat,arm,2026,week,out,bank,games)
            if not admitted(path,deadline):jobs.state(path,'checkpoint',message='Model block saved; resume for simulation/archive');return
            out=out[out.game_id.isin(targetgames.game_id)].copy()
            out=E.simulate(out,bank,config['sims'],config['seed']);out['arm']=arm
            out['created_at']=decision.isoformat();out['source_observed_at']=meta['source_observed_at'];out['config_hash']=config['signature']
            for k,v in cutoff.items():out[k]=v
            out['horizon_weeks']=week-cutoff['training_last_completed_week'];out['data_hash']=meta['fingerprint']
            banks[(arm,stat)]=bank;rows.append(out);trained.append({'stat':stat,'arm':arm,'rows':len(train),'seasons':sorted(int(s) for s in train.season.unique())})
    combined=pd.concat(rows,ignore_index=True)
    if config['scope']!='games':
        extra=first_td(combined,players,games,decision,config['seed'],config['sims'])
        combined=pd.concat([combined,extra],ignore_index=True)
    for col,value in [('confidence_tier','C'),('coherence_flag','not reconciled'),('stability_flag','single seed; not tested'),('scenario_sensitivity','not tested')]:combined[col]=value
    player=combined[~combined.stat.isin(E.GAME_STATS)].copy();game=combined[combined.stat.isin(E.GAME_STATS)].copy()
    if len(player):player=quote_comparison(player,decision)
    if len(game):game=game_comparison(game,targetgames,decision)
    combined=pd.concat([player,game],ignore_index=True)
    if 'line_type' not in combined:combined['line_type']=pd.Series(index=combined.index,dtype='object')
    missing=combined.line_type.isna()
    combined.loc[missing,'line_type']=np.where(combined.loc[missing,'consensus_line'].notna(),'consensus','unavailable')
    combined=correct_comparisons(combined,banks)
    warm=combined.interval_method.str.contains('warm-up',na=False)&combined.stat.isin(['pass_yds','rec_yds','rush_yds','margin','total'])&combined.consensus_line.notna()
    combined.loc[warm,'probability_method']='training-residual empirical CDF; unvalidated warm-up'
    created=pd.Timestamp.now(tz='UTC')
    if not pd.to_datetime(combined.kickoff_utc,utc=True).gt(created).all():raise ValueError('A kickoff occurred before archive completion; no backdated archive emitted')
    output=path/'forecasts'/created.strftime('%Y%m%dT%H%M%S%fZ');output.mkdir(parents=True,exist_ok=False)
    combined['decision_started_at']=combined.created_at;combined['created_at']=created.isoformat()
    combined['early_projection_note']='Uses information available at creation; future lineup/weather/results unknown. Matched six-game/four-prop-member shadow ensembles, not production champion.'
    combined.drop(columns=['actual','loss'],errors='ignore').to_csv(output/'projections.csv',index=False)
    leans=combined[combined.arm.eq('fpds')].copy()
    leans['investigation_score']=leans.gap.abs()/(leans.q90-leans.q10).clip(lower=1)
    leans.loc[leans.skew_artifact_flag | ~leans.line_status.eq('current'),'investigation_score']=np.nan
    leans['rank_in_game']=leans.groupby('game_id').investigation_score.rank(method='first',ascending=False,na_option='bottom')
    leans.drop(columns=['actual','loss'],errors='ignore').to_csv(output/'leans.csv',index=False)
    summary={'created_at':created.isoformat(),'action':'project','week':week,'games':int(targetgames.game_id.nunique()),'rows':len(combined),
             **cutoff,'training':trained,'path':str(output),'signature':config['signature'],'data_hash':meta['fingerprint'],
             'sims':config['sims'],'seed':config['seed'],'status':'manual exploratory shadow; no promotion; not play-by-play; intervals use labelled training-residual warm-up'}
    write_once(output/'FORECAST.json',summary);atomic(path/'SUMMARY.json',summary)
    jobs.state(path,'complete',message='New local manual projection revision saved; earlier archives unchanged')


def worker(job):
    path=jobs.directory(job);config=read(path/'JOB.json')
    admission=read(path/'ADMISSION.json');deadline=pd.Timestamp.now(tz='UTC')+pd.Timedelta(hours=admission['hours'])
    try:
        _,signature=jobs.registered()
        if signature!=config['signature']:raise ValueError('Code/configuration changed; exact worker refused')
        meta=prepare(path,config,deadline)
        if config['action']=='prepare':
            write_once(path/'SUMMARY.json',{'created_at':now(),'action':'prepare','tables':len(meta['groups']),'source_policy':'full-history-authority-v1','path':meta['path']})
            jobs.state(path,'complete',message='Authoritative source and matched feature store prepared')
        elif config['action']=='compare':compare(path,config,meta,deadline)
        else:project(path,config,meta,deadline)
    except Exception:
        with (path/'ERROR_PRIVATE.log').open('a',encoding='utf-8') as log:traceback.print_exc(file=log)
        jobs.state(path,'failed',message='Failed; private error retained. No fallback, promotion or old-archive overwrite.')
        return 1
    finally:
        lock=jobs.ROOT/'ACTIVE.json'
        if lock.exists() and read(lock).get('job')==job:lock.unlink()
    return 0
