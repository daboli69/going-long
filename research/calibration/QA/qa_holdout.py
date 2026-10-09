"""QA reproduction of Auditor B holdout (receptions, pass_yds) + subgroup harm analysis. Independent refit; 2025 never used for fitting."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
import calibration_models as cm
frame = cm.load_frame()
print('seasons', sorted(frame.season.unique()), 'maxweek', frame.groupby('season').week.max().to_dict())
pol = json.load(open(cm.REPO/'config/calibration_policy.json'))
def brier(p,y): return float(((p-y)**2).mean())
for m in ('receptions','pass_yds'):
    fr = frame[frame.season<=2025]
    rows, long = cm.build_long(fr, m)
    pr = cm.long_probs(rows, long, m, models=('v2',))['v2']
    long = long.assign(p=pr)
    tr = long[long.season.isin((2021,2022,2023,2024))]
    ho = long[long.season==2025]
    # independent refit on 2021-24
    if m=='receptions':
        a,b = cm.fit_logistic(cm.logit(tr.p.to_numpy()), tr.y.to_numpy())
        print(m,'my refit 21-24', a,b, 'deployed', pol['markets'][m]['params'])
        P = pol['markets'][m]['params']
        cal = cm.platt_apply(ho.p.to_numpy(), P)
        # 2021-23 refit applied (B's frozen)
        tr3 = long[long.season.isin((2021,2022,2023))]
        a3,b3 = cm.fit_logistic(cm.logit(tr3.p.to_numpy()), tr3.y.to_numpy()); print(' refit21-23',a3,b3)
    else:
        P = pol['markets'][m]['params']
        tgt = tr.y.mean(); print(m,'overall over-rate 21-24',tgt,'deployed target',P['target'])
        cal = P['w']*ho.p.to_numpy()+(1-P['w'])*P['target']
    y = ho.y.to_numpy(); raw = ho.p.to_numpy()
    print(m,'n',len(ho),'brier raw',brier(raw,y),'cal',brier(cal,y))
    print(' slope raw',cm.point_metrics(raw,y)['slope'],'cal',cm.point_metrics(cal,y)['slope'])
    ho = ho.assign(cal=cal, raw=raw)
    # subgroups
    def rep(name, mask):
        mask=np.asarray(mask)
        if mask.sum()<200: return
        print(f'  {name:28s} n={mask.sum():6d} raw={brier(raw[mask],y[mask]):.4f} cal={brier(cal[mask],y[mask]):.4f} d={brier(raw[mask],y[mask])-brier(cal[mask],y[mask]):+.4f} mean_raw={raw[mask].mean():.3f} mean_cal={cal[mask].mean():.3f} rate={y[mask].mean():.3f}')
    rep('all', np.ones(len(ho),bool))
    rep('main line', ho.is_main.to_numpy())
    for pos in ho.position.unique(): rep('pos '+pos, ho.position==pos)
    for lo,hi in ((1,4),(5,8),(9,13),(14,18)): rep(f'week {lo}-{hi}', (ho.week>=lo)&(ho.week<=hi))
    for lo,hi in ((0,0),(1,2),(3,5),(6,20)): rep(f'k {lo}-{hi}', (ho.k>=lo)&(ho.k<=hi))
    rep('over-favored raw>=.5', raw>=.5); rep('under-favored raw<.5', raw<.5)
    rep('main over-fav', (raw>=.5)&ho.is_main.to_numpy()); rep('main under-fav', (raw<.5)&ho.is_main.to_numpy())
    med = ho['median'].to_numpy()
    q = np.quantile(med,[0,.25,.5,.75,.9,1])
    for i in range(len(q)-1): rep(f'median {q[i]:.1f}-{q[i+1]:.1f}', (med>=q[i])&(med<=q[i+1]))
    for o in sorted(ho.off.unique()): rep(f'offset {o}', ho.off==o)
    for lo,hi in ((0,.1),(.1,.3),(.3,.7),(.7,.9),(.9,1.01)): rep(f'raw p {lo}-{hi}', (raw>=lo)&(raw<hi))
    # per-season (fit on 21-24 incl 2024 so 2024 is in-sample)
    # early-season mean bias k=0
    rows25=rows[rows.season==2025]
    for kk in (0,1,2):
        r=rows25[rows25.k==kk]
        if len(r)>100:
            pp=cm.model_params(r,m,'v2'); 
            mean = pp['lam'] if m=='receptions' else (1-pp['p0'])*np.exp(pp['mu']+pp['sig']**2/2)
            print(f'  mean bias k={kk} n={len(r)} pred={mean.mean():.3f} obs={r["y_"+m].mean():.3f}')
