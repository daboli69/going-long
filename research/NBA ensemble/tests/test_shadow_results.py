from pathlib import Path
import pandas as pd
import pytest
from nba_lab import shadow_results as R
from nba_lab.config import once,digest


def setup(tmp_path,monkeypatch):
    for key in ('CACHE','ARCHIVES','REPORTS'):monkeypatch.setattr(R,key,tmp_path/key)
    R.CACHE.mkdir()
    games=pd.DataFrame([{'game_id':'one','tipoff':pd.Timestamp('2026-10-23T23:00Z'),'home':'ONE','away':'TWO',
                         'completed':True,'home_score':110,'away_score':100}])
    games.to_parquet(R.CACHE/'games.parquet',index=False)
    for folder in ('individual_forecasts','score_forecasts'):
        for name,time in [('first','2026-10-23T12:00Z'),('second','2026-10-23T14:00Z')]:
            directory=R.ARCHIVES/folder/name;directory.mkdir(parents=True)
            once(directory/'META.json',{'fixture':True})
            row={'game_id':'one','tipoff':games.tipoff[0],'home':'ONE','away':'TWO','created_at':time,
                 'training_available_through':'2026-10-01T00:00Z','calibration_available_through':'2026-10-22T00:00Z','config_hash':'fixture'}
            if folder=='individual_forecasts':row.update(candidate='test',p_home=.7)
            else:row.update(method='ridge',home_margin=6.,total=220.,p_home_score_model=.7,
                            margin_p10=-10,margin_p90=20,total_p10=180,total_p90=260)
            pd.DataFrame([row]).to_parquet(directory/'predictions.parquet',index=False)


def test_shadow_scoring_waits_for_results_deduplicates_revisions_and_is_immutable(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch)
    early=R.score('2026-10-24T12:00Z');assert early['summary']==[] and early['pending_revision_rows']==4
    result=R.score('2026-10-25T12:00Z')
    assert len(result['summary'])==2 and all(s['n']==1 for s in result['summary'])
    score=next(s for s in result['summary'] if s['kind']=='scores')
    assert score['margin_mae']==4 and score['total_mae']==10 and score['margin_coverage_80']==1
    files=list(R.ARCHIVES.glob('*/*/scored/*.json'));before={str(p):digest(p) for p in files}
    R.score('2026-10-26T12:00Z');assert {str(p):digest(p) for p in files}==before


def test_shadow_scoring_refuses_postgame_prediction(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch)
    path=R.ARCHIVES/'individual_forecasts/first/predictions.parquet'
    d=pd.read_parquet(path);d['created_at']='2026-10-24T00:00Z';d.to_parquet(path,index=False)
    with pytest.raises(ValueError,match='Non-pregame'):R.score('2026-10-26T12:00Z')
