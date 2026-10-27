"""Same-field distribution, tail, covariance and overlapping-leader diagnostics."""
import math
import numpy as np

from scripts.king_court.simulation import leader_summary


def crps(samples,truth):
    x=np.sort(np.asarray(samples),axis=0)
    n=len(x)
    factor=(2*np.arange(1,n+1)-n-1)
    if x.ndim==2:
        factor=factor[:,None]
    return np.mean(abs(x-truth),axis=0)-np.sum(factor*x,axis=0)/(n*n)


def correlation(cov):
    d=np.sqrt(np.maximum(0,np.diag(cov)))
    den=np.outer(d,d)
    return np.divide(cov,den,out=np.zeros_like(cov),where=den>1e-12)


def evaluate(samples,slate,profiles):
    ids=samples['player_ids']
    if set(ids)!=set(slate['outcomes']):
        raise ValueError('Incomplete paired diagnostic field')
    actual=np.array([[slate['outcomes'][pid][k] for k in ('points','rebounds','assists')] for pid in ids])
    y=actual.sum(axis=1)
    pra=samples['pra'];n=len(pra)
    leaders,_=leader_summary(pra)
    actual_leaders=y==y.max()
    actual_sole=actual_leaders&(actual_leaders.sum()==1)
    actual_tied=actual_leaders&(actual_leaders.sum()>1)
    means=pra.mean(axis=0);var=pra.var(axis=0,ddof=1)
    q=np.quantile(pra,[.1,.9,.95],axis=0)
    scores=crps(pra,y)
    rows=[]
    cov_sum=np.zeros((3,3));residuals=[]
    for j,(pid,p) in enumerate(zip(ids,profiles)):
        comp=np.stack([samples[k][:,j] for k in ('points','rebounds','assists')],axis=1)
        cov=np.cov(comp,rowvar=False)
        cov_sum+=cov
        delta=actual[j]-comp.mean(axis=0)
        residuals.append(delta.tolist())
        lp=leaders[j]['inclusive_leader_probability']
        clipped=float(np.clip(lp,.5/n,1-.5/n))
        avg=p.get('season_average_pra');simple=p.get('point_minutes_rate',p['minutes_mean']*p.get('weighted_pra_per_minute',0))
        rows.append(dict(player_id=pid,experience=p['experience'],role_change=p.get('role_change','unknown'),
                         actual=int(y[j]),mean=float(means[j]),variance=float(var[j]),mae=float(abs(means[j]-y[j])),crps=float(scores[j]),
                         coverage80=bool(q[0,j]<=y[j]<=q[1,j]),above_q90=bool(y[j]>q[1,j]),above_q95=bool(y[j]>q[2,j]),
                         standardized_squared_error=float((y[j]-means[j])**2/max(1e-8,var[j])),
                         inclusive_leader_probability=lp,actual_leader=int(actual_leaders[j]),
                         leader_brier=float((lp-actual_leaders[j])**2),
                         sole_brier=float((leaders[j]['sole_leader_probability']-actual_sole[j])**2),
                         tied_brier=float((leaders[j]['tied_leader_probability']-actual_tied[j])**2),
                         leader_log_loss=float(-int(actual_leaders[j])*math.log(clipped)-(1-int(actual_leaders[j]))*math.log(1-clipped)),
                         leader_mc_se=leaders[j]['monte_carlo_se']['inclusive_leader_probability'],
                         q90_exceedance_probability=float(np.mean(pra[:,j]>q[1,j])),
                         q90_mc_se=float(math.sqrt(np.mean(pra[:,j]>q[1,j])*(1-np.mean(pra[:,j]>q[1,j]))/n)),
                         mean_mc_se=float(math.sqrt(var[j]/n)),season_average_error=abs(avg-y[j]) if avg is not None else None,
                         minutes_rate_error=float(abs(simple-y[j])),evidence=p['evidence'],prior=p.get('prior',{})))
    pair_stats={label:[] for label in ('teammate','opponent')}
    empirical={label:[] for label in pair_stats}
    for i,p in enumerate(profiles):
        for j in range(i):
            other=profiles[j]
            if p['game_id']!=other['game_id'] or var[i]<=0 or var[j]<=0:
                continue
            label='teammate' if p['team']==other['team'] else 'opponent'
            value=float(np.mean((pra[:,i]-means[i])*(pra[:,j]-means[j]))/math.sqrt(var[i]*var[j]))
            pair_stats[label].append(value)
            empirical[label].append(float((y[i]-means[i])*(y[j]-means[j])/math.sqrt(var[i]*var[j])))
    maximum=pra.max(axis=1);observed=int(y.max())
    return dict(date=slate['date'],players=rows,player_games=len(rows),
                mae=float(np.mean([r['mae'] for r in rows])),crps=float(np.mean(scores)),coverage80=float(np.mean([r['coverage80'] for r in rows])),
                q90_exceedance=float(np.mean([r['above_q90'] for r in rows])),q95_exceedance=float(np.mean([r['above_q95'] for r in rows])),
                mean_variance=float(np.mean(var)),standardized_squared_error=float(np.mean([r['standardized_squared_error'] for r in rows])),
                leader_brier=float(np.mean([r['leader_brier'] for r in rows])),sole_brier=float(np.mean([r['sole_brier'] for r in rows])),
                tied_brier=float(np.mean([r['tied_brier'] for r in rows])),leader_log_loss=float(np.mean([r['leader_log_loss'] for r in rows])),
                simulated_component_covariance=(cov_sum/len(rows)).tolist(),observed_component_residuals=residuals,
                simulated_dependence={k:float(np.mean(v)) if v else None for k,v in pair_stats.items()},
                observed_standardized_pair_products={k:float(np.mean(v)) if v else None for k,v in empirical.items()},
                slate_maximum=dict(observed=observed,mean=float(maximum.mean()),variance=float(maximum.var(ddof=1)),
                                   q10_q90_q95=np.quantile(maximum,[.1,.9,.95]).tolist(),crps=float(crps(maximum,observed)),
                                   above_q90=bool(observed>np.quantile(maximum,.9)),mean_mc_se=float(maximum.std(ddof=1)/math.sqrt(n))))


def aggregate(evaluations):
    if not evaluations:
        return dict(status='no_eligible_slates',slates=0)
    rows=[r for e in evaluations for r in e['players']]
    scalar=('mae','crps','coverage80','q90_exceedance','q95_exceedance','mean_variance','standardized_squared_error',
            'leader_brier','sole_brier','tied_brier','leader_log_loss')
    result={k:float(np.mean([e[k] for e in evaluations])) for k in scalar}
    residual=np.array([r for e in evaluations for r in e['observed_component_residuals']])
    covariance=np.mean([e['simulated_component_covariance'] for e in evaluations],axis=0)
    result.update(slates=len(evaluations),player_games=len(rows),
                  simulated_component_correlation=correlation(covariance).tolist(),
                  observed_residual_component_correlation=correlation(np.cov(residual,rowvar=False)).tolist(),
                  correlation_limit='Observed residual covariance includes mean error and postgame-field conditioning; it is a diagnostic, not a direct estimate of every player conditional covariance.',
                  mean_slate_max_crps=float(np.mean([e['slate_maximum']['crps'] for e in evaluations])),
                  mean_predicted_slate_max=float(np.mean([e['slate_maximum']['mean'] for e in evaluations])),
                  mean_observed_slate_max=float(np.mean([e['slate_maximum']['observed'] for e in evaluations])),
                  slate_max_above_q90=float(np.mean([e['slate_maximum']['above_q90'] for e in evaluations])),
                  mean_inclusive_leader_mc_se=float(np.mean([r['leader_mc_se'] for r in rows])),
                  mean_PRA_mean_mc_se=float(np.mean([r['mean_mc_se'] for r in rows])),
                  simulated_dependence={k:float(np.mean([e['simulated_dependence'][k] for e in evaluations if e['simulated_dependence'][k] is not None])) for k in ('teammate','opponent')},
                  observed_pair_products={k:float(np.mean([e['observed_standardized_pair_products'][k] for e in evaluations if e['observed_standardized_pair_products'][k] is not None])) for k in ('teammate','opponent')})
    result['experience_groups']={}
    for group in ('rookie','second_year','established','unknown'):
        selected=[r for r in rows if r['experience']==group]
        result['experience_groups'][group]=dict(player_games=len(selected),mae=float(np.mean([r['mae'] for r in selected])) if selected else None,
                                               status='insufficient_or_missing_verified_metadata' if len(selected)<20 else 'reused_diagnostic_only')
    result['role_groups']={g:dict(player_games=sum(r['role_change']==g for r in rows),mae=float(np.mean([r['mae'] for r in rows if r['role_change']==g]))) for g in sorted({r['role_change'] for r in rows})}
    result['reliability_bins']=[]
    for lo,hi in ((0,.01),(.01,.05),(.05,.1),(.1,.25),(.25,.5),(.5,1.00001)):
        selected=[r for r in rows if lo<=r['inclusive_leader_probability']<hi]
        if selected:
            result['reliability_bins'].append(dict(lower=lo,upper=min(hi,1),n=len(selected),
                                                  predicted=float(np.mean([r['inclusive_leader_probability'] for r in selected])),actual=float(np.mean([r['actual_leader'] for r in selected]))))
    result['point_baselines']={k:dict(paired_player_games=sum(r[k] is not None for r in rows),
                                    baseline_mae=float(np.mean([r[k] for r in rows if r[k] is not None])) if any(r[k] is not None for r in rows) else None,
                                    model_mae_same_players=float(np.mean([r['mae'] for r in rows if r[k] is not None])) if any(r[k] is not None for r in rows) else None)
                               for k in ('season_average_error','minutes_rate_error')}
    return result


def paired_intervals(original,repaired,seed=271026):
    a={r['date']:r for r in original};b={r['date']:r for r in repaired}
    if set(a)!=set(b):
        raise ValueError('Paired slate dates differ')
    dates=sorted(a)
    if not dates:
        return dict(slates=0,status='no_paired_slates')
    rng=np.random.default_rng(seed)
    indexes=rng.integers(0,len(dates),size=(4000,len(dates)))
    result={}
    for metric in ('mae','crps','coverage80','q90_exceedance','q95_exceedance','leader_brier','sole_brier','tied_brier','leader_log_loss'):
        difference=np.array([b[d][metric]-a[d][metric] for d in dates])
        result[metric]=dict(repair_minus_original=float(difference.mean()),whole_slate_95_interval=np.quantile(difference[indexes].mean(axis=1),[.025,.975]).tolist())
    return dict(slates=len(dates),paired=result,limitations='Reused postgame-field diagnostics; not an untouched evaluation. Whole-slate resampling does not remove longer serial/team dependence.')
