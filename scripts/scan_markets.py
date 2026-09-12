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
from topdown.alerts import format_arbitrage
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
    # Schedule-driven monitoring continues even when the odds provider is down.
    data_root=Path(os.getenv('TOPDOWN_DATA_ROOT',str(ROOT)))
    history_data=json.loads((data_root/'data/history.json').read_text())['betting']
    names=history_data.get('team_names',{})
    reverse={code:name for name,code in names.items()}
    schedule=json.loads((data_root/'data/nfl_betting.json').read_text()).get('games',[])
    events=[]
    for g in schedule:
        home,away=reverse.get(g.get('home')),reverse.get(g.get('away'))
        if home and away and stamp(g.get('kickoff')) is not None:
            events.append(dict(event=uid(home,away,stamp(g['kickoff'])),home=home,away=away,kickoff=g['kickoff']))
    report_path=Path(os.getenv('INACTIVES_FILE',str(ROOT/'private/inactives.json')))
    reports={r['event']:r for r in journal.rows('inactive_report')}
    try:
        manual=json.loads(report_path.read_text()) if report_path.exists() else {}
        if isinstance(manual,dict):reports.update(manual)
    except (OSError,ValueError):pass
    from topdown.inactives import update_inactives
    reports,inactive_status=update_inactives(journal,events,reports,now,notify if send else None)
    headers={'X-API-Key':key};base='https://parlay-api.com/v1/sports/americanfootball_nfl/'
    responses={};failures=[]
    for endpoint,params in [('odds',{'markets':'h2h,spreads,totals','regions':'us,eu','oddsFormat':'american'}),('props',{'markets':'player_passing_yards,player_rushing_yards,player_receiving_yards,player_receptions,player_passing_tds','limit':10000})]:
        try:
            r=requests.get(base+endpoint,params=params,headers=headers,timeout=35);r.raise_for_status();rows=r.json()
            if not isinstance(rows,list):raise ValueError('Unexpected provider schema')
            responses[endpoint]=rows
        except (requests.RequestException,ValueError) as exc:
            responses[endpoint]=[];failures.append({'endpoint':endpoint,'type':type(exc).__name__})
    try:
        r=requests.get('https://parlay-api.com/v1/sports/americanfootball_ncaaf/odds',params={'markets':'h2h,spreads,totals','regions':'us,eu','oddsFormat':'american'},headers=headers,timeout=35);r.raise_for_status()
        responses['ncaa']=r.json()
        if not isinstance(responses['ncaa'],list):raise ValueError('Unexpected NCAA odds schema')
    except (requests.RequestException,ValueError) as exc:
        responses['ncaa']=[];failures.append({'endpoint':'ncaa_odds','type':type(exc).__name__})
    # Freshness is assessed after network calls, not at the start of a slow request.
    now=time.time();at=datetime.fromtimestamp(now,timezone.utc).isoformat()
    quotes=normalize(responses['odds'],responses['props'])+normalize(responses['ncaa'],[],sport='ncaa')
    for q in quotes:journal.append('quote',uid(q),dict(q,observed_at=at))
    for report in reports.values():
        journal.append('inactive_report',uid(report),dict(report,observed_at=at))
    previous={}
    for row in journal.rows('reference'):
        if stamp(row['observed_at'])<now:previous[row['key']]={'at':stamp(row['observed_at']),'probability':row['probability']}
    from settle_markets import settle
    data_root=Path(os.getenv('TOPDOWN_DATA_ROOT',str(ROOT)))
    settle(journal,data_root,now)
    settlements={s['prediction_id']:s for s in journal.rows('settlement')}
    penalties={};predictions=[];arbs=[]
    history_predictions=journal.rows('prediction')
    for sport in ('nfl','ncaa'):
        penalties[sport]=feedback([p for p in history_predictions if p.get('sport','nfl')==sport],settlements,now)
        picks,candidates=evaluate([q for q in quotes if q.get('sport','nfl')==sport],reports,now,bankroll=float(os.getenv('RESEARCH_BANKROLL','1000')),previous=previous,calibration_penalty=penalties[sport],min_ev=float(os.getenv('MIN_EV','0.03')),favorite_ev=float(os.getenv('FAVORITE_MIN_EV','0.025')),fallback_ev=float(os.getenv('SINGLE_SOURCE_EV_EXTRA','0.005')))
        predictions.extend(picks);arbs.extend(candidates)
    from topdown.secondary import context
    historical=json.loads((data_root/'data/nfl_betting.json').read_text())
    names=json.loads((data_root/'data/history.json').read_text())['betting'].get('team_names',{})
    secondary={}
    for q in quotes:
        if q['event'] not in secondary:secondary[q['event']]=context(q,historical.get('games',[]),names,now) if q.get('sport','nfl')=='nfl' else None
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
        if not p.get('actionable') or not 0<stamp(p['kickoff'])-now<=600:continue
        for q in groups.get(p['selection'],[]):
            qt=stamp(q['updated_at']);kick=stamp(p['kickoff'])
            if qt is not None and stamp(p['observed_at'])<qt<kick and 0<=now-qt<=180:
                f=fair_pair(q['prices']);side=p['side_index']
                journal.append('closing',uid(p['id'],q['book'],qt),{'sport':p.get('sport','nfl'),'prediction_id':p['id'],'book':q['book'],'probability':f['proportional'][side],'quoted_at':q['updated_at'],'observed_at':at,'near_kickoff':kick-qt<=600,'selection':p['selection']})
    sent={n['alert_key'] for n in journal.rows('notification')}
    for p in sorted(predictions,key=lambda p:-p['ev']):
        alert=uid(p['event'],p['selection'],p['side'],p['book'],VERSION)
        if not send or not p['actionable'] or alert in sent:continue
        message=f"GOING {p.get('sport','nfl').upper()} price check: {p['away']} at {p['home']} | {p.get('player') or ''} {p['market']} {p['side']} {p['line']} | {p['book']} {p['american']:+} | estimated repeat return {100*p['ev']:.1f}% after policy discount; suggested size ${p['proposed_stake']:.2f}. Check availability and rules. Not a guaranteed outcome."
        if p.get('sport')=='ncaa':message+=' NCAA availability not independently verified.'
        try:
            channel=notify(message)
            if channel:
                journal.append('notification',alert,{'sport':p.get('sport','nfl'),'alert_key':alert,'prediction_id':p['id'],'channel':channel,'observed_at':at});sent.add(alert)
        except requests.RequestException:
            failures.append({'endpoint':'notification','type':'delivery_failed_or_unknown'})
    for arb in arbs:
        journal.append('arbitrage',uid(arb,at),dict(arb,observed_at=at))
        alert=uid('arbitrage',arb['selection'],arb['books'])
        if send and arb['actionable'] and alert not in sent:
            try:
                channel=notify(format_arbitrage(arb))
                if channel:journal.append('notification',alert,{'alert_key':alert,'channel':channel,'observed_at':at});sent.add(alert)
            except requests.RequestException:failures.append({'endpoint':'notification','type':'delivery_failed_or_unknown'})
    try:sync=journal.sync()
    except requests.RequestException:sync={'status':'unavailable_local_journal_retained'}
    books=sorted({q['book'] for q in quotes if q['book']})
    sports={sport:{'quote_pairs':sum(q.get('sport','nfl')==sport for q in quotes),'research_predictions':sum(p.get('sport','nfl')==sport for p in predictions),'actionable_predictions':sum(p.get('sport','nfl')==sport and p['actionable'] for p in predictions),'reference_books':sorted({q['book'] for q in quotes if q.get('sport','nfl')==sport and q['book'] in SHARP})} for sport in ('nfl','ncaa')}
    status={'sports':sports,'observed_at':at,'model_version':VERSION,'quote_pairs':len(quotes),'reference_books':sorted(SHARP.intersection(books)),'required_reference_books':1,'single_source_extra_hurdle':float(os.getenv('SINGLE_SOURCE_EV_EXTRA','0.005')),'timestamp_desyncs':sum(p.get('timestamp_delta_seconds',0)>60 for p in predictions),'pending_inactives':sum(p.get('inactive_state')=='pending_inactives' for p in predictions),'research_predictions':len(predictions),'actionable_predictions':sum(p['actionable'] for p in predictions),'arbitrage_candidates':len(arbs),'inactives_configured':True,'inactive_feed':inactive_status,'supabase':sync,'notifications_configured':bool(os.getenv('DISCORD_WEBHOOK_URL') or (os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'))),'failures':failures,'possibly_truncated':len(responses['props'])>=10000,'calibration_penalty':penalties,'notice':'Pinnacle is required; a single reference adds a safety hurdle. NFL official inactives must pass. NCAA availability is not independently verified; both sports require final-window and price checks. No market-volume or bettor-identity data is available.'}
    atomic_json(Path(os.getenv('TOPDOWN_STATUS_FILE',str(ROOT/'data/topdown_status.json'))),status)
    journal.append('run',uid(at),status)
    try:journal.sync()
    except requests.RequestException:pass  # Run remains durable for the next retry.
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
