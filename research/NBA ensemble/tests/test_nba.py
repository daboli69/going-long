from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pandas as pd
import pytest
from nba_lab import features as F,models as M,sources as S
from nba_lab.config import KEYS


def games(n=30):
    return pd.DataFrame([{'game_id':str(i),'season':2024,'tipoff':pd.Timestamp('2024-01-01T00:00Z')+pd.Timedelta(days=2*i),
        'home_id':'1','away_id':'2','home':'ONE','away':'TWO','home_score':110+(i%2),'away_score':100+(i%3),
        'completed':True,'neutral':False} for i in range(n)])


def boxes(d):
    return pd.DataFrame([{'game_id':r.game_id,'team_id':t,'points':p,'fgm':40,'fg3m':10,'fga':85,'fta':20,'oreb':10,'dreb':30,'tov':12}
        for r in d.itertuples() for t,p in [(r.home_id,r.home_score),(r.away_id,r.away_score)]])


def test_target_score_and_box_cannot_change_own_pregame_features():
    d=games();b=boxes(d)
    x,_=F.build(d,b,asof='2025-01-01T00:00Z')
    d.loc[20,['home_score','away_score']]=[90,130]
    b.loc[b.game_id.eq('20'),'points']=np.where(b.loc[b.game_id.eq('20'),'team_id'].eq('1'),90,130)
    changed,_=F.build(d,b,asof='2025-01-01T00:00Z')
    pd.testing.assert_series_equal(x.loc[20,F.feature_columns(x)],changed.loc[20,F.feature_columns(changed)])
    assert x.loc[20,'home_win']!=changed.loc[20,'home_win']


def test_result_release_delay_and_future_outcome_canary():
    d=games(3);d.loc[1,'tipoff']=d.loc[0,'tipoff']+pd.Timedelta(hours=20)
    frame,_=F.build(d,boxes(d),asof='2025-01-01T00:00Z')
    assert frame.iloc[1].home_history==0
    before,_=F.build(d,boxes(d),asof='2024-01-02T00:00Z')
    d.loc[2,['home_score','away_score']]=[50,200]
    after,_=F.build(d,boxes(d),asof='2024-01-02T00:00Z')
    pd.testing.assert_frame_equal(before[F.feature_columns(before)],after[F.feature_columns(after)])
    assert after.home_win.isna().all() # strict24h availability, not <=


def test_no_result_or_market_column_in_feature_whitelist():
    d=games();d['closing_line']=4
    f,_=F.build(d,boxes(d),asof='2025-01-01T00:00Z')
    columns=F.feature_columns(f)
    assert not set(columns)&{'home_win','home_score','away_score','completed','closing_line','tipoff'}
    assert pd.to_datetime(f.latest_input_available_at,utc=True).dropna().lt(f.decision_at.iloc[1:]).all()


def test_missing_boxes_are_unknown_and_mismatches_quarantined():
    d=games(3);b=boxes(d);b.loc[0,'points']=999
    f,issues=F.build(d,b,asof='2025-01-01T00:00Z')
    assert issues and np.isnan(f.iloc[1].home_ortg_5)
    assert np.isfinite(f.iloc[1].home_points_5)


def test_duplicate_games_and_boxes_refused():
    d=games(3);b=boxes(d)
    with pytest.raises(ValueError):F.build(pd.concat([d,d.iloc[:1]]),b)
    with pytest.raises(ValueError):F.build(d,pd.concat([b,b.iloc[:1]]))


def test_all_six_models_and_probability_bounds():
    assert len({type(M.make(k).steps[-1][1]).__name__ for k in KEYS})==6
    p=np.array([[.6,.7,.4,.5,.55,.35],[.2,.3,.4,.2,.1,.3]])
    combined,w,stack=M.combine(p)
    assert np.isclose(w.sum(),1) and stack is None
    assert all(np.isfinite(v).all() and ((v>=0)&(v<=1)).all() for v in combined.values())


def test_stacking_uses_only_provided_earlier_oof_data():
    rng=np.random.default_rng(5);p=rng.uniform(.1,.9,(200,6));y=(p[:,0]>.5).astype(int)
    future=rng.uniform(.1,.9,(12,6))
    combined,w,stack=M.combine(future,p,y)
    assert len(combined['stacked'])==12 and stack is not None and np.isclose(w.sum(),1)


def test_chronological_fit_rejects_overlap_before_any_estimator():
    d=games();d['home_win']=1
    with pytest.raises(ValueError,match='overlap'):M.fit(d,d,['neutral'])


def test_fit_requires_outcome_availability_embargo():
    d=games();d['home_win']=1
    train=d.iloc[:1].copy();cal=d.iloc[1:2].copy()
    cal['tipoff']=train.tipoff.max()+pd.Timedelta(hours=20)
    with pytest.raises(ValueError,match='available'):M.fit(train,cal,['neutral'])


def test_real_six_member_training_and_calibration():
    rng=np.random.default_rng(19)
    d=pd.DataFrame({'tipoff':pd.date_range('2017-01-01',periods=420,freq='2D',tz='UTC'),
                    'feature':rng.normal(size=420)})
    d['home_win']=(rng.random(420)<1/(1+np.exp(-d.feature))).astype(int)
    bundle=M.fit(d.iloc[:300],d.iloc[301:401],['feature'],threads=1,log=lambda _:None)
    p=M.probabilities(bundle,d.iloc[401:])
    assert p.shape==(19,6) and np.isfinite(p).all() and ((p>0)&(p<1)).all()
    assert bundle['medians'][0]==d.feature.iloc[:300].median()
    assert pd.Timestamp(bundle['training_outcomes_available_through'])<d.tipoff.iloc[301]


def test_logloss_and_paired_ci_direction():
    y=np.array([0,1]*100);good=np.where(y,.8,.2);bad=np.full(len(y),.5)
    result=M.paired_ci(y,good,bad,draws=200)
    assert result['ci_high']<0 and M.scores(y,good)['accuracy']==1


def test_free_fetch_reuses_archive_and_refuses_unknown_host(tmp_path,monkeypatch):
    monkeypatch.setattr(S,'DATA',tmp_path);monkeypatch.setattr(S,'RAW',tmp_path/'raw')
    response=Mock(content=b'{"data":[]}');response.raise_for_status.return_value=None
    client=Mock();client.get.return_value=response
    first=S.fetch('https://api.pbpstats.com/test','fixture',session=client)
    second=S.fetch('https://api.pbpstats.com/test','fixture',session=client)
    assert first==second and client.get.call_count==1
    with pytest.raises(ValueError):S.fetch('https://unknown.invalid/api','bad',session=client)


def test_scoreboard_upcoming_scores_not_outcomes():
    teams=[{'homeAway':side,'team':{'id':str(i),'abbreviation':side},'score':'0'} for side,i in [('home',1),('away',2)]]
    d=S.scoreboard({'events':[{'id':'g','season':{'year':2027,'type':2},'date':'2026-10-23T23:00Z',
        'status':{'type':{'completed':False}},'competitions':[{'competitors':teams}]}]})
    assert d.home_score.isna().all() and not d.completed.any()


def test_schedule_quarantines_postponed_and_cup_final():
    base={'game_id':1,'season':2026,'season_type':2,'date':'2026-01-01T20:00Z','home_id':1,'away_id':2,
          'home_abbreviation':'ONE','away_abbreviation':'TWO','status_type_completed':True,'home_score':110,'away_score':100}
    d=pd.DataFrame([base|{'game_id':1,'status_type_name':'STATUS_FINAL','notes_headline':''},
                    base|{'game_id':2,'status_type_name':'STATUS_POSTPONED','notes_headline':''},
                    base|{'game_id':3,'status_type_name':'STATUS_FINAL','notes_headline':'NBA Cup Championship'},
                    base|{'game_id':4,'status_type_name':'STATUS_FINAL','notes_headline':'NBA Cup - Semifinals'}])
    assert S.schedules(d).game_id.tolist()==['1','4']


@pytest.mark.parametrize('page',['Today','Model Debate','Research & Calibration','Data & Sources'])
def test_app_without_data_is_safe(page,tmp_path,monkeypatch):
    # Isolate artifact paths; no live network, fits or NFL data in ordinary UI tests.
    from nba_lab import config as C
    for name in ('CACHE','DATA','MODELS','REPORTS','ARCHIVES'):monkeypatch.setattr(C,name,tmp_path/name)
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(str(C.ROOT/'app.py')).run(timeout=30)
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception
