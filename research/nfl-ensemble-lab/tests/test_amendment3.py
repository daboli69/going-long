import numpy as np
import pandas as pd
import pytest
from lab.props.amendment3.research import rolling_lines,allocate,scale_scorers


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
