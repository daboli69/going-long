"""Reconstruct pregame rows; release completed results only after tipoff +24h."""
from collections import defaultdict,deque
import heapq
import numpy as np
import pandas as pd
from .config import CACHE,DATA,atomic,now

STATS=('win','margin','points','allowed','poss','ortg','drtg','efg','tov_rate','orb_rate','ft_rate')


def rates(own,opp,points,allowed):
    def number(row,key):return float(row.get(key,np.nan))
    def divide(x,y):return x/y if np.isfinite(x) and np.isfinite(y) and y>0 else np.nan
    fga,fta,oreb,tov=[number(own,k) for k in ('fga','fta','oreb','tov')]
    poss=fga+.44*fta-oreb+tov
    oposs=number(opp,'fga')+.44*number(opp,'fta')-number(opp,'oreb')+number(opp,'tov')
    return {'points':points,'allowed':allowed,'margin':points-allowed,'win':float(points>allowed),
        'poss':poss if np.isfinite(poss) and poss>0 else np.nan,'ortg':100*divide(points,poss),
        'drtg':100*divide(allowed,oposs),'efg':divide(number(own,'fgm')+.5*number(own,'fg3m'),fga),
        'tov_rate':divide(tov,fga+.44*fta+tov),'orb_rate':divide(oreb,oreb+number(opp,'dreb')),
        'ft_rate':divide(fta,fga)}


def build(games,boxes,asof=None):
    asof=pd.Timestamp(asof or pd.Timestamp.now(tz='UTC'))
    games=games.copy();games.tipoff=pd.to_datetime(games.tipoff,utc=True)
    if games.game_id.duplicated().any():raise ValueError('Duplicate game IDs before feature building')
    if boxes.duplicated(['game_id','team_id']).any():raise ValueError('Duplicate team/game boxes')
    lookup={(str(r.game_id),str(r.team_id)):r._asdict() for r in boxes.itertuples(index=False)}
    history=defaultdict(lambda:deque(maxlen=82));elo=defaultdict(lambda:1500.)
    scheduled=defaultdict(list);queue=[];rows=[];quarantine=[];season=None;latest=None
    for g in games.sort_values(['tipoff','game_id']).itertuples(index=False):
        decision=min(g.tipoff,asof)
        while queue and queue[0][0]<decision:
            available,_,old,own,opp=heapq.heappop(queue)
            home,away=str(old.home_id),str(old.away_id)
            probability=1/(1+10**((elo[away]-elo[home]-(0 if old.neutral else 65))/400))
            change=20*(float(old.home_score>old.away_score)-probability)
            elo[home]+=change;elo[away]-=change
            history[home].append(rates(own,opp,old.home_score,old.away_score))
            history[away].append(rates(opp,own,old.away_score,old.home_score))
            latest=available
        if season is not None and g.season!=season:
            for team in elo:elo[team]=1500+.75*(elo[team]-1500)
        season=g.season
        home,away=str(g.home_id),str(g.away_id)
        record={'game_id':str(g.game_id),'season':int(g.season),'tipoff':g.tipoff,'decision_at':decision,
            'home':g.home,'away':g.away,'home_id':home,'away_id':away,'completed':bool(g.completed),
            'home_win':float(g.home_score>g.away_score) if g.completed and g.tipoff+pd.Timedelta(hours=24)<asof else np.nan,
            'result_available_at':g.tipoff+pd.Timedelta(hours=24),
            'latest_input_available_at':latest,'home_history':len(history[home]),'away_history':len(history[away]),
            'neutral':float(g.neutral),'elo_diff':elo[home]-elo[away],
            'elo_probability':1/(1+10**((elo[away]-elo[home]-(0 if g.neutral else 65))/400))}
        vectors={}
        for label,team in [('home',home),('away',away)]:
            data=list(history[team]);values={}
            earlier=[t for t in scheduled[team] if t<g.tipoff]
            days=(g.tipoff-earlier[-1]).total_seconds()/86400 if earlier else 10.
            values['rest_days']=min(10.,max(0.,days));values['back_to_back']=float(days<1.5)
            values['games_last4days']=sum(t>g.tipoff-pd.Timedelta(days=4) for t in earlier)
            for window in (5,10,20):
                for stat in STATS:
                    x=[r[stat] for r in data[-window:] if np.isfinite(r[stat])]
                    values[f'{stat}_{window}']=float(np.mean(x)) if x else np.nan
            for name,value in values.items():record[label+'_'+name]=value
            record[label+'_box_history']=sum(np.isfinite(r['ortg']) for r in data[-20:])
            vectors[label]=values
        for name in vectors['home']:record['diff_'+name]=vectors['home'][name]-vectors['away'][name]
        record['eligible']=min(record['home_history'],record['away_history'])>=10
        rows.append(record)
        # Schedules are known calendar inputs; no future outcome updates enter the queue.
        scheduled[home].append(g.tipoff);scheduled[away].append(g.tipoff)
        if g.completed and g.tipoff+pd.Timedelta(hours=24)<asof:
            own=lookup.get((str(g.game_id),home),{});opp=lookup.get((str(g.game_id),away),{})
            for box,score in [(own,g.home_score),(opp,g.away_score)]:
                if box and box.get('points')!=score:
                    quarantine.append({'game_id':str(g.game_id),'reason':'Box score disagrees with schedule final'})
                    if box is own:own={}
                    else:opp={}
            heapq.heappush(queue,(g.tipoff+pd.Timedelta(hours=24),str(g.game_id),g,own,opp))
    result=pd.DataFrame(rows)
    cutoff=pd.to_datetime(result.latest_input_available_at,utc=True)
    if (cutoff.notna()&cutoff.ge(result.decision_at)).any():raise AssertionError('Feature availability is not strictly pre-decision')
    return result,quarantine


def feature_columns(frame):
    # Explicit whitelist: never select score/result/market fields by accident.
    return ['neutral','elo_diff']+[c for c in frame if c.startswith('diff_')]


def run(asof=None):
    games=pd.read_parquet(CACHE/'games.parquet');boxes=pd.read_parquet(CACHE/'team_boxes.parquet')
    frame,issues=build(games,boxes,asof)
    frame.to_parquet(CACHE/'features.parquet',index=False)
    summary={'created_at':now(),'rows':len(frame),'eligible':int(frame.eligible.sum()),'features':feature_columns(frame),
             'quarantine':issues,'warning':'Reconstructed earlier-game history; revised source data and conservative +24h availability proxy, not historical archived lineups.'}
    atomic(DATA/'FEATURE_AUDIT.json',summary);return frame
