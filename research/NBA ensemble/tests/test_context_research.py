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


def test_context_forecasts_append_and_keep_failed_gate_label(tmp_path,monkeypatch):
    from nba_lab.config import once,atomic,digest
    from pathlib import Path
    for name in ('ROOT','CACHE','MODELS','ARCHIVES','DATA'):monkeypatch.setattr(R,name,tmp_path/name)
    once(R.ROOT/'docs/PREGAME_CONTEXT_FROZEN.json',{'methods':list(R.METHODS),'base_columns':['x'],
        'development_gate':{m:False for m in R.METHODS},'code_hashes':{}})
    atomic(R.DATA/'SOURCES.json',{'fixture':True});R.CACHE.mkdir();(R.CACHE/'pregame_context_features.parquet').write_bytes(b'fixture')
    time=pd.Timestamp.now(tz='UTC');future=time+pd.Timedelta(days=1)
    d=pd.DataFrame({'tipoff':pd.date_range('2018-01-01',periods=700,freq='2D',tz='UTC'),
                    'game_id':[str(i) for i in range(700)],'eligible':True,'season':2019,'completed':True,
                    'home_win':np.tile([0,1],350),'home':'ONE','away':'TWO','home_season_history_20':1,
                    'away_season_history_20':1,'home_prior_season_fraction_20':.95,'away_prior_season_fraction_20':.95})
    upcoming=d.iloc[-1:].copy();upcoming['tipoff']=future;upcoming['game_id']='future';upcoming['home_win']=np.nan;upcoming['completed']=False
    d=pd.concat([d,upcoming],ignore_index=True)
    monkeypatch.setattr(R,'frame',lambda:(d,['x']));monkeypatch.setattr(R,'fit',lambda *a:{'fixture':True})
    monkeypatch.setattr(R,'probability',lambda bundle,test:np.full(len(test),.55))
    date=future.tz_convert('America/New_York').date();first=R.archive(date)
    path=Path(first['path'])/'predictions.parquet';checksum=digest(path);second=R.archive(date)
    assert first['path']!=second['path'] and digest(path)==checksum
    out=pd.read_parquet(path);assert len(out)==2 and not out.development_gate_passed.any()
    assert (pd.to_datetime(out.created_at,utc=True)<out.tipoff).all()
    assert R.archive(date-pd.Timedelta(days=4)) is None
