"""Fixed walk-forward test of margin ratings, travel and recent-roster strength across past seasons."""
import time
import numpy as np
import pandas as pd
from .config import ROOT,REPORTS,KEYS,now,read,once
from . import models as M
from .features import feature_columns
from .strength import RATING,TRAVEL,ROSTER,run as feature_run
from .research_io import fingerprint,update

OUT=REPORTS/'strength_v1'
STUDIES={'A':{'seasons':tuple(range(2019,2027)),'first_train':2016,
              'configs':{'control':(),'rating':RATING,'travel':TRAVEL,'rating_travel':RATING+TRAVEL}},
         'B':{'seasons':(2023,2024,2025,2026),'first_train':2021,
              'configs':{'control_b':(),'roster':ROSTER,'all':RATING+TRAVEL+ROSTER}}}
COMPARISONS=[('A','rating','control'),('A','travel','control'),('A','rating_travel','control'),
             ('B','roster','control_b'),('B','all','control_b')]
ALPHA=.05/len(COMPARISONS)


def load():
    d=feature_run()
    return d[d.eligible&d.home_win.notna()&d.season.ge(2016)&d.season.le(2026)].sort_values(['tipoff','game_id']).reset_index(drop=True)


def protocol_hash():
    return fingerprint([ROOT/'docs/STRENGTH_PREREGISTRATION.md',ROOT/'nba_lab/strength.py',ROOT/'nba_lab/strength_research.py',
                        ROOT/'nba_lab/models.py',ROOT/'nba_lab/features.py'])


def fold(d,study,config,season,history,threads,log):
    spec=STUDIES[study];path=OUT/f'{study}_{config}_{season}.parquet'
    if path.exists():return pd.read_parquet(path)
    cols=feature_columns(d.drop(columns=[c for c in d if c.startswith('diff_') and c in RATING+TRAVEL+ROSTER]))+list(spec['configs'][config])
    pool=d[d.season.ge(spec['first_train'])]
    train=pool[pool.season.le(season-2)];cal=pool[pool.season.eq(season-1)];test=pool[pool.season.eq(season)]
    log(f'{study}/{config}/{season}: train {len(train)} cal {len(cal)} test {len(test)}')
    bundle=M.fit(train,cal,cols,threads,log=lambda _:None);p=M.probabilities(bundle,test)
    hp=np.concatenate([h[list(KEYS)].to_numpy() for h in history]) if history else None
    hy=np.concatenate([h.home_win.to_numpy(int) for h in history]) if history else None
    combined,_,_=M.combine(p,hp,hy)
    out=test[['game_id','season','home_win','elo_probability']].copy()
    for j,key in enumerate(KEYS):out[key]=p[:,j]
    for method,prob in combined.items():out[method]=prob
    out['stacking_fallback']=hp is None
    out.to_parquet(path,index=False);return out


def compare(a,b,column='stacked'):
    y=a.home_win.to_numpy(int);ci=M.paired_ci(y,a[column].to_numpy(),b[column].to_numpy(),alpha=ALPHA)
    sa,sb=M.scores(y,a[column]),M.scores(y,b[column])
    seasons={int(s):M.scores(x.home_win,x[column])['log_loss']-M.scores(b.loc[x.index].home_win,b.loc[x.index,column])['log_loss']
             for s,x in a.groupby('season')}
    return {'n':len(y),'log_loss':sa['log_loss'],'control_log_loss':sb['log_loss'],'brier_delta':sa['brier']-sb['brier'],
            'accuracy':sa['accuracy'],'control_accuracy':sb['accuracy'],'relative_loss_reduction':1-sa['log_loss']/sb['log_loss'],
            **ci,'season_deltas':seasons,'seasons_improving':sum(v<0 for v in seasons.values())}


def research(threads=1,log=print):
    OUT.mkdir(parents=True,exist_ok=True);key=protocol_hash();manifest=OUT/'MANIFEST.json'
    if manifest.exists() and read(manifest)['protocol']!=key:raise ValueError('Strength protocol changed after checkpoints; new preregistration required')
    update(manifest,{'protocol':key,'started_at':now()})
    result=OUT/'RESULTS.json'
    if result.exists():return read(result)
    d=load();start=time.time();frames={}
    for study,spec in STUDIES.items():
        for config in spec['configs']:
            history=[]
            for season in spec['seasons']:history.append(fold(d,study,config,season,history,threads,log))
            frames[(study,config)]=pd.concat(history).set_index('game_id').sort_index()
    rows=[]
    for study,candidate,control in COMPARISONS:
        a,b=frames[(study,candidate)],frames[(study,control)]
        if not a.index.equals(b.index):raise AssertionError('Candidate and control games differ')
        row={'study':study,'candidate':candidate,'control':control,**compare(a,b)}
        need=int(np.ceil(.75*len(STUDIES[study]['seasons'])))
        row['passed']=bool(row['ci_high']<0 and row['seasons_improving']>=need and row['brier_delta']<=0)
        row['members']={k:{'delta':compare(a,b,k)['delta'],'ci_high':compare(a,b,k)['ci_high']} for k in (*KEYS,'equal')}
        rows.append(row)
    descriptive={f'{s}/{c}':{m:M.scores(f.home_win,f[m]) for m in (*KEYS,'equal','stacked','elo_probability')} for (s,c),f in frames.items()}
    out={'created_at':now(),'protocol':key,'alpha_per_comparison':ALPHA,'comparisons':rows,'descriptive':descriptive,
         'seconds':round(time.time()-start,1),'base_fits':sum(6*len(s['seasons'])*len(s['configs']) for s in STUDIES.values())}
    once(result,out);return out
