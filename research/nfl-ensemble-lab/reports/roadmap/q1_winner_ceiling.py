"""Checklist step: entropy ceiling and market calibration for game winners (read-only, archived Kalshi quotes).
Market price used = last hourly mid with ts <= kickoff - LAG hours (conservative whichever way the candle stamp is read).
No sportsbook closing lines are used."""
import json, sys
import numpy as np, pandas as pd
LAG=float(sys.argv[1]) if len(sys.argv)>1 else 2.0
k=pd.read_parquet("data/cache/homewin_deep/kalshi_history.parquet")
g=pd.read_parquet("data/cache/games.parquet")[["game_id","season","week","completed","tie","home_win","margin"]].rename(columns={"game_id":"gid"})
k=k[k.ts<=k.kickoff_utc-pd.Timedelta(hours=LAG)]
last=k.sort_values("ts").groupby(["gid","side"]).tail(1).pivot(index="gid",columns="side",values="mid").dropna()
last["p"]=last.home/(last.home+last.away)
d=g.merge(last[["p"]],left_on="gid",right_index=True)
d=d[(d.completed==True)&(~d.tie.astype(bool))].copy(); d["y"]=d.home_win.astype(float)
p=d.p.clip(0.01,0.99).values; y=d.y.values
ll=lambda p,y:-(y*np.log(p)+(1-y)*np.log(1-p))
H=lambda p:-(p*np.log(p)+(1-p)*np.log(1-p))
d["ll"]=ll(p,y); d["H"]=H(p); d["gap"]=d.ll-d.H
d["wk"]=d.season.astype(str)+"_"+d.week.astype(str)
# block bootstrap by week
rng=np.random.default_rng(0); wk=d.groupby("wk").gap.agg(["sum","count"])
B=[ (lambda i:(wk["sum"].values[i].sum()/wk["count"].values[i].sum()))(rng.integers(0,len(wk),len(wk))) for _ in range(5000)]
# calibration: logistic y ~ a + b*logit(p)
def logit_fit(X,y):
    b=np.zeros(X.shape[1])
    for _ in range(50):
        mu=1/(1+np.exp(-X@b)); W=mu*(1-mu); H_=X.T@(X*W[:,None]); step=np.linalg.solve(H_,X.T@(y-mu)); b=b+step
        if np.abs(step).max()<1e-10: break
    return b,np.sqrt(np.diag(np.linalg.inv(H_)))
lg=np.log(p/(1-p)); bb,se=logit_fit(np.column_stack([np.ones(len(lg)),lg]),y)
out=dict(lag_hours=LAG,n_games=int(len(d)),seasons=d.season.value_counts().sort_index().to_dict(),
 realized_log_loss=float(d.ll.mean()),entropy_ceiling=float(d.H.mean()),gap=float(d.gap.mean()),
 gap_ci95=[float(np.percentile(B,2.5)),float(np.percentile(B,97.5))],
 brier=float(((p-y)**2).mean()),home_win_rate=float(y.mean()),
 mz_logit_intercept=float(bb[0]),mz_logit_slope=float(bb[1]),mz_se=[float(x) for x in se],
 mz_slope_ci95=[float(bb[1]-1.96*se[1]),float(bb[1]+1.96*se[1])])
# same games, walk-forward Elo (only where available)
w=pd.read_parquet("data/cache/homewin_deep/walk_forward.parquet")[["gid","p_elo","p_xgb_deep"]]
e=d.merge(w,on="gid")
if len(e):
    out["walk_forward_overlap"]=int(len(e))
    for c in ["p_elo","p_xgb_deep"]: out[c+"_log_loss_same_games"]=float(ll(e[c].clip(.01,.99).values,e.y.values).mean())
    out["market_log_loss_same_games"]=float(e.ll.mean())
json.dump(out,open("reports/roadmap/q1_winner_ceiling.json","w"),indent=1); print(json.dumps(out,indent=1))

# paired differences vs market on the same games (positive = model worse than market), block bootstrap by week
e["wk"]=e.season.astype(str)+"_"+e.week.astype(str)
pair={}
for c in ["p_elo","p_xgb_deep"]:
    e["dl"]=ll(e[c].clip(.01,.99).values,e.y.values)-e.ll.values
    t=e.groupby("wk").dl.agg(["sum","count"]); bs=[(lambda i:t["sum"].values[i].sum()/t["count"].values[i].sum())(rng.integers(0,len(t),len(t))) for _ in range(5000)]
    pair[c]=dict(mean_diff=float(e.dl.mean()),ci95=[float(np.percentile(bs,2.5)),float(np.percentile(bs,97.5))])
out["paired_log_loss_minus_market"]=pair
json.dump(out,open("reports/roadmap/q1_winner_ceiling.json","w"),indent=1); print(json.dumps(pair,indent=1))
