"""Explicit local launches, private logs, bounded deadlines and exact resume."""
import json
import os
import re
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime,timezone
import psutil
from ..config import LAB_ROOT
from ..fpds_research.common import ROOT as A6,read,now,digest,sha

ROOT=A6/'manual'
PROTOCOL=LAB_ROOT/'docs/FPDS_MANUAL_PROTOCOL.json'


def atomic(path,value):
    """Resolve the late-installed sharing-lock adapter, including UI launches."""
    from ..fpds_research import common as C
    if getattr(C.atomic,'_fpds_io_retry',False):return C.atomic(path,value)
    from ..fpds_worker import retry_atomic
    return retry_atomic(C.atomic,path,value,logpath=ROOT/'operational_io'/f'retries_{os.getpid()}.jsonl')


def registered():
    paths=[PROTOCOL,LAB_ROOT/'docs/PHASE10_PREREGISTRATION.md',LAB_ROOT/'lab/fpds_sources.py']+list(Path(__file__).parent.glob('*.py'))
    paths += [LAB_ROOT/p for p in ('lab/config.py','lab/models.py','lab/ensemble.py','lab/fpds_research/models.py','lab/fpds_research/features.py','lab/props/ensemble/features.py','lab/props/ensemble/production.py','lab/props/ensemble/members.py')]
    for path in paths:
        rel=subprocess.check_output(['git','ls-files','--full-name',str(path)],cwd=LAB_ROOT,text=True).strip()
        if not rel:raise ValueError('Commit the manual protocol before fitting')
        committed=subprocess.check_output(['git','show','HEAD:'+rel],cwd=LAB_ROOT).decode('utf-8').replace('\r\n','\n')
        if committed!=path.read_text(encoding='utf-8'):raise ValueError('Manual preregistration has uncommitted changes')
    p=read(PROTOCOL)
    code={str(f.relative_to(LAB_ROOT)):sha(f) for f in paths if f.suffix=='.py'}
    from importlib.metadata import version
    versions={name:version(name) for name in ('numpy','pandas','scikit-learn','xgboost','torch')}
    return p,digest({'protocol':p,'code':code,'versions':versions,'python':sys.version,'source_policy':sha(LAB_ROOT/'lab/fpds_sources.py')})


def directory(job):
    if not re.fullmatch('[a-f0-9]{32}',job):raise ValueError('Invalid manual job ID')
    return ROOT/'jobs'/job


def active():
    lock=ROOT/'ACTIVE.json'
    if not lock.exists():return None
    try:
        value=read(lock);pid=value.get('pid')
        if not pid:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(value['created_at'])).total_seconds()
            return value if age<60 else None
        p=psutil.Process(pid)
        if p.is_running() and not p.status()==psutil.STATUS_ZOMBIE and value['job'] in p.cmdline():return value
    except (OSError,ValueError,psutil.NoSuchProcess):
        if lock.exists() and datetime.now(timezone.utc).timestamp()-lock.stat().st_mtime<60:return {'job':'starting','pid':None}
    except psutil.AccessDenied:return value
    return None


def state(path,phase,**values):
    previous=read(path/'STATUS.json') if (path/'STATUS.json').exists() else {}
    atomic(path/'STATUS.json',dict(previous,phase=phase,updated_at=now(),**values))


@contextmanager
def launch_lock():
    ROOT.mkdir(parents=True,exist_ok=True)
    with (ROOT/'LAUNCH.lock').open('a+b') as file:
        file.seek(0,2)
        if not file.tell():file.write(b'0');file.flush()
        file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise ValueError('Another manual launch is in progress')
        try:yield
        finally:
            file.seek(0)
            if os.name=='nt':msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(file.fileno(),fcntl.LOCK_UN)


def launch(*args,**kwargs):
    with launch_lock():return _launch(*args,**kwargs)


def _launch(action,week=None,scope='all',sims=10000,seed=17,hours=2,refresh=True,resume=None):
    if action not in ('prepare','compare','project'):raise ValueError('Unknown manual action')
    if scope not in ('all','games','props'):raise ValueError('Unknown target scope')
    if week is not None and not 1<=int(week)<=18:raise ValueError('Week must be 1-18')
    if not 100<=int(sims)<=100000:raise ValueError('Simulation count must be 100-100000')
    if not 0<=int(seed)<2**32:raise ValueError('Seed outside supported range')
    if not .1<=float(hours)<=6:raise ValueError('Runtime must be 0.1-6 hours')
    _,signature=registered()
    ROOT.mkdir(parents=True,exist_ok=True)
    if active():raise ValueError('A manual job is already running; refresh its status')
    lock=ROOT/'ACTIVE.json'
    if lock.exists():lock.unlink()  # Stale operational lock only; never source/archive data.
    job=resume or uuid.uuid4().hex;path=directory(job)
    if resume:
        config=read(path/'JOB.json')
        if config['signature']!=signature:raise ValueError('Code/protocol changed; exact resume refused')
        if read(path/'STATUS.json').get('phase') not in ('checkpoint','failed'):raise ValueError('Only an interrupted job can resume')
    else:
        path.mkdir(parents=True,exist_ok=False)
        config={'job':job,'created_at':now(),'action':action,'week':week,'scope':scope,'sims':int(sims),'seed':int(seed),'refresh':bool(refresh),'signature':signature}
        with (path/'JOB.json').open('x',encoding='utf-8') as f:json.dump(config,f,indent=2)
    with lock.open('x',encoding='utf-8') as f:json.dump({'job':job,'pid':None,'created_at':now()},f)
    try:
        atomic(path/'ADMISSION.json',{'created_at':now(),'hours':min(hours,2) if config['action']=='project' else hours,'resume':bool(resume)})
        stop=path/'STOP_REQUESTED.json'
        if stop.exists():stop.unlink()
        state(path,'queued')
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'IDLE_PRIORITY_CLASS',0)
        with (path/'PRIVATE.log').open('a',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,'-m','lab.low_priority','-m','lab.fpds_manual','worker','--job',job],cwd=LAB_ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=flags)
        atomic(lock,{'job':job,'pid':process.pid,'created_at':now()})
        return job
    except Exception:
        if lock.exists() and read(lock).get('job')==job:lock.unlink()
        state(path,'failed',message='Launch failed; inspect the private local log')
        raise


def list_jobs():
    output=[]
    for p in sorted((ROOT/'jobs').glob('*/JOB.json'),reverse=True):
        try:
            job=read(p);status=read(p.with_name('STATUS.json'))
            output.append({k:job.get(k) for k in ('job','created_at','action','week','scope')}|status)
        except (OSError,ValueError):continue
    return sorted(output,key=lambda x:x['created_at'],reverse=True)


def stop(job):
    path=directory(job)
    atomic(path/'STOP_REQUESTED.json',{'requested_at':now(),'policy':'finish current fit/block; save checkpoint'})
