"""Fixed matched-label local research; every failed block stays visible."""
import hashlib
import time
import traceback
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

from . import targets as T,roles as R,simulation as D,drives as V,storage as S
from ..fpds_manual import engine as E,jobs
from ..fpds_improve import storage as A8,core as C
from ..fpds_improve.run import weights,identifiers,diagnostics
from ..fpds_followup import load_blocks,interval_score,align
from ..fpds_research import models as M
from ..fpds_research.common import read,write_once,now
from ..config import RAW_DIR,LAB_ROOT

FAMILY_SIZES={'provider':6,'role':6,'role_mixture':6,'shared':7,'drives':3,'groups':3}


def rng_for(*tokens):
    return np.random.default_rng(int.from_bytes(hashlib.sha256(':'.join(map(str,tokens)).encode()).digest()[:8],'little'))


def prepare(path,protocol,production=False):
    if (path/'PREPARED.json').exists():
        return tuple(pd.read_parquet(path/f) for f in ('players.parquet','games.parquet','observations.parquet','drives.parquet'))
    from ..props.ensemble.features import PBP_COLS
    import pyarrow.parquet as pq
    from ..data_pipeline import INJURY_VALID
    source=jobs.directory(protocol['source_job']);meta=read(source/'INPUT.json');parent=A8.ROOT/protocol['parent']
    if production:
        players=pd.read_parquet(Path(meta['path'])/'players.parquet');games=pd.read_parquet(Path(meta['path'])/'games.parquet')
    else:
        players=pd.read_parquet(parent/'players.parquet');games=pd.read_parquet(parent/'strong_games.parquet')
    for d in (players,games):d['kickoff_utc']=pd.to_datetime(d.kickoff_utc,utc=True)
    observations=[];drive_rows=[];audits=[];drive_audits=[]
    for season in range(2021,2027 if production else 2025):
        file=RAW_DIR/f'play_by_play_{season}.parquet'
        cols=list(dict.fromkeys(PBP_COLS+T.EXTRA+V.COLS));names=pq.read_schema(file).names
        missing=set(cols)-set(names)
        if missing:raise ValueError('Required local PBP columns unavailable; no guessing')
        p=pd.read_parquet(file,columns=cols)
        if production:
            clock=E.availability(games);decision=pd.Timestamp.now(tz='UTC')
            known=[clock.get((s,w),pd.Timestamp.max.tz_localize('UTC'))<decision for s,w in zip(p.season,p.week)]
            p=p[known]
        roster=pd.read_parquet(RAW_DIR/f'roster_weekly_{season}.parquet',columns=['season','week','team','gsis_id','pfr_id','position'])
        snaps=pd.read_parquet(RAW_DIR/f'snap_counts_{season}.parquet')
        if production:snaps=snaps[snaps.game_id.isin(p.game_id.unique())]
        obs,audit=T.reconstruct(p,roster,snaps);observations.append(obs);audits.append({'season':season,**audit})
        drive,da=V.extract(p);drive_rows.append(drive);drive_audits.append({'season':season,**da})
    obs=pd.concat(observations,ignore_index=True)
    old=players.copy();players=T.join_targets(players,obs)
    changed={s:int((old[s].notna()&players[s].notna()&old[s].ne(players[s])).sum()) for s in T.STATS}
    unknown={s:int(players[s].isna().sum()) for s in T.STATS}
    players=R.enrich(players,obs,games,pd.read_parquet(INJURY_VALID),pd.Timestamp.now(tz='UTC') if production else None)
    drive=pd.concat(drive_rows,ignore_index=True);clock=E.availability(games)
    drive['available_at']=[clock.get((s,w),pd.NaT) for s,w in zip(drive.season,drive.week)]
    drive=drive.dropna(subset=['available_at'])
    report={'created_at':now(),'target_audits':audits,'drive_audits':drive_audits,'candidate_rows':len(players),
            'changed_known_candidate_targets':changed,'unknown_candidate_labels':unknown,
            'pregame_injury_known_rows':int(players.r10_injury_known.sum()),'pregame_role_changed_rows':int(players.r10_changed.sum()),
            'rule':'new target version; unknowns excluded per stat identically for all arms. Postgame participation never a feature or pregame eligibility filter. No official player box-score source present locally.'}
    for name,d in [('players',players),('games',games),('observations',obs),('drives',drive)]:d.to_parquet(path/(name+'.parquet'),index=False)
    write_once(path/'PREPARED.json',report)
    return players,games,obs,drive


def base_history(path,stat,arm):
    return load_blocks(path,f'base__{stat}__{arm}')


def residual_bank(history,train,stat):
    if len(history)>=100:return (history.actual-history.pred).to_numpy(float)
    return (train[stat]-train[stat].mean()).dropna().to_numpy(float)


def simulate_current(current,stat,bank,sims,kind,latent=None):
    u=[];role=[]
    for r in current.itertuples():
        generator=rng_for(20261021,stat,r.game_id,r.pid)
        noise=generator.normal(size=sims)
        if kind=='shared':noise=.5*latent[r.game_id][:,D.ORDER.index(stat)]+np.sqrt(.75)*noise
        u.append(norm.cdf(noise))
        a=np.asarray(r.r10_ratios,float)
        role.append(generator.choice(a,sims) if kind=='role_mixture' else np.ones(sims))
    values=D.draws(stat,current.pred.to_numpy(float),np.array(u),bank,np.array(role))
    out=D.summaries(current,values);out['simulation_mean']=out.pred
    out['pred']=current.pred.to_numpy(float)  # Keep the point model; evaluate distributions separately.
    if stat=='anytime_td' and kind=='role_mixture':
        out['pred']=[float(np.mean(-np.expm1(np.log1p(-np.clip(r.pred,0,1-1e-9))*np.asarray(r.r10_ratios,float)))) for r in current.itertuples()]
    return out,values


def assemble_loss(frame,stat,metric):
    if metric=='crps':return frame.crps.to_numpy(float)
    if metric=='interval':return interval_score(frame)
    if metric=='energy':return frame.pred.to_numpy(float)
    return M.loss(stat,frame.actual,frame.pred)


def comparison(family,stat,variant,new,ref,metric='point'):
    d=align(new,ref)
    reference=ref.set_index(['game_id']+(['pid'] if 'pid' in ref else [])).loc[
        pd.MultiIndex.from_frame(d[['game_id','pid']]) if 'pid' in d else d.game_id].reset_index()
    a=assemble_loss(reference,stat,metric);b=assemble_loss(d,stat,metric)
    effect=E.paired(b-a,d.game_id,FAMILY_SIZES[family])
    seasons={str(s):float(np.asarray(b-a)[d.season.eq(s)].mean()) for s in (2022,2023,2024)}
    diag=diagnostics(new,stat) if stat!='energy' else {}
    return {'family':family,'stat':stat,'variant':variant,'metric':metric,**effect,
            'control_loss':float(np.mean(a)),'new_loss':float(np.mean(b)),'seasons':seasons,'diagnostics':diag}


def research(path,hours=2):
    protocol,signature=S.registered();hashes=S.inputs(protocol);deadline=time.monotonic()+hours*3600
    if (path/'RUN.json').exists():
        saved=read(path/'RUN.json')
        if saved['signature']!=signature or saved['inputs']!=hashes:raise ValueError('Resume changed source/config')
        if (path/'SUMMARY.json').exists():raise ValueError('Completed run immutable')
    else:write_once(path/'RUN.json',{'created_at':now(),'protocol':protocol,'signature':signature,'inputs':hashes})
    S.status(path,'preparing',step='known-label target reconstruction and role source clocks')
    players,games,obs,drives=prepare(path,protocol)
    meta=read(jobs.directory(protocol['source_job'])/'INPUT.json');old=read(A8.ROOT/protocol['parent']/'RUN.json')['protocol']
    for season in protocol['discovery']:
        for week in protocol['refit_weeks']:
            if time.monotonic()>deadline-300:S.status(path,'checkpoint',step=f'{season}/w{week}');return
            S.status(path,'running',step=f'{season}/w{week}')
            fail=path/f'{season}_w{week:02d}.FAILED.json'
            if fail.exists():continue
            try:run_block(path,protocol,old,meta,players,games,drives,season,week)
            except Exception:
                (path/f'{season}_w{week:02d}.PRIVATE.log').write_text(traceback.format_exc(),encoding='utf-8')
                write_once(fail,{'status':'failed/logged/skipped; whole block/families ineligible'})
    summarize(path,protocol,hashes)


def run_block(path,protocol,old,meta,players,games,drives,season,week):
    sims=protocol['sims'];current={};trains={};banks={}
    for stat in T.STATS:
        data=E.data_for(stat,players,games);data=data[data[stat].notna()]
        target=data[data.season.eq(season)&data.week.between(week,min(week+3,18))].copy()
        if target.empty:raise ValueError('Empty corrected target block')
        decision=target.kickoff_utc.min();train=E.training_rows(data,games,decision,season,week,stat)
        trains[stat]=train
        for arm in ('control','fpds','role'):
            variant=f'role__{stat}__fpds' if arm=='role' else f'base__{stat}__{arm}'
            file=S.block(path,variant,season,week)
            history=C.earlier(load_blocks(path,variant),decision)
            bank=residual_bank(history,train,stat)
            if file.exists():out=pd.read_parquet(file)
            else:
                S.ledger(path,variant,'hist')
                cols=C.task_columns(meta,stat,old,'control' if arm=='control' else 'fpds')+(R.COLS if arm=='role' else [])
                pred,_=M.fit_predict(train,target,stat,cols,'hist',max(1,(__import__('os').cpu_count() or 2)-2),weights(train,season))
                out=identifiers(target,stat,games,pred)
                for c in R.COLS+['r10_ratios']:out[c]=target[c].to_numpy()
                out['position']=target.position.to_numpy()
                out['training_cutoff']=train.kickoff_utc.max().isoformat()
                out,_=simulate_current(out,stat,bank,sims,'independent')
                S.save(path,variant,season,week,out)
            if arm=='fpds':current[stat]=out;banks[stat]=bank
    decision=min(pd.to_datetime(d.kickoff_utc,utc=True).min() for d in current.values())
    histories={s:C.earlier(base_history(path,s,'fpds'),decision) for s in T.STATS}
    parent=A8.ROOT/protocol['parent']
    for stat in E.GAME_STATS:histories[stat]=C.earlier(load_blocks(parent,f'strong_games__{stat}__control__equal'),decision)
    aux=path/f'AUX_{season}_w{week:02d}.json'
    if aux.exists():corr=np.asarray(read(aux)['correlation'])
    else:
        S.ledger(path,'shared_copula','earlier_game_rank_correlation');corr,n=D.correlation(histories,decision)
        write_once(aux,{'correlation':corr.tolist(),'earlier_complete_games':n})
    game_ids=set().union(*(set(d.game_id) for d in current.values()))
    latent={g:rng_for('latent',g).multivariate_normal(np.zeros(9),corr,size=sims) for g in game_ids}
    arrays={};independent={}
    for stat,out in current.items():
        for kind in ('role_mixture','shared'):
            variant=f'{kind}__{stat}__fpds';file=S.block(path,variant,season,week)
            # Regeneration for aggregate diagnostics uses fixed common random numbers, no fits.
            value,draw=simulate_current(out,stat,banks[stat],sims,kind,latent)
            if not file.exists():S.ledger(path,variant);S.save(path,variant,season,week,value)
            if kind=='shared':arrays[stat]=(out,draw)
        _,draw=simulate_current(out,stat,banks[stat],sims,'independent');independent[stat]=(out,draw)
        if stat in ('pass_yds','rec_yds','rush_yds'):
            for grouped in (False,True):
                name=('groups' if grouped else 'global')+f'__{stat}__fpds';file=S.block(path,name,season,week)
                if not file.exists():
                    S.ledger(path,name,'earlier_conformal')
                    calibrated=D.calibrate(out,histories[stat],grouped);S.save(path,name,season,week,calibrated)
    # Joint energy score uses standardized stat aggregates; same eligible players,
    # same marginal game forecasts and same scale in both arms.
    complete=set.intersection(*(set(d.game_id) for d in current.values()))
    game_targets=games[games.game_id.isin(complete)&games.season.eq(season)&games.week.between(week,min(week+3,18))]
    energy_rows=[];energy_ref=[]
    for g in game_targets.itertuples():
        vectors=[];refs=[];actual=[];scales=[]
        for stat in D.ORDER:
            hist=histories[stat]
            if len(hist)>10:scale=float(hist.groupby('game_id').actual.mean().std())
            elif stat in trains:scale=float(trains[stat].groupby('game_id')[stat].mean().std())
            else:
                training=E.training_rows(games,games,decision,season,week,stat)
                scale=float(training[stat].std())
            scale=max(scale if np.isfinite(scale) else 1,1)
            scales.append(scale)
            if stat in E.GAME_STATS:
                ref=load_blocks(parent,f'strong_games__{stat}__control__equal')
                row=ref[ref.game_id.eq(g.game_id)]
                if row.empty:break
                gen=rng_for('game_energy',g.game_id,stat);z=gen.normal(size=sims)
                bank=(hist.actual-hist.pred).to_numpy(float) if len(hist)>=100 else np.array([0.])
                values=D.draws(stat,row.pred.to_numpy(),norm.cdf(z)[None,:],bank)[0]
                shared=D.draws(stat,row.pred.to_numpy(),norm.cdf(.5*latent[g.game_id][:,D.ORDER.index(stat)]+np.sqrt(.75)*z)[None,:],bank)[0]
                actual.append(float(row.actual.iloc[0]));refs.append(values);vectors.append(shared)
            else:
                d,draw=arrays[stat];take=d.game_id.eq(g.game_id).to_numpy()
                actual.append(float(d.loc[take,'actual'].mean()));vectors.append(draw[take].mean(0));refs.append(independent[stat][1][take].mean(0))
        if len(actual)!=9:continue
        base={'game_id':g.game_id,'season':season,'week':g.week,'actual':0.,'available_at':E.availability(games).loc[(g.season,g.week)]}
        energy_rows.append(dict(base,pred=D.energy(np.column_stack(vectors),actual,np.array(scales))))
        energy_ref.append(dict(base,pred=D.energy(np.column_stack(refs),actual,np.array(scales))))
    for name,rows in [('joint_energy',energy_rows),('independent_energy',energy_ref)]:
        if rows and not S.block(path,name,season,week).exists():S.ledger(path,name);S.save(path,name,season,week,pd.DataFrame(rows))
    drive_file=path/f'DRIVE_FIT_{season}_w{week:02d}.json'
    if not drive_file.exists():S.ledger(path,'drive_state','earlier_drive_density');write_once(drive_file,{'decision':decision.isoformat()})
    past=drives[drives.available_at.lt(decision)]
    drive_outputs={s:[] for s in E.GAME_STATS};drive_meta=[]
    for g in games[games.season.eq(season)&games.week.between(week,min(week+3,18))].itertuples():
        scores,info=V.simulate(past,g.home_team,g.away_team,sims,rng_for('drive',g.game_id))
        margin=scores[:,0]-scores[:,1];total=scores.sum(1);non_ties=margin!=0
        win=float((margin[non_ties]>0).mean()) if non_ties.any() else .5
        drive_meta.append({'earlier_ot_games':info['earlier_ot_games'],'tie_probability':info['simulated_tie_probability']})
        for stat,draw,point in [('win',(margin>0).astype(float),win),('margin',margin,float(margin.mean())),('total',total,float(total.mean()))]:
            if stat=='win' and pd.isna(g.win):continue
            frame=pd.DataFrame([{'game_id':g.game_id,'season':season,'week':g.week,'actual':getattr(g,stat),'pred':point,
                                 'available_at':E.availability(games).loc[(g.season,g.week)]}])
            frame=D.summaries(frame,draw[None,:]);frame['pred']=point
            drive_outputs[stat].append(frame)
    for stat,rows in drive_outputs.items():
        name='drives__'+stat
        if rows and not S.block(path,name,season,week).exists():S.ledger(path,name);S.save(path,name,season,week,pd.concat(rows,ignore_index=True))
    file=path/f'DRIVE_DIAGNOSTICS_{season}_w{week:02d}.json'
    if not file.exists():write_once(file,{'games':len(drive_meta),'minimum_earlier_ot_games':min(x['earlier_ot_games'] for x in drive_meta),
                                       'mean_simulated_tie_probability':float(np.mean([x['tie_probability'] for x in drive_meta]))})


def summarize(path,protocol,hashes):
    rows=[];errors=[]
    specs=[]
    for stat in T.STATS:
        specs += [('provider',stat,f'base__{stat}__fpds',f'base__{stat}__control','point'),
                  ('role',stat,f'role__{stat}__fpds',f'base__{stat}__fpds','point')]
        for family in ('role_mixture','shared'):specs.append((family,stat,f'{family}__{stat}__fpds',f'base__{stat}__fpds','point' if stat=='anytime_td' else 'crps'))
        if stat in ('pass_yds','rec_yds','rush_yds'):specs.append(('groups',stat,f'groups__{stat}__fpds',f'global__{stat}__fpds','interval'))
    specs.append(('shared','energy','joint_energy','independent_energy','energy'))
    for stat in E.GAME_STATS:specs.append(('drives',stat,'drives__'+stat,None,'point'))
    for family,stat,variant,reference,metric in specs:
        try:
            new=load_blocks(path,variant)
            if new.empty:raise ValueError('Missing output')
            if family=='drives':
                ref=load_blocks(A8.ROOT/protocol['parent'],f'strong_games__{stat}__control__equal')
                # Ties are absent from winner baseline, retained for margin/total.
                new=new[new.game_id.isin(ref.game_id)]
            else:ref=load_blocks(path,reference)
            rows.append(comparison(family,stat,variant,new,ref,metric))
        except Exception:
            (path/(variant+'.SUMMARY_PRIVATE.log')).write_text(traceback.format_exc(),encoding='utf-8');errors.append(variant)
    failures=[p.name for p in path.glob('*.FAILED.json')]
    for family,count in FAMILY_SIZES.items():
        entries=sorted([r for r in rows if r['family']==family],key=lambda x:x['p']);prev=0.
        for i,r in enumerate(entries):
            prev=max(prev,min(1,r['p']*(count-i)));r['holm_p']=prev
            r['relative_reduction']=-r['delta']/max(r['control_loss'],1e-9)
            r['seasons_agreeing']=sum(v<0 for v in r['seasons'].values())
            gate=not failures and len(entries)==count and not any(x.startswith(family) for x in errors) and r['games']>=200 and r['relative_reduction']>=.01 and r['corrected_ci95'][1]<0 and prev<.05 and r['seasons_agreeing']>=2
            if family=='groups':gate=gate and r['diagnostics']['coverage80']>=.78
            r['nomination']=bool(gate)
    group_diagnostics=[]
    for stat in T.STATS:
        d=load_blocks(path,f'base__{stat}__fpds')
        if d.empty:continue
        for (pos,changed),part in d.groupby(['position','r10_changed'],dropna=False):
            group_diagnostics.append({'stat':stat,'position':str(pos),'role_changed':bool(changed),**diagnostics(part,stat)})
    intact=all(Path(p).exists() and S.sha(p)==v for p,v in hashes.items())
    if not intact:raise ValueError('Inputs changed; quarantine results')
    result={'created_at':now(),'rows':rows,'failures':failures,'comparison_failures':errors,'trials':read(path/'TRIALS.json'),
            'audit':read(path/'PREPARED.json'),'groups':group_diagnostics,'inputs_unchanged':intact,
            'limitations':'Reconstructed targets not independent official certification. Previously examined2022–24 only; revised FPDS. No new2025/2026 scores, market edge, promotion or default replacement. Copula is a statistical joint prototype, not a single physically reconciled play-by-play simulation.'}
    write_once(path/'SUMMARY.json',result)
    dest=LAB_ROOT/'reports/run_20261021'/('A10_'+path.name);dest.mkdir(parents=True,exist_ok=False)
    write_once(dest/'AGGREGATE_RESULTS.json',result)
    lines=['# Targets, roles and simulations — Amendment10','',result['limitations'],'',
           '|Family / target|n / games|Control → new primary loss|Delta [corrected95% CI]|Nomination|','|---|---|---|---|---|']
    for r in rows:
        lo,hi=r['corrected_ci95'];lines.append(f"|{r['family']} / {r['stat']} ({r['metric']})|{r['n']}/{r['games']}|{r['control_loss']:.5f} → {r['new_loss']:.5f}|{r['delta']:+.5f} [{lo:+.5f},{hi:+.5f}]|{r['nomination']}|")
    lines+=['',f"Failed blocks:{len(failures)}; comparison failures:{len(errors)}; fit calls:{result['trials']['fit_calls']}; output versions:{len(result['trials']['outputs'])}; unchanged input hashes:{intact}.",
            '', 'Unknown target labels were excluded identically per stat, not filled with zeros. This is a new evaluation cohort; old-report losses are not directly comparable.',
            '', 'Scenarios have unknown occurrence probabilities; replacements remain other players. Role-mixture probabilities arise only from empirical prior workload ratios, not invented injury/availability odds.',
            '', 'Game winner probabilities condition on a non-tie final score; tie mass is separate. Defensive/special-teams scores are included in extracted score-pair events. No game market line is an input.']
    (dest/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    S.status(path,'complete',comparisons=len(rows),failures=len(failures)+len(errors),nominations=sum(r['nomination'] for r in rows))


def project(path,season,week,sims=2000):
    """Explicit frozen shadow refit, never a production pointer/default change."""
    protocol,signature=S.registered();hashes=S.inputs(protocol,production=True)
    creation=pd.Timestamp.now(tz='UTC')
    write_once(path/'RUN.json',{'created_at':creation.isoformat(),'signature':signature,'protocol':protocol,'inputs':hashes,'action':'project'})
    S.status(path,'preparing',step='explicit frozen shadow refit; no scoring')
    players,games,obs,drives=prepare(path,protocol,production=True)
    from ..props.ensemble.production import completed_cutoff
    cutoff=completed_cutoff(games,creation)
    target_games=games[games.season.eq(season)&games.week.eq(week)&games.kickoff_utc.gt(creation)]
    if target_games.empty:raise ValueError('No unstarted prepared games for requested week; prepare the existing weekly pipeline first')
    target_players=players[players.game_id.isin(target_games.game_id)]
    if target_players.empty:raise ValueError('No prepared pregame player candidates; do not guess future rosters')
    meta=read(jobs.directory(protocol['source_job'])/'INPUT.json');old=read(A8.ROOT/protocol['parent']/'RUN.json')['protocol']
    # Unknown target outcomes remain NaN; only training_rows selects known past.
    clock=E.availability(games);allowed=[clock.get((s,w),pd.Timestamp.max.tz_localize('UTC'))<creation for s,w in zip(players.season,players.week)]
    training=players[np.asarray(allowed)&((players.season<2026)|players.week.le(cutoff['training_last_completed_week']))]
    headers={'created_at':creation.isoformat(),'config_hash':signature,'source_hash':__import__('lab.fpds_research.common',fromlist=['digest']).digest(hashes),
             **cutoff,'source_feature_cutoff':meta.get('feature_creation_cutoff','unknown; frozen A7 snapshot'),'shadow_only':True}
    output=[];scenarios=[]
    for stat in T.STATS:
        tr=E.data_for(stat,training,games);tr=tr[tr[stat].notna()]
        target=E.data_for(stat,target_players,games)
        if target.empty:continue
        cols=C.task_columns(meta,stat,old,'fpds')+R.COLS
        S.ledger(path,f'project__{stat}','hist')
        p,model=M.fit_predict(tr,target,stat,cols,'hist',max(1,(__import__('os').cpu_count() or 2)-2),weights(tr,season))
        import joblib
        joblib.dump(model,path/(stat+'.joblib'))
        current=target[['game_id','pid','team','position']+R.COLS+['r10_ratios']].copy().reset_index(drop=True)
        current['actual']=0.;current['pred']=p
        # No in-sample residual calibration: use completed, strictly earlier
        # discovery OOF role errors if available, otherwise label unavailable.
        completed=sorted(p.parent for p in S.ROOT.glob('*/SUMMARY.json'))
        previous=completed[-1] if completed else None
        hist=load_blocks(previous,f'role__{stat}__fpds') if previous else pd.DataFrame()
        hist=C.earlier(hist,creation) if len(hist) else hist
        bank=(hist.actual-hist.pred).to_numpy(float) if len(hist)>=100 else np.array([0.])
        out,_=simulate_current(current,stat,bank,sims,'role_mixture')
        out=out.drop(columns=['actual','r10_ratios','crps'],errors='ignore');out['stat']=stat
        out['calibration_status']='earlier discovery OOF only; transfer to current season unvalidated' if len(hist)>=100 else 'unavailable; deterministic yard intervals are not calibrated'
        for k,v in headers.items():out[k]=v
        output.append(out)
        for r in current.itertuples():
            for scenario in R.scenario_rows(r):scenarios.append({'game_id':r.game_id,'pid':r.pid,'stat':stat,**scenario,**headers})
    if not output:raise ValueError('No eligible prepared players')
    pd.concat(output,ignore_index=True).to_csv(path/f'shadow_players_{season}_w{week:02d}.csv',index=False)
    write_once(path/'SCENARIOS_PRIVATE.json',{'metadata':headers,'rows':scenarios})
    past=drives[pd.to_datetime(drives.available_at,utc=True).lt(creation)];game_rows=[]
    for g in target_games.itertuples():
        score,info=V.simulate(past,g.home_team,g.away_team,sims,rng_for('project_drive',g.game_id))
        margin=score[:,0]-score[:,1];total=score.sum(1);ties=margin==0
        game_rows.append({'game_id':g.game_id,'home_team':g.home_team,'away_team':g.away_team,
                          'home_win_probability_conditional_no_tie':float((margin[~ties]>0).mean()) if (~ties).any() else .5,
                          'margin_mean':float(margin.mean()),'total_mean':float(total.mean()),
                          'margin_q10':float(np.quantile(margin,.1)),'margin_q50':float(np.quantile(margin,.5)),'margin_q90':float(np.quantile(margin,.9)),
                          'total_q10':float(np.quantile(total,.1)),'total_q50':float(np.quantile(total,.5)),'total_q90':float(np.quantile(total,.9)),**info,**headers})
    pd.DataFrame(game_rows).to_csv(path/f'shadow_games_{season}_w{week:02d}.csv',index=False)
    if not all(S.sha(Path(p))==v for p,v in hashes.items()):raise ValueError('Source changed; quarantine projection')
    write_once(path/'PROJECT.json',{'metadata':headers,'games':len(game_rows),'player_stat_rows':sum(map(len,output)),
                                   'warning':'Unvalidated frozen shadow output, not default projections. Scenarios unknown probability. No scoring or promotion.'})
    S.status(path,'complete',games=len(game_rows),player_stat_rows=sum(map(len,output)))
