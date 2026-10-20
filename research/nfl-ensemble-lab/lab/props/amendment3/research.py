"""2022-only pseudo-line and accounting diagnostics; no model selection/refit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from scipy.stats import poisson
from ... import metrics
from ..ensemble.data import OUT
from ..ensemble.research import clustered_difference

YARDS = ("pass_yds", "rush_yds", "rec_yds")
KEY = ["game_id", "pid", "stat"]


def ci(ids, values):
    return clustered_difference(ids, values, seed=20261020)


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)


def rolling_lines(predictions, observations):
    """Changing current/future outcomes cannot change the current pseudo-line."""
    if set(predictions.season) != {2022} or observations.season.gt(2022).any():
        raise ValueError("Development rows must be 2022, histories <=2022")
    d = predictions.copy();d["pseudo_line"] = np.nan;d["prior_games"] = 0
    groups = {pid:z for pid,z in observations.groupby("pid")}
    for index,r in d.iterrows():
        if r.stat == "anytime_td":
            d.loc[index,"pseudo_line"] = .5
            continue
        h = groups.get(r.pid)
        if h is None or r.stat not in h:
            continue
        h = h[(h.season < r.season) | ((h.season == r.season) & (h.week < r.week))]
        values = h[r.stat].dropna()
        d.loc[index,"prior_games"] = len(values)
        if len(values) >= 3:
            d.loc[index,"pseudo_line"] = np.floor(float(values.median())*2+.5)/2
    return d


def probability(mean, line, stat, residuals=None):
    if stat == "anytime_td":
        return float(mean if line < 1 else 0.)
    if stat not in YARDS:
        return float(poisson.sf(np.floor(line), max(mean,1e-6)))
    return float(np.mean(mean+residuals>line))


def pseudo_diagnostics(predictions, observations, destination):
    d = rolling_lines(predictions, observations)
    rows=[]
    for stat,g in d.groupby("stat"):
        for week,z in g.groupby("week"):
            h=g[g.week.lt(week)].dropna(subset=["actual","equal"])
            if stat in YARDS and len(h)<100:
                continue
            residuals=(h.actual-h.equal).to_numpy(float);residuals-=residuals.mean() if len(residuals) else 0.
            for r in z.dropna(subset=["pseudo_line","actual","equal"]).itertuples():
                median = r.q50 if stat in YARDS else (float(poisson.ppf(.5,max(r.equal,1e-6))) if stat!="anytime_td" else float(r.equal>=.5))
                for label,line in (("rolling_pseudo_line",r.pseudo_line),("model_mean",r.equal),("model_median",median)):
                    if not np.isfinite(line):
                        continue
                    p=probability(r.equal,line,stat,residuals)
                    rows.append({"game_id":r.game_id,"pid":r.pid,"stat":stat,"week":int(week),"threshold":label,"line":float(line),"actual_over":int(r.actual>line),"p_over":p,"p_push":float(np.mean(r.equal+residuals==line)) if stat in YARDS else float(poisson.pmf(line,max(r.equal,1e-6))) if stat!="anytime_td" and line==int(line) else 0.,"history_rows":len(h),"nominal_continuous_median_tail":.5 if stat in YARDS and label=="model_median" else None})
    result=[];data=pd.DataFrame(rows)
    for (stat,threshold),g in data.groupby(["stat","threshold"]):
        bias=ci(g.game_id,g.actual_over-g.p_over)
        row={"stat":stat,"threshold":threshold,"n":len(g),"games":g.game_id.nunique(),"average_probability":float(g.p_over.mean()),"observed_frequency":float(g.actual_over.mean()),"bias":bias,"brier":metrics.brier(g.actual_over,g.p_over),"reliability":metrics.calibration_table(g.actual_over,g.p_over).to_dict("records"),"source":"earlier-week centered OOF residuals" if stat in YARDS else "Poisson approximation" if stat!="anytime_td" else "frozen equal binary probability"}
        row["adequate_diagnostic"] = bool(row["games"]>=100 and abs(bias["difference"])<=.05 and bias["ci95"][0]<=0<=bias["ci95"][1])
        if stat in YARDS and threshold=="model_median":
            row["observed_minus_nominal_half"]=ci(g.game_id,g.actual_over-.5)
        result.append(row)
    data.to_parquet(destination/"pseudo_lines2022.parquet",index=False)
    value={"results":result,"scope":"Synthetic rolling player medians; no real prop lines or market-performance claim. Quantiles are saved quantile-head outputs, not mixture medians."}
    save(destination/"pseudo_calibration.json",value)
    return value


def allocate(values, structural_values, team_total):
    values=np.maximum(np.asarray(values,float),0.)
    structural_values=np.maximum(np.asarray(structural_values,float),0.)
    if not np.isfinite(team_total) or team_total<0:
        raise ValueError("Team total unavailable")
    other_fraction=max(0.,1.-structural_values.sum()/team_total) if team_total else 0.
    eligible_total=team_total*(1-other_fraction)
    if values.sum()==0:
        return np.zeros(len(values)),team_total,0.
    scale=eligible_total/values.sum()
    reconciled=values*scale;other=max(0.,team_total-reconciled.sum())
    return reconciled,other,scale


def scale_scorers(probabilities, target, other):
    p=np.clip(np.asarray(probabilities,float),0.,1.);desired=target-other
    if desired < -1e-8 or desired>np.count_nonzero(p)+1e-8:
        raise ValueError("Infeasible expected-distinct-scorer target")
    if desired<=0:
        return np.zeros(len(p))
    lo,hi=0.,1.
    while np.minimum(hi*p,1.).sum()<desired-1e-10:
        hi*=2
        if hi>1e15:raise ValueError("Cannot allocate scorer mass")
    for _ in range(100):
        mid=(lo+hi)/2
        if np.minimum(mid*p,1.).sum()<desired:lo=mid
        else:hi=mid
    return np.minimum(hi*p,1.)


def reconcile(predictions, structural, totals, include_unmatched=False):
    d=predictions.merge(structural[KEY+["mean"]].rename(columns={"mean":"structural_mean"}),on=KEY,validate="one_to_one",how="left" if include_unmatched else "inner")
    d['structural_eligibility_missing']=d.structural_mean.isna()
    d["reconciled"]=np.nan;team_rows=[];errors=[]
    for (gid,team,stat),g in d.groupby(["game_id","team","stat"]):
        t=totals.get(gid,{}).get(team,{})
        target=t.get(stat)
        if target is None:
            errors.append({"game_id":gid,"team":team,"stat":stat,"reason":"all-player structural total missing"});continue
        try:
            if stat=="anytime_td":
                other=max(0.,target-g.structural_mean.sum())
                transformed=scale_scorers(g.equal,target,other);scale=np.nan
            else:
                transformed,other,scale=allocate(g.equal,g.structural_mean.fillna(0),target)
            assert abs(transformed.sum()+other-target)<=1e-8
            d.loc[g.index,"reconciled"]=transformed
            d.loc[g.index,'reconciliation_coverage']='assumption: incomplete structural eligibility' if g.structural_eligibility_missing.any() else 'matched structural scope'
            for q in ("q10","q50","q90"):
                if q in d and stat in YARDS:
                    d.loc[g.index,"reconciled_"+q]=np.maximum(g[q].to_numpy(float),0.)*scale
            team_rows.append({"game_id":gid,"team":team,"stat":stat,"team_total":target,"original_eligible_sum":float(g.equal.sum()),"reconciled_eligible_sum":float(transformed.sum()),"other_players_projection":float(other),"remainder_fraction":float(other/max(target,1e-12)),"structural_missing_rows":int(g.structural_eligibility_missing.sum()),"remainder_basis":"other/unresolved structural eligibility mass; missing members are not zero-volume evidence" if g.structural_eligibility_missing.any() else "structural other-player mass","definition":"expected distinct scorers" if stat=="anytime_td" else "simulated team total"})
        except ValueError as exc:
            errors.append({"game_id":gid,"team":team,"stat":stat,"reason":str(exc)})
    return d,pd.DataFrame(team_rows),errors


def pinball(y,quantiles):
    error=np.asarray(y)[:,None]-np.asarray(quantiles)
    tau=np.asarray([.1,.5,.9])
    return np.maximum(tau*error,(tau-1)*error).mean(1)


def accounting_scores(d,primary=True):
    results=[]
    for stat in (*YARDS,"anytime_td"):
        g=d[d.stat.eq(stat)].dropna(subset=["reconciled","equal","actual"])
        if g.empty:
            continue
        y=g.actual.to_numpy(float)
        for metric in (("mae","pinball") if stat in YARDS else ("brier","log_loss")):
            if metric=="mae":delta=abs(g.reconciled-y)-abs(g.equal-y)
            elif metric=="pinball":delta=pinball(y,g[["reconciled_q10","reconciled_q50","reconciled_q90"]])-pinball(y,g[["q10","q50","q90"]])
            elif metric=="brier":delta=(g.reconciled-y)**2-(g.equal-y)**2
            else:
                a=np.clip(g.reconciled,1e-6,1-1e-6);b=np.clip(g.equal,1e-6,1-1e-6)
                delta=-y*np.log(a)-(1-y)*np.log(1-a)+y*np.log(b)+(1-y)*np.log(1-b)
            results.append({"stat":stat,"metric":metric,"comparison":ci(g.game_id,delta)})
    if not primary:
        return [r|{'decision':'descriptive full-scope supplement; matched primary gates unchanged'} for r in results]
    tests={(r["stat"],r["metric"]):r for r in results}
    slots=[tests.get((s,m)) for s in (*YARDS,"anytime_td") for m in (("mae","pinball") if s in YARDS else ("brier","log_loss"))]
    order=sorted(range(8),key=lambda i:slots[i]["comparison"].get("p_improvement_one_sided",1) if slots[i] else 1)
    maximum=0.
    for rank,i in enumerate(order):
        if slots[i] is None:continue
        r=slots[i];c=r["comparison"];maximum=max(maximum,min(1.,c.get("p_improvement_one_sided",1)*(8-rank)))
        r["holm_p"]=maximum
        r["passes_metric_gate"]=bool(c["games"]>=100 and c["ci95"][1]<0 and maximum<.05)
    for r in results:
        r["decision"]="Challenger diagnostic only" if all(z["passes_metric_gate"] for z in results if z["stat"]==r["stat"]) and sum(z["stat"]==r["stat"] for z in results)==2 else "Rejected"
    return results


def run(destination, deadline=None):
    destination.mkdir(parents=True,exist_ok=False)
    predictions=pd.read_parquet(OUT/"dev_predictions.parquet")
    assert set(predictions.season)=={2022}
    errors=[]
    try:
        observations=pd.read_parquet(OUT/"observations_allowed.parquet",filters=[("season","<=",2022)])
        pseudo_diagnostics(predictions,observations,destination)
    except Exception as exc:
        errors.append({"phase":"A","error":repr(exc)});print('FAILED pseudo-line diagnostic',repr(exc),flush=True)
    try:
        from ..ensemble import structural as S
        recovered=destination/"structural_recovery";recovered.mkdir()
        for name in ("features.parquet","simulator_tables_through_2021.joblib"):
            shutil.copy2(OUT/name,recovered/name)
        anchors={}
        for p in (OUT/"structural_dev2022").glob("*.json"):
            if p.name=="errors.json":continue
            j=json.loads(p.read_text());m=next(v for v in j["games"] if v["member"]=="sim_independent")
            anchors[j["game_id"]]=m["anchor_points"]
            if j["n_sims"]!=1000:raise ValueError('Saved simulation count differs from preregistered recovery count')
        old=S.OUT;S.OUT=recovered
        try:S.run(2022,n_sims=1000,deadline=deadline,anchor_overrides=anchors,log=lambda s:print(s,flush=True))
        finally:S.OUT=old
        structural=[];totals={}
        for p in (recovered/"structural_dev2022").glob("*.parquet"):
            g=pd.read_parquet(p);g=g[g.member.eq("sim_independent")]
            original=pd.read_parquet(OUT/"structural_dev2022"/p.name);original=original[original.member.eq("sim_independent")]
            matched=g.merge(original[KEY+["mean"]],on=KEY,suffixes=("","_old"),validate="one_to_one")
            if len(matched)!=len(g) or not np.allclose(matched["mean"],matched.mean_old,rtol=0,atol=1e-9):
                errors.append({"game_id":p.stem,"phase":"BC","error":"regenerated means differ; game blocked"});continue
            structural.append(g)
            j=json.loads(p.with_suffix('.json').read_text())
            totals[p.stem]=next(v['team_totals'] for v in j['games'] if v['member']=='sim_independent')
        if not structural:raise ValueError('No identical regenerated structural games')
        d,teams,blocked=reconcile(predictions,pd.concat(structural,ignore_index=True),totals)
        errors+=blocked
        d.to_parquet(destination/'accounting2022.parquet',index=False);teams.to_csv(destination/'other_players2022.csv',index=False)
        save(destination/'accounting2022.json',{'results':accounting_scores(d),'reliability_atd':[{"method":method,"bins":metrics.calibration_table(z.actual,z[method]).to_dict('records')} for method in ('equal','reconciled') for z in [d[d.stat.eq('anytime_td')].dropna(subset=[method])]],'scope':'Shadow only. Distinct-scorer target, explicit other-player mass. No 2026 selection.'})
    except Exception as exc:
        errors.append({'phase':'BC','error':repr(exc)});print('FAILED accounting diagnostic',repr(exc),flush=True)
    save(destination/'errors.json',errors)
    print(json.dumps({'destination':str(destination),'errors':len(errors)}),flush=True)


if __name__=='__main__':
    import psutil,os
    process=psutil.Process();process.nice(psutil.IDLE_PRIORITY_CLASS);process.cpu_affinity(list(range(psutil.cpu_count()-2)))
    os.environ['OMP_NUM_THREADS']=str(psutil.cpu_count()-2)
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--deadline');a=p.parse_args()
    run(a.directory,a.deadline)
