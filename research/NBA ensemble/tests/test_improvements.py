import numpy as np
import pandas as pd
import pytest
from test_nba import games,boxes
from nba_lab import features as F,adjusted as A,individual as I,score_models as S


def fixture():
    g=games(35);b=boxes(g);base,_=F.build(g,b,asof='2025-01-01T00:00Z')
    return g,b,base


def test_opponent_adjustment_own_and_future_outcome_canaries():
    g,b,base=fixture();before=A.build(base,g,b)
    g.loc[20,['home_score','away_score']]=[90,130]
    b.loc[b.game_id.eq('20'),'points']=np.where(b.loc[b.game_id.eq('20'),'team_id'].eq('1'),90,130)
    changed_base,_=F.build(g,b,asof='2025-01-01T00:00Z');after=A.build(changed_base,g,b)
    cols=[c for c in before if '_adj_' in c]
    pd.testing.assert_frame_equal(before.loc[:20,cols],after.loc[:20,cols])
    assert not np.isclose(before.loc[21,'home_adj_margin_20'],after.loc[21,'home_adj_margin_20'])


def test_adjustment_24h_release_and_duplicate_rejection():
    g,b,base=fixture();g.loc[1,'tipoff']=g.loc[0,'tipoff']+pd.Timedelta(hours=20)
    base,_=F.build(g,b,asof='2025-01-01T00:00Z');out=A.build(base,g,b)
    assert np.isnan(out.loc[1,'home_adj_margin_20'])
    with pytest.raises(ValueError,match='Duplicate'):A.build(base,pd.concat([g,g.iloc[:1]]),b)


def test_reduced_features_and_missingness_are_explicit():
    g,b,base=fixture();d=A.build(base,g,b)
    assert not any(c.endswith(('_5','_10')) for c in I.columns('svm_simple',d))
    assert len([c for c in I.columns('logistic_adjusted',d) if c.startswith('diff_adj_')])==3
    assert len(I.make('hist_native_missing',1).steps)==2


def test_chronological_neural_epoch_selection_ignores_external_calibration():
    rng=np.random.default_rng(4);n=500
    d=pd.DataFrame({'tipoff':pd.date_range('2018-01-01',periods=n,freq='2D',tz='UTC'),
                    'season':[2018]*350+[2019]*150,'x':rng.normal(size=n),'home_win':np.tile([0,1],250)})
    model,info=I.neural(d,['x'],max_epochs=8,patience=3)
    assert 1<=info['selected_epoch']<=8 and info['internal_validation_season']==2019
    assert np.isfinite(model.predict_proba(d[['x']].to_numpy())[:,1]).all()


def test_score_feature_whitelist_excludes_current_results():
    g,b,base=fixture();d=A.build(base,g,b)
    d['home_score']=123;d['margin']=7;d['total']=221
    cols=S.columns(d)
    assert not set(cols)&{'home_score','home_win','margin','total','completed'}


def test_empirical_crps_matches_direct_pairwise_definition():
    residuals=np.array([-2.,0.,3.]);point=np.array([100.,103.]);actual=np.array([101.,100.])
    expected=np.abs(point[:,None]+residuals-actual[:,None]).mean(axis=1)-.5*np.abs(residuals[:,None]-residuals[None,:]).mean()
    np.testing.assert_allclose(S.crps(point,actual,residuals),expected)


def test_score_distribution_preserves_team_score_coherence():
    bundle={'method':'league_mean','mean':np.array([6.,220.]),'bias':np.zeros(2),
            'residuals':np.array([[-10.,-20.],[0.,0.],[10.,20.]])}
    point,q,p=S.distribution(bundle,pd.DataFrame(index=range(3)))
    home=(point[:,1]+point[:,0])/2;away=(point[:,1]-point[:,0])/2
    np.testing.assert_allclose(home+away,point[:,1]);np.testing.assert_allclose(home-away,point[:,0])
    assert q.shape==(3,2,3) and np.all((p>=0)&(p<=1)) and np.all(q[:,:,0]<=q[:,:,1])


def test_score_calibration_rejects_overlap():
    d=pd.DataFrame({'tipoff':pd.date_range('2024-01-01',periods=400,freq='D',tz='UTC')})
    with pytest.raises(ValueError,match='overlap'):S.fit('ridge',d,d)


@pytest.mark.parametrize('name',[k for k in I.SPECS if k!='mlp_small'])
def test_modified_estimator_calibrates_and_predicts(name):
    rng=np.random.default_rng(22);n=520
    d=pd.DataFrame({'tipoff':pd.date_range('2018-01-01',periods=n,freq='2D',tz='UTC'),
                    'season':[2018]*400+[2020]*120,'home_win':np.tile([0,1],260),
                    'neutral':0.,'elo_diff':rng.normal(size=n),'diff_margin_20':rng.normal(size=n),
                    **{f'diff_{s}_20':rng.normal(size=n) for s in ('adj_margin','adj_attack','adj_defense')}})
    d.loc[0,'diff_margin_20']=np.nan
    cols=I.columns(name,d);bundle,meta=I.fit(name,d.iloc[:400],d.iloc[401:],cols,threads=1)
    p=bundle[1].predict_proba(I.M.raw(bundle[0],d.iloc[401:][cols].to_numpy()).reshape(-1,1))[:,1]
    assert len(p)==119 and np.isfinite(p).all() and np.all((p>0)&(p<1))
