"""Manual local controls. Never prints source rows or prediction rows."""
import argparse
from . import jobs


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('action',choices=['plan','prepare','compare','project','status','resume','stop','worker'])
    p.add_argument('--week',type=int);p.add_argument('--scope',choices=['all','games','props'],default='all')
    p.add_argument('--sims',type=int,default=10000);p.add_argument('--seed',type=int,default=17)
    p.add_argument('--hours',type=float,default=2);p.add_argument('--no-refresh',action='store_true');p.add_argument('--job')
    a=p.parse_args()
    try:
        if a.action=='worker':
            from ..fpds_worker import install
            install()
            from .run import worker
            return worker(a.job)
        if a.action=='plan':
            from ..fpds_sources import select_sources,HISTORY_FOLDER
            from ..fpds_research.protocol import title
            files=select_sources()
            print('Authoritative folder: '+HISTORY_FOLDER)
            print('Selected versions:',len(files),' / tables:',len({title(f)[0] for f in files}))
            print('Manual compare: fixed 2022-24 development; same game/prop ensemble families with vs without FPDS. No new 2025 pass.')
            print('Manual project: all available historical years through last available completed week; selected future week; shadow only.')
            return 0
        if a.action=='status':
            for row in jobs.list_jobs()[:10]:print(row['job'],row['action'],row['phase'],row.get('step',''))
            return 0
        if a.action=='stop':jobs.stop(a.job);print('Stop requested after current block');return 0
        if a.action=='resume':
            if not a.job:raise ValueError('--job is required for exact resume')
            job=jobs.launch('compare',hours=a.hours,resume=a.job)
        else:job=jobs.launch(a.action,week=a.week,scope=a.scope,sims=a.sims,seed=a.seed,hours=a.hours,refresh=not a.no_refresh)
        print('Local manual job started: '+job)
        print('Private outputs: '+str(jobs.directory(job)))
        return 0
    except Exception as error:
        # Parser errors can contain source values: diagnostics stay private.
        import traceback
        from datetime import datetime,timezone
        folder=jobs.ROOT/'errors';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_PRIVATE.log')
        path.write_text(traceback.format_exc(),encoding='utf-8')
        safe=(a.action!='plan' and isinstance(error,ValueError)) or str(error).startswith(('Authoritative FPDS full-history folder','A newer FPDS export changed schema','A newer loose FPDS export is incomplete'))
        print('STOP: '+(str(error) if safe else type(error).__name__+'; details retained in the local private diagnostic'))
        return 1


if __name__=='__main__':raise SystemExit(main())
