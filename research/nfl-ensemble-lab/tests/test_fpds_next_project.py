"""Forecast I/O integration with fixture data and mocked estimators only."""
import numpy as np
import pandas as pd
import pytest
from lab.fpds_next import run as X,roles as R,storage as S,targets as T


def test_explicit_shadow_project_is_immutable_and_records_cutoff(tmp_path,monkeypatch):
    now=pd.Timestamp.now(tz='UTC')
    g=pd.DataFrame({'game_id':['past','future'],'season':[2026,2026],'week':[6,7],
                    'kickoff_utc':[now-pd.Timedelta(days=4),now+pd.Timedelta(days=4)],
                    'home_team':['BUF','BUF'],'away_team':['NYJ','NYJ']})
    players=pd.DataFrame({'game_id':['past','future'],'season':[2026,2026],'week':[6,7],
                          'kickoff_utc':g.kickoff_utc,'pid':['fixture','fixture'],'team':['BUF','BUF'],'position':['WR','WR']})
    for stat in T.STATS:players[stat]=[1.,np.nan]
    for c in R.COLS:players[c]=0.
    players['r10_ratios']=[[1.],[1.]]
    drives=pd.DataFrame({'available_at':[now-pd.Timedelta(days=3)]})
    protocol={'source_job':'eb191266fa1449c1817980abe1878bb9','parent':'20261021T200416Z',
              'max_fit_calls':400,'max_output_versions':45}
    monkeypatch.setattr(S,'ROOT',tmp_path/'studies')
    monkeypatch.setattr(S,'registered',lambda:(protocol,'fixture_config_hash'))
    monkeypatch.setattr(S,'inputs',lambda *a,**k:{})
    monkeypatch.setattr(X,'prepare',lambda *a,**k:(players,g,pd.DataFrame(),drives))
    monkeypatch.setattr(X,'read',lambda p:{'protocol':{}} if p.name=='RUN.json' else {'feature_creation_cutoff':now.isoformat()})
    monkeypatch.setattr(X.E,'data_for',lambda stat,frame,games:frame.copy())
    monkeypatch.setattr(X.C,'task_columns',lambda *a:[])
    calls=[]
    def model(train,target,stat,*a,**k):
        assert train.week.max()==6 and target.week.min()==7
        calls.append(stat)
        return np.full(len(target),.5),object()
    monkeypatch.setattr(X.M,'fit_predict',model)
    import joblib
    monkeypatch.setattr(joblib,'dump',lambda *a,**k:None)
    import lab.props.ensemble.production as production
    monkeypatch.setattr(production,'completed_cutoff',lambda *a,**k:{'training_last_completed_week':6,'training_cutoff_date':'fixture_cutoff'})
    monkeypatch.setattr(X.V,'simulate',lambda *a:(np.tile([21.,17.],(100,1)),{'earlier_games':10,'earlier_ot_games':2,'simulated_tie_probability':0.}))
    path=tmp_path/'output';path.mkdir()
    X.project(path,2026,7,100)
    assert len(calls)==6
    p=pd.read_csv(path/'shadow_players_2026_w07.csv');games=pd.read_csv(path/'shadow_games_2026_w07.csv')
    assert {'created_at','training_cutoff_date','config_hash','source_hash','shadow_only'}<=set(p)
    assert p.training_cutoff_date.eq('fixture_cutoff').all()
    assert p.calibration_status.str.contains('unavailable').all()
    assert games.margin_mean.iloc[0]==4 and games.total_mean.iloc[0]==38
    with pytest.raises(FileExistsError):X.project(path,2026,7,100)
