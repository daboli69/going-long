"""Amendment 4 only: paired 2023 development; subscription derivatives local.

No confirmation/holdout entry point and no evaluation CLI import. Fits are not
registered or connected to the champion, production props, or weekly pipeline.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import traceback
import zlib

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from .. import fpds_ingest as I,metrics
from ..config import LAB_ROOT,RAW_DIR
from ..data_pipeline import FEATURE_STORE
from .ensemble.features import FEATURES,eligible
from .ensemble.members import Members,KEYS
from .ensemble.production import season_weight_map
from .ensemble.research import clustered_difference
from .ensemble.combine import loss_rows

STATS=('rec','rec_yds','rush_yds','anytime_td')
TRAIN=(2021,2022)
DEV=2023
KEY=['game_id','pid','stat']


def check_registration():
    relative=subprocess.check_output(['git','ls-files','--full-name','docs/PHASE10_PREREGISTRATION.md'],cwd=LAB_ROOT,text=True).strip()
    committed=subprocess.check_output(['git','show','HEAD:'+relative],cwd=LAB_ROOT,text=True,encoding='utf-8')
    current=(LAB_ROOT/'docs/PHASE10_PREREGISTRATION.md').read_text(encoding='utf-8')
    if '## Amendment 4' not in committed or current!=committed:raise ValueError('Amendment4 must be committed unchanged before fitting')
    return hashlib.sha256(committed.encode()).hexdigest()


def deadline_check(deadline,budget=30):
    if (pd.Timestamp(deadline)-pd.Timestamp.now(tz='UTC')).total_seconds()<budget:raise TimeoutError('Insufficient remaining deadline budget')


def predictions(model,frame):
    return model.predict(frame)


def calibrated(raw,current_history,current_actual,history_actual):
    """Earlier emitted weeks only; return transform for fixed permutation checks."""
    if len(current_history)>=100 and len(np.unique(history_actual))==2:
        p=np.clip(np.asarray(current_history),metrics.EPS,1-metrics.EPS)
        fit=LogisticRegression(C=1.,max_iter=1000).fit(np.log(p/(1-p))[:,None],history_actual)
        def transform(a):
            a=np.clip(np.asarray(a),metrics.EPS,1-metrics.EPS)
            return fit.predict_proba(np.log(a/(1-a))[:,None])[:,1]
        return transform(raw),transform
    return raw,lambda a:np.asarray(a)


def permute(frame,columns,table,seed):
    """Preserve all table columns together; team context moves as a team."""
    result=frame.copy();rng=np.random.default_rng(seed)
    if table=='run_pass_report':
        teams=frame[['team']+columns].drop_duplicates('team')
        values=teams[columns].to_numpy()[rng.permutation(len(teams))]
        mapping=pd.DataFrame(values,index=teams.team,columns=columns)
        result[columns]=mapping.loc[frame.team].to_numpy()
    else:
        for _,idx in frame.groupby('position').groups.items():
            result.loc[idx,columns]=frame.loc[rng.permutation(idx),columns].to_numpy()
    return result


def fit_models(frame,columns,out,threads,deadline):
    fitted={};train=frame[frame.season.isin(TRAIN)]
    if set(train.season)!={2021,2022}:raise ValueError('Training must contain both2021 and2022 only')
    with (out/'fit_private.log').open('x',encoding='utf-8') as log:
        for stat in STATS:
            target=train[eligible(train,stat)&train[stat].notna()].copy()
            weight=target.season.map(season_weight_map(TRAIN,reference_season=DEV)).to_numpy(float);weight/=weight.mean()
            for arm,cols in [('base',FEATURES),('fpds',FEATURES+columns)]:
                deadline_check(deadline,240)
                # The production=True flag only verifies the committed model
                # configuration/authorizes these recent identities; fits remain
                # isolated here and the explicit training guard above controls data.
                model=Members().fit(target,stat,cols,threads,lambda s:log.write(s+'\n'),sample_weight=weight,production=True)
                if model.errors or set(model.models)!=set(KEYS):raise RuntimeError('Member fit incomplete; see PRIVATE local fit log')
                joblib.dump(model,out/f'{arm}_{stat}.joblib');fitted[(arm,stat)]=model
                print(f'Fitted {arm}/{stat}: {len(target)} training rows',flush=True)
    return fitted


def structural(frame,out,deadline):
    from . import models as M,players as PL,sim as S,game as G
    from .ensemble.structural import build_inputs
    deadline_check(deadline,3600)
    table=M.fit(TRAIN,season_weights=season_weight_map(TRAIN,reference_season=DEV))
    S.calibrate_clock(table);joblib.dump(table,out/'structural_tables_2021_2022.joblib')
    panel=PL.panel(M.load_pbp([2022,2023]),table)
    games=pd.read_parquet(FEATURE_STORE,filters=[('season','=',DEV)])
    games=games[games.game_type.eq('REG')].sort_values(['week','game_id'])
    destination=out/'structural';destination.mkdir(exist_ok=False)
    rows=[];errors=[];durations=[]
    for index,game in enumerate(games.itertuples(index=False),1):
        deadline_check(deadline,max(60.,max(durations[-10:],default=20)*1.5))
        started=time.monotonic()
        try:
            teams,players,cols,info,a=build_inputs(frame,panel,DEV,game)
            if any(not len(t['recv_cols']) or not len(t['rush_cols']) for t in teams):raise ValueError('Missing prior eligible player pool')
            home=frame[frame.game_id.eq(game.game_id)&frame.team.eq(game.home_team)]
            if home.empty:raise ValueError('No independent home context')
            total=float(home.ind_total.iloc[0]);margin=float(home.ind_team_margin.iloc[0])
            points=[max(0.,(total+margin)/2),max(0.,(total-margin)/2)]
            rng=np.random.default_rng(zlib.crc32(game.game_id.encode()))
            efficiency,_=S.calibrate_v2(table,teams,players,points,rng)
            result=S.simulate(table,teams,players,1000,efficiency,rng,record_td=True)
            valid=G.eligible(info,a)
            valid += [(t,pid,'anytime_td') for t,pid in sorted({(t,pid) for t,pid,k in valid if k in ('rec','rush_yds')})]
            current=[]
            for team,pid,stat in valid:
                if stat not in STATS:continue
                samples=result['stats'][stat][:,cols[pid]]
                current.append({'game_id':game.game_id,'pid':pid,'stat':stat,'structural':float(samples.mean()),'samples':samples.astype('float32').tolist()})
            pd.DataFrame(current).to_parquet(destination/(game.game_id+'.parquet'),index=False);rows+=current
        except Exception as exc:
            # Detailed local error is private; console receives only case count/type.
            with (out/'structural_private_errors.log').open('a',encoding='utf-8') as f:f.write(traceback.format_exc()+'\n')
            errors.append({'game_id':game.game_id,'error_type':type(exc).__name__})
        durations.append(time.monotonic()-started)
        print(f'Structural development game {index}/{len(games)}; errors={len(errors)}',flush=True)
    I.write_once(out/'structural_status.json',{'games':len(games),'files':len(list(destination.glob('*.parquet'))),'errors':errors,'training_seasons':list(TRAIN),'development_season':DEV,'sims':1000})
    return pd.DataFrame(rows).drop(columns='samples'),errors


def walk_forward(frame,fitted,structural_rows,columns,groups,out,deadline):
    data=[];history={(arm,stat):{'raw':[],'actual':[]} for stat in STATS for arm in ['base','fpds']}
    dev=frame[frame.season.eq(DEV)].copy()
    shared={(r.game_id,r.pid,r.stat):r.structural for r in structural_rows.itertuples()}
    for week,current in dev.groupby('week',sort=True):
        deadline_check(deadline,120)
        for stat in STATS:
            target=current[eligible(current,stat)&current[stat].notna()].copy().reset_index(drop=True)
            if target.empty:continue
            struct=np.array([shared.get((r.game_id,r.pid,stat),np.nan) for r in target.itertuples()]);present=np.isfinite(struct)
            result=target[['game_id','pid','team','position','season','week']].copy();result['stat']=stat;result['actual']=target[stat].to_numpy()
            result['structural']=struct;result['member_count']=4+present.astype(int)
            result['members']=np.where(present,'logreg,random_forest,xgboost,mlp,sim_independent','logreg,random_forest,xgboost,mlp')
            fp_transform=None
            for arm in ['base','fpds']:
                model=fitted[(arm,stat)];p=predictions(model,target)
                for key in KEYS:result[arm+'_'+key]=p[key]
                raw=(sum(p[key] for key in KEYS)+np.nan_to_num(struct))/(4+present)
                previous=history[(arm,stat)]
                value,transform=calibrated(raw,previous['raw'],result.actual,previous['actual']) if stat=='anytime_td' else (raw,lambda a:np.asarray(a))
                result[arm]=value
                result[arm+'_raw']=raw
                result[arm+'_calibration_rows']=len(previous['raw']) if stat=='anytime_td' else 0
                if arm=='fpds':fp_transform=transform
                for q in [10,50,90]:
                    if f'q{q}' in p:result[f'{arm}_head_q{q}']=np.maximum(0,p[f'q{q}'])
                previous['raw'].extend(raw.tolist());previous['actual'].extend(result.actual.tolist())
            for table,cols in groups.items():
                changed=permute(target,cols,table,20261020+int(week)+zlib.crc32((stat+table).encode()))
                p=predictions(fitted[('fpds',stat)],changed)
                raw=(sum(p[k] for k in KEYS)+np.nan_to_num(struct))/(4+present)
                result['permuted_'+table]=fp_transform(raw)
            result['fpds_nonmissing_features']=target[columns].notna().sum(axis=1)
            data.append(result)
        print(f'Walk-forward development week {int(week)} complete',flush=True)
    result=pd.concat(data,ignore_index=True);result.to_parquet(out/'predictions_2023_PRIVATE.parquet',index=False)
    return result


def summarize(data,groups,structural_errors,out):
    results=[];importance=[]
    for stat,g in data.groupby('stat'):
        base=loss_rows(stat,g.actual,g.base);fp=loss_rows(stat,g.actual,g.fpds)
        delta=clustered_difference(g.game_id,fp-base,2000,20261020)
        row={'stat':stat,'metric':'Brier' if stat=='anytime_td' else 'Poisson deviance' if stat=='rec' else 'MAE',
             'n':len(g),'games':int(g.game_id.nunique()),'control_loss':float(base.mean()),'fpds_loss':float(fp.mean()),'paired':delta,
             'structural_rows':int(g.structural.notna().sum()),'four_member_fallback_rows':int(g.structural.isna().sum()),
             'fpds_missing_all_rows':int(g.fpds_nonmissing_features.eq(0).sum()),'member_losses':{}}
        for arm in ['base','fpds']:
            for key in KEYS:row['member_losses'][arm+'_'+key]=float(loss_rows(stat,g.actual,g[arm+'_'+key]).mean())
        if stat=='anytime_td':
            row['log_loss_delta']=clustered_difference(g.game_id,
                -(g.actual*np.log(np.clip(g.fpds,1e-8,1-1e-8))+(1-g.actual)*np.log(np.clip(1-g.fpds,1e-8,1-1e-8)))+
                (g.actual*np.log(np.clip(g.base,1e-8,1-1e-8))+(1-g.actual)*np.log(np.clip(1-g.base,1e-8,1-1e-8))),2000,20261020)
            row['reliability']={a:metrics.calibration_table(g.actual,g[a]).to_dict('records') for a in ['base','fpds']}
        if stat in ('rec_yds','rush_yds'):
            row['quantile_head_diagnostics']={}
            for q in [.1,.5,.9]:
                losses={a:np.maximum(q*(g.actual-g[f'{a}_head_q{int(q*100)}']),(q-1)*(g.actual-g[f'{a}_head_q{int(q*100)}'])) for a in ['base','fpds']}
                row['quantile_head_diagnostics'][str(q)]=clustered_difference(g.game_id,losses['fpds']-losses['base'],2000,20261020)
            row['head_interval_coverage']={a:float((g.actual.ge(g[f'{a}_head_q10'])&g.actual.le(g[f'{a}_head_q90'])).mean()) for a in ['base','fpds']}
        for table in groups:
            d=clustered_difference(g.game_id,loss_rows(stat,g.actual,g['permuted_'+table])-fp,2000,20261020)
            importance.append({'stat':stat,'table':table,'metric':row['metric'],'paired':d,'tentative_useful':bool(d['ci95'][0]>0)})
        results.append(row)
    ranked=sorted(range(len(results)),key=lambda i:results[i]['paired']['p_improvement_one_sided']);previous=0.
    for rank,i in enumerate(ranked):
        row=results[i];previous=max(previous,min(1.,row['paired']['p_improvement_one_sided']*(4-rank)));row['holm_p']=previous
        row['passes_metric_gate']=bool(row['games']>=200 and row['n']>=300 and row['paired']['difference']<=-.01*row['control_loss'] and row['paired']['ci95'][1]<0 and previous<.05)
        complete=not structural_errors and row['four_member_fallback_rows']==0
        row['passes_full_ensemble_gate']=bool(row['passes_metric_gate'] and complete)
        row['decision']='Challenger: development only; confirmation pending' if row['passes_full_ensemble_gate'] else 'Rejected full-ensemble gate; diagnostic only'
    result={'experiment':'Amendment4 FPDS incremental value','training_seasons':list(TRAIN),'development_season':DEV,'confirmation_season':2024,'confirmation_status':'PENDING; not run','untouched_modeling_season':2025,
            'primary':results,'table_permutation':importance,'structural_errors':structural_errors,'status':'Shadow development only; no promotion',
            'asof_limitation':'Historical weekly inputs reconstructed from earlier source games; 2026 retrieval is not proof of original publication/version timestamps. Strict observation-aware historical view is unavailable.',
            'quantile_scope':'Fixed learned quantile-head diagnostic, not the full ensemble mixture interval; never substituted for a primary metric.'}
    I.write_once(out/'RESULTS.json',result);return result


def run(base_path,deadline):
    registration=check_registration();deadline_check(deadline,4500)
    imported=I.latest();source=Path(imported['directory'])
    if set(imported['tables'])!=set(I.FEATURE_FIELDS):raise ValueError('Six predeclared weekly table families required; inspect metadata-only inventory')
    out=I.CACHE/'research'/('dev2023_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));out.mkdir(parents=True,exist_ok=False)
    I.write_once(out/'PLAN.json',{'created_at':I.utc(),'preregistration_sha256':registration,'implementation_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=LAB_ROOT,text=True).strip(),
       'base_path':str(base_path),'base_sha256':I.sha(base_path),'import_revision':imported['revision'],'train':list(TRAIN),'dev':DEV,'confirmation':'pending','modeling_holdout':2025,'deadline':str(deadline)})
    frame=pd.read_parquet(base_path,filters=[('season','in',[2021,2022,2023])])
    if set(frame.season)!={2021,2022,2023} or frame.duplicated(['game_id','pid']).any():raise ValueError('Unsafe base feature rows')
    valid=frame.history_last_season.notna()
    if not ((frame.loc[valid,'history_last_season']<frame.loc[valid,'season'])|((frame.loc[valid,'history_last_season']==frame.loc[valid,'season'])&(frame.loc[valid,'history_last_week']<frame.loc[valid,'week']))).all():raise ValueError('Base feature history not strictly earlier')
    tables={t:pd.read_parquet(source/(t+'.parquet'),filters=[('season','in',[2021,2022,2023])]) for t in imported['tables']}
    joined=I.asof_features(frame,tables)
    groups={t:[c for c in info['features'] if c in joined] for t,info in imported['tables'].items()}
    groups={t:c for t,c in groups.items() if c};columns=sorted({c for cols in groups.values() for c in cols})
    if len(groups)!=6 or not columns:raise ValueError('Fixed FPDS feature groups incomplete')
    I.write_once(out/'FEATURES.json',{'groups':groups,'columns':columns,'coverage_counts':{c:int(joined[c].notna().sum()) for c in columns},'rows':len(joined)})
    print('Private research directory: '+str(out),flush=True)
    import psutil
    fitted=fit_models(joined,columns,out,max(1,psutil.cpu_count()-2),deadline)
    # Only the NFL baseline columns are used in the shared simulator.
    struct,errors=structural(frame,out,deadline)
    result=walk_forward(joined,fitted,struct,columns,groups,out,deadline)
    summary=summarize(result,groups,errors,out)
    print('Completed2023 development;2024 confirmation pending;2025 modeling holdout untouched.',flush=True)
    return out,summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-features',type=Path,required=True);parser.add_argument('--deadline',required=True)
    a=parser.parse_args()
    try:
        out,result=run(a.base_features,a.deadline)
        print('Aggregate metrics saved locally. No raw subscription rows printed.');return 0
    except Exception as exc:
        I.CACHE.mkdir(parents=True,exist_ok=True)
        error=I.CACHE/('RESEARCH_ERROR_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.txt')
        error.write_text(traceback.format_exc(),encoding='utf-8')
        print('FPDS research stopped: '+type(exc).__name__+'; PRIVATE error retained locally; no confirmation/holdout run.',flush=True);return 1


if __name__=='__main__':raise SystemExit(main())
