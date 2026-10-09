"""QA: in-production-gate (|line| within +/-50% of model mean) 2025 holdout, receptions + pass_yds, by side/subgroup. Params fit on 2021-24 only."""
import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
import calibration_models as cm
pol = json.load(open(cm.REPO/'config/calibration_policy.json'))['markets']
frame = cm.load_frame()
def br(p,y): return ((p-y)**2).mean()
def table(name, raw, cal, y, mask):
    mask=np.asarray(mask)
    if mask.sum()<150: return
    # bettor-side view: favored side (what a bettor picks) win-prob vs rate
    print(f'  {name:30s} n={mask.sum():6d} brier raw={br(raw[mask],y[mask]):.4f} cal={br(cal[mask],y[mask]):.4f} gain={br(raw[mask],y[mask])-br(cal[mask],y[mask]):+.4f}')
for m in ('receptions','pass_yds'):
    rows,long=cm.build_long(frame,m); pr=cm.long_probs(rows,long,m,models=('v2',))['v2']; long=long.assign(p=pr)
    par=cm.model_params(rows,m,'v2'); mean=(par['lam'] if m=='receptions' else (1-par['p0'])*np.exp(par['mu']+par['sig']**2/2))[long.row.to_numpy()]
    long=long.assign(mean=mean, gate=(long.line>=.5*mean)&(long.line<=1.5*mean))
    P=pol[m]['params']
    def app(p): return cm.platt_apply(p,P) if m=='receptions' else P['w']*p+(1-P['w'])*P['target']
    ho=long[long.season==2025]; y=ho.y.to_numpy(); raw=ho.p.to_numpy(); cal=np.where(ho.gate, app(raw), raw)
    print(m,'share of holdout rows in gate',ho.gate.mean().round(3),'| wired (gated) brier raw',br(raw,y).round(5),'gated-cal',br(cal,y).round(5))
    g=ho.gate.to_numpy()
    print('  in-gate only: slope raw',round(cm.point_metrics(raw[g],y[g])['slope'],3),'cal',round(cm.point_metrics(cal[g],y[g])['slope'],3),'| in-gate mean_p raw/cal/rate',raw[g].mean().round(3),cal[g].mean().round(3),y[g].mean().round(3))
    table('in-gate all',raw,cal,y,g)
    table('in-gate main line',raw,cal,y,g&ho.is_main.to_numpy())
    table('in-gate Over-fav (raw>=.5)',raw,cal,y,g&(raw>=.5)); table('in-gate Under-fav',raw,cal,y,g&(raw<.5))
    for lo in (.8,.9): 
        s=g&(raw>=lo); t=g&(raw<=1-lo)
        if s.sum()>50: print(f'  Over raw>={lo}: n={s.sum()} raw_p={raw[s].mean():.3f} cal_p={cal[s].mean():.3f} hit={y[s].mean():.3f}')
        if t.sum()>50: print(f'  Under raw>={lo}: n={t.sum()} raw_pu={(1-raw[t]).mean():.3f} cal_pu={(1-cal[t]).mean():.3f} hit={(1-y[t]).mean():.3f}')
    if m=='receptions':
        for nm,mask in (('mean>=5 (high volume)',ho['median']>=5),('mean<2 (low volume)',ho['median']<2),('k<=2 early',ho.k<=2),('week<=4',ho.week<=4),('week 1-2',ho.week<=2),('RB',ho.position=='RB'),('TE',ho.position=='TE')):
            table(nm+' in-gate',raw,cal,y,g&np.asarray(mask))
        # by season stability: apply 2021-24-fit on each earlier season is in-sample; use 2021-23 fit on 2024 as out-of-sample
        tr=long[long.season.isin((2021,2022,2023))]; a,b=cm.fit_logistic(cm.logit(tr.p.to_numpy()),tr.y.to_numpy())
        h4=long[long.season==2024]; r4=h4.p.to_numpy(); c4=np.where(h4.gate,cm.platt_apply(r4,{'a':a,'b':b}),r4); print('  2024 OOS (fit 21-23): brier raw',br(r4,h4.y.to_numpy()).round(5),'cal',br(c4,h4.y.to_numpy()).round(5))
        # mean-bias vs line over/under shift: calibrated Over at main line
        mm=ho.is_main.to_numpy()&g
        print('  main line Over: raw_p',raw[mm].mean().round(3),'cal_p',cal[mm].mean().round(3),'hit',y[mm].mean().round(3))
