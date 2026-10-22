"""Manual bounded local targets/roles/joint-simulation study."""
import argparse
import os
import traceback
from datetime import datetime,timezone
import psutil
from threadpoolctl import threadpool_limits
from . import storage as S
from ..fpds_research.common import read,write_once,now
from ..fpds_manual import jobs


def preflight(path,action):
    if action=='resume':
        if not (path/'RUN.json').exists():raise SystemExit('Exact existing snapshot required')
        if (path/'SUMMARY.json').exists() or (path/'PROJECT.json').exists():
            raise SystemExit('Completed snapshot is immutable; no repeated scoring or status overwrite')
    elif path.exists():raise SystemExit('New run directory must be unused')


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['audit','research','resume','project','status'])
    p.add_argument('--run');p.add_argument('--hours',type=float,default=2)
    p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int);p.add_argument('--sims',type=int,default=2000)
    a=p.parse_args()
    if a.run and not a.run.isalnum():raise SystemExit('Invalid run ID')
    if not .2<=a.hours<=3:raise SystemExit('Runtime must be0.2–3hours')
    if not 100<=a.sims<=10000:raise SystemExit('Use100–10000sims')
    if a.action=='status':
        for f in sorted(S.ROOT.glob('*/STATUS.json')):
            d=read(f);print(f.parent.name,d.get('phase'),d.get('step',''))
        return
    if a.action=='project' and (a.season!=2026 or not a.week or not 1<=a.week<=18):raise SystemExit('Explicit2026week1–18 required')
    path=S.ROOT/(a.run or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    preflight(path,a.action)
    if jobs.active():raise SystemExit('Another manual model job is active')
    proc=psutil.Process();proc.nice(psutil.IDLE_PRIORITY_CLASS if os.name=='nt' else 19)
    cpus=proc.cpu_affinity();proc.cpu_affinity(cpus[:max(1,len(cpus)-2)])
    S.ROOT.mkdir(parents=True,exist_ok=True);lock=S.ROOT/'ACTIVE.json'
    if lock.exists():
        info=read(lock)
        if psutil.pid_exists(info['pid']):
            old=psutil.Process(info['pid'])
            if abs(old.create_time()-info['process_created'])<1:raise SystemExit('Study already active')
        lock.unlink()  # Stale operational pointer only, never data/archive.
    write_once(lock,{'pid':proc.pid,'process_created':proc.create_time()})
    try:
        from ..fpds_worker import install
        install();S.registered()
        from .run import research,prepare,project
        path.mkdir(parents=True,exist_ok=a.action=='resume')
        with threadpool_limits(max(1,(os.cpu_count() or 2)-2)):
            if a.action=='audit':
                protocol,signature=S.registered()
                write_once(path/'RUN.json',{'created_at':now(),'protocol':protocol,'signature':signature,'inputs':S.inputs(protocol)})
                prepare(path,protocol);S.status(path,'audited',step='targets prepared; no model fit')
            elif a.action=='project':project(path,a.season,a.week,a.sims,a.hours)
            else:research(path,a.hours)
        print('Local Amendment10:',path.name,read(path/'STATUS.json')['phase'],'; private data retained locally')
    except KeyboardInterrupt:
        S.status(path,'checkpoint',message='Interrupted; completed blocks retained; resume exact frozen snapshot')
        raise SystemExit(130)
    except Exception:
        path.mkdir(parents=True,exist_ok=True)
        (path/'ERROR_PRIVATE.log').write_text(traceback.format_exc(),encoding='utf-8')
        S.status(path,'failed',message='Private diagnostic retained; no promotion')
        raise SystemExit('Failed; private diagnostic retained; no raw rows printed')
    finally:
        if lock.exists() and read(lock).get('pid')==proc.pid:lock.unlink()


if __name__=='__main__':main()
