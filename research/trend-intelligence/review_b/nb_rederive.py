"""Review B: independent NB-vs-Poisson receptions re-derivation. Reads cached public nflverse-derived frame; writes nothing but stdout."""
import sys, numpy as np, pandas as pd
from scipy.stats import nbinom, poisson
from scipy.optimize import minimize_scalar, minimize
sys.path.insert(0, 'C:/Users/travi/OneDrive/Documents/ChatGPT/GOING-claude-fpdata')
def _blend(frame, market, c):
    cur, prior, k = frame['cur_' + market].to_numpy(float), frame['prior_' + market].to_numpy(float), frame['k'].to_numpy(float)
    return np.where(np.isnan(cur), prior, np.where(np.isnan(prior), cur, (k * np.nan_to_num(cur) + c * np.nan_to_num(prior)) / (k + c)))
P = 'C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/FantasyPoints/research/cache/champion_2021_2025.parquet'
f = pd.read_parquet(P); f = f[f.ready & f.position.isin(['WR','TE','RB'])].dropna(subset=['champ_receptions','y_receptions']).reset_index(drop=True)
f['mu'] = np.maximum(_blend(f,'receptions',2), 0.01)
LINES = [2.5,3.5,4.5,5.5,6.5,7.5,8.5]
def cdf(k, mu, phi, pw=2.0):
    if phi <= 1e-9: return poisson.cdf(k, mu)
    var = mu + phi*mu**pw; n = mu**2/(var-mu); return nbinom.cdf(k, n, n/(n+mu))
def pmf_ll(y, mu, phi, pw=2.0):
    if phi <= 1e-9: return poisson.logpmf(y, mu)
    var = mu + phi*mu**pw; n = mu**2/(var-mu); return nbinom.logpmf(y, n, n/(n+mu))
dev = f[f.season<=2023]
def fit1(d, pw=2.0):
    r = minimize_scalar(lambda p: -pmf_ll(d.y_receptions.values, d.mu.values, p, pw).mean(), bounds=(0,2), method='bounded'); return r.x
print('phi pooled 2021-23', fit1(dev), 'all-years', fit1(f))
for pos in ['WR','TE','RB']: print(' phi', pos, round(fit1(dev[dev.position==pos]),3), 'n', (dev.position==pos).sum())
for s in [2021,2022,2023,2024,2025]: print(' phi year', s, round(fit1(f[f.season==s]),3))
# mean-dependence: power fit var = mu + phi*mu^pw
def nll(x, d): return -pmf_ll(d.y_receptions.values, d.mu.values, np.exp(x[0]), x[1]).mean()
r = minimize(nll, [np.log(.2),2.0], args=(dev,), method='Nelder-Mead'); print('power fit phi,pw', np.exp(r.x[0]), r.x[1], 'll', -r.fun, 'vs pw2', -nll([np.log(fit1(dev)),2.0],dev), 'pois', pmf_ll(dev.y_receptions.values, dev.mu.values,0).mean())
# NB1: var=mu*(1+a): pw=1
r1 = minimize_scalar(lambda a: -pmf_ll(dev.y_receptions.values, dev.mu.values, a, 1.0).mean(), bounds=(1e-4,3), method='bounded'); print('NB1 a',r1.x,'ll',-r1.fun)
# empirical var/mean by mu bin on dev
dev2 = dev.assign(b=pd.qcut(dev.mu,6)); g = dev2.groupby('b',observed=True).apply(lambda d: pd.Series({'mu':d.mu.mean(),'ybar':d.y_receptions.mean(),'var':((d.y_receptions-d.mu)**2).mean()})); g['phi_impl']=(g['var']-g.mu)/g.mu**2; print(g.round(3))
phi = fit1(dev); phiPos = {p: fit1(dev[dev.position==p]) for p in ['WR','TE','RB']}
pwfit = (np.exp(r.x[0]), r.x[1])
# Recalibration on dev: per-line logistic on logit(p_over_pois)

class _M:
    def __init__(s,params): s.params=params
def _glm(y,X):
    from scipy.optimize import minimize
    x=X[:,1]
    def nl(b):
        z=b[0]+b[1]*x; return np.sum(np.logaddexp(0,z)-y*z)
    r=minimize(nl,[0,1],method='BFGS'); return _M(r.x)
class sm:
    class families:
        Binomial=staticmethod(lambda: None)
    @staticmethod
    def add_constant(x): return np.column_stack([np.ones(len(x)),x])
    @staticmethod
    def GLM(y,X,family=None):
        class G:
            def fit(self): return _glm(y,X)
        return G()
def logit(p): p=np.clip(p,1e-6,1-1e-6); return np.log(p/(1-p))
recal = {}
for L in LINES:
    p = poisson.sf(np.floor(L), dev.mu.values); yy=(dev.y_receptions.values>L).astype(float)
    m = sm.GLM(yy, sm.add_constant(logit(p)), family=sm.families.Binomial()).fit(); recal[L]=m.params
# pooled across lines recal too
Xp=[];Yp=[]
for L in LINES: Xp.append(logit(poisson.sf(np.floor(L),dev.mu.values))); Yp.append((dev.y_receptions.values>L).astype(float))
mp = sm.GLM(np.concatenate(Yp), sm.add_constant(np.concatenate(Xp)), family=sm.families.Binomial()).fit(); print('pooled recal a,b', mp.params)
def probs(d, model):
    mu=d.mu.values; out={}
    for L in LINES:
        k=np.floor(L)
        if model=='POIS': p=poisson.sf(k,mu)
        elif model=='NB': p=1-cdf(k,mu,phi)
        elif model=='NBpos': 
            p=np.zeros(len(d))
            for pos,ph in phiPos.items(): m=(d.position==pos).values; p[m]=1-cdf(k,mu[m],ph)
        elif model=='NB1': p=1-cdf(k,mu,r1.x,1.0)
        elif model=='NBpow': p=1-cdf(k,mu,*pwfit)
        elif model=='REC': a,b=recal[L]; p=1/(1+np.exp(-(a+b*logit(poisson.sf(k,mu)))))
        elif model=='RECP': a,b=mp.params; p=1/(1+np.exp(-(a+b*logit(poisson.sf(k,mu)))))
        elif model=='NB+REC': a,b=recal[L]; p=1/(1+np.exp(-(a+b*logit(1-cdf(k,mu,phi)))))
        elif model=='BASE': p=np.full(len(d),(dev.y_receptions>L).mean())
        out[L]=np.clip(p,1e-6,1-1e-6)
    return out
def ci(v,g,draws=2000,seed=1):
    _,inv=np.unique(g,return_inverse=True); s=np.bincount(inv,weights=v); c=np.bincount(inv).astype(float)
    rng=np.random.default_rng(seed); idx=rng.integers(0,len(s),(draws,len(s))); b=s[idx].sum(1)/c[idx].sum(1); return np.quantile(b,[.025,.975])
def score(d, model, near):
    P=probs(d,model); br=[];ll=[];ids=[]; ps=[];ys=[]
    for L in LINES:
        y=(d.y_receptions.values>L).astype(float); m = (np.abs(L-d.mu.values)<=near) if near else np.ones(len(d),bool)
        p=P[L][m]; br.append((p-y[m])**2); ll.append(-(y[m]*np.log(p)+(1-y[m])*np.log(1-p))); ids.append(d.player_id.values[m]); ps.append(p); ys.append(y[m])
    return np.concatenate(br),np.concatenate(ll),np.concatenate(ids),np.concatenate(ps),np.concatenate(ys)
def calib(p,y):
    m=sm.GLM(y,sm.add_constant(logit(p)),family=sm.families.Binomial()).fit(); return m.params
MODELS=['NB1','NB','NBpos','NBpow','REC','RECP','NB+REC','BASE']
for near in [None,1.5]:
  for yr in [2024,2025]:
    for pos in ['ALL','WR','TE','RB']:
        d=f[(f.season==yr)&((f.position==pos) if pos!='ALL' else True)]
        bP,lP,idP,pP,yP=score(d,'POIS',near)
        a,b=calib(pP,yP)
        print(f'--- near={near} {yr} {pos} n_rows={len(d)} n_obs={len(bP)} POIS brier={bP.mean():.5f} ll={lP.mean():.5f} calib int={a:.3f} slope={b:.3f}')
        for m in MODELS:
            bM,lM,idM,pM,yM=score(d,m,near)
            db=bP-bM; dl=lP-lM; cb=ci(db,idP); cl=ci(dl,idP); a2,b2=calib(pM,yM)
            print(f'   {m:7s} dBrier%={100*db.mean()/bP.mean():+.2f} [{100*cb[0]/bP.mean():+.2f},{100*cb[1]/bP.mean():+.2f}]  dLL={dl.mean():+.5f} [{cl[0]:+.5f},{cl[1]:+.5f}] calib int={a2:+.3f} slope={b2:.3f}')
# per-line and tails (pooled all positions, no near filter), mean predicted vs actual over rate
for yr in [2024,2025]:
    d=f[f.season==yr]; P0=probs(d,'POIS'); P1=probs(d,'NB'); P2=probs(d,'REC')
    print(yr,'line: actual over / pois / nb / recal(pois);  Brier pois nb rec')
    for L in LINES:
        y=(d.y_receptions.values>L); print(f' {L}: {y.mean():.4f} {P0[L].mean():.4f} {P1[L].mean():.4f} {P2[L].mean():.4f} | {((P0[L]-y)**2).mean():.5f} {((P1[L]-y)**2).mean():.5f} {((P2[L]-y)**2).mean():.5f}')
# decile tail reliability for high mean rows
d=f[(f.season>=2024)&(f.mu>=4)]; 
for L in [6.5,7.5,8.5]:
    y=(d.y_receptions.values>L); print('mu>=4 rows',len(d),L,'actual',round(y.mean(),4),'pois',round(poisson.sf(np.floor(L),d.mu.values).mean(),4),'nb',round((1-cdf(np.floor(L),d.mu.values,phi)).mean(),4))
print('=== high-mean rows (mu>=4), 2024-25, lines 5.5..8.5: actual / pois / nb / nb1 ; brier')
d=f[(f.season>=2024)&(f.mu>=4)]
for L in [4.5,5.5,6.5,7.5,8.5]:
    y=(d.y_receptions.values>L); k=np.floor(L); mu=d.mu.values
    ps=[poisson.sf(k,mu),1-cdf(k,mu,phi),1-cdf(k,mu,r1.x,1.0)]
    print(L,round(y.mean(),4),[round(p.mean(),4) for p in ps],[round(((p-y)**2).mean(),5) for p in ps])
print('=== low-mean rows (mu<1.6) lines 2.5')
d=f[(f.season>=2024)&(f.mu<1.6)]; y=(d.y_receptions.values>2.5); mu=d.mu.values
print(len(d),round(y.mean(),4),[round(p.mean(),4) for p in [poisson.sf(2,mu),1-cdf(2,mu,phi),1-cdf(2,mu,r1.x,1.0)]])
