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
from football_context import build_scope
from pbp_features import player_ids


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


def walk_forward_roles(rows, snaps, roster, charts, season):
    """Measure next-game results for role flags using only earlier games.

    This does not turn the screen into a projection adjustment. It records whether
    the mechanism survives chronological testing so a later model change can be
    compared with an untouched future period.
    """
    games=defaultdict(list)
    for row in rows:
        if row.get('season')==season and row.get('season_type')=='REG' and row.get('week') is not None:
            games[int(row['week'])].append(row)
    chart={(str(r.get('nflverse_game_id')),r.get('play_id')):r for r in charts}
    records=[]
    for week,test in sorted(games.items()):
        if week<4:continue
        cutoff=min(str(r.get('game_date'))[:10] for r in test)
        scope=build_scope(rows,snaps,roster,charts,season,cutoff)
        actual=defaultdict(lambda:{'yards':0,'catches':0});appeared=set()
        for r in test:
            if r.get('qb_dropback')==1:
                appeared.update(player_ids(chart.get((str(r.get('game_id')),r.get('play_id')),{}).get('offense_players')))
            pid=r.get('receiver_player_id')
            if pid:
                appeared.add(pid);actual[pid]['yards']+=r.get('receiving_yards') or 0;actual[pid]['catches']+=r.get('complete_pass') or 0
        for pid,p in scope['players'].items():
            signal=p.get('role_signal') or {}
            if pid not in appeared or not signal.get('eligible') or not p.get('games'):continue
            baseline_yards=p.get('yards',0)/p['games'];baseline_catches=p.get('actual_catches',0)/p['games']
            records.append({'season':season,'week':week,'cutoff':cutoff,'player_id':pid,'position':p['position'],
                            'status':signal['status'],'above_average':signal['above_average'],'unrewarded':signal['unrewarded'],
                            'baseline_yards':baseline_yards,'actual_yards':actual[pid]['yards'],
                            'baseline_catches':baseline_catches,'actual_catches':actual[pid]['catches']})
    def group(name,predicate):
        sample=[r for r in records if predicate(r)]
        return {'name':name,'players_games':len(sample),
                'mean_yards':mean(r['actual_yards'] for r in sample) if sample else None,
                'baseline_yards':mean(r['baseline_yards'] for r in sample) if sample else None,
                'mean_yards_vs_baseline':mean(r['actual_yards']-r['baseline_yards'] for r in sample) if sample else None,
                'yards_baseline_mae':mean(abs(r['actual_yards']-r['baseline_yards']) for r in sample) if sample else None,
                'mean_catches_vs_baseline':mean(r['actual_catches']-r['baseline_catches'] for r in sample) if sample else None}
    groups=[group('all_eligible',lambda r:True),group('above_average_role',lambda r:r['above_average']),group('role_ahead_of_results',lambda r:r['unrewarded'])]
    return {'schema_version':1,'season':season,'validation_scope':'chronological_next_game_diagnostic','promotion_eligible':False,
            'decision':'experimental_only','records':records,'groups':groups,
            'method':'Each weekly flag uses only games dated before that week. Actual participation is used only to decide whether the player appeared in the graded game. No market prices, ROI or claimed lift.',
            'limitations':['Latest nflverse revisions are not a vintage archive.','Actual game participation is known retrospectively.','No projection adjustment is promoted from this diagnostic.']}


def main():
    p=argparse.ArgumentParser();p.add_argument('--start',type=int,default=2023);p.add_argument('--end',type=int,default=2026);p.add_argument('--output',default='private/nfl-context-backtest.json');p.add_argument('--role-season',type=int);p.add_argument('--role-output',default='data/football_role_validation.json');p.add_argument('--role-records-output',default='private/football_role_validation_records.json');a=p.parse_args()
    import nflreadpy as nfl
    games=nfl.load_schedules(list(range(a.start,a.end+1))).to_dicts()
    usable=[]
    for g in games:
        if g.get('game_type')!='REG' or not g.get('gametime'):continue
        g['kickoff_ts']=datetime.fromisoformat(str(g['gameday'])+'T'+str(g['gametime'])).replace(tzinfo=ZoneInfo('America/New_York')).timestamp()
        if g['kickoff_ts']+12*3600<datetime.now(timezone.utc).timestamp():usable.append(g)
    result=walk_forward(usable);Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({k:v for k,v in result.items() if k!='predictions'}))
    if a.role_season:
        rows=nfl.load_pbp([a.role_season]).to_dicts();snaps=nfl.load_snap_counts([a.role_season]).to_dicts();roster=nfl.load_rosters([a.role_season]).to_dicts();charts=nfl.load_participation([a.role_season]).to_dicts()
        role=walk_forward_roles(rows,snaps,roster,charts,a.role_season)
        records_path=Path(a.role_records_output);records_path.parent.mkdir(parents=True,exist_ok=True);records_path.write_text(json.dumps(role,indent=2,allow_nan=False))
        summary={k:v for k,v in role.items() if k!='records'};summary['audited_player_games']=len(role['records'])
        path=Path(a.role_output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(summary,indent=2,allow_nan=False));print(json.dumps(summary))


if __name__=='__main__':main()
