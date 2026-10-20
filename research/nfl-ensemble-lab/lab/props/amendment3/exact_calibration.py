"""Descriptive exact weekly-CDF supplement; no new selection or thresholds."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from ... import metrics
from ..ensemble.data import OUT
from ..projections10 import distribution
from .research import rolling_lines,ci,save,pinball,YARDS


def exact_rows(predictions, observations, structural):
    d=rolling_lines(predictions,observations)
    structural_groups={key:z for key,z in structural.groupby(['game_id','pid','stat'])}
    rows=[];quantiles=[]
    for stat,g in d.groupby('stat'):
        for week,z in g.groupby('week'):
            history=predictions[predictions.week.lt(week)]
            if stat in YARDS and len(history[history.stat.eq(stat)].dropna(subset=['equal','actual']))<100:
                continue
            for row in z.dropna(subset=['pseudo_line','actual','equal']).to_dict('records'):
                key=(row['game_id'],row['pid'],stat)
                samples,source=distribution(row,history,structural_groups.get(key,structural.iloc[:0]))
                q=np.maximum(np.quantile(samples,[.1,.5,.9]),0.)
                if stat in YARDS:
                    quantiles.append({k:row[k] for k in ('game_id','pid','team','stat','actual','equal')}|dict(zip(('q10','q50','q90'),q)))
                for name,line in (('rolling_pseudo_line',row['pseudo_line']),('published_mean',row['equal']),('displayed_mixture_median',q[1])):
                    if stat=='anytime_td':
                        p=float(row['equal']) if 0<=line<1 else 1. if line<0 else 0.
                        push=(1-row['equal']) if line==0 else row['equal'] if line==1 else 0.
                    else:
                        p=float((samples>line).mean());push=float((samples==line).mean())
                    rows.append({k:row[k] for k in ('game_id','pid','stat','week')}|{'threshold':name,'line':float(line),'actual_over':int(row['actual']>line),'p_over':p,'p_push':float(push),'source':source,'max_residual_week':int(history.week.max()) if len(history) else None,'binary_median_not_displayed':stat=='anytime_td' and name=='displayed_mixture_median'})
    return pd.DataFrame(rows),pd.DataFrame(quantiles)


def run(destination,accounting):
    destination.mkdir(parents=True,exist_ok=False)
    predictions=pd.read_parquet(OUT/'dev_predictions.parquet')
    observations=pd.read_parquet(OUT/'observations_allowed.parquet',filters=[('season','<=',2022)])
    assert set(predictions.season)=={2022}
    structural=pd.concat([pd.read_parquet(p) for p in (OUT/'structural_dev2022').glob('*.parquet')],ignore_index=True)
    data,q=exact_rows(predictions,observations,structural)
    data.to_parquet(destination/'exact_pseudo2022.parquet',index=False)
    results=[]
    for (stat,threshold),g in data.groupby(['stat','threshold']):
        results.append({'stat':stat,'threshold':threshold,'n':len(g),'games':g.game_id.nunique(),'average_p_over':float(g.p_over.mean()),'observed_frequency':float(g.actual_over.mean()),'bias':ci(g.game_id,g.actual_over-g.p_over),'brier':metrics.brier(g.actual_over,g.p_over),'reliability':metrics.calibration_table(g.actual_over,g.p_over).to_dict('records')})
    save(destination/'exact_calibration.json',{'results':results,'scope':'Exact frozen weekly member mixture, strictly earlier-week 2022 residuals. Binary ATD uses the published analytic probability. Synthetic lines; no market, returns or selection claim. Binary median is an outcome median, not a displayed probability median.'})
    approximate=accounting.parent/'pseudo_lines2022.parquet'
    if approximate.exists():
        original=pd.read_parquet(approximate)
        correction=original[original.stat.eq('anytime_td') & original.line.isin([0.,1.])].merge(predictions[['game_id','pid','stat','equal']],on=['game_id','pid','stat'],validate='many_to_one')
        correction['original_p_push']=correction.p_push
        correction['p_push']=np.where(correction.line.eq(0),1-correction.equal,correction.equal)
        correction=correction[abs(correction.p_push-correction.original_p_push)>1e-12]
        correction.to_parquet(destination/'approximate_push_metadata_correction.parquet',index=False)
        save(destination/'approximate_push_metadata_correction.json',{'rows':len(correction),'scope':'A3-A Bernoulli outcome-median push-mass metadata only. Original file retained. P(over), events, Brier/bias and thresholds unchanged. No forecast file affected.'})
    if accounting.exists():
        a=pd.read_parquet(accounting)
        a=a[a.stat.isin(YARDS)].dropna(subset=['reconciled'])
        scales={}
        for key,z in a.groupby(['game_id','team','stat']):
            denominator=np.maximum(z.equal,0).sum()
            scales[key]=float(z.reconciled.sum()/denominator) if denominator else 0.
        q['scale']=[scales.get((r.game_id,r.team,r.stat),np.nan) for r in q.itertuples()]
        q=q.dropna(subset=['scale'])
        supplemental=[]
        for stat,z in q.groupby('stat'):
            original=z[['q10','q50','q90']].to_numpy(float)
            delta=pinball(z.actual,original*z.scale.to_numpy()[:,None])-pinball(z.actual,original)
            supplemental.append({'stat':stat,'metric':'displayed mixture pinball','comparison':ci(z.game_id,delta),'decision':'descriptive supplement; original quantile-head primary gate unchanged'})
        q.to_parquet(destination/'mixture_quantiles2022.parquet',index=False)
        save(destination/'mixture_pinball.json',{'results':supplemental})
    print('Exact-CDF diagnostic saved:',destination,flush=True)


if __name__=='__main__':
    import psutil,os
    psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS);psutil.Process().cpu_affinity(list(range(psutil.cpu_count()-2)))
    os.environ['OMP_NUM_THREADS']=str(psutil.cpu_count()-2)
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--accounting',type=Path,required=True);a=p.parse_args()
    run(a.directory,a.accounting)
