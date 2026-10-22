"""Strictly prior played-game roles and explicit unknown scenario probabilities."""
import numpy as np
import pandas as pd
from ..fpds_research.features import availability

COLS=['r10_last1','r10_last3','r10_last8','r10_cv','r10_ratio','r10_changed','r10_team_changed','r10_qb_changed','r10_injury_known','r10_out']


def enrich(candidates,observations,games,injuries,asof=None):
    clock=availability(games);obs=observations.copy()
    obs['available_at']=[clock.get((s,w),pd.NaT) for s,w in zip(obs.season,obs.week)]
    obs=obs.dropna(subset=['available_at']).sort_values(['available_at','game_id'])
    obs['usage']=obs.targets+obs.carries+obs.dropbacks
    panels={p:d for p,d in obs.groupby('pid')}
    qb=obs[obs.dropbacks.gt(0)].sort_values('dropbacks').groupby(['game_id','team']).tail(1)
    teams={t:d.sort_values('available_at') for t,d in qb.groupby('team')}
    injuries=injuries.copy();injuries['available_at']=pd.to_datetime(injuries.available_at,utc=True)
    injury_panels={p:d for p,d in injuries.dropna(subset=['gsis_id']).groupby('gsis_id')}
    rows=[];ratios=[]
    for r in candidates.itertuples():
        decision=pd.Timestamp(r.kickoff_utc)
        if asof is not None:decision=min(decision,pd.Timestamp(asof))
        h=panels.get(r.pid,pd.DataFrame())
        if len(h):h=h[h.available_at.lt(decision)].tail(8)
        v=h.usage.to_numpy(float) if len(h) else np.array([])
        one=float(v[-1]) if len(v) else np.nan
        prev=float(np.mean(v[-4:-1])) if len(v)>1 else one
        ratio=one/max(prev,1) if len(v) else 1.
        recent=float(np.mean(v[-3:])) if len(v) else np.nan
        avg=float(v.mean()) if len(v) else np.nan
        change=abs(ratio-1)>.5
        team_change=bool(len(h) and h.team.iloc[-1]!=r.team)
        q=teams.get(r.team,pd.DataFrame())
        if len(q):q=q[q.available_at.lt(decision)].tail(2)
        qb_change=bool(len(q)>=2 and q.pid.iloc[-1]!=q.pid.iloc[-2])
        injury=injury_panels.get(r.pid,pd.DataFrame());known=False;out=False
        if len(injury):
            injury=injury[injury.available_at.lt(decision)&injury.season.eq(r.season)&injury.week.eq(r.week)&injury.team.eq(r.team)]
            if len(injury):known=True;out=str(injury.sort_values('available_at').report_status.iloc[-1]).lower()=='out'
        rows.append([one,recent,avg,float(v.std()/max(avg,1)) if len(v) else np.nan,ratio,int(change),int(team_change),int(qb_change),int(known),int(out)])
        values=np.clip(v/max(avg,1),.25,2) if len(v) else np.ones(1)
        values=values/max(float(values.mean()),1e-9)
        ratios.append(values.tolist())
    result=candidates.reset_index(drop=True).copy()
    result[COLS]=np.asarray(rows,float);result['r10_ratios']=ratios
    return result


def scenario_rows(row):
    ratios=np.asarray(row.r10_ratios,float)
    result=[{'scenario':name,'usage_multiplier':float(v),'occurrence_probability':None,
             'label':'scenario, not forecast; empirical prior workload percentile; replacement remains other players'}
            for name,v in zip(('low_role','base_role','high_role'),np.quantile(ratios,[.1,.5,.9]))]
    if row.r10_out:
        result.append({'scenario':'verified_pregame_out','usage_multiplier':0.,'occurrence_probability':None,
                       'label':'known Out status; zero-usage scenario; market settlement/action not inferred'})
    return result
