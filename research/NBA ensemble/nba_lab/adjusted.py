"""Opponent context is historical pregame context; release results only after24h."""
from collections import defaultdict,deque
import heapq
import numpy as np
import pandas as pd
from .config import CACHE,REPORTS,now,digest
from .features import rates
from .research_io import update

ADJUSTED=('adj_margin','adj_attack','adj_defense')


def build(base,games,boxes):
    if base.game_id.duplicated().any() or games.game_id.duplicated().any():raise ValueError('Duplicate feature/game identity')
    if boxes.duplicated(['game_id','team_id']).any():raise ValueError('Duplicate team box identity')
    context=base.set_index('game_id');lookup={(str(r.game_id),str(r.team_id)):r._asdict() for r in boxes.itertuples(index=False)}
    history=defaultdict(lambda:deque(maxlen=20));queue=[];rows=[];latest=None
    for g in games.sort_values(['tipoff','game_id']).itertuples(index=False):
        if str(g.game_id) not in context.index:continue
        prior=context.loc[str(g.game_id)];decision=pd.Timestamp(prior.decision_at)
        while queue and queue[0][0]<decision:
            available,_,entries=heapq.heappop(queue)
            for team,stats in entries:history[team].append(stats)
            latest=available
        row={'game_id':str(g.game_id),'adjusted_latest_available_at':latest}
        home,away=str(g.home_id),str(g.away_id)
        for side,team in [('home',home),('away',away)]:
            for stat in ADJUSTED:
                values=[r[stat] for r in history[team] if np.isfinite(r[stat])]
                row[f'{side}_{stat}_20']=float(np.mean(values)) if values else np.nan
        for stat in ADJUSTED:row[f'diff_{stat}_20']=row[f'home_{stat}_20']-row[f'away_{stat}_20']
        rows.append(row)
        # Future/current-game outcomes never enter this game's features.
        if g.completed:
            own=lookup.get((str(g.game_id),home),{});opp=lookup.get((str(g.game_id),away),{})
            if own and own.get('points')!=g.home_score:own={}
            if opp and opp.get('points')!=g.away_score:opp={}
            hr=rates(own,opp,g.home_score,g.away_score);ar=rates(opp,own,g.away_score,g.home_score)
            entries=[]
            for side,other,team,stat in [('home','away',home,hr),('away','home',away,ar)]:
                entries.append((team,{'adj_margin':stat['margin']+prior[f'{other}_margin_20'],
                    'adj_attack':stat['ortg']-prior[f'{other}_drtg_20'],
                    'adj_defense':stat['drtg']-prior[f'{other}_ortg_20']}))
            heapq.heappush(queue,(pd.Timestamp(g.tipoff)+pd.Timedelta(hours=24),str(g.game_id),entries))
    out=base.merge(pd.DataFrame(rows),on='game_id',validate='one_to_one')
    available=pd.to_datetime(out.adjusted_latest_available_at,utc=True)
    if (available.notna()&available.ge(out.decision_at)).any():raise AssertionError('Opponent-adjustment availability leak')
    return out


def run():
    source=CACHE/'features.parquet';games_path=CACHE/'games.parquet';box_path=CACHE/'team_boxes.parquet'
    inputs={str(p):digest(p) for p in (source,games_path,box_path)}
    path=CACHE/'improvement_features.parquet';meta=CACHE/'IMPROVEMENT_FEATURES.json'
    from .config import read
    if path.exists() and meta.exists() and read(meta)['inputs']==inputs:return pd.read_parquet(path)
    base=pd.read_parquet(source);games=pd.read_parquet(games_path);boxes=pd.read_parquet(box_path)
    out=build(base,games,boxes);out.to_parquet(path,index=False)
    update(meta,{'created_at':now(),'rows':len(out),'inputs':inputs,'formulas':'See docs/IMPROVEMENTS_PREREGISTRATION.md'})
    return out
