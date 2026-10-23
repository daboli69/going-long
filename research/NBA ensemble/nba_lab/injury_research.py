"""Fixed walk-forward test: strength shadow inputs with and without official pregame injury values."""
import time
import numpy as np
import pandas as pd
from .config import ROOT,REPORTS,KEYS,now,read,once
from . import models as M
from .features import feature_columns
from .strength import RATING,TRAVEL,ROSTER
from .injury_features import INJURY,run as feature_run
from .research_io import fingerprint,update

OUT=REPORTS/'injury_v1';SEASONS=(2024,2025,2026);FIRST_TRAIN=2022;ALPHA=.05
CONFIGS={'strength':RATING+TRAVEL+ROSTER,'strength_injury':RATING+TRAVEL+ROSTER+INJURY}


def columns(d,extra):
    new=RATING+TRAVEL+ROSTER+INJURY
    return feature_columns(d.drop(columns=[c for c in new if c in d]))+list(extra)


def load():
    d=feature_run()
    return d[d.eligible&d.home_win.notna()&d.season.between(FIRST_TRAIN,2026)].sort_values(['tipoff','game_id']).reset_index(drop=True)


def protocol_hash():
    return fingerprint([ROOT/'docs/INJURY_PREREGISTRATION.md',ROOT/'nba_lab/injury_features.py',ROOT/'nba_lab/injury_research.py',
                        ROOT/'nba_lab/injury_reports.py',ROOT/'nba_lab/strength.py',ROOT/'nba_lab/models.py',ROOT/'nba_lab/features.py'])


def fold(d,config,season,history,threads,log):
    path=OUT/f'{config}_{season}.parquet'
    if path.exists():return pd.read_parquet(path)
    train=d[d.season.le(season-2)];cal=d[d.season.eq(season-1)];test=d[d.season.eq(season)]
    log(f'{config}/{season}: train {len(train)} cal {len(cal)} test {len(test)}')
    bundle=M.fit(train,cal,columns(d,CONFIGS[config]),threads,log=lambda _:None);p=M.probabilities(bundle,test)
    hp=np.concatenate([h[list(KEYS)].to_numpy() for h in history]) if history else None
    hy=np.concatenate([h.home_win.to_numpy(int) for h in history]) if history else None
    combined,_,_=M.combine(p,hp,hy)
    out=test[['game_id','season','home_win','elo_probability']].copy()
    for j,key in enumerate(KEYS):out[key]=p[:,j]
    for method,prob in combined.items():out[method]=prob
    out.to_parquet(path,index=False);return out


def research(threads=1,log=print):
    from .strength_research import compare
    OUT.mkdir(parents=True,exist_ok=True);key=protocol_hash();manifest=OUT/'MANIFEST.json'
    if manifest.exists() and read(manifest)['protocol']!=key:raise ValueError('Injury protocol changed after checkpoints; new preregistration required')
    update(manifest,{'protocol':key,'started_at':now()})
    result=OUT/'RESULTS.json'
    if result.exists():return read(result)
    d=load();start=time.time();frames={}
    for config in CONFIGS:
        history=[]
        for season in SEASONS:history.append(fold(d,config,season,history,threads,log))
        frames[config]=pd.concat(history).set_index('game_id').sort_index()
    a,b=frames['strength_injury'],frames['strength']
    if not a.index.equals(b.index):raise AssertionError('Candidate and control games differ')
    row={'candidate':'strength_injury','control':'strength',**compare(a,b)}
    # One preregistered comparison, so the interval is uncorrected.
    row.update(M.paired_ci(a.home_win.to_numpy(),a.stacked.to_numpy(),b.stacked.to_numpy(),alpha=ALPHA))
    row['passed']=bool(row['ci_high']<0 and row['seasons_improving']==len(SEASONS) and row['brier_delta']<=0)
    row['members']={k:compare(a,b,k)['delta'] for k in (*KEYS,'equal')}
    out={'created_at':now(),'protocol':key,'comparison':row,
         'descriptive':{c:{m:M.scores(f.home_win,f[m]) for m in (*KEYS,'equal','stacked','elo_probability')} for c,f in frames.items()},
         'seconds':round(time.time()-start,1),'base_fits':6*len(SEASONS)*len(CONFIGS)}
    once(result,out);return out
