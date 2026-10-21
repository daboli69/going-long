"""Operational admission only: a long refit cannot straddle a kickoff."""
import argparse
import subprocess
import os
import pandas as pd
from .data_pipeline import FEATURE_STORE
from .props.ensemble.production import completed_cutoff


def check(games,week,now):
    target=games[games.season.eq(2026)&games.week.eq(week)&~games.completed&games.kickoff_utc.gt(now)]
    if target.empty:raise ValueError('No unstarted games in requested week')
    if target.kickoff_utc.min()<=now+pd.Timedelta(hours=2):
        raise ValueError('A kickoff is inside the2h refit budget. Use --comparisons-only or rerun after it starts; never backdate a forecast.')
    return len(target)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--week',type=int);p.add_argument('--deadline');p.add_argument('--threads',type=int)
    p.add_argument('--branch-only',action='store_true');p.add_argument('--run',action='store_true');a=p.parse_args()
    branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    if not branch.startswith('codex/projections-'):raise SystemExit('STOP: weekly research requires the authorized codex/projections branch')
    if a.branch_only:print('Authorized local research branch confirmed');raise SystemExit(0)
    g=pd.read_parquet(FEATURE_STORE);g['kickoff_utc']=pd.to_datetime(g.kickoff_utc,utc=True);now=pd.Timestamp.now(tz='UTC')
    week=a.week or completed_cutoff(g)['training_last_completed_week']+1
    try:print(f'Weekly admission: {check(g,week,now)} unstarted games; earliest kickoff is outside the2h fit budget')
    except ValueError as e:raise SystemExit(str(e))
    if a.run:
        from .fpds_research.weekly import run
        from .fpds_research.common import private_error
        a.deadline=min(pd.Timestamp(a.deadline) if a.deadline else now+pd.Timedelta(hours=2),now+pd.Timedelta(hours=2)).isoformat()
        a.threads=a.threads or max(1,(os.cpu_count() or 2)-2)
        try:result=run(a);print('New private shadow archive: '+result['path'])
        except Exception:
            private_error('weekly_admission');raise SystemExit('Weekly pipeline stopped; private diagnostic retained')
