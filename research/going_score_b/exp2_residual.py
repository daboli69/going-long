import pandas as pd, numpy as np
from types import SimpleNamespace as NS
d=pd.read_parquet('panel.parquet'); d=d[d.n_prior>=4]
d['y3x']=d.y3
out=[]
def fit(df,y,xs):
    df=df.dropna(subset=[y]+xs)
    X=np.c_[np.ones(len(df)),df[xs].values]; Y=df[y].values
    XtXi=np.linalg.inv(X.T@X); b=XtXi@X.T@Y; e=Y-X@b
    g=df.player_id.values; meat=np.zeros((X.shape[1],)*2)
    for u in np.unique(g):
        i=g==u; s_=X[i].T@e[i]; meat+=np.outer(s_,s_)
    V=XtXi@meat@XtXi; se=np.sqrt(np.diag(V))
    names=['const']+xs
    return NS(params=dict(zip(names,b)),tvalues=dict(zip(names,b/se))),len(df)
per={'dev21-23':(2021,2023),'val24':(2024,2024),'hold25':(2025,2025)}
print('--- A. Does trailing residual (act-xfp) add after xfp_e6 & act? target y1 (coef on res_m16 given xfp_e6, wopr/vol)')
for pos in ['QB','RB','WR','TE']:
  for p,(a,b) in per.items():
    df=d[(d.position==pos)&d.season.between(a,b)]
    m,n=fit(df,'y1',['xfp_e6','res_m16'])
    m3,_=fit(df,'y3',['xfp_e6','res_m16'])
    out.append(dict(test='A_res_adds',pos=pos,period=p,n=n,coef_res_y1=m.params['res_m16'],t_y1=m.tvalues['res_m16'],coef_xfp_y1=m.params['xfp_e6'],coef_res_y3=m3.params['res_m16'],t_y3=m3.tvalues['res_m16']))
print(pd.DataFrame(out).round(3).to_string())
print('--- B. Persistence of residual: y1_res ~ res_m16 (slope = share of surplus that persists). 1-slope = regression to mean')
o2=[]
for pos in ['QB','RB','WR','TE']:
  for p,(a,b) in per.items():
    df=d[(d.position==pos)&d.season.between(a,b)]
    for lab,y,x in [('total_res','y1_res','res_m16'),('td_res','y1_tdres','tdres_m8'),('rec_res','y1_recres','recres_m8'),('yds_res','y1_ydsres','yds_res_m8')]:
        x=x if x in df else x
        m,n=fit(df,y,[x]); o2.append(dict(pos=pos,period=p,comp=lab,n=n,slope=m.params[x],t=m.tvalues[x],mean_next=df[y].mean()))
B=pd.DataFrame(o2); print(B.pivot_table(index=['pos','comp'],columns='period',values=['slope','t']).round(3).to_string())
pd.concat([pd.DataFrame(out),B]).to_csv('exp2_results.csv',index=False)
