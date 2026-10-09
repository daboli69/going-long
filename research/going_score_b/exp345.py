import pandas as pd, numpy as np
from scipy.stats import spearmanr
pd.set_option('display.width',250)
d=pd.read_parquet('panel.parquet'); d=d[d.n_prior>=4]
rng=np.random.default_rng(11)
SETS={
 'S0 xfp_e6+xfp_m16 (shrunk xFP)':['xfp_e6','xfp_m16'],
 'S1 +res_m16':['xfp_e6','xfp_m16','res_m16'],
 'S2 +vol_m8':['xfp_e6','xfp_m16','vol_m8'],
 'S3 +share(tgt,wopr)':['xfp_e6','xfp_m16','target_share_m8','wopr_m8','air_yards_share_m8'],
 'S4 +vegas impl total':['xfp_e6','xfp_m16','IMPL'],
 'S5 +impl+res':['xfp_e6','xfp_m16','res_m16','IMPL'],
 'S6 full composite':['xfp_e6','xfp_m16','res_m16','vol_m8','target_share_m8','wopr_m8','air_yards_share_m8','IMPL'],
 'A0 act_e6 only':['act_e6'],
 'A1 act_e6+act_m16':['act_e6','act_m16'],
}
def fitpred(tr,te,cols,y):
    tr=tr.dropna(subset=cols+[y]); 
    X=np.c_[np.ones(len(tr)),tr[cols].values]; b=np.linalg.lstsq(X,tr[y].values,rcond=None)[0]
    te=te.dropna(subset=cols)
    return te.index, np.c_[np.ones(len(te)),te[cols].values]@b, b
res=[];coefs=[]
for tgt,impl in [('y1','y1_impl'),('y3','y3_impl')]:
  for pos in ['QB','RB','WR','TE']:
    dd=d[(d.position==pos)&d[tgt].notna()].copy(); dd['IMPL']=dd[impl]
    dd=dd.dropna(subset=['xfp_e6','xfp_m16','res_m16','vol_m8','target_share_m8','wopr_m8','air_yards_share_m8','IMPL','act_e6','act_m16'])
    for ev in [2024,2025]:
        tr=dd[dd.season.between(2021,ev-1)]; te=dd[dd.season==ev]
        P={}
        for n,c in SETS.items():
            idx,p,b=fitpred(tr,te,c,tgt); P[n]=pd.Series(p,idx)
            if n.startswith('S6'): coefs.append(dict(target=tgt,pos=pos,test=ev,**dict(zip(['c']+c,b))))
        y=te[tgt]; pid=te.player_id.values; up=np.unique(pid); ix={u:np.where(pid==u)[0] for u in up}
        se0=((P['S0 xfp_e6+xfp_m16 (shrunk xFP)']-y)**2).values
        for n,p in P.items():
            se=((p-y)**2).values
            dm=[]
            for _ in range(400):
                s=rng.choice(len(up),len(up)); ii=np.concatenate([ix[up[k]] for k in s]); dm.append(se[ii].mean()-se0[ii].mean())
            wk=te.assign(p=p).groupby('week').apply(lambda g:spearmanr(g.p,g[tgt])[0] if len(g)>8 else np.nan).mean()
            res.append(dict(target=tgt,pos=pos,test=ev,model=n,n=len(te),r2=1-se.sum()/((y-y.mean())**2).sum(),wk_spearman=wk,
                 dMSE_vs_S0=se.mean()-se0.mean(),lo=np.percentile(dm,2.5),hi=np.percentile(dm,97.5),rel_gain_pct=100*(se0.mean()-se.mean())/se0.mean()))
R=pd.DataFrame(res);R.to_csv('exp5_nested.csv',index=False)
pd.DataFrame(coefs).to_csv('exp3_full_coefs.csv',index=False)
for tgt in ['y1','y3']:
    print('=== rel MSE gain % vs S0 (pos x test) CI sig marked *',tgt)
    R2=R[R.target==tgt].copy(); R2['s']=R2.rel_gain_pct.round(2).astype(str)+np.where((R2.lo>0)|(R2.hi<0),'*','')
    print(R2.pivot_table(index='model',columns=['pos','test'],values='s',aggfunc='first').to_string())
    print(R2[R2.model.str.startswith('S0')][['pos','test','r2','wk_spearman']].round(3).to_string())
print(pd.DataFrame(coefs).round(3).to_string())

# ---- Exp3 correlations among components (player-level means, within position) 
comps=['xfp_m8','res_m8','vol_m8','target_share_m8','wopr_m8','air_yards_share_m8','impl_m8']
for pos in ['QB','RB','WR','TE']:
    dd=d[(d.position==pos)&d.season.between(2021,2025)].dropna(subset=comps)
    print('--- corr',pos); print(dd[comps].corr().round(2).to_string())
    dd[comps].corr().round(3).to_csv(f'exp3_corr_{pos}.csv')
