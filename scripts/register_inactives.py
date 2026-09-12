"""Register a reviewed official inactive report, with fetched document hash.
Example: python scripts/register_inactives.py --event EVENT_HASH --team "New Orleans Saints"
 --source https://www.nfl.com/news/ACTUAL_REPORT --published-at ISO --players FILE.json
The operator must verify team, date and complete names in the source before running.
This is an honest review step until an official machine-readable feed is configured.
"""
import argparse,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from build_pipeline import atomic_json


def main():
    p=argparse.ArgumentParser();p.add_argument('--event',required=True);p.add_argument('--team',required=True);p.add_argument('--source',required=True);p.add_argument('--published-at',required=True);p.add_argument('--players',required=True);a=p.parse_args()
    if urlparse(a.source).hostname not in ('www.nfl.com','nfl.com') or not a.source.startswith('https://'):raise ValueError('Use the official nfl.com report')
    r=requests.get(a.source,timeout=30);r.raise_for_status()
    if urlparse(r.url).hostname not in ('www.nfl.com','nfl.com'):raise ValueError('Unexpected report redirect')
    players=json.loads(Path(a.players).read_text())
    if not isinstance(players,list) or not all(isinstance(x,str) and x.strip() for x in players):raise ValueError('Expected inactive player names')
    path=Path(os.getenv('INACTIVES_FILE',str(Path(__file__).resolve().parents[1]/'private/inactives.json')));path.parent.mkdir(parents=True,exist_ok=True)
    reports=json.loads(path.read_text()) if path.exists() else {};report=reports.setdefault(a.event,{'event':a.event,'teams':[]})
    report['teams']=[t for t in report['teams'] if t['name']!=a.team]+[{'name':a.team,'status':'official_confirmed','source_url':r.url,'source_sha256':hashlib.sha256(r.content).hexdigest(),'published_at':a.published_at,'verified_at':datetime.now(timezone.utc).isoformat(),'inactive_players':players,'verification':'operator_checked_against_official_document'}]
    atomic_json(path,reports);print('Official report registered; the other team and all quote gates are still required.')

if __name__=='__main__':main()
