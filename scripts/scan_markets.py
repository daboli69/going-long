"""Persistent-host scanner: python scripts/scan_markets.py --once or --interval 60.
Research collects before inactives; push alerts fail closed without verified reports.
"""
import argparse
import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone
import requests
from topdown.model import evaluate, uid, stamp, fair_pair, performance, SHARP, VERSION
from topdown.feed import normalize
from topdown.journal import Journal
from build_pipeline import atomic_json

ROOT=Path(__file__).resolve().parents[1]


def notify(text):
    webhook=os.getenv('DISCORD_WEBHOOK_URL')
    token,chat=os.getenv('TELEGRAM_BOT_TOKEN'),os.getenv('TELEGRAM_CHAT_ID')
    if webhook:
        r=requests.post(webhook,params={'wait':'true'},json={'content':text[:1900],'allowed_mentions':{'parse':[]}},timeout=20);r.raise_for_status();return 'discord'
    if token and chat:
        r=requests.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':chat,'text':text[:3900]},timeout=20);r.raise_for_status()
        if not r.json().get('ok'):raise RuntimeError('Telegram rejected notification')
        return 'telegram'
    return None


def feedback(predictions, settlements, now):
    eligible=[];seen=set()
    for p in sorted(predictions,key=lambda p:(p['observed_at'],-p.get('ev',0))):
        key=(p['event'],p['selection'],p['side'])
        s=settlements.get(p['id'])
        if key in seen or not p['actionable']:continue
        seen.add(key)
        if not s or s['status'] not in ('win','loss') or stamp(s['observed_at'])>=now or stamp(p['observed_at'])>=stamp(p['kickoff']):continue
        eligible.append((p,s))
    if len(eligible)<50 or len({p['event'] for p,s in eligible})<20:return 0.
    return min(.05,max(0,sum(p['raw_probability']-int(s['status']=='win') for p,s in eligible)/(100+len(eligible))))


def scan(journal, send=False):
    now=time.time();at=datetime.fromtimestamp(now,timezone.utc).isoformat();key=os.getenv('PARLAY_API_KEY')
    if not key:raise RuntimeError('PARLAY_API_KEY is required on the scanner host')
    headers={'X-API-Key':key};base='https://parlay-api.com/v1/sports/americanfootball_nfl/'
    responses={};failures=[]
    for endpoint,params in [('odds',{'markets':'h2h,spreads,totals','regions':'us,eu','oddsFormat':'american'}),('props',{'markets':'player_passing_yards,player_rushing_yards,player_receiving_yards,player_receptions,player_passing_tds','limit':10000})]:
        try:
            r=requests.get(base+endpoint,params=params,headers=headers,timeout=35);r.raise_for_status();rows=r.json()
            if not isinstance(rows,list):raise ValueError('Unexpected provider schema')
            responses[endpoint]=rows
        except (requests.RequestException,ValueError) as exc:
            responses[endpoint]=[];failures.append({'endpoint':endpoint,'type':type(exc).__name__})
    # Freshness is assessed after network calls, not at the start of a slow request.
    now=time.time();at=datetime.fromtimestamp(now,timezone.utc).isoformat()
    quotes=normalize(responses['odds'],responses['props'])
    for q in quotes:journal.append('quote',uid(q),dict(q,observed_at=at))
    report_path=Path(os.getenv('INACTIVES_FILE',str(ROOT/'private/inactives.json')))
    reports=json.loads(report_path.read_text()) if report_path.exists() else {}
    previous={}
    for row in journal.rows('reference'):
        if stamp(row['observed_at'])<now:previous[row['key']]={'at':stamp(row['observed_at']),'probability':row['probability']}
    from settle_markets import settle
    settle(journal,ROOT,now)
    settlements={s['prediction_id']:s for s in journal.rows('settlement')}
    penalty=feedback(journal.rows('prediction'),settlements,now)
    predictions,arbs=evaluate(quotes,reports,now,bankroll=float(os.getenv('RESEARCH_BANKROLL','1000')),previous=previous,calibration_penalty=penalty)
    from topdown.secondary import context
    historical=json.loads((ROOT/'data/nfl_betting.json').read_text())
    names=json.loads((ROOT/'data/history.json').read_text())['betting'].get('team_names',{})
    secondary={}
    for q in quotes:
        if q['event'] not in secondary:secondary[q['event']]=context(q,historical.get('games',[]),names,now)
    for p in predictions:
        p['secondary']=secondary.get(p['event'])
        if p['market']=='totals' and p['secondary'] and abs(p['line']-p['secondary']['estimated_total'])>14:
            p['actionable']=False;p['proposed_stake']=0;p['reasons'].append('Extreme difference from the secondary scoring check; review required')
        journal.append('prediction',p['id'],p)
    for p in predictions:
        k=p['selection']+'|'+str(p['side_index'])
        journal.append('reference',uid(k,at),{'key':k,'probability':p['raw_probability'],'observed_at':at})
    # Observe later sharp prices at the SAME contract. A sample is only called
    # near kickoff when it was quoted within ten minutes before kickoff.
    groups={}
    for q in quotes:
        if q['book'] in SHARP and fair_pair(q['prices']):groups.setdefault(q['selection'],[]).append(q)
    for p in journal.rows('prediction'):
        for q in groups.get(p['selection'],[]):
            qt=stamp(q['updated_at']);kick=stamp(p['kickoff'])
            if qt is not None and stamp(p['observed_at'])<qt<kick and 0<=now-qt<=180:
                f=fair_pair(q['prices']);side=p['side_index']
                journal.append('closing',uid(p['id'],q['book'],qt),{'prediction_id':p['id'],'book':q['book'],'probability':f['proportional'][side],'quoted_at':q['updated_at'],'observed_at':at,'near_kickoff':kick-qt<=600,'selection':p['selection']})
    sent={n['alert_key'] for n in journal.rows('notification')}
    for p in sorted(predictions,key=lambda p:-p['ev']):
        alert=uid(p['event'],p['selection'],p['side'],p['book'],VERSION)
        if not send or not p['actionable'] or alert in sent:continue
        message=f"GOING price check: {p['away']} at {p['home']} | {p.get('player') or ''} {p['market']} {p['side']} {p['line']} | {p['book']} {p['american']:+} | estimated repeat return {100*p['ev']:.1f}% after policy discount; suggested size ${p['proposed_stake']:.2f}. Check availability and rules. Not a guaranteed outcome."
        try:
            channel=notify(message)
            if channel:
                journal.append('notification',alert,{'alert_key':alert,'prediction_id':p['id'],'channel':channel,'observed_at':at});sent.add(alert)
        except requests.RequestException:
            failures.append({'endpoint':'notification','type':'delivery_failed_or_unknown'})
    for arb in arbs:
        journal.append('arbitrage',uid(arb,at),dict(arb,observed_at=at))
        alert=uid('arbitrage',arb['selection'],arb['books'])
        if send and arb['actionable'] and alert not in sent:
            try:
                channel=notify(f"GOING displayed-price arbitrage candidate: {arb['selection'][:12]} | {', '.join(arb['books'])} | quoted return {arb['return_if_executable']*100:.1f}%. Accepted stakes, limits and matching void rules still need checking.")
                if channel:journal.append('notification',alert,{'alert_key':alert,'channel':channel,'observed_at':at});sent.add(alert)
            except requests.RequestException:failures.append({'endpoint':'notification','type':'delivery_failed_or_unknown'})
    try:sync=journal.sync()
    except requests.RequestException:sync={'status':'unavailable_local_journal_retained'}
    books=sorted({q['book'] for q in quotes if q['book']})
    status={'observed_at':at,'model_version':VERSION,'quote_pairs':len(quotes),'reference_books':sorted(SHARP.intersection(books)),'required_reference_books':2,'research_predictions':len(predictions),'actionable_predictions':sum(p['actionable'] for p in predictions),'arbitrage_candidates':len(arbs),'inactives_configured':bool(reports),'supabase':sync,'notifications_configured':bool(os.getenv('DISCORD_WEBHOOK_URL') or (os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'))),'failures':failures,'possibly_truncated':len(responses['props'])>=10000,'calibration_penalty':penalty,'notice':'Research only until two fresh reference books, verified official inactives and all price checks pass. No market-volume or bettor-identity data is available.'}
    atomic_json(ROOT/'data/topdown_status.json',status)
    journal.append('run',uid(at),status)
    print(json.dumps(status));return status


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');parser.add_argument('--send',action='store_true');parser.add_argument('--interval',type=int,default=60);args=parser.parse_args()
    journal=Journal(os.getenv('TOPDOWN_DB',str(ROOT/'private/topdown.sqlite')))
    while True:
        started=time.monotonic()
        try:scan(journal,args.send)
        except Exception as exc:
            # Never serialize request URLs: Telegram/webhook URLs contain secrets.
            print(json.dumps({'status':'scan_failed','type':type(exc).__name__}))
            if args.once:raise SystemExit(1)
        if args.once:break
        time.sleep(max(10,max(30,args.interval)-(time.monotonic()-started)))

if __name__=='__main__':main()
