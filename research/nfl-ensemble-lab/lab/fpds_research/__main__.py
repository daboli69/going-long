"""Offline CLI. Errors are private; console output is metadata/counts only."""
import argparse
import sys
from .common import ROOT, REPORT, now, private_error


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('command',choices=['ingest','audit','features','screen','walkforward','report','weekly'])
    p.add_argument('--phase',choices=['discovery','validation','descriptive'],default='discovery')
    p.add_argument('--threads',type=int,default=None)
    p.add_argument('--deadline')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--week',type=int)
    args=p.parse_args()
    if args.deadline is None:
        import pandas as pd
        args.deadline=(pd.Timestamp.now(tz='UTC')+pd.Timedelta(hours=2)).isoformat() if args.command=='weekly' else '2026-10-21T12:49:41Z'
    try:
        if args.command=='ingest':
            from .ingest import run
            result=run();print(f"Import complete: {len(result['files'])} files / {len(result['working_tables'])} tables")
        elif args.command=='audit':
            from .audit import run
            result=run();print(f"Audit complete: {len(result['tables'])} tables; metadata dictionary written")
        elif args.command=='features':
            from .features import run
            result=run();print(f"Feature store complete: {result['rows']} rows, {len(result['groups'])} groups")
        elif args.command in ('screen','walkforward'):
            from .walkforward import run
            result=run(args);print('Research step complete; see aggregate report and private checkpoints')
        elif args.command=='report':
            from .report import run
            run();print('Aggregate report updated')
        else:
            from .weekly import run
            result=run(args);print('Weekly shadow revision written: '+result['path'])
        return 0
    except Exception:
        path=private_error(args.command)
        print('FAILED: '+args.command+'; private diagnostic saved under data/cache/fpds/amendment6/errors',file=sys.stderr)
        return 1


if __name__=='__main__':sys.exit(main())
