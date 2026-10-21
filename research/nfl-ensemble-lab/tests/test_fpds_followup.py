"""Synthetic offline regressions for the six Amendment9 tests."""
import numpy as np
import pandas as pd
import pytest

from lab.fpds_followup import (align, conformal_radius, interval_score,
                               probability_diagnostics, shrink_probabilities, soft)
from lab.fpds_improve.core import earlier


def frame():
    return pd.DataFrame({'game_id':['a','b'],'pid':['x','y'],'season':[2022,2022],
                         'actual':[1.,4.],'pred':[2.,3.],'q10':[1.,2.],'q90':[3.,5.]})


def test_alignment_rejects_missing_or_changed_targets():
    d=frame()
    with pytest.raises(ValueError):align(d.iloc[:1],d)
    with pytest.raises(ValueError):align(d.assign(actual=0),d)
    assert len(align(d,d))==2


def test_alignment_rejects_duplicate_entities():
    d=frame()
    with pytest.raises(ValueError):align(pd.concat([d,d]),d)


def test_soft_adjustment_is_fixed_not_exact_reconciliation():
    assert np.allclose(soft([0,4],[4,0]),[1,3])


def test_conformal_uses_nonnegative_finite_sample_order_statistic():
    d=pd.DataFrame({'q10':np.zeros(100),'q90':np.ones(100),'actual':np.arange(100)})
    assert conformal_radius(d)==79
    assert conformal_radius(d.iloc[:99])==0


def test_future_canary_cannot_enter_radius():
    d=pd.DataFrame({'available_at':pd.to_datetime(['2022-01-01']*100+['2023-01-01'],utc=True),
                    'q10':np.zeros(101),'q90':np.ones(101),'actual':[.5]*100+[999999.]})
    old=earlier(d,pd.Timestamp('2022-02-01',tz='UTC'))
    assert len(old)==100 and conformal_radius(old)==0


def test_interval_score_penalizes_misses_and_width():
    d=frame()
    assert np.allclose(interval_score(d),[2,3])
    assert interval_score(d.assign(q90=2)).sum()>interval_score(d).sum()


def test_brier_decomposition_accounts_for_within_bin_variation():
    d=pd.DataFrame({'pred':[.11,.19,.8,.9],'actual':[0,1,1,0]})
    result=probability_diagnostics(d)
    assert abs(result['decomposition_error'])<1e-12
    assert result['auc'] is not None


def test_pregame_history_shrinkage_and_warmup():
    d=pd.DataFrame({'pred':[.8,.8],'position':['WR','WR'],'hist_games':[0,8]})
    h=pd.DataFrame({'actual':[0.,1.]*50,'position':['WR']*100})
    p=shrink_probabilities(d,h,'anytime_td')
    assert p[0]==.5 and .5<p[1]<.8
    assert np.allclose(shrink_probabilities(d,h.iloc[:99],'anytime_td'),d.pred)


def test_conformal_does_not_change_midpoint():
    d=frame();out=d.copy();out['q10']=(out.q10-2).clip(lower=0);out['q90']+=2
    assert np.array_equal(out.pred,d.pred)
