import pandas as pd
import pytest
from nba_lab import outcomes as O
from nba_lab.config import once,digest


def setup_archives(tmp_path,monkeypatch):
    for key in ('CACHE','ARCHIVES','REPORTS'):monkeypatch.setattr(O,key,tmp_path/key)
    O.CACHE.mkdir()
    games=pd.DataFrame([{'game_id':'one','tipoff':pd.Timestamp('2026-10-23T23:00Z'),
                         'home':'ONE','away':'TWO','completed':True,'home_score':100,'away_score':90}])
    games.to_parquet(O.CACHE/'games.parquet',index=False)
    for version,created in [('first','2026-10-23T12:00Z'),('second','2026-10-23T14:00Z')]:
        folder=O.ARCHIVES/'forecasts'/version;folder.mkdir(parents=True)
        once(folder/'META.json',{'created_at':created})
        pd.DataFrame([{'game_id':'one','tipoff':games.tipoff[0],'created_at':created,'home':'ONE','away':'TWO',
                       'training_outcomes_available_through':'2026-10-01T00:00Z',
                       'calibration_outcomes_available_through':'2026-10-22T00:00Z',
                       'p_home':.7,'model_version':version,'config_hash':'fixture'}]).to_parquet(folder/'predictions.parquet',index=False)


def test_results_require_availability_and_revisions_do_not_duplicate_games(tmp_path,monkeypatch):
    setup_archives(tmp_path,monkeypatch)
    assert O.score('2026-10-24T12:00Z')['metrics']['n']==0
    result=O.score('2026-10-25T12:00Z')
    assert result['metrics']['n']==1 and result['scored_revision_rows']==2
    files=list(O.ARCHIVES.glob('forecasts/*/scored/*.json'))
    before={str(p):digest(p) for p in files}
    O.score('2026-10-26T12:00Z')
    assert {str(p):digest(p) for p in files}==before


def test_post_tipoff_or_post_training_forecast_cannot_be_scored(tmp_path,monkeypatch):
    setup_archives(tmp_path,monkeypatch)
    path=O.ARCHIVES/'forecasts/first/predictions.parquet'
    rows=pd.read_parquet(path);rows['created_at']='2026-10-24T00:00Z';rows.to_parquet(path,index=False)
    with pytest.raises(ValueError,match='non-pregame'):O.score('2026-10-26T12:00Z')
    rows['created_at']='2026-10-21T00:00Z';rows.to_parquet(path,index=False)
    with pytest.raises(ValueError,match='cutoff'):O.score('2026-10-26T12:00Z')


def test_forecasts_append_revisions_preserve_ties_and_exclude_started_games(tmp_path,monkeypatch):
    import numpy as np
    from nba_lab import engine as E
    from nba_lab.config import atomic
    for key in ('CACHE','ARCHIVES','DATA'):monkeypatch.setattr(E,key,tmp_path/key)
    E.CACHE.mkdir();atomic(E.DATA/'SOURCES.json',{'fixture':True})
    time=pd.Timestamp.now(tz='UTC');tipoff=time+pd.Timedelta(days=1)
    row={'game_id':'future','tipoff':tipoff,'home':'ONE','away':'TWO','completed':False,'eligible':True,
         'home_history':20,'away_history':20,'home_box_history':20,'away_box_history':20,
         'latest_input_available_at':time-pd.Timedelta(days=1)}
    pd.DataFrame([row,row|{'game_id':'started','tipoff':tipoff-pd.Timedelta(days=2)}]).to_parquet(E.CACHE/'features.parquet',index=False)
    bundle={'selected_method':'equal','weights':np.full(6,1/6),'stacker':None,'version':'fixture','config_hash':'fixture',
            **{k:'2020-01-01T00:00Z' for k in ('trained_through','calibrated_through','training_outcomes_available_through','calibration_outcomes_available_through')}}
    monkeypatch.setattr(E,'load',lambda:bundle)
    monkeypatch.setattr(E.M,'probabilities',lambda b,f:np.tile([.6,.6,.6,.4,.4,.4],(len(f),1)))
    date=tipoff.tz_convert('America/New_York').date()
    first,meta=E.predict(date)
    from pathlib import Path
    original=Path(meta['path'])/'predictions.parquet';before=digest(original)
    second,revision=E.predict(date)
    assert meta['path']!=revision['path'] and before==digest(original)
    assert len(first)==1 and first.iloc[0].vote=='tie' and first.iloc[0].winner=='coin flip'
    old,_=E.predict((tipoff-pd.Timedelta(days=2)).tz_convert('America/New_York').date())
    assert old.empty
