"""Fail-closed one-click local refresh; immutable private shadow revisions only."""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys
import numpy as np
import pandas as pd
from scipy.stats import norm,poisson
from .common import ROOT, LAB_ROOT, STATS, SEED, now, stamp, read, write_once, digest, sha, registered, private_error
from .features import latest_features
from . import models as M


def command(args,directory,label,timeout=1200):
    with (directory/(label+'.log')).open('x',encoding='utf-8') as log:
        result=subprocess.run(args,cwd=LAB_ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
    if result.returncode:raise RuntimeError('Weekly phase failed; private phase log retained')


def quote_comparison(rows,asof):
    """Independent distributions are fixed before market prices are read."""
    from ..props.lines import archived_lines
    from ..props.amendment2.sheets import classify
    quotes=archived_lines(asof=asof)
    d=rows.copy()
    for c in ('consensus_line','p_over','p_under','gap','market_probability_novig','line_age_hours'):d[c]=np.nan
    d['line_status']='unavailable';d['line_type']='unavailable';d['consensus_rule']='modal latest line per traditional book; smallest line breaks ties'
    if quotes.empty:return d
    q=quotes[quotes.pregame_verified & quotes.period.eq('FULL') & quotes.gsis_id.notna()].copy()
    q=q.sort_values('quote_time').drop_duplicates(['event_id','gsis_id','stat','book'],keep='last')
    q['line_type']=[classify(b,bool(f)) for b,f in zip(q.book,q.dfs)]
    for ix,r in d.iterrows():
        if r.stat=='first_td':continue  # Offensive-only model contract is not verified against book settlement.
        if r.stat=='anytime_td':d.loc[ix,['p_over','p_under']]=[r['mean'],1-r['mean']]
        z=q[q.gsis_id.eq(r.pid)&q.stat.eq(r.stat)&q.home.eq(r.home_team)&q.away.eq(r.away_team)&q.line_type.eq('alternate')]
        if len(z) and 'kickoff_utc' in d:
            ko=pd.to_datetime(z.kickoff,utc=True,errors='coerce')
            z=z[(ko-pd.Timestamp(r.kickoff_utc)).abs().le(pd.Timedelta(minutes=15))]
        if z.empty:continue
        lines=pd.to_numeric(z.line,errors='coerce');votes=lines.value_counts()
        if votes.empty:
            if r.stat=='anytime_td':
                ref=z.sort_values(['quote_time','book']).iloc[-1]
                d.loc[ix,['line_type','line_status','line_age_hours']]=['binary quote; no numeric line',ref.line_status,ref.line_age_hours]
                from ..market81 import american_to_prob
                try:
                    a,b=float(american_to_prob(float(ref.over_odds))),float(american_to_prob(float(ref.under_odds)))
                    if np.isfinite(a+b) and a+b>0:d.loc[ix,'market_probability_novig']=a/(a+b)
                except (ValueError,TypeError):pass
            continue
        line=float(min(votes[votes.eq(votes.max())].index));matching=z[lines.eq(line)].sort_values('book')
        ref=matching.iloc[0]
        d.loc[ix,['consensus_line','line_type','line_status','line_age_hours']]=[line,'consensus',ref.line_status,ref.line_age_hours]
        if r.stat=='anytime_td':
            over=r['mean'];under=1-over
        elif r.stat in ('rec','pass_tds'):
            over=float(poisson.sf(np.floor(line),max(r['mean'],1e-6)));under=float(poisson.cdf(np.ceil(line)-1,max(r['mean'],1e-6)))
        else:
            scale=max((r.q90-r.q10)/2.563,1.)
            over=float(norm.sf((line-r['mean'])/scale));under=1-over
        d.loc[ix,['p_over','p_under','gap']]=[over,under,r['mean']-line]
        def implied(price):
            try:
                a=float(price);return -a/(-a+100) if a<0 else 100/(a+100)
            except (ValueError,TypeError):return np.nan
        a,b=implied(ref.over_odds),implied(ref.under_odds)
        if np.isfinite(a+b) and a+b>0:d.loc[ix,'market_probability_novig']=a/(a+b)
    d['skew_artifact_flag']=(d['mean']-d.consensus_line)*(d['median']-d.consensus_line)<0
    return d


def append_results_log(directory,observations,games):
    """Descriptive only; never feeds model/configuration selection."""
    import json
    path=ROOT/'RESULTS_LOG.jsonl';seen=set()
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line:seen.add(read_key(json.loads(line)))
    completed=set(games.loc[games.completed & games.kickoff_utc.lt(pd.Timestamp.now(tz='UTC')),'game_id'])
    actual=pd.read_parquet(observations,columns=['game_id','pid']+list(STATS))
    actual=actual[actual.game_id.isin(completed)].drop_duplicates(['game_id','pid'])
    added=[]
    for forecast in (ROOT/'weekly').glob('2026_w*_r*'):
        if not (forecast/'FORECAST.json').exists():continue
        p=pd.read_csv(forecast/'projections.csv')
        for (game_id,stat,arm),z in p[p.stat.isin(STATS)&p.game_id.isin(completed)].groupby(['game_id','stat','arm']):
            key=(forecast.name,game_id,stat,arm)
            if key in seen:continue
            joined=z.merge(actual[['game_id','pid',stat]],on=['game_id','pid'],validate='one_to_one').dropna(subset=[stat])
            if joined.empty:continue
            kickoff=games.loc[games.game_id.eq(game_id),'kickoff_utc'].iloc[0]
            created=pd.to_datetime(joined.created_at,utc=True)
            if not created.lt(kickoff).all():continue
            value={'created_at':now(),'revision':forecast.name,'game_id':game_id,'stat':stat,'arm':arm,'n':len(joined),
                   'primary_loss':float(M.loss(stat,joined[stat],joined['mean']).mean()),'purpose':'descriptive only; no decisions or tuning'}
            added.append(value);seen.add(key)
    if added:
        with path.open('a',encoding='utf-8') as f:
            for value in added:f.write(json.dumps(value,allow_nan=False)+'\n')
    write_once(directory/'RESULTS_APPEND.json',{'created_at':now(),'new_descriptive_game_stat_rows':len(added),'log':str(path),'no_tuning':True})


def read_key(row):return (row['revision'],row['game_id'],row['stat'],row['arm'])


def game_comparison(rows,games,asof):
    from ..props.amendment2.revision import latest_games
    from ..props.amendment2.sheets import consensus
    from ..props.independent import spread_label
    quotes=latest_games(games,asof)
    if len(quotes):quotes=consensus(quotes)
    d=rows.copy()
    d['consensus_line']=np.nan;d['gap']=np.nan;d['p_over']=np.nan;d['line_status']='unavailable'
    for ix,r in d.iterrows():
        if r.stat=='margin':d.loc[ix,'spread_display']=spread_label(r.home_team,r.away_team,r['mean'])
        if quotes.empty:continue
        q=quotes[quotes.game_id.eq(r.game_id)&quotes.stat.eq(r.stat)&quotes.is_consensus_representative]
        if q.empty:continue
        ref=q.iloc[0];line=float(ref.consensus_line)
        d.loc[ix,['consensus_line','gap','line_status']]=[line,r['mean']-line,ref.line_status]
        d.loc[ix,'p_over']=float(norm.sf((line-r['mean'])/max((r.q90-r.q10)/2.563,1)))
    d['comparison_warning']='Research only; normal approximation to residual interval; game gaps are not validated signals.'
    return d


def revision_directory(week):
    root=ROOT/'weekly';root.mkdir(parents=True,exist_ok=True)
    revisions=[]
    for p in root.glob(f'2026_w{week:02d}_r*'):
        try:revisions.append(int(p.name.split('_r')[1].split('_')[0]))
        except ValueError:continue
    path=root/f'2026_w{week:02d}_r{max(revisions,default=0)+1:03d}_{stamp()}'
    path.mkdir(exist_ok=False)
    return path


def fit_frozen(spec,train,target,meta,research,threads,weights):
    from .walkforward import columns_for,completed_blocks
    columns=columns_for(spec,meta);kind=spec['model'];stat=spec['stat']
    if kind in ('equal','weighted','stacked'):
        members=[];history=None;keys=['game_id','pid']
        for i,key in enumerate(('linear','hist','xgboost','mlp')):
            child=spec|{'id':f'{stat}__all__all__{key}','model':key}
            p,_=M.fit_predict(train,target,stat,columns,key,threads,weights);members.append(p)
            h=completed_blocks(research,child)
            h=h[h.season<=2025]
            piece=h[keys+['actual','raw']].rename(columns={'raw':f'm{i}'})
            history=piece if history is None else history.merge(piece[keys+[f'm{i}']],on=keys,validate='one_to_one')
        p,state=M.combine(members,history,stat,kind)
        state['member_min']=np.min(members,axis=0);state['member_max']=np.max(members,axis=0)
        return p,state
    if kind=='blend':
        # A blend needs real current lines, which are a benchmark-only exception.
        # Keep its market-informed output separate from independent frozen forecasts.
        raise ValueError('Market-informed blend cannot be emitted as an independent forecast; separate current-line contract required')
    return M.fit_predict(train,target,stat,columns,kind,threads,weights)


def run(args):
    from ..data_pipeline import FEATURE_STORE
    from ..props.ensemble.production import completed_cutoff,season_weight_map
    from ..props.ensemble.features import eligible
    from .ingest import run as ingest
    from .audit import run as audit
    from .features import run as features,availability
    from .walkforward import columns_for, completed_blocks, residuals
    from .report import frozen
    registered()
    research=Path(read(ROOT/'LATEST_RESEARCH.json')['path']);selection=frozen(research)
    if not (research/'VALIDATION_COMPLETE.json').exists():raise ValueError('Frozen single validation must finish before weekly shadow refit')
    original_games=pd.read_parquet(FEATURE_STORE);cutoff=completed_cutoff(original_games)
    week=args.week or cutoff['training_last_completed_week']+1
    directory=revision_directory(week)
    try:
        if pd.Timestamp(args.deadline)-pd.Timestamp.now(tz='UTC')<pd.Timedelta(minutes=60):raise TimeoutError('Weekly pipeline needs its60min worst-case budget remaining')
        # Git fetch only; no branch switch or write to the root market file.
        command(['git','fetch','origin','main'],directory,'fetch',120)
        command([sys.executable,'-m','lab.phase10_archive','--remote-main'],directory,'market_archive',300)
        command([sys.executable,'-m','lab.cli','refresh'],directory,'refresh',1200)
        games=pd.read_parquet(FEATURE_STORE);games['kickoff_utc']=pd.to_datetime(games.kickoff_utc,utc=True)
        cutoff=completed_cutoff(games)
        if getattr(args,'strict_drop',False):
            from ..fpds_drop import validate_completed_week
            validate_completed_week(games,week)
        if week<=cutoff['training_last_completed_week']:raise ValueError('Requested week is already completed')
        ingest_manifest=ingest();audit(ingest_manifest)
        # Existing feature builder is scoped to a new private path; old artifacts never overwritten.
        from ..props.weekly10 import outputs
        from ..props.ensemble.data import prepare
        base=directory/'base';base.mkdir()
        with outputs(base):
            prepare(prospective_week=week,production=True,completed_week=cutoff['training_last_completed_week'],log=lambda _:None)
        meta=features(base=base/'features_production.parquet')
        frame=pd.read_parquet(Path(meta['path'])/'players.parquet')
        gameframe=pd.read_parquet(Path(meta['path'])/'games.parquet')
        decision=pd.Timestamp.now(tz='UTC')
        if pd.Timestamp(meta['source_observed_at'])>=decision:raise ValueError('Source import must precede forecast decision')
        future=gameframe[gameframe.season.eq(2026)&gameframe.week.eq(week)&gameframe.kickoff_utc.gt(decision)&~gameframe.completed]
        if future.empty:raise ValueError('No unstarted games remain in requested week')
        source=frame[frame.game_id.isin(future.game_id)]
        rows=[];game_rows=[]
        specs={s['stat']:s for s in selection['configurations']}
        for stat in STATS+('margin','total','win'):
            target=source[eligible(source,stat)] if stat in STATS else future
            allrows=frame if stat in STATS else gameframe
            known=(allrows.season<2026)|((allrows.season==2026)&allrows.week.le(cutoff['training_last_completed_week']))
            clock=availability(gameframe)
            known &= np.array([clock.get((s,w),pd.Timestamp.max.tz_localize('UTC'))<decision for s,w in zip(allrows.season,allrows.week)])
            train=allrows[known & allrows[stat].notna()]
            if stat in STATS:train=train[eligible(train,stat)]
            for arm,spec in [('control',{'id':f'{stat}__control__all__linear','stat':stat,'arm':'control','group':'all','model':'linear'}),('frozen',specs[stat])]:
                if target.empty:continue
                if pd.Timestamp(args.deadline)-pd.Timestamp.now(tz='UTC')<pd.Timedelta(minutes=3):raise TimeoutError('Weekly refit deadline reached')
                columns=columns_for(spec,meta);weights=train.season.map(season_weight_map(train.season.unique())).to_numpy(float);weights/=weights.mean()
                kind=spec['model']
                p,model=fit_frozen(spec,train,target,meta,research,args.threads or max(1,(__import__('os').cpu_count() or 2)-2),weights)
                history=completed_blocks(research,spec)
                if M.binary(stat):p,_=M.calibrated(p,history)
                error,method=residuals(model,train,columns,stat,history)
                q=p[None,:]+np.quantile(error,[.1,.5,.9])[:,None]
                if stat!='margin':q=np.maximum(q,0)
                if M.binary(stat):q=np.clip(q,0,1)
                for i,r in enumerate(target.itertuples()):
                    row={'game_id':r.game_id,'kickoff_utc':pd.Timestamp(r.kickoff_utc).isoformat(),'season':2026,'week':week,'stat':stat,'arm':arm,'mean':float(p[i]),'median':float(q[1,i]),
                         'q10':float(q[0,i]),'q50':float(q[1,i]),'q90':float(q[2,i]),'created_at':decision.isoformat(),
                         'training_cutoff_date':cutoff['training_cutoff_date'],'training_last_completed_week':cutoff['training_last_completed_week'],
                         'config_hash':digest(spec),'data_hash':meta['fingerprint'],'source_observed_at':meta['source_observed_at'],
                         'interval_method':method,'status':'shadow; no promotion; historical revisions/publication unverified'}
                    row['member_min']=float(model['member_min'][i]) if isinstance(model,dict) and 'member_min' in model else float(p[i])
                    row['member_max']=float(model['member_max'][i]) if isinstance(model,dict) and 'member_max' in model else float(p[i])
                    row['model_family']=spec['model']
                    if stat in STATS:
                        game=future[future.game_id.eq(r.game_id)].iloc[0]
                        row.update(pid=r.pid,team=r.team,name=r.name,position=r.position,home_team=game.home_team,away_team=game.away_team)
                        rows.append(row)
                    else:row.update(home_team=r.home_team,away_team=r.away_team);game_rows.append(row)
        # Retrieve context only; archived weather/inactives never enter models without historical validity.
        from ..inactives10 import collect
        from ..prospective import fetch_weather
        if pd.Timestamp(args.deadline)-pd.Timestamp.now(tz='UTC')<pd.Timedelta(minutes=25):raise TimeoutError('Context archive needs its25min worst-case budget remaining')
        inactive=collect(future,now=decision)
        if not inactive.get('ok'):raise RuntimeError('Inactive collector failed; no downstream comparison emitted')
        weather=fetch_weather(future)
        write_once(directory/'CONTEXT.json',{'created_at':now(),'inactive_archive':inactive,'weather_context':weather,'model_input':False})
        # First-TD probabilities derive from frozen ATD hazards, with explicit residual classes.
        from .first_td import labels,probabilities
        history_labels=labels(range(2021,2027))
        known_games=gameframe[gameframe.completed & ((gameframe.season<2026)|(gameframe.season.eq(2026)&gameframe.week.le(cutoff['training_last_completed_week'])))]
        clock=availability(gameframe)
        known_games=known_games[[clock.get((r.season,r.week),pd.Timestamp.max.tz_localize('UTC'))<decision for r in known_games.itertuples()]]
        prior_games=known_games.merge(history_labels,on='game_id')
        no_td=(int(prior_games.scorer.eq('NO_OFFENSIVE_TD').sum())+1)/(len(prior_games)+2)
        eligible_ids=set(map(tuple,frame.loc[eligible(frame,'anytime_td'),['game_id','pid']].to_numpy()))
        scored=prior_games[prior_games.scorer.ne('NO_OFFENSIVE_TD')]
        other=(sum((r.game_id,r.scorer) not in eligible_ids for r in scored.itertuples())+1)/(len(scored)+2)
        first=[];atd=pd.DataFrame(rows).query("stat == 'anytime_td'")
        first_spec=specs['first_td']
        first_sources=[atd[atd.arm.eq('control')].copy()]
        if first_spec['arm']=='control':
            source_first=atd[atd.arm.eq('control')].copy();source_first['arm']='frozen'
        elif specs['anytime_td']['arm']=='all' and specs['anytime_td']['model']=='linear':
            source_first=atd[atd.arm.eq('frozen')].copy()
        else:
            source_first=atd[atd.arm.eq('control')].copy();source_first['arm']='frozen'
            train=frame[((frame.season<2026)|(frame.season.eq(2026)&frame.week.le(cutoff['training_last_completed_week'])))&frame.anytime_td.notna()]
            train=train[eligible(train,'anytime_td')]
            train=train[[clock.get((r.season,r.week),pd.Timestamp.max.tz_localize('UTC'))<decision for r in train.itertuples()]]
            target=source[eligible(source,'anytime_td')]
            dep={'id':'anytime_td__all__all__linear','stat':'anytime_td','arm':'all','group':'all','model':'linear'}
            columns=columns_for(dep,meta);weights=train.season.map(season_weight_map(train.season.unique())).to_numpy(float);weights/=weights.mean()
            p,_=M.fit_predict(train,target,'anytime_td',columns,'linear',args.threads or 1,weights)
            h=completed_blocks(research,dep);p,_=M.calibrated(p,h)
            mapping=pd.DataFrame({'game_id':target.game_id,'pid':target.pid,'value':p})
            source_first=source_first.drop(columns='mean').merge(mapping,on=['game_id','pid'],validate='one_to_one').rename(columns={'value':'mean'})
        first_sources.append(source_first)
        for (game_id,arm),z in pd.concat(first_sources,ignore_index=True).groupby(['game_id','arm']):
            ids,probability=probabilities(z.pid,z['mean'],no_td,other)
            for pid,p in zip(ids,probability):
                template=z.iloc[0].to_dict() if pid in ('OTHER_PLAYERS','NO_OFFENSIVE_TD') else z[z.pid.eq(pid)].iloc[0].to_dict()
                template.update(stat='first_td',pid=pid,mean=float(p),median=float(p),q10=np.nan,q50=np.nan,q90=np.nan,
                                model_family='ATD hazard normalization; exploratory',member_min=np.nan,member_max=np.nan,
                                config_hash=digest(first_spec if arm=='frozen' else {'id':'first_td__control__all__linear'}))
                if pid in ('OTHER_PLAYERS','NO_OFFENSIVE_TD'):template.update(name=pid,team='GAME')
                first.append(template)
        players=pd.concat([pd.DataFrame(rows),pd.DataFrame(first)],ignore_index=True);projections=quote_comparison(players,decision)
        projections['confidence_tier']='C';projections['stability_flag']='not tested';projections['coherence_flag']='not reconciled';projections['scenario_sensitivity']='not tested'
        projections.to_csv(directory/'projections.csv',index=False)
        game_sheet=game_comparison(pd.DataFrame(game_rows),future,decision)
        game_sheet.to_csv(directory/'game_projections.csv',index=False)
        game_sheet['line_type']=np.where(game_sheet.consensus_line.notna(),'consensus','unavailable')
        game_sheet['confidence_tier']='C';game_sheet['name']=game_sheet.away_team+'@'+game_sheet.home_team
        game_sheet['coherence_flag']='not reconciled';game_sheet['stability_flag']='not tested';game_sheet['scenario_sensitivity']='not tested'
        leans=pd.concat([projections[projections.arm.eq('frozen')],game_sheet[game_sheet.arm.eq('frozen')]],ignore_index=True)
        leans['investigation_note']='Research-only comparison; coverage/revised-data risk, stability, coherence and scenarios remain unvalidated.'
        leans['investigation_score']=leans.gap.abs()/(leans.q90-leans.q10).clip(lower=1)
        leans['rank_in_game']=leans.groupby('game_id').investigation_score.rank(ascending=False,method='first',na_option='bottom')
        leans.sort_values(['game_id','rank_in_game']).to_csv(directory/'leans.csv',index=False)
        (directory/'leans.md').write_text('# FPDS shadow comparisons\n\nNo qualified investigation-readiness claim. Historical publication/revisions are unverified; no historical prop-price edge is established. Every row is tier C until stability, coherence and scenario checks are completed. See local leans.csv.\n',encoding='utf-8')
        result={'created_at':now(),'path':str(directory),'week':week,'games':len(future),'player_rows':len(projections),**cutoff,
                'frozen_config_hash':digest(selection),'data_hash':meta['fingerprint'],'files':{p.name:sha(p) for p in directory.glob('*.csv')}}
        write_once(directory/'FORECAST.json',result)
        append_results_log(directory,base/'observations_production.parquet',games)
        return result
    except Exception:
        write_once(directory/'FAILURE.json',{'created_at':now(),'private_error':private_error('weekly'),'status':'stopped; partial new revision retained; earlier files unchanged'})
        raise
