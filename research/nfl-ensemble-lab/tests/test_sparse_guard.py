"""Sparse-column guard for the scaled members; entirely synthetic rows."""
import numpy as np
import pandas as pd
import pytest
from lab.fpds_research import models as M


def frames(n=400,filled=3):
    rng=np.random.default_rng(7)
    train=pd.DataFrame({'a':rng.normal(size=n),'b':rng.normal(size=n)})
    train['rush_yds']=np.maximum(45+20*train.a+rng.normal(0,10,n),0)
    # Empty for this position in training, then filled at prediction time.
    train['sparse']=np.nan
    train.loc[train.index[:filled],'sparse']=[0.10,0.1001,0.1002][:filled]
    test=pd.DataFrame({'a':rng.normal(size=50),'b':rng.normal(size=50),'sparse':rng.uniform(.2,.6,50)})
    return train,test


def test_covered_drops_only_nearly_empty_columns():
    train,_=frames()
    assert M.covered(train,['a','b','sparse'],.01)==['a','b']
    assert M.covered(train,['a','b','sparse'],.005)==['a','b','sparse']


def test_unguarded_scaled_input_is_out_of_range():
    train,test=frames()
    pipe=M.estimator('rush_yds','linear')
    pipe.fit(train[['a','b','sparse']].to_numpy(np.float32),train.rush_yds.to_numpy(float))
    z=pipe[:-1].transform(test[['a','b','sparse']].to_numpy(np.float32))
    assert np.abs(z).max()>100


@pytest.mark.parametrize('key',['linear','mlp'])
def test_guard_matches_fit_without_the_sparse_column(key):
    train,test=frames()
    guarded,_=M.fit_predict(train,test,'rush_yds',['a','b','sparse'],key,min_coverage=.01)
    clean,_=M.fit_predict(train,test,'rush_yds',['a','b'],key)
    assert np.allclose(guarded,clean)
    assert guarded.max()<200


def test_default_keeps_champion_columns_and_trees_are_exempt():
    train,test=frames()
    cols=['a','b','sparse']
    base,_=M.fit_predict(train,test,'rush_yds',cols,'linear')
    same,_=M.fit_predict(train,test,'rush_yds',cols,'linear',min_coverage=None)
    assert np.array_equal(base,same)
    tree,_=M.fit_predict(train,test,'rush_yds',cols,'hist')
    guarded,_=M.fit_predict(train,test,'rush_yds',cols,'hist',min_coverage=.01)
    assert np.array_equal(tree,guarded)


def test_guard_refuses_to_fit_on_nothing():
    train,test=frames()
    with pytest.raises(ValueError):
        M.fit_predict(train,test,'rush_yds',['sparse'],'linear',min_coverage=.01)
