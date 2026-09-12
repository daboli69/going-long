"""Export only time-stamped local observations, not reconstructed historical prices."""
import argparse
import json
from pathlib import Path
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from topdown.model import stamp, fresh
from settle_markets import MAP


def actual_outcomes(quotes,root):
    result=json.loads((root/'data/results.json').read_text())
    history=json.loads((root/'data/history.json').read_text())['betting']
    names=history.get('team_names',{});out=[]
    for q in {q['selection']:q for q in quotes}.values():
        home,away=names.get(q['home']),names.get(q['away'])
        games=[g for g in result['games'].values() if g['sport']=='nfl' and g['home']==home and g['away']==away and abs(stamp(g['kickoff'])-stamp(q['kickoff']))<60]
        if len(games)!=1:continue
        g=games[0];value=None
        if q['market']=='totals':value=g['homeScore']+g['awayScore']
        elif q['market'] in ('spreads','h2h'):value=g['homeScore']-g['awayScore']
        elif q['market'] in MAP:
            players=[pid for pid,p in history.get('profiles',{}).items() if p.get('name')==q.get('player') and p.get('team') in (home,away)]
            if len(players)==1:
                date=datetime.fromtimestamp(stamp(q['kickoff']),ZoneInfo('America/New_York')).date().isoformat()
                value=result['players'].get(players[0]+'|'+date,{}).get(MAP[q['market']])
        if value is not None:out.append(dict(selection=q['selection'],actual=value,observed_at=result['generated_at']))
    return out


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',default='private/topdown.sqlite');p.add_argument('--output',default='private/replay-input.json');a=p.parse_args()
    db=sqlite3.connect(Path(a.db).resolve().as_uri()+'?mode=ro',uri=True)
    rows=db.execute("SELECT kind,observed_at,payload FROM journal WHERE kind IN ('quote','run','inactive_report') ORDER BY observed_at, CASE WHEN kind='run' THEN 1 ELSE 0 END")
    quotes={};reports={};snapshots=[];closes=[]
    for kind,at,body in rows:
        record=json.loads(body)
        if record.get('test'):continue
        if kind=='quote':
            quotes[(record['selection'],record['book'])]=record
            t=stamp(record['updated_at']);kick=stamp(record['kickoff'])
            if t is not None and 0<kick-t<=600 and stamp(at)<kick:
                closes.append(dict(selection=record['selection'],book=record['book'],prices=record['prices'],quoted_at=record['updated_at']))
        elif kind=='inactive_report':reports[record['event']]=record
        else:snapshots.append(dict(observed_at=at,quotes=[q for q in quotes.values() if fresh(q,stamp(at))],reports=dict(reports)))
    output=dict(snapshots=snapshots,outcomes=actual_outcomes(quotes.values(),Path(__file__).resolve().parents[1]),closes=closes,notice='Only recorded prices and published results are exported. Missing outcomes/closes stay unscored.')
    Path(a.output).write_text(json.dumps(output,allow_nan=False));print('Exported',len(snapshots),'real observed snapshots')


if __name__=='__main__':main()
