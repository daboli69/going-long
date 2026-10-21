"""Append-only private experiment snapshots and metadata-only diagnostics."""
import hashlib
import json
import subprocess
import time
from pathlib import Path
import pandas as pd

from ..config import LAB_ROOT
from ..fpds_manual import jobs
from ..fpds_research.common import read,sha,digest,write_once,now

ROOT=jobs.ROOT.parent/'improvement8'
PROTOCOL=LAB_ROOT/'docs/FPDS_IMPROVEMENT_PROTOCOL.json'


def registered():
    paths=[PROTOCOL,LAB_ROOT/'docs/FPDS_A8_REPAIR_PROTOCOL.json',LAB_ROOT/'docs/PHASE10_PREREGISTRATION.md']+sorted(Path(__file__).parent.glob('*.py'))
    for p in paths:
        rel=subprocess.check_output(['git','ls-files','--full-name',str(p)],cwd=LAB_ROOT,text=True).strip()
        if not rel:raise ValueError('Commit Amendment8 implementation before fitting')
        saved=subprocess.check_output(['git','show','HEAD:'+rel],cwd=LAB_ROOT).decode('utf-8').replace('\r\n','\n')
        if saved!=p.read_text(encoding='utf-8'):raise ValueError('Uncommitted Amendment8 protocol/source; launch refused')
    dependencies=['lab/fpds_manual/engine.py','lab/fpds_manual/features.py','lab/fpds_manual/run.py','lab/fpds_research/models.py','lab/fpds_research/features.py','lab/models.py','lab/features.py','lab/ensemble.py']
    from importlib.metadata import version
    return read(PROTOCOL),digest({'files':{str(p.relative_to(LAB_ROOT)):sha(p) for p in paths},
                                 'dependencies':{p:sha(LAB_ROOT/p) for p in dependencies},
                                 'versions':{p:version(p) for p in ['numpy','pandas','scikit-learn','xgboost','torch']}})


def atomic(path,value):return jobs.atomic(path,value)


def status(path,phase,**extra):
    atomic(path/'STATUS.json',{'phase':phase,'updated_at':now(),**extra})


def ledger(path,variant,head=None,output=True):
    file=path/'TRIALS.json'
    d=read(file) if file.exists() else {'output_configurations':[],'fit_configurations':[],'fit_calls':0}
    if output:d['output_configurations']=sorted(set(d['output_configurations'])|{variant})
    if head is not None:
        d['fit_configurations']=sorted(set(d['fit_configurations'])|{variant+'/'+head});d['fit_calls']+=1
    repair=read(path/'REPAIR.json') if (path/'REPAIR.json').exists() else None
    limits=(repair['outputs'],repair['max_fit_configurations'],repair['max_fit_dispatches']) if repair else (147,300,4500)
    if len(d['output_configurations'])>limits[0] or len(d['fit_configurations'])>limits[1] or d['fit_calls']>limits[2]:
        raise ValueError('Registered fixed budget exceeded')
    atomic(file,d)


def block_path(path,variant,season,week):return path/'blocks'/variant/f'{season}_w{week:02d}.parquet'


def save(path,variant,season,week,frame):
    file=block_path(path,variant,season,week);file.parent.mkdir(parents=True,exist_ok=True)
    if file.exists():raise ValueError('Completed block is immutable')
    temporary=file.with_suffix('.parquet.pending');frame.to_parquet(temporary,index=False);temporary.replace(file)


def history(path,variant,decision):
    files=sorted(p for p in (path/'blocks'/variant).glob('*.parquet') if '.pending.' not in p.name)
    if not files:return pd.DataFrame()
    d=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
    return d[pd.to_datetime(d.available_at,utc=True).lt(decision)]


def source_blocks(source,stat,arm):
    files=sorted((source/'blocks'/stat/arm).glob('*.parquet'))
    return pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)


def audit_source(source):
    paths=[source/'JOB.json',source/'INPUT.json',source/'SUMMARY.json']+sorted((source/'blocks').glob('**/*.parquet'))
    meta=read(source/'INPUT.json')
    paths += [Path(meta['path'])/name for name in meta['files']]
    paths += [Path(meta['base_source']).with_name('observations_production.parquet')]
    from ..data_pipeline import GAMES_TABLE,TEAM_GAMES,QB_GAMES,INJURY_VALID
    paths += [GAMES_TABLE,TEAM_GAMES,QB_GAMES,INJURY_VALID]
    return {str(p):sha(p) for p in paths}
