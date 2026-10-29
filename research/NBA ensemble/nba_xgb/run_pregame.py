"""Scheduled pregame chain for one ET game day: refresh sources, collect the day's injury report, issue the immutable forecast.

    python -m nba_xgb.run_pregame --date 2026-10-29 --at 18:15
Waits until `--at` (ET), then runs: nba_lab refresh, nba_lab extra-data, injury_live.collect, avail_daily.run. If the day's pregame cutoff
has already passed the forecast is refused (avail_daily raises) and the failure is logged, never silently relabelled.
"""
import argparse
import subprocess
import sys
import time
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / 'research_nba_xgb' / 'live' / 'pregame_chain.log'


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f'{pd.Timestamp.now(tz="UTC").isoformat()} {msg}'
    print(line, flush=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def sh(args):
    r = subprocess.run([sys.executable, '-W', 'ignore', *args], cwd=ROOT, capture_output=True, text=True)
    log(f'{" ".join(args)} -> exit {r.returncode}')
    if r.returncode:
        log((r.stderr or r.stdout)[-600:])
    return r.returncode


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--at', required=True, help='HH:MM America/New_York')
    a = ap.parse_args()
    target = pd.Timestamp(f'{a.date} {a.at}', tz='America/New_York')
    while pd.Timestamp.now(tz='UTC') < target:
        time.sleep(20)
    log(f'chain start for {a.date}')
    sh(['-m', 'nba_lab.cli', 'refresh'])
    sh(['-m', 'nba_lab.cli', 'extra-data'])
    sh(['-m', 'nba_xgb.injury_live', '--season', '2027', '--days-back', '1', '--deadline', '120'])
    rc = sh(['-m', 'nba_xgb.avail_daily', '--date', a.date])
    log('forecast ' + ('written' if rc == 0 else 'FAILED'))
