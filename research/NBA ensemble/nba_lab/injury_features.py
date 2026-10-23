"""Value of players listed Out/Doubtful or Questionable on the official pregame injury report."""
from collections import defaultdict,deque
import heapq
import numpy as np
import pandas as pd
from .config import CACHE,now,digest,read
from .strength import gmsc,PLAYER_PRIOR_MIN,PLAYER_REPLACEMENT,PLAYER_GAMES
from .research_io import update

# Fixed before any outcome evaluation (docs/INJURY_PREREGISTRATION.md).
TEAM_GAMES=10;OUT=('Out','Doubtful');QUESTIONABLE=('Questionable',)
INJURY=('diff_out_gmsc','diff_questionable_gmsc')


def build(base,games,players,reports):
    if base.game_id.duplicated().any():raise ValueError('Duplicate feature identity')
    context=base.set_index('game_id')
    box=defaultdict(lambda:defaultdict(list))
    played=players[players.minutes.fillna(0).gt(0)&~players.did_not_play.astype(bool)]
    for r in played.to_dict('records'):
        box[str(r['game_id'])][str(r['team_id'])].append((str(r['athlete_id']),float(r['minutes']),gmsc(r)))
    listed=defaultdict(list)
    for r in reports.dropna(subset=['game_id','team_id']).to_dict('records'):
        listed[(str(r['game_id']),str(r['team_id']))].append(r)
    history=defaultdict(lambda:deque(maxlen=PLAYER_GAMES));team_games=defaultdict(lambda:deque(maxlen=TEAM_GAMES))
    queue=[];rows=[];latest=None

    def per_minute(a):
        h=history[a];m=sum(x for x,_ in h);s=sum(y for _,y in h)
        return (s+PLAYER_PRIOR_MIN*PLAYER_REPLACEMENT)/(m+PLAYER_PRIOR_MIN)

    def value(gid,team,decision):
        entries=listed.get((gid,team),[])
        if any(e['not_yet_submitted'] for e in entries):return np.nan,np.nan,None
        recent=team_games[team]
        if not recent:return np.nan,np.nan,None
        stamps=[pd.Timestamp(e['available_at']) for e in entries]
        if any(t>=decision for t in stamps):raise AssertionError('Injury report not available before decision')
        expected=lambda a:sum(g.get(a,0.) for g in recent)/len(recent)
        out=sum(per_minute(e['athlete_id'])*expected(e['athlete_id']) for e in entries if e['status'] in OUT and e['athlete_id'])
        q=sum(per_minute(e['athlete_id'])*expected(e['athlete_id']) for e in entries if e['status'] in QUESTIONABLE and e['athlete_id'])
        return out,q,max(stamps) if stamps else None

    for g in games.sort_values(['tipoff','game_id']).itertuples(index=False):
        gid=str(g.game_id)
        if gid not in context.index:continue
        decision=pd.Timestamp(context.loc[gid,'decision_at'])
        while queue and queue[0][0]<decision:
            available,old=heapq.heappop(queue);latest=available
            for team,entries in box.get(old,{}).items():
                team_games[team].append({a:m for a,m,_ in entries})
                for a,m,s in entries:history[a].append((m,s))
        home,away=str(g.home_id),str(g.away_id)
        ho,hq,ht=value(gid,home,decision);ao,aq,at=value(gid,away,decision)
        stamps=[t for t in (ht,at) if t is not None]
        rows.append({'game_id':gid,'diff_out_gmsc':ho-ao,'diff_questionable_gmsc':hq-aq,'home_out_gmsc':ho,'away_out_gmsc':ao,
                     'injury_box_latest_available_at':latest,'injury_report_available_at':max(stamps) if stamps else pd.NaT})
        if g.completed and pd.notna(g.home_score):heapq.heappush(queue,(pd.Timestamp(g.tipoff)+pd.Timedelta(hours=24),gid))
    out=base.merge(pd.DataFrame(rows),on='game_id',validate='one_to_one')
    decision=pd.to_datetime(out.decision_at,utc=True)
    for col in ('injury_box_latest_available_at','injury_report_available_at'):
        t=pd.to_datetime(out[col],utc=True)
        if (t.notna()&t.ge(decision)).any():raise AssertionError('Injury feature availability leak: '+col)
    return out


def run(force=False):
    from .strength import run as strength_run
    base=strength_run()
    paths=[CACHE/'strength_features.parquet',CACHE/'games.parquet',CACHE/'player_boxes.parquet',CACHE/'injury_reports.parquet']
    inputs={p.name:digest(p) for p in paths}
    path=CACHE/'injury_features.parquet';meta=CACHE/'INJURY_FEATURES.json'
    if not force and path.exists() and meta.exists() and read(meta)['inputs']==inputs:return pd.read_parquet(path)
    out=build(base,pd.read_parquet(paths[1]),pd.read_parquet(paths[2]),pd.read_parquet(paths[3]))
    out.to_parquet(path,index=False)
    update(meta,{'created_at':now(),'rows':len(out),'inputs':inputs,'columns':list(INJURY),'protocol':'docs/INJURY_PREREGISTRATION.md'})
    return out
