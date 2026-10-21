"""python -m lab.fpds_improve run|resume|status (local private outputs only)."""
import argparse
import json
import traceback
from pathlib import Path
from datetime import datetime,timezone
from . import storage as S


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('action',choices=['run','resume','status','repair-opportunity'])
    parser.add_argument('--run');parser.add_argument('--hours',type=float,default=3)
    parser.add_argument('--parent')
    args=parser.parse_args()
    if not .2<=args.hours<=3:raise SystemExit('Runtime must be0.2–3hours')
    if args.run and (not args.run.isalnum()):raise SystemExit('Invalid run identifier')
    if args.action=='repair-opportunity' and (not args.parent or not args.parent.isalnum()):raise SystemExit('A valid repair parent is required')
    path=S.ROOT/(args.run or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    if args.action=='status':
        for p in sorted(S.ROOT.glob('*/STATUS.json'),reverse=True):
            value=S.read(p);print(p.parent.name,value.get('phase'),value.get('step',''))
        return
    if args.action=='resume' and not (path/'RUN.json').exists():raise SystemExit('Exact run snapshot required')
    if args.action=='run' and path.exists():raise SystemExit('New run identifier must be unused; existing snapshots are immutable')
    if args.action=='resume' and (path/'STATUS.json').exists() and S.read(path/'STATUS.json').get('phase')=='complete':
        raise SystemExit('Completed study is immutable; do not repeat it as independent evidence')
    from ..fpds_manual import jobs
    import os,psutil
    if jobs.active():raise SystemExit('A manual model job is active; wait before starting this study')
    S.ROOT.mkdir(parents=True,exist_ok=True)
    lock=S.ROOT/'ACTIVE.json'
    if lock.exists():
        value=S.read(lock)
        try:
            p=psutil.Process(value['pid'])
            if p.is_running() and 'lab.fpds_improve' in p.cmdline():raise SystemExit('An improvement study is already active')
        except psutil.NoSuchProcess:pass
        lock.unlink()  # Stale operational pointer only.
    with lock.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'run':path.name},f)
    try:
        from ..fpds_worker import install
        install()
        from .run import run
        print('Local Amendment8 run:',path.name,flush=True)
        run(path,args.hours,repair_parent=args.parent if args.action=='repair-opportunity' else None)
        print('Status:',S.read(path/'STATUS.json')['phase'],flush=True)
    except Exception:
        path.mkdir(parents=True,exist_ok=True)
        (path/'ERROR_PRIVATE.log').write_text(traceback.format_exc(),encoding='utf-8')
        S.status(path,'failed',message='Private diagnostic retained; no raw values printed')
        print('Stopped; private diagnostic retained. No promotion.',flush=True)
        raise SystemExit(1)
    finally:
        if lock.exists() and S.read(lock).get('pid')==os.getpid():lock.unlink()


if __name__=='__main__':main()
