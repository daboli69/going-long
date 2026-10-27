import pandas as pd
from nba_lab import engine_availability as A
from nba_lab import injury_reports as R


def test_reason_categories():
    assert A.reason_kind('G League - Two-Way') =='g_league'
    assert A.reason_kind('Injury/Illness - Left Ankle; Sprain')=='injury'
    assert A.reason_kind('Rest')=='rest' and A.reason_kind('League Suspension')=='suspension'
    assert A.reason_kind(None)=='other'


def test_only_versions_published_before_the_decision_are_seen():
    t=pd.Timestamp('2025-01-01T22:00Z')
    entries=[(t-pd.Timedelta(hours=2),'a'),(t-pd.Timedelta(minutes=1),'b'),(t,'c'),(t+pd.Timedelta(hours=1),'d')]
    assert [e for _,e in A.at_decision(entries,t)]==['a','b']


def test_baseline_is_training_rate_by_status():
    train=pd.DataFrame({'status':['Out','Out','not_listed','not_listed'],'played':[0.,0.,1.,0.]})
    test=pd.DataFrame({'status':['Out','not_listed','Probable']})
    p=A.baseline(train,test)
    assert p[0]==1e-4 and p[1]==.5 and p[2]==.25


def test_day_slots_cover_morning_to_last_tipoff():
    hourly=R.day_slots(pd.Timestamp('2023-01-16T00:00Z'),pd.Timestamp('2023-01-16T03:00Z'))
    assert str(hourly[0].time())=='09:00:00' and str(hourly[-1].time())=='22:00:00'
    quarter=R.day_slots(pd.Timestamp('2026-01-16T00:00Z'),pd.Timestamp('2026-01-16T00:30Z'))
    assert (quarter[1]-quarter[0])==pd.Timedelta(minutes=15)
