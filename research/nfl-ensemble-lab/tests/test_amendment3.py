import numpy as np
import pandas as pd
import pytest
from lab.props.amendment3.research import rolling_lines,allocate,scale_scorers
from lab.props.weekly10 import execute,outputs,select_slate
from lab.props.amendment2.simulation import anonymous_replacement


def test_pseudo_line_excludes_same_week_and_future():
    p=pd.DataFrame([dict(season=2022,week=4,pid='p',stat='rush_yds')])
    h=pd.DataFrame([dict(season=2022,week=w,pid='p',rush_yds=y) for w,y in ((1,10),(2,20),(3,30),(4,999),(5,1000))])
    first=rolling_lines(p,h).pseudo_line.iloc[0]
    h.loc[h.week.ge(4),'rush_yds']=-999
    assert first==rolling_lines(p,h).pseudo_line.iloc[0]==20
    h['season']=2023
    with pytest.raises(ValueError):rolling_lines(p,h)


def test_allocate_retains_other_mass_and_conserves():
    values,other,scale=allocate([10,30],[20,40],100.)
    assert np.allclose(values,[15,45])
    assert other==40 and abs(values.sum()+other-100)<1e-8
    values,other,_=allocate([0,0],[20,40],100.)
    assert values.sum()==0 and other==100


def test_distinct_scorer_scaling_caps_and_preserves_other():
    probabilities=scale_scorers([.9,.1,.1],2.,.5)
    assert np.all((probabilities>=0)&(probabilities<=1))
    assert abs(probabilities.sum()+.5-2)<1e-8
    with pytest.raises(ValueError):scale_scorers([0.,.2],3.,0.)


def test_pipeline_stops_before_downstream_on_failure(tmp_path):
    calls=[]
    def first():calls.append('first');return {'ok':True}
    def failed():calls.append('failed');raise ValueError('fixture failure')
    def forbidden():calls.append('forbidden')
    with pytest.raises(RuntimeError,match='STOPPED at fail'):
        execute([('first',1,first),('fail',1,failed),('never',1,forbidden)],tmp_path,pd.Timestamp.now(tz='UTC')+pd.Timedelta(minutes=1))
    assert calls==['first','failed']
    assert (tmp_path/'FAILURE.json').exists()


def test_pipeline_budget_guard_and_existing_revision(tmp_path):
    calls=[]
    with pytest.raises(RuntimeError,match='STOPPED'):
        execute([('fit',60,lambda:calls.append('fit'))],tmp_path,pd.Timestamp.now(tz='UTC'))
    assert not calls


def test_isolated_output_restores_all_modules_even_on_failure(tmp_path):
    from lab.props.ensemble import data,production,structural
    from lab.props import projections10
    modules=[data,production,structural,projections10]
    previous=[m.OUT for m in modules]
    with pytest.raises(ValueError):
        with outputs(tmp_path):
            assert all(m.OUT==tmp_path for m in modules)
            raise ValueError('fixture')
    assert [m.OUT for m in modules]==previous


def test_anonymous_replacement_keeps_identity_unknown():
    original={'NE':pd.DataFrame([{'pid':'real','position':'QB'}])}
    changed,pid=anonymous_replacement(original,'NE','QB')
    assert pid=='assumption:QB:NE' and not pid.startswith('00-')
    assert list(original['NE'].pid)==['real']
    assert len(changed['NE'])==2


def test_standalone_inactives_cli_is_read_only(monkeypatch):
    from lab import inactives10
    future=pd.Timestamp.now(tz='UTC')+pd.Timedelta(days=2)
    frame=pd.DataFrame([dict(season=2026,week=8,completed=False,kickoff_utc=future)])
    monkeypatch.setattr(inactives10.pd,'read_parquet',lambda p:frame)
    monkeypatch.setattr(inactives10,'parser_module',lambda:pytest.fail('No game in T90; must not retrieve'))
    assert inactives10.main(['collect','--week','8'])==0
