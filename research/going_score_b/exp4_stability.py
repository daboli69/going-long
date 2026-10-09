import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
from scipy.stats import spearmanr
pd.set_option('display.width',250)
d=pd.read_parquet('panel.parquet').sort_values(['player_id','season','week'])
g=d.groupby('player_id')
HL=[0.5,1,2,3,4,6,8,12,20]
for h in HL: d[f'xe{h}']=g['xfp'].transform(lambda s:s.shift(1).ewm(halflife=h,min_periods=3).mean())
d['ae6']=d['act_e6']
d['pg']=d.groupby('player_id')['xfp'].shift(1)
sc={'last game xFP':'pg','act_m3':'act_m3','act_m8':'act_m8','act_e3':'act_e3','act_e6':'act_e6',**{f'xfp_ewm_hl{h}':f'xe{h}' for h in HL}}
# autocorr: score at game t vs score at game t-1 for same player (consecutive played games), per position, avg Spearman across weeks
d['gi']=g.cumcount()
rows=[]
dd=d[(d.n_prior>=5)&d.season.between(2021,2025)&d.y1.notna()&d.y3.notna()]
for pos in ['QB','RB','WR','TE']:
    x=dd[dd.position==pos]
    for n,c in sc.items():
        prev=d.groupby('player_id')[c].shift(1).reindex(x.index)
        ok=x[c].notna()&prev.notna()
        ac=spearmanr(x.loc[ok,c],prev[ok])[0]
        r1=np.corrcoef(x.loc[x[c].notna(),c],x.loc[x[c].notna(),'y1'])[0,1]**2
        r3=np.corrcoef(x.loc[x[c].notna(),c],x.loc[x[c].notna(),'y3'])[0,1]**2
        rows.append(dict(pos=pos,score=n,rank_autocorr=ac,r2_y1=r1,r2_y3=r3))
R=pd.DataFrame(rows);R.to_csv('exp4_stability.csv',index=False)
for pos in ['QB','RB','WR','TE']:
    print(pos);print(R[R.pos==pos].drop(columns='pos').round(3).to_string(index=False))
