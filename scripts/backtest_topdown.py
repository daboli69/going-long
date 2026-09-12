"""Chronological replay of recorded prices; outcomes never become training prices.

Input JSON: snapshots [{observed_at, quotes, reports}], outcomes
[{selection, actual, observed_at}], closes [{selection, book, prices, quoted_at}].
Quotes use topdown.feed.normalize's schema. Each snapshot must represent a real
archived retrieval. Reports retain publication AND verification timestamps.
Actual is the total/stat value, or home score minus away score for game sides.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from topdown.model import evaluate, stamp, fair_pair, SHARP, performance
from scan_markets import feedback


def replay(data):
    snapshots=sorted(data.get('snapshots',[]),key=lambda s:stamp(s['observed_at']))
    predictions=[];settlements={};previous={};folds=[];seen=set();graded=[]
    outcomes=defaultdict(list)
    for r in data.get('outcomes',[]):
        if stamp(r.get('observed_at')) is None:raise ValueError('Outcome availability time required')
        outcomes[r['selection']].append(r)
    def settle_until(now):
        for p in predictions:
            if p['id'] in settlements:continue
            available=[r for r in outcomes[p['selection']] if stamp(p['kickoff'])<stamp(r['observed_at'])<now]
            if not available:continue
            r=min(available,key=lambda r:stamp(r['observed_at']))
            value=r['actual'];target=p['line'];over=p['side_index']==0
            if p['market']=='spreads':value+=p['line'];target=0
            if p['market']=='h2h':target=0
            status='refund' if value==target else 'win' if (value>target)==over else 'loss'
            settlements[p['id']]={'prediction_id':p['id'],'status':status,'observed_at':r['observed_at']}
    # Fit feedback once per calendar week from settled PRIOR-week decisions only.
    # The price model itself is a fixed benchmark, not a fitted outcome predictor.
    fold=None;penalty=0
    for snapshot in snapshots:
        now=stamp(snapshot['observed_at'])
        if now is None:raise ValueError('Snapshot availability time required')
        week=datetime.fromtimestamp(now,timezone.utc).strftime('%G-W%V')
        if week!=fold:
            settle_until(now)
            penalty=feedback(predictions,settlements,now)
            folds.append(dict(week=week,training_predictions=len(predictions),available_settlements=len(settlements),penalty=penalty,cutoff=snapshot['observed_at']))
            fold=week
        picks,_=evaluate(snapshot['quotes'],snapshot.get('reports',{}),now,previous=previous,calibration_penalty=penalty)
        for p in picks:
            key=(p['selection'],p['side'])
            if p['actionable'] and key not in seen:
                predictions.append(p);seen.add(key)
            previous[p['selection']+'|'+str(p['side_index'])]={'at':now,'probability':p['raw_probability']}
    evaluation_at=max([stamp(r['observed_at']) for rows in outcomes.values() for r in rows]+[stamp(s['observed_at']) for s in snapshots]+[0])+1
    settle_until(evaluation_at)
    bands=performance(predictions,settlements,evaluation_at)
    for p in predictions:
        if p['id'] not in settlements:continue
        candidates=[c for c in data.get('closes',[]) if c['selection']==p['selection'] and c['book'] in SHARP and stamp(c.get('quoted_at')) is not None and stamp(p['observed_at'])<stamp(c['quoted_at'])<stamp(p['kickoff']) and stamp(p['kickoff'])-stamp(c['quoted_at'])<=600 and fair_pair(c['prices'])]
        # Pinnacle close is primary; never substitute today's or another line's price.
        candidates=[c for c in candidates if c['book']=='pinnacle']
        close=max(candidates,key=lambda c:stamp(c['quoted_at']),default=None)
        probability=fair_pair(close['prices'])['proportional'][p['side_index']] if close else None
        graded.append(dict(prediction_id=p['id'],odds_band=p['odds_band'],closing_probability=probability,price_advantage=p['odds']*probability-1 if probability is not None else None,forecast_minus_close=p['probability']-probability if probability is not None else None))
    for band,b in bands.items():
        rows=[r for r in graded if r['odds_band']==band and r['price_advantage'] is not None]
        b['closing_matches']=len(rows)
        b['mean_price_advantage']=sum(r['price_advantage'] for r in rows)/len(rows) if rows else None
        b['mean_forecast_minus_close']=sum(r['forecast_minus_close'] for r in rows)/len(rows) if rows else None
    return dict(status='evaluated' if bands else 'insufficient_historical_prices_or_eligible_bets',folds=folds,selected=len(predictions),graded=len(settlements),bands=bands,closing_comparisons=graded,notes=['$100 flat stakes; first eligible observation per contract/side.','Near-kickoff recorded Pinnacle price, not a guaranteed last tradable price.','Missing archived inactives/prices block picks; missing closes leave price comparison blank.','Multiple bets within one game are not independent evidence.'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    result=replay(json.loads(Path(args.input).read_text()))
    Path(args.output).write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps({k:result[k] for k in ('status','selected','graded','bands')}))


if __name__=='__main__':main()
