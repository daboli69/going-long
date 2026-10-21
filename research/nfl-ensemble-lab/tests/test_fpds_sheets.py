"""Fixed synthetic distributions and clocks; never reads research checkpoints."""
import numpy as np
import pandas as pd
import pytest
from lab.fpds_sheets import correct_comparisons
from lab.fpds_weekly_guard import check


def test_fixed_empirical_probabilities_and_binary_gap_guard():
    common={'arm':'frozen','line_type':'consensus','p_over':.9,'p_under':.1,'q10':0.,'q90':60.,'line_status':'current'}
    rows=[common|{'stat':'rec_yds','mean':10.,'median':5.,'consensus_line':8.,'gap':2.},
          common|{'stat':'anytime_td','mean':.2,'median':0.,'consensus_line':.5,'gap':-.3},
          common|{'stat':'rec','mean':2.,'median':2.,'consensus_line':1.5,'gap':.5}]
    d=correct_comparisons(pd.DataFrame(rows),{('frozen','rec_yds'):[-10.,-5.,0.,50.]})
    assert d.iloc[0].p_over==.5 and d.iloc[0].p_under==.5 and d.iloc[0].skew_artifact_flag
    assert np.isnan(d.iloc[1].gap) and d.iloc[1].p_over==.2
    assert 'Poisson' in d.iloc[2].probability_method
    assert np.allclose(d.p_over+d.p_under+d.p_push,1)
    assert set(d.confidence_tier)=={'C'}


def test_near_kickoff_refit_is_blocked():
    now=pd.Timestamp('2026-10-20T12:00Z')
    games=pd.DataFrame({'season':[2026],'week':[7],'completed':[False],'kickoff_utc':[now+pd.Timedelta(hours=1)]})
    with pytest.raises(ValueError,match='2h refit budget'):check(games,7,now)
    games['kickoff_utc']=now+pd.Timedelta(hours=3)
    assert check(games,7,now)==1
