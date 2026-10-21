"""Aggregated metrics only; no raw observations, identities or features published."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import poisson
from .common import ROOT, REPORT, LAB_ROOT, SEED, now, read, atomic, write_once, digest
from . import models as M


def paired(frame,family_size=1):
    d=frame.dropna(subset=['delta'])
    group=d.groupby('game_id').delta.agg(['sum','size'])
    if group.empty:return {'n':0,'games':0,'delta':None,'ci95':None,'corrected_ci95':None,'p':1.}
    rng=np.random.default_rng(SEED);sample=rng.integers(0,len(group),(2000,len(group)))
    draws=group['sum'].to_numpy()[sample].sum(1)/group['size'].to_numpy()[sample].sum(1)
    effect=float(d.delta.mean());alpha=.025/max(1,family_size)
    return {'n':len(d),'games':len(group),'delta':effect,'ci95':np.quantile(draws,[.025,.975]).tolist(),
            'corrected_ci95':np.quantile(draws,[alpha,1-alpha]).tolist(),
            'p':float((np.sum(draws-effect<=effect)+1)/2001),'family_tests':family_size,
            'tail_resolution_warning':alpha<1/2000}


def diagnostics(d,stat):
    if d.empty:return {}
    y=d.actual.to_numpy(float);p=d.pred.to_numpy(float)
    out={'n':len(d),'games':int(d.game_id.nunique()),'primary_loss':float(M.loss(stat,y,p).mean())}
    if M.binary(stat):
        q=np.clip(p,1e-9,1-1e-9)
        out['log_loss']=float(np.mean(-y*np.log(q)-(1-y)*np.log1p(-q)))
        bins=[]
        for low in np.arange(0,1,.1):
            mask=(p>=low)&(p<low+.1)
            if mask.any():bins.append({'low':float(low),'n':int(mask.sum()),'predicted':float(p[mask].mean()),'observed':float(y[mask].mean())})
        out['reliability']=bins
    else:
        out['mae']=float(np.mean(abs(y-p)));out['rmse']=float(np.sqrt(np.mean((y-p)**2)))
        if 'crps' in d:out['crps_empirical_residual']=float(d.crps.mean())
        if stat in ('rec','pass_tds'):out['poisson_log_loss']=float(-poisson.logpmf(y,np.maximum(p,1e-9)).mean())
        if 'q10' in d:
            out['interval80_coverage']=float(np.mean((y>=d.q10)&(y<=d.q90)))
            out['pinball']={str(q):float(np.maximum(q*(y-d[c]),(q-1)*(y-d[c])).mean()) for q,c in ((.1,'q10'),(.5,'q50'),(.9,'q90'))}
            # Three-quantile approximation only; not exact continuous CRPS.
            out['crps_three_quantile_approx']=2*float(np.mean(list(out['pinball'].values())))
        if 'pseudo_line' in d:
            mask=d.pseudo_line.notna().to_numpy();line=d.pseudo_line.to_numpy(float)
            if stat in ('rec','pass_tds'):over=poisson.sf(np.floor(line),np.maximum(p,1e-6))
            else:
                from scipy.stats import norm
                scale=np.maximum((d.q90-d.q10).to_numpy()/2.563,1)
                over=norm.sf((line-p)/scale)
            actual=(y>line).astype(float)
            out['pseudo_line_brier']=float(np.mean((over[mask]-actual[mask])**2)) if mask.any() else None
            out['above_mean_fraction']=float((y>p).mean());out['above_median_fraction']=float((y>d.q50.to_numpy()).mean())
    return out


def results(directory,phase='discovery'):
    from .walkforward import completed_blocks
    protocol=read(LAB_ROOT/'docs/FPDS_AMENDMENT6_TRIALS.json')
    specs=protocol['trials'];seasons={'discovery':[2022,2023,2024],'validation':[2025],'descriptive':[2026]}[phase]
    family_size={f:sum(x['family']==f and x['arm']!='control' for x in specs) for f in {x['family'] for x in specs}}
    rows=[];ledger=read(Path(directory)/'LEDGER.json')
    for s in specs:
        if s['arm']=='control':continue
        d=completed_blocks(directory,s);control=s|{'id':f"{s['stat']}__control__all__linear"}
        b=completed_blocks(directory,control)
        if d.empty or b.empty:continue
        d=d[d.season.isin(seasons)];b=b[b.season.isin(seasons)]
        if d.empty:continue
        keys=['game_id']+(['pid'] if 'pid' in d else [])
        j=d.merge(b[keys+['pred','loss']],on=keys,suffixes=('','_control'),validate='one_to_one')
        if j.empty:continue
        j['delta']=j.loss-j.loss_control
        r=dict(configuration=s,**paired(j,family_size[s['family']]),
               control_loss=float(j.loss_control.mean()),new_loss=float(j.loss.mean()),
               seasons_agreeing=int(sum(z.delta.mean()<0 for _,z in j.groupby('season'))),
               by_season={str(year):{'n':len(z),'delta':float(z.delta.mean())} for year,z in j.groupby('season')},
               identical_sample=len(j)==len(b),diagnostics=diagnostics(j,s['stat']) if s['stat']!='first_td' else {'brier':float(j.brier.mean())})
        r['relative_reduction']=-r['delta']/max(r['control_loss'],1e-12)
        r['run_status']=ledger.get(s['id'],{}).get('status','unknown')
        # Table removal and model-family comparisons also retain the full-feature linear reference.
        reference=s|{'id':f"{s['stat']}__all__all__linear"}
        full=completed_blocks(directory,reference)
        if len(full) and s['id']!=reference['id']:
            full=full[full.season.isin(seasons)]
            extra=j.merge(full[keys+['loss']],on=keys,suffixes=('','_full'),validate='one_to_one')
            if len(extra):
                extra['delta']=extra.loss-extra.loss_full
                r['vs_full_feature_linear']=paired(extra,family_size[s['family']])
        rows.append(r)
    for family in family_size:
        group=sorted([r for r in rows if r['configuration']['family']==family],key=lambda x:x['p'])
        running=0.
        for i,r in enumerate(group):
            # Failed/unavailable registered slots still consume multiplicity budget.
            running=max(running,min(1.,r['p']*(family_size[family]-i)));r['holm_p']=running
    for r in rows:
        stat=r['configuration']['stat']
        r['discovery_gate']=bool(phase=='discovery' and r['games']>=200 and (r['n']>=300 or stat in ('margin','total','win','first_td')) and
            r['run_status']=='complete' and r['identical_sample'] and r['relative_reduction']>=.01 and r['corrected_ci95'][1]<0 and r['holm_p']<.05 and r['seasons_agreeing']>=2 and
            r['configuration']['model']!='distribution')
    return rows


def freeze(directory,rows):
    protocol=read(LAB_ROOT/'docs/FPDS_AMENDMENT6_TRIALS.json');selection=[]
    for stat in ('rec','rec_yds','rush_yds','anytime_td','pass_yds','pass_tds','margin','total','win','first_td'):
        candidates=[r for r in rows if r['configuration']['stat']==stat and r['discovery_gate'] and r['configuration']['model']!='blend']
        if candidates:chosen=min(candidates,key=lambda x:x['new_loss'])['configuration']
        else:chosen=next(x for x in protocol['trials'] if x['stat']==stat and x['arm']=='control')
        selection.append(chosen)
    value={'created_at':now(),'configurations':selection,'selection':'discovery only; control where no full gate passed',
           'market_informed_configurations':[r['configuration'] for r in rows if r['configuration']['model']=='blend' and r['discovery_gate']],
           'validation_warning':'2025 previously examined for old simulator; one pass, no changes',
           'trial_count':len(read(directory/'LEDGER.json')),'research_path':str(directory)}
    dest=LAB_ROOT/'docs/FPDS_AMENDMENT6_FROZEN.json'
    if dest.exists():
        previous=read(dest)
        if previous['configurations']!=selection:raise ValueError('Frozen config already exists; cannot reselect')
        return previous
    write_once(dest,value)
    return value


def frozen(directory):
    import subprocess
    dest=LAB_ROOT/'docs/FPDS_AMENDMENT6_FROZEN.json'
    if not dest.exists():raise ValueError('Discovery selection not frozen')
    rel=subprocess.check_output(['git','ls-files','--full-name',str(dest)],cwd=LAB_ROOT,text=True).strip()
    if not rel:raise ValueError('Commit frozen selection BEFORE validation')
    blob=subprocess.check_output(['git','show','HEAD:'+rel],cwd=LAB_ROOT).decode('utf-8').replace('\r\n','\n')
    if blob!=dest.read_text(encoding='utf-8'):raise ValueError('Frozen selection differs from commit')
    result=read(dest)
    if result['research_path']!=str(directory):raise ValueError('Frozen selection belongs to a different data/code fingerprint')
    return result


def run():
    directory=Path(read(ROOT/'LATEST_RESEARCH.json')['path'])
    rows=results(directory)
    atomic(REPORT/'FPDS_A6_DISCOVERY.json',{'created_at':now(),'research_path':str(directory),'rows':rows})
    if (directory/'DISCOVERY_COMPLETE.json').exists():freeze(directory,rows)
    return rows
