import numpy as np
import pandas as pd
import pytest
from nba_lab import calibration as C


def history():
    dates=list(pd.date_range('2022-10-01',periods=1300,freq='6h',tz='UTC'))
    seasons=[2023]*1300
    for season,start in [(2024,'2023-10-01'),(2025,'2024-10-01')]:
        dates+=list(pd.date_range(start,periods=40,freq='D',tz='UTC'));seasons += [season]*40
    rng=np.random.default_rng(17);p=rng.uniform(.1,.9,len(dates))
    return pd.DataFrame({'game_id':[str(i) for i in range(len(dates))],'season':seasons,
        'tipoff':dates,'home_win':(rng.random(len(dates))<p).astype(int),'stacked':p})


@pytest.mark.parametrize('method',['platt','isotonic'])
def test_monthly_calibration_never_uses_current_or_future_month_labels(method):
    d=history();first,count=C.walkforward(d,method,300)
    changed=d.copy();changed.loc[changed.tipoff.ge('2023-10-01') & changed.tipoff.lt('2023-11-01'),'home_win']^=1
    after,_=C.walkforward(changed,method,300)
    october=first.tipoff.ge('2023-10-01')&first.tipoff.lt('2023-11-01')
    np.testing.assert_allclose(first.loc[october,'candidate'],after.loc[october,'candidate'])
    assert (pd.to_datetime(first.calibration_outcomes_available_through,utc=True)<pd.to_datetime(first.calibrator_fit_at,utc=True)).all()
    assert (pd.to_datetime(first.calibrator_fit_at,utc=True)<=first.tipoff).all()
    assert count==4 and len(first)==80 and first.candidate.between(0,1).all()


def test_insufficient_history_fails_instead_of_dropping_target_rows():
    with pytest.raises(ValueError,match='Insufficient'):C.walkforward(history(),'platt',2000)


def test_discovery_loader_never_opens_confirmation_or_operational_data(monkeypatch):
    d=history();opened=[]
    def reader(path,columns):
        season=int(path.parent.name.split('_')[1]);opened.append(season)
        assert season in (2023,2024,2025)
        return d[d.season.eq(season)][columns].copy()
    monkeypatch.setattr(C.pd,'read_parquet',reader)
    assert len(C.load_history())==len(d) and opened==[2023,2024,2025]


def test_completed_run_is_cached_and_changed_fingerprint_is_refused(tmp_path,monkeypatch):
    monkeypatch.setattr(C,'REPORTS',tmp_path)
    monkeypatch.setattr(C,'fingerprint',lambda:'same')
    monkeypatch.setattr(C,'load_history',history)
    out=C.run(log=lambda _:None)
    assert out['trial_count']==6 and out['calibrator_fits']==24 and not out['failures']
    def forbid():raise AssertionError('Completed run must not load data or refit')
    monkeypatch.setattr(C,'load_history',forbid)
    assert C.run()['created_at']==out['created_at']
    monkeypatch.setattr(C,'fingerprint',lambda:'changed')
    with pytest.raises(ValueError,match='changed'):C.run()


def test_active_lock_refuses_duplicate_work(tmp_path,monkeypatch):
    monkeypatch.setattr(C,'REPORTS',tmp_path);monkeypatch.setattr(C,'fingerprint',lambda:'same')
    lock=tmp_path/'calibration_v1/RUN_LOCK.json';C.once(lock,{'fixture':True})
    with pytest.raises(ValueError,match='already running'):C.run()
