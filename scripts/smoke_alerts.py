"""Explicit synthetic connectivity test, excluded from the prediction journal."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from topdown.model import evaluate, uid
from scan_markets import notify


def main():
    root=Path(__file__).resolve().parents[1]
    os.environ.update(json.loads((root/'private/connections.json').read_text()))
    now=time.time()
    iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
    event='SMOKE-TEST-'+uid(now)[:12]
    q=dict(event=event,selection=event,home='TEST HOME',away='TEST AWAY',kickoff=iso(now+3600),updated_at=iso(now-10),book='pinnacle',prices=[-110,-110],market='totals',line=44.5,sides=['Over','Under'],no_refund=True)
    team=lambda name:dict(name=name,status='official_confirmed',source_url='https://www.nfl.com/SMOKE-TEST-NOT-A-REAL-REPORT',source_sha256=uid('synthetic'),published_at=iso(now-60),verified_at=iso(now-30),inactive_players=[])
    # These objects exist only in this process; never register them as live reports.
    reports={event:dict(event=event,teams=[team('TEST HOME'),team('TEST AWAY')])}
    picks,_=evaluate([q,dict(q,book='bookmaker'),dict(q,book='draftkings',prices=[120,-140])],reports,now)
    pick=next(p for p in picks if p['actionable'] and p['side']=='Over')
    row=dict(id=uid(event),owner_id=os.environ['GOING_OWNER_ID'],kind='notification',observed_at=iso(now),payload=dict(test=True,label='SYNTHETIC SMOKE TEST — NOT A BET',simulation=pick))
    key=os.environ['SUPABASE_SERVICE_ROLE_KEY'];headers={'apikey':key,'Authorization':'Bearer '+key}
    url=os.environ['SUPABASE_URL']+'/rest/v1/market_journal'
    r=requests.post(url,headers=headers,json=row,timeout=30);r.raise_for_status()
    r=requests.get(url,headers=headers,params={'id':'eq.'+row['id'],'select':'id,kind,payload'},timeout=30);r.raise_for_status()
    assert r.json()[0]['payload']['test'] is True and r.json()[0]['kind']=='notification'
    channel=notify('GOING SYNTHETIC SMOKE TEST — NOT A BET. Simulated inactives and a mock price passed the gates. Supabase write/read verified. This record is excluded from returns, training and performance claims. Test ID: '+event)
    result=dict(test=True,test_id=event,supabase='write_and_read_verified',discord='delivered' if channel=='discord' else 'not_delivered',excluded_from_performance=True)
    (root/'private/smoke-result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()
