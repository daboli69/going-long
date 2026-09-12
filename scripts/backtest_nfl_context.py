"""Expanding-week NFL score baseline. No invented historical betting prices."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo
from topdown.model import secondary_baseline


def walk_forward(games):
    folds=defaultdict(list)
    for game in games:
        if game.get('home_score') is None or game.get('away_score') is None:continue
        folds[(game['season'],game['week'])].append(game)
    history=[];results=[]
    for (season,week),test in sorted(folds.items()):
        cutoff=min(g['kickoff_ts'] for g in test)
        train=[g for g in history if g['kickoff_ts']+12*3600<cutoff]
        if len(train)>=64:
            league=mean([g[k] for g in train for k in ('home_score','away_score')])
            def rate(team,venue,field):
                prior=[g for g in train if g[venue+'_team']==team]
                current=[g for g in prior if g['season']==season]
                # Only past games enter either window; their overlap is not extra evidence.
                sample=current or prior
                if not sample:return league
                return secondary_baseline(mean(g[field] for g in sample),mean(g[field] for g in sample[-4:]),len(current),league,week)['rating']
            for g in test:
                home=(rate(g['home_team'],'home','home_score')+rate(g['away_team'],'away','home_score'))/2
                away=(rate(g['away_team'],'away','away_score')+rate(g['home_team'],'home','away_score'))/2
                results.append(dict(game_id=g['game_id'],season=season,week=week,training_games=len(train),training_cutoff=datetime.fromtimestamp(cutoff,timezone.utc).isoformat(),projected_margin=home-away,projected_total=home+away,actual_margin=g['home_score']-g['away_score'],actual_total=g['home_score']+g['away_score']))
        history.extend(sorted(test,key=lambda g:g['kickoff_ts']))
    rmse=lambda kind:math.sqrt(mean((r['projected_'+kind]-r['actual_'+kind])**2 for r in results)) if results else None
    return dict(games=len(results),margin_error_points=rmse('margin'),total_error_points=rmse('total'),roi=None,closing_price_advantage=None,notice='Score-only walk-forward baseline. Historical closing prices alone cannot price earlier decisions. Latest nflverse revisions; not a vintage-data archive.',predictions=results)


def main():
    p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=2023);p.add_argument('--end',type=int,default=2026);p.add_argument('--output',default='private/nfl-context-backtest.json');a=p.parse_args()
    import nflreadpy as nfl
    games=nfl.load_schedules(list(range(a.start,a.end+1))).to_dicts()
    usable=[]
    for g in games:
        if g.get('game_type')!='REG' or not g.get('gametime'):continue
        g['kickoff_ts']=datetime.fromisoformat(str(g['gameday'])+'T'+str(g['gametime'])).replace(tzinfo=ZoneInfo('America/New_York')).timestamp()
        if g['kickoff_ts']+12*3600<datetime.now(timezone.utc).timestamp():usable.append(g)
    result=walk_forward(usable);Path(a.output).write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({k:v for k,v in result.items() if k!='predictions'}))


if __name__=='__main__':main()
