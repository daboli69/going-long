"""QA independent reproduction of Auditor A per-market slope/skill straight from data/public_tracker."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from tracker_store import load_tracker
from scipy.special import expit
recs = load_tracker(ROOT/'data')['records']
print('records', len(recs), 'kinds', pd.Series([r['kind'] for r in recs]).value_counts().to_dict())
settle={}
for r in recs:
    if r['kind']=='settlement':
        p=r['payload']; k=p['prediction_id']
        if k not in settle or str(p['observed_at'])>=str(settle[k]['observed_at']): settle[k]=p
rows=[]
for r in recs:
    if r['kind']!='prediction': continue
    p=r['payload']; s=settle.get(p['id'])
    if not s or s['status'] not in ('win','loss'): continue
    rows.append(dict(contract=p.get('canonical_contract') or p.get('selection'),id=p['id'],group=p['tracking_group'],market=p['market'],side=p['side'],line=p['line'],player=p.get('player'),home=p['home'],away=p['away'],ko=str(p['kickoff'])[:10],p=p['probability'],y=1.0 if s['status']=='win' else 0.0,mv=p.get('model_version'),cohort=p.get('model_cohort')))
df=pd.DataFrame(rows)
print('settled w/l', len(df), df.group.value_counts().to_dict())
print('model_version', df.mv.value_counts(dropna=False).to_dict()); print('cohort', df.cohort.value_counts(dropna=False).to_dict())
# dedupe: one observation per (player,market,line,side,game)
d=df.drop_duplicates('contract').copy()
print('dedup n', len(d))
def logit(p): p=np.clip(p,1e-6,1-1e-6); return np.log(p/(1-p))
def fit(x,y):
    a,b=0.,1.
    for _ in range(50):
        q=expit(a+b*x); w=q*(1-q)
        g=np.array([(y-q).sum(),((y-q)*x).sum()]); H=np.array([[w.sum(),(w*x).sum()],[(w*x).sum(),(w*x*x).sum()]])
        s=np.linalg.solve(H,g); a+=s[0]; b+=s[1]
        if abs(s).max()<1e-9: break
    return a,b
for m in ('player_receptions','player_receiving_yards','player_passing_yards','player_rushing_yards','totals'):
    s=d[d.market==m]
    br=((s.p-s.y)**2).mean()
    # per market-side base-rate reference
    ref=np.mean([((g.y-g.y.mean())**2).mean()*len(g) for _,g in s.groupby('side')]) if False else sum(((g.y-g.y.mean())**2).sum() for _,g in s.groupby('side'))/len(s)
    a,b=fit(logit(s.p.to_numpy()),s.y.to_numpy())
    print(f'{m:24s} n={len(s)} brier={br:.4f} base_ref(side)={ref:.4f} skill={1-br/ref:+.3f} slope={b:.3f} int={a:+.3f} meanp={s.p.mean():.3f} rate={s.y.mean():.3f}')
    # by cohort/model version
    print('   by mv', s.groupby('mv').size().to_dict())

print('--- bin check')
hi=d[d.p>=0.9]; print('p>=.9 n',len(hi),'win',hi.y.mean().round(3),'mean_p',hi.p.mean().round(3)); print(hi.groupby('market').agg(n=('y','size'),win=('y','mean'),mp=('p','mean')).round(3))
b=d[(d.p>=.9)&(d.p<1)]; print(pd.cut(d.p,[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0]).value_counts().sort_index().to_dict())
for lo,hi_ in ((.9,.95),(.93,.96)):
    s=d[(d.p>=lo)&(d.p<hi_)]; print(lo,hi_,len(s),s.y.mean().round(3),s.p.mean().round(3))
# receptions + rec yds sub-slice: Over vs Under, by high prob, by version (is any v3/calibrated record present?)
for m in ('player_receptions','player_receiving_yards'):
    s=d[d.market==m]
    for side,g in s.groupby('side'): print(m,side,len(g),'brier',((g.p-g.y)**2).mean().round(4),'meanp',g.p.mean().round(3),'rate',g.y.mean().round(3))
print('latest prediction obs:', max(str(r['payload']['observed_at']) for r in recs if r['kind']=='prediction'))
