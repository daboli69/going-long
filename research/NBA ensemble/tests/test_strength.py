import numpy as np
import pandas as pd
from nba_lab import features as F,strength as S

COLS=[*S.RATING,*S.TRAVEL,*S.ROSTER]


def games(n=30):
    return pd.DataFrame([{'game_id':str(i),'season':2024,'tipoff':pd.Timestamp('2024-01-01T00:00Z')+pd.Timedelta(days=2*i),
        'home_id':'1' if i%2 else '2','away_id':'2' if i%2 else '1','home':'DEN' if i%2 else 'BOS','away':'BOS' if i%2 else 'DEN',
        'home_score':110+(i%2),'away_score':100+(i%3),'completed':True,'neutral':False} for i in range(n)])


def boxes(d):
    return pd.DataFrame([{'game_id':r.game_id,'team_id':t,'points':p,'fgm':40,'fg3m':10,'fga':85,'fta':20,'oreb':10,'dreb':30,'tov':12}
        for r in d.itertuples() for t,p in [(r.home_id,r.home_score),(r.away_id,r.away_score)]])


def players(d):
    rows=[]
    for r in d.itertuples():
        for team in (r.home_id,r.away_id):
            for k in range(8):
                rows.append({'game_id':r.game_id,'team_id':team,'athlete_id':f'{team}-{k}','minutes':30.,'did_not_play':False,
                             'points':10+k,'field_goals_made':4,'field_goals_attempted':9,'free_throws_made':2,'free_throws_attempted':2,
                             'offensive_rebounds':1,'defensive_rebounds':3,'steals':1,'assists':2,'blocks':0,'fouls':2,'turnovers':1})
    return pd.DataFrame(rows)


def make(d,p=None,asof='2025-01-01T00:00Z'):
    base,_=F.build(d,boxes(d),asof=asof);return S.build(base,d,players(d) if p is None else p)


def test_target_and_future_outcomes_cannot_change_strength_features():
    d=games();x=make(d)
    changed=d.copy();changed.loc[20:,['home_score','away_score']]=[[60,140]]*10
    p=players(changed);p.loc[p.game_id.astype(int).ge(20),'points']=60
    y=make(changed,p)
    pd.testing.assert_frame_equal(x.loc[:20,COLS],y.loc[:20,COLS])
    assert not x.loc[21:,'diff_mov_elo'].equals(y.loc[21:,'diff_mov_elo'])


def test_results_inside_24_hours_are_not_used():
    d=games(3);d.loc[1,'tipoff']=d.loc[0,'tipoff']+pd.Timedelta(hours=20)
    x=make(d)
    assert x.loc[1,'diff_mov_elo']==0 and np.isnan(x.loc[1,'diff_ridge_net']) and np.isnan(x.loc[1,'diff_roster_gmsc'])
    assert pd.to_datetime(x.strength_latest_available_at,utc=True).dropna().lt(x.decision_at[x.strength_latest_available_at.notna()]).all()


def test_travel_altitude_and_bubble_are_calendar_only():
    d=games(4);x=make(d)
    assert x.loc[1,'altitude_home']==1 and x.loc[0,'altitude_home']==0
    assert x.loc[0,'diff_travel_1000km']<-2.5 and x.loc[0,'diff_tz_shift']==-2 # Denver flies to Boston
    bubble=games(2);bubble['season']=2020;bubble['tipoff']=pd.Timestamp('2020-08-01T00:00Z')+pd.Timedelta(days=2)*np.arange(2)
    y=make(bubble)
    assert (y.altitude_home==0).all()


def test_absent_rotation_player_is_counted_without_target_box():
    d=games(14);p=players(d)
    p=p[~(p.game_id.eq('12')&p.athlete_id.eq('1-0'))]
    x=make(d,p)
    # Team 1 is away in game 12 and home in 13; its star missed 12, released before 13.
    assert x.loc[13,'diff_absent_gmsc']>0 and x.loc[12,'diff_absent_gmsc']==0
