"""Immutable local snapshots with committed code and dependency fingerprints."""
import subprocess
from pathlib import Path
from importlib.metadata import version
from ..fpds_improve import storage as A8
from ..fpds_research.common import read,sha,digest,write_once,now
from ..fpds_manual import jobs
from ..config import LAB_ROOT,RAW_DIR

ROOT=A8.ROOT.parent/'simulation10'
PROTOCOL=LAB_ROOT/'docs/FPDS_A10_PROTOCOL.json'


def registered():
    paths=[PROTOCOL,LAB_ROOT/'docs/PHASE10_PREREGISTRATION.md']+sorted(Path(__file__).parent.glob('*.py'))
    paths+=[LAB_ROOT/p for p in ['lab/fpds_manual/engine.py','lab/fpds_research/models.py','lab/fpds_improve/core.py',
                               'lab/fpds_improve/run.py','lab/fpds_research/features.py','lab/props/ensemble/production.py']]
    for p in paths:
        rel=subprocess.check_output(['git','ls-files','--full-name',str(p)],cwd=LAB_ROOT,text=True).strip()
        if not rel:raise ValueError('Commit Amendment10 implementation before fitting')
        text=subprocess.check_output(['git','show','HEAD:'+rel],cwd=LAB_ROOT).decode('utf-8').replace('\r\n','\n')
        if text!=p.read_text(encoding='utf-8'):raise ValueError('Uncommitted study implementation/dependency')
    return read(PROTOCOL),digest({'files':{str(p.relative_to(LAB_ROOT)):sha(p) for p in paths},
                                 'versions':{x:version(x) for x in ['numpy','pandas','scipy','scikit-learn']}})


def inputs(protocol,production=False):
    source=jobs.directory(protocol['source_job']);meta=read(source/'INPUT.json')
    parent=A8.ROOT/protocol['parent']
    paths=[source/'INPUT.json',parent/'players.parquet',parent/'strong_games.parquet',parent/'RUN.json']
    paths+=[Path(meta['path'])/f for f in meta['files']]
    from ..data_pipeline import INJURY_VALID
    paths+=[INJURY_VALID]
    for s in range(2021,2027 if production else 2025):
        for prefix in ('play_by_play','roster_weekly','snap_counts'):
            p=RAW_DIR/f'{prefix}_{s}.parquet'
            if not p.exists():raise ValueError('Missing local input: '+p.name)
            paths.append(p)
    return {str(p):sha(p) for p in paths}


def ledger(path,output,head=None):
    f=path/'TRIALS.json';d=read(f) if f.exists() else {'outputs':[],'fit_calls':0,'heads':[]}
    d['outputs']=sorted(set(d['outputs'])|{output})
    if head is not None:d['fit_calls']+=1;d['heads']=sorted(set(d['heads'])|{output+'/'+head})
    protocol=read(path/'RUN.json')['protocol']
    if d['fit_calls']>protocol['max_fit_calls'] or len(d['outputs'])>protocol['max_output_versions']:raise ValueError('Fixed trial budget exceeded')
    A8.atomic(f,d)


def block(path,variant,season,week):return A8.block_path(path,variant,season,week)
save=A8.save
history=A8.history
status=A8.status
