"""Margin ratings, travel and recent-roster strength; every result released only after tipoff+24h."""
from collections import defaultdict,deque
import heapq
import math
import numpy as np
import pandas as pd
from .config import CACHE,now,digest,read
from .research_io import update

# Fixed before any outcome evaluation (docs/STRENGTH_PREREGISTRATION.md).
MOV_K,MOV_HFA,MOV_CARRY=20.,100.,.75
RIDGE_HALF_LIFE,RIDGE_LAMBDA,RIDGE_CAP=45.,5.,30.
PLAYER_PRIOR_MIN,PLAYER_REPLACEMENT,PLAYER_GAMES,ROTATION_GAMES,ABSENT_MPG=150.,.22,40,5,20.
# Arena latitude, longitude, standard UTC offset and altitude flag (public arena locations).
ARENAS={'ATL':(33.757,-84.396,-5,0),'BKN':(40.683,-73.976,-5,0),'BOS':(42.366,-71.062,-5,0),'CHA':(35.225,-80.839,-5,0),
    'CHI':(41.881,-87.674,-6,0),'CLE':(41.497,-81.688,-5,0),'DAL':(32.790,-96.810,-6,0),'DEN':(39.749,-105.008,-7,1),
    'DET':(42.341,-83.055,-5,0),'GS':(37.768,-122.388,-8,0),'HOU':(29.751,-95.362,-6,0),'IND':(39.764,-86.155,-5,0),
    'LAC':(33.945,-118.341,-8,0),'LAL':(34.043,-118.267,-8,0),'MEM':(35.138,-90.051,-6,0),'MIA':(25.781,-80.188,-5,0),
    'MIL':(43.045,-87.917,-6,0),'MIN':(44.979,-93.276,-6,0),'NO':(29.949,-90.082,-6,0),'NY':(40.751,-73.993,-5,0),
    'OKC':(35.463,-97.515,-6,0),'ORL':(28.539,-81.384,-5,0),'PHI':(39.901,-75.172,-5,0),'PHX':(33.446,-112.071,-7,0),
    'POR':(45.532,-122.667,-8,0),'SA':(29.427,-98.438,-6,0),'SAC':(38.580,-121.500,-8,0),'TOR':(43.643,-79.379,-5,0),
    'UTAH':(40.768,-111.901,-7,1),'WSH':(38.898,-77.021,-5,0)}
BUBBLE=(pd.Timestamp('2020-07-01',tz='UTC'),pd.Timestamp('2020-10-31',tz='UTC'))
RATING=('diff_mov_elo','diff_ridge_net')
TRAVEL=('diff_travel_1000km','diff_tz_shift','altitude_home')
ROSTER=('diff_roster_gmsc','diff_absent_gmsc')
EPOCH=pd.Timestamp('2014-09-01',tz='UTC')


def venue(g):
    """Known calendar location; neutral sites and the 2020 Orlando restart have no home arena."""
    tip=pd.Timestamp(g.tipoff)
    if BUBBLE[0]<=tip<=BUBBLE[1] and int(g.season)==2020:return ARENAS['ORL'],True
    if g.neutral:return None,True
    return ARENAS.get(g.home),False


def km(a,b):
    if a is None or b is None:return np.nan
    p1,p2=math.radians(a[0]),math.radians(b[0]);dl=math.radians(b[1]-a[1])
    h=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 12742*math.asin(min(1.,math.sqrt(h)))


def gmsc(r):
    f=lambda k:float(r.get(k) or 0)
    return (f('points')+.4*f('field_goals_made')-.7*f('field_goals_attempted')-.4*(f('free_throws_attempted')-f('free_throws_made'))
            +.7*f('offensive_rebounds')+.3*f('defensive_rebounds')+f('steals')+.7*f('assists')+.7*f('blocks')-.4*f('fouls')-f('turnovers'))


class Ridge:
    """Exponentially decayed ridge margin ratings; weights rescaled analytically to avoid refits per game."""
    def __init__(self):
        self.index={};self.A=np.zeros((1,1));self.b=np.zeros(1)
    def column(self,team):
        if team not in self.index:
            n=len(self.index)+1;self.index[team]=n
            A=np.zeros((n+1,n+1));A[:n,:n]=self.A;self.A=A;self.b=np.append(self.b,0.)
        return self.index[team]
    def add(self,home,away,margin,neutral,tip):
        i,j=self.column(home),self.column(away);x=np.zeros(len(self.b));x[0]=0. if neutral else 1.;x[i]=1.;x[j]=-1.
        w=2**((tip-EPOCH).total_seconds()/86400/RIDGE_HALF_LIFE)
        self.A+=w*np.outer(x,x);self.b+=w*float(np.clip(margin,-RIDGE_CAP,RIDGE_CAP))*x
    def ratings(self,at):
        if len(self.b)<3:return {}
        s=2**(-(at-EPOCH).total_seconds()/86400/RIDGE_HALF_LIFE)
        penalty=np.full(len(self.b),RIDGE_LAMBDA);penalty[0]=1e-3
        r=np.linalg.solve(s*self.A+np.diag(penalty),s*self.b)
        return {t:r[k] for t,k in self.index.items()}


def roster_value(players,team_games,team):
    """Pregame roster estimate from the latest released team game; never the target game's box."""
    recent=team_games[team]
    if not recent:return np.nan,np.nan
    def per_minute(athlete):
        rows=players[athlete]
        minutes=sum(m for m,_ in rows);score=sum(s for _,s in rows)
        return (score+PLAYER_PRIOR_MIN*PLAYER_REPLACEMENT)/(minutes+PLAYER_PRIOR_MIN)
    latest=recent[-1];expected={}
    for athlete in latest:
        played=[game[athlete] for game in list(recent)[-ROTATION_GAMES:] if athlete in game]
        expected[athlete]=float(np.mean(played))
    total=sum(expected.values())
    strength=sum(per_minute(a)*m for a,m in expected.items())*240/total if total>0 else np.nan
    window=list(recent)[-10:];absent=0.
    for athlete in {a for game in window for a in game}:
        mpg=sum(game.get(athlete,0.) for game in window)/len(window)
        if mpg>=ABSENT_MPG and athlete not in latest:absent+=per_minute(athlete)*mpg
    return strength,absent


def build(base,games,players=None):
    if base.game_id.duplicated().any() or games.game_id.duplicated().any():raise ValueError('Duplicate feature/game identity')
    context=base.set_index('game_id')
    box=defaultdict(lambda:defaultdict(list))
    if players is not None and len(players):
        played=players[players.minutes.fillna(0).gt(0)&~players.did_not_play.astype(bool)]
        for r in played[['game_id','team_id','athlete_id','minutes']+[c for c in played if c in (
                'points','field_goals_made','field_goals_attempted','free_throws_attempted','free_throws_made','offensive_rebounds',
                'defensive_rebounds','steals','assists','blocks','fouls','turnovers')]].to_dict('records'):
            box[str(r['game_id'])][str(r['team_id'])].append((str(r['athlete_id']),float(r['minutes']),gmsc(r)))
    elo=defaultdict(lambda:1500.);ridge=Ridge();queue=[];rows=[];latest=None;season=None
    last_venue={};players_hist=defaultdict(lambda:deque(maxlen=PLAYER_GAMES));team_games=defaultdict(lambda:deque(maxlen=10));cached=None
    for g in games.sort_values(['tipoff','game_id']).itertuples(index=False):
        gid=str(g.game_id)
        if gid not in context.index:continue
        decision=pd.Timestamp(context.loc[gid,'decision_at']);changed=False
        while queue and queue[0][0]<decision:
            available,_,old=heapq.heappop(queue);latest=available;changed=True
            home,away=str(old.home_id),str(old.away_id);margin=float(old.home_score-old.away_score)
            diff=elo[home]-elo[away]+(0 if old.neutral else MOV_HFA);p=1/(1+10**(-diff/400))
            winner_diff=diff if margin>0 else -diff
            change=MOV_K*((abs(margin)+3)**.8)/(7.5+.006*winner_diff)*(float(margin>0)-p)
            elo[home]+=change;elo[away]-=change
            ridge.add(home,away,margin,bool(old.neutral) or venue(old)[1],pd.Timestamp(old.tipoff))
            for team,entries in box.get(str(old.game_id),{}).items():
                team_games[team].append({a:m for a,m,_ in entries})
                for a,m,s in entries:players_hist[a].append((m,s))
        if changed or cached is None:cached=ridge.ratings(decision)
        if season is not None and g.season!=season:
            for team in elo:elo[team]=1500+MOV_CARRY*(elo[team]-1500)
        season=g.season;home,away=str(g.home_id),str(g.away_id)
        here,neutral=venue(g);row={'game_id':gid,'strength_latest_available_at':latest}
        row['diff_mov_elo']=elo[home]-elo[away]
        row['diff_ridge_net']=cached.get(home,0.)-cached.get(away,0.) if cached else np.nan
        travel={}
        for side,team in (('home',home),('away',away)):
            before=last_venue.get(team,ARENAS.get(g.home if side=='home' else g.away))
            travel[side]=(km(before,here)/1000,abs(here[2]-before[2]) if here and before else np.nan)
            last_venue[team]=here or before
        row['diff_travel_1000km']=travel['home'][0]-travel['away'][0]
        row['diff_tz_shift']=travel['home'][1]-travel['away'][1]
        row['altitude_home']=float(bool(here and not neutral and here[3]))
        if box:
            hs,ha=roster_value(players_hist,team_games,home);as_,aa=roster_value(players_hist,team_games,away)
            row['diff_roster_gmsc']=hs-as_;row['diff_absent_gmsc']=ha-aa
        else:row['diff_roster_gmsc']=row['diff_absent_gmsc']=np.nan
        rows.append(row)
        if g.completed and pd.notna(g.home_score):
            heapq.heappush(queue,(pd.Timestamp(g.tipoff)+pd.Timedelta(hours=24),gid,g))
    out=base.merge(pd.DataFrame(rows),on='game_id',validate='one_to_one')
    available=pd.to_datetime(out.strength_latest_available_at,utc=True)
    if (available.notna()&available.ge(pd.to_datetime(out.decision_at,utc=True))).any():raise AssertionError('Strength feature availability leak')
    return out


def run(force=False):
    paths=[CACHE/'features.parquet',CACHE/'games.parquet',CACHE/'player_boxes.parquet']
    inputs={p.name:digest(p) for p in paths if p.exists()}
    path=CACHE/'strength_features.parquet';meta=CACHE/'STRENGTH_FEATURES.json'
    if not force and path.exists() and meta.exists() and read(meta)['inputs']==inputs:return pd.read_parquet(path)
    base=pd.read_parquet(paths[0]);games=pd.read_parquet(paths[1])
    players=pd.read_parquet(paths[2]) if paths[2].exists() else None
    out=build(base,games,players);out.to_parquet(path,index=False)
    update(meta,{'created_at':now(),'rows':len(out),'inputs':inputs,'columns':[*RATING,*TRAVEL,*ROSTER],
                 'protocol':'docs/STRENGTH_PREREGISTRATION.md'})
    return out
