"""Offline retrospective diagnostic; revised public data, not live receipts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import props_challenger as P
from game_challenger import load_games
from td_volume import snap_games
from scripts.trend_research import champion

POSITIONS = {'pass_yds':['QB'], 'pass_tds':['QB'], 'receptions':['RB','WR','TE'], 'rec_yds':['RB','WR','TE'], 'rush_yds':['QB','RB','WR','TE']}


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def replay(cache, schedule):
    # An offline adapter; no private inputs or provider calls.
    old_cache, old_download = champion.cache, champion._download
    champion.cache = lambda _: cache
    def offline(_, destination):
        if not destination.exists():
            raise ValueError('Offline cache incomplete: '+str(destination))
        return destination
    champion._download = offline
    try:
        appearances = champion.appearances(ROOT, range(2019,2026))
    finally:
        champion.cache, champion._download = old_cache, old_download
    games = load_games(schedule)
    game_by_team = {(g['season'],g['week'],team):g for g in games for team in [g['home'],g['away']]}
    weekly_cutoff = {}
    for g in games:
        key = (g['season'],g['week'])
        weekly_cutoff[key] = min(weekly_cutoff.get(key,float('inf')),g['kickoff'])
    raw_schedule = pd.read_csv(schedule)
    starts = champion.verified_starts(raw_schedule[raw_schedule.season.between(2019,2025)])
    snap_ids = snap_games(cache)
    rows = []
    for r in appearances.to_dict('records'):
        g = game_by_team.get((r['season'],r['week'],r['team']))
        if not g or snap_ids.get((r['player_id'],r['season'],r['week'])) != g['id']:
            continue
        item = {k:r[k] for k in ['player_id','team','position']}
        item.update(season=int(r['season']),week=int(r['week']),game_id=g['id'],game_type='REG',
                    completed=True,participated=True,verified_start=starts.get((r['season'],r['week'],r['team']))==r['player_id'],
                    kickoff=stamp(g['kickoff']),available_at=stamp(g['kickoff']+43200))
        for dest, source in [('attempts','attempts'),('carries','carries'),('targets','targets'),('pass_yds','passing_yards'),('pass_tds','passing_tds'),('receptions','receptions'),('rec_yds','receiving_yards'),('rush_yds','rushing_yards')]:
            item[dest] = float(r[source])
        rows.append(item)
    priors, excluded = {}, {}
    for market, positions in POSITIONS.items():
        for position in positions:
            earlier = [r for r in rows if r['position']==position and r['season']<=2022]
            supported = []
            for r in earlier:
                try:
                    supported.extend(P._rows([r],market,float('inf')))
                except ValueError as error:
                    reason='training unsupported '+market+': '+str(error)
                    excluded[reason]=excluded.get(reason,0)+1
            priors[(market,position)] = P.fit_prior(supported,market=market,position=position,trained_through='2023-03-01T00:00:00Z',demand_prior_games=2,efficiency_prior_opportunities=20)
    grouped = {}
    for r in rows:
        grouped.setdefault(r['player_id'],[]).append(r)
    predictions = []
    for pid, player in grouped.items():
        previous = []
        for r in sorted(player,key=lambda x:(x['kickoff'],x['game_id'])):
            cutoff = weekly_cutoff[(r['season'],r['week'])]
            if r['season']>=2023:
                for market, positions in POSITIONS.items():
                    if r['position'] not in positions or market.startswith('pass_') and not r['verified_start']:
                        continue
                    try:
                        P._rows([r],market,float('inf'))
                    except ValueError as error:
                        reason='evaluation unsupported '+market+': '+str(error)
                        excluded[reason]=excluded.get(reason,0)+1
                        continue
                    prior = priors[(market,r['position'])]
                    decision = stamp(cutoff)
                    forecast = P.predict(previous,player_id=pid,team=r['team'],position=r['position'],season=r['season'],market=market,
                                         decision_at=decision,roster_at=stamp(cutoff-3600),roster_verified=True,prior=prior)
                    eligible = [x for x in previous if P._time(x['available_at'])<cutoff and (not market.startswith('pass_') or x['verified_start'])]
                    champion_window = eligible[-12:]
                    if forecast['status']!='experimental' or len(champion_window)<5:
                        reason = forecast.get('reason','Insufficient reconstructed Champion history')
                        excluded[reason] = excluded.get(reason,0)+1
                        continue
                    current = [x for x in eligible if x['season']==r['season']]
                    last_other = max((x['kickoff'] for x in current if x['team']!=r['team']),default='')
                    current = [x for x in current if x['team']==r['team'] and x['kickoff']>last_other]
                    weights = champion.season_weights([x['season'] for x in champion_window],r['season'])
                    predictions.append(dict(season=r['season'],game_id=r['game_id'],player_id=pid,position=r['position'],market=market,
                                            y=r[market],challenger=forecast['mean'],baseline=np.mean([x[market] for x in current]),
                                            raw_champion=sum(w*x[market] for w,x in zip(weights,champion_window)),
                                            opportunity_only=forecast['demand']*np.prod(list(prior['rates'].values())),
                                            unshrunk=(sum(x[P.MARKETS[market][0]] for x in current)/len(current))*(sum(x[market] for x in current)/sum(x[P.MARKETS[market][0]] for x in current))))
            previous.append(r)
    return predictions, priors, excluded


def summarize(rows):
    report = {}
    rng = np.random.default_rng(20261011)
    for market in POSITIONS:
        report[market] = {}
        for season in [2023,2024,2025]:
            f = pd.DataFrame([r for r in rows if r['market']==market and r['season']==season])
            if f.empty:
                report[market][str(season)]={'n':0};continue
            models={}
            for name in ['challenger','baseline','raw_champion','opportunity_only','unshrunk']:
                e=f[name].to_numpy(float)-f.y.to_numpy(float)
                models[name]={'mae':float(np.abs(e).mean()),'rmse':float(np.sqrt((e*e).mean())),'bias':float(e.mean())}
            paired={}
            for other in ['baseline','raw_champion']:
                delta=np.abs(f.challenger-f.y)-np.abs(f[other]-f.y)
                paired[other]={}
                for cluster in ['game_id','player_id']:
                    codes,_=pd.factorize(f[cluster]);sums=np.bincount(codes,weights=delta);counts=np.bincount(codes)
                    draws=rng.integers(0,len(counts),size=(1000,len(counts)))
                    boot=sums[draws].sum(axis=1)/counts[draws].sum(axis=1)
                    paired[other][cluster]={'delta_challenger_minus_other':float(delta.mean()),'ci95':[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))]}
            report[market][str(season)]={'n':len(f),'games':int(f.game_id.nunique()),'players':int(f.player_id.nunique()),'models':models,'paired_mae':paired,
                                        'positions':{pos:{'n':len(g),'mae':{name:float(np.abs(g[name]-g.y).mean()) for name in ['challenger','baseline','raw_champion']}} for pos,g in f.groupby('position')}}
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cache',type=Path,default=ROOT/'.cache/model-confidence-public');parser.add_argument('--schedule',type=Path,default=ROOT/'.cache/model-confidence-games.csv');parser.add_argument('--output',type=Path,default=HERE/'props_results.json');args=parser.parse_args()
    rows,priors,excluded=replay(args.cache,args.schedule)
    result={'status':'retrospective_diagnostic_no_promotion','protocol':'props_protocol.json','training':'2019–2022 complete public observations; 2016–2018 unavailable; no fallback fabricated',
            'reports':summarize(rows),'priors':{m+'|'+p:v for (m,p),v in priors.items()},'exclusions':excluded,
            'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in list(args.cache.glob('*.csv'))+[args.schedule]},
            'limitations':['Revised public data; kickoff+12h is an assumed conservative result delay, not a historical feed receipt.','Conditioned on positive offensive snaps and retrospectively observed QB starts; roster verification is a labeled retrospective oracle, not pregame injury validation.','2024–25 previously researched; no untouched prospective promotion holdout.','Raw Champion weighted-mean policy only; passing-yards refit, probability calibration and injury adjustments are not reproduced.','All comparisons are projections; no synthetic lines, market probabilities or profit claim.','No 2026 outcomes loaded.']}
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({m:{s:{'n':v['n'],'mae':{k:r['mae'] for k,r in v.get('models',{}).items()}} for s,v in seasons.items()} for m,seasons in result['reports'].items()},indent=2))
