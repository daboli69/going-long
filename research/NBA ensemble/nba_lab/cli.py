"""One local entry point; never imports NFL packages or credentials."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from .config import ROOT,REPORTS,DATA,now,atomic,low_priority


def main():
    threads=low_priority()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['refresh','features','develop','confirm','train','predict','daily','calibrate','research-next','score-forecast','shadow-forecast','extra-data','score','context','report','app'])
    parser.add_argument('--date');parser.add_argument('--start',type=int,default=2015);parser.add_argument('--end',type=int)
    parser.add_argument('--source',choices=['nba_api','pbpstats']);parser.add_argument('--season',type=int,default=2026)
    args=parser.parse_args()
    try:
        from . import sources,features,engine
        atomic(REPORTS/'STATUS.json',{'at':now(),'action':args.action,'state':'running'})
        if args.action=='refresh':out=sources.refresh(args.start,args.end)
        elif args.action=='features':out={'rows':len(features.run())}
        elif args.action=='develop':out=engine.develop(threads)
        elif args.action=='confirm':out=engine.confirm(threads)
        elif args.action=='train':out={'version':engine.train(threads)['version']}
        elif args.action=='calibrate':
            from .calibration import run
            result=run()
            out={k:result[k] for k in ('trial_count','successful_candidates','calibrator_fits','elapsed_seconds','decision')}
        elif args.action=='research-next':
            from .individual import run
            from .score_models import research
            from .config import once
            lock=REPORTS/'IMPROVEMENTS_RUN_LOCK.json'
            try:once(lock,{'created_at':now(),'action':'research-next'})
            except FileExistsError:raise ValueError('Research already running or interrupted; review IMPROVEMENTS_RUN_LOCK.json before resuming')
            try:individual=run(threads);score_result=research()
            finally:lock.unlink(missing_ok=True)
            out={'individual_results':individual['results'],'individual_failures':individual['failures'],
                 'score_results':score_result['results'],'score_failures':score_result['failures'],
                 'selected_shadow_score_method':score_result['selected_shadow_method']}
        elif args.action=='score-forecast':
            from .score_models import archive
            out=archive(args.date)
        elif args.action=='shadow-forecast':
            from .score_models import archive as score_archive
            from .winner_shadow import archive as individual_archive
            out={'scores':score_archive(args.date),'individuals':individual_archive(args.date,threads)}
        elif args.action=='extra-data':
            from .extra_data import collect
            report=collect(end=args.end)
            out={'seasons':list(report['coverage']),'issues':report['issues'],'injury_context':report['injury_context']}
        elif args.action=='predict':_,out=engine.predict(args.date)
        elif args.action=='score':
            from .outcomes import score
            out=score()
        elif args.action=='daily':
            from .outcomes import score
            sources.refresh(args.start,args.end);score();features.run();engine.train(threads)
            _,out=engine.predict(args.date)
            from .extra_data import collect
            collect(end=args.end)
            if (ROOT/'docs/SCORE_FROZEN_CONFIG.json').exists():
                from .score_models import archive
                archive(args.date)
            if (ROOT/'docs/INDIVIDUAL_SHADOW_CONFIG.json').exists():
                from .winner_shadow import archive
                archive(args.date,threads)
        elif args.action=='context':
            if not args.source:raise ValueError('Specify --source nba_api or pbpstats')
            out=sources.optional_context(args.source,args.season)
        elif args.action=='report':
            path=REPORTS/'INITIAL_RESEARCH.md'
            print(path.read_text(encoding='utf-8') if path.exists() else 'No completed confirmation report yet.')
            return 0
        else:
            return subprocess.call([sys.executable,'-m','streamlit','run',str(ROOT/'app.py'),
                '--server.address','127.0.0.1','--server.port','8502','--server.headless','true','--browser.gatherUsageStats','false'],cwd=ROOT)
        atomic(REPORTS/'STATUS.json',{'at':now(),'action':args.action,'state':'complete'})
        print(json.dumps(out,default=str,indent=2) if out is not None else 'No unstarted games on this date.')
        return 0
    except Exception as error:
        atomic(REPORTS/'STATUS.json',{'at':now(),'action':args.action,'state':'failed','error':type(error).__name__,'message':str(error)[:400]})
        print('STOP: '+type(error).__name__+': '+str(error)[:400]);return 1


if __name__=='__main__':raise SystemExit(main())
