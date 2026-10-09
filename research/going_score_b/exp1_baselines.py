import pandas as pd, numpy as np, json
d=pd.read_parquet('panel.parquet')
rng=np.random.default_rng(7)
d['pos']=d.position
d['hasprior']=d.n_prior>=4
# models: name -> feature list (None = raw single feature, no fit)
M={
 'act_m3':['act_m3'],'act_m8':['act_m8'],'act_m16':['act_m16'],
 'act_e1.5':['act_e1.5'],'act_e3':['act_e3'],'act_e6':['act_e6'],
 'xfp_m3':['xfp_m3'],'xfp_m8':['xfp_m8'],'xfp_m16':['xfp_m16'],'xfp_e3':['xfp_e3'],'xfp_e6':['xfp_e6'],
}
F={ # fitted OLS models
 'ols[act_m8]':['act_m8'],
 'ols[xfp_m8]':['xfp_m8'],
 'ols[xfp_e3]':['xfp_e3'],
 'ols[xfp_e3,act_e3]':['xfp_e3','act_e3'],
 'ols[xfp_m8,res_m8]':['xfp_m8','res_m8'],
 'ols[xfp_e3,xfp_m16]':['xfp_e3','xfp_m16'],
 'ols[xfp_e3,xfp_m16,res_m16]':['xfp_e3','xfp_m16','res_m16'],
 'ols[+vol,share]':['xfp_e3','xfp_m16','res_m16','vol_m8','target_share_m8','wopr_m8'],
}
def ols(X,y):
    X1=np.c_[np.ones(len(X)),X]; b=np.linalg.lstsq(X1,y,rcond=None)[0]; return b
def pred(b,X): return np.c_[np.ones(len(X)),X]@b
rows=[];boot=[]
for tgt in ['y1','y3']:
  for pos in ['QB','RB','WR','TE']:
    dd=d[(d.pos==pos)&d.hasprior&d[tgt].notna()].copy()
    dd=dd.dropna(subset=['act_m16','xfp_m16','act_e6','xfp_e6'])
    dev=dd[dd.season.between(2021,2023)]
    for name,cols in F.items():
        cols_ok=[c for c in cols]
    for ev,df in [('val2024',dd[dd.season==2024]),('hold2025',dd[dd.season==2025])]:
        P={}
        for n,c in M.items(): P[n]=df[c[0]].values
        for n,c in F.items():
            tr=dev.dropna(subset=c); te=df.dropna(subset=c)
            b=ols(tr[c].values,tr[tgt].values)
            p=pd.Series(pred(b,df[c].fillna(df[c].mean()).values),index=df.index)
            P[n]=p.values
        y=df[tgt].values
        # fixed baseline = act_m8
        base=(P['act_m8']-y)**2
        pid=df.player_id.values; up=np.unique(pid); idx={u:np.where(pid==u)[0] for u in up}
        for n,p in P.items():
            se=(p-y)**2
            r2=1-se.sum()/((y-y.mean())**2).sum()
            from scipy.stats import spearmanr
            sp=spearmanr(p,y)[0]
            # clustered bootstrap CI for MSE diff vs act_m8
            diffs=[]
            for _ in range(300):
                s=rng.choice(len(up),len(up)); ii=np.concatenate([idx[up[k]] for k in s])
                diffs.append(se[ii].mean()-base[ii].mean())
            rows.append(dict(target=tgt,pos=pos,eval=ev,model=n,n=len(df),rmse=np.sqrt(se.mean()),r2=r2,spearman=sp,
                dMSE_vs_act_m8=se.mean()-base.mean(),lo=np.percentile(diffs,2.5),hi=np.percentile(diffs,97.5)))
R=pd.DataFrame(rows);R.to_csv('exp1_results.csv',index=False)
pd.set_option('display.width',250)
for tgt in ['y1','y3']:
  for ev in ['val2024','hold2025']:
    print('=====',tgt,ev)
    print(R[(R.target==tgt)&(R['eval']==ev)].pivot(index='model',columns='pos',values='r2').round(3))
