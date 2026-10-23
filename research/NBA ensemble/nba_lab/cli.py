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
    parser.add_argument('action',choices=['refresh','features','develop','confirm','train','predict','daily','context','report','app'])
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
        elif args.action=='predict':_,out=engine.predict(args.date)
        elif args.action=='daily':
            sources.refresh(args.start,args.end);features.run();engine.train(threads)
            _,out=engine.predict(args.date)
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
