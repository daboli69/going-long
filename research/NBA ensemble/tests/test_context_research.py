import numpy as np
import pandas as pd
import pytest
from nba_lab import context_research as R


def test_context_groups_cannot_implicitly_select_other_context_or_outcome_fields():
    base=['neutral','elo_diff','diff_margin_20']
    age=R.columns('season_continuity',base);shared=R.columns('shared_possessions',base)
    assert len(age)==len(base)+11 and len(shared)==len(base)+2
    assert set(shared)-set(base)=={'diff_shared_ortg_20','diff_shared_drtg_20'}
    assert not set(age)&{'home_win','home_score','tipoff'}


def test_context_fit_uses_train_only_preprocessing_and_chronological_calibration():
    rng=np.random.default_rng(12);n=520
    d=pd.DataFrame({'tipoff':pd.date_range('2018-01-01',periods=n,freq='2D',tz='UTC'),
                    'x':rng.normal(size=n),'home_win':np.tile([0,1],260)})
    bundle=R.fit(d.iloc[:400],d.iloc[401:],['x'])
    p=R.probability(bundle,d.iloc[401:]);assert len(p)==119 and np.isfinite(p).all() and np.all((p>0)&(p<1))
    assert np.isclose(bundle['model'].steps[1][1].mean_[0],d.x.iloc[:400].mean())
    with pytest.raises(ValueError,match='overlap'):R.fit(d,d,['x'])


def test_context_gate_cannot_be_selected_by_early_season_subset():
    n=200
    d=pd.DataFrame({'home_win':np.tile([0,1],100),'control':.5,'probability':.5,'season':[2024]*100+[2025]*100,
                    'home_season_history_20':1,'away_season_history_20':1})
    result=R.result(d)
    assert not result['accepted_exploratory'] and result['early_season_descriptive']['n']==n
