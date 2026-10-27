import numpy as np
import pandas as pd
import pytest

from lab.qb_asof_audit import VERSION, compare, losses, novig, power, qb_evidence, select_quote, select_snapshot


def test_snapshot_boundary_and_version():
    t=pd.Timestamp('2026-10-26T22:45Z')
    rows=[{'model_version':VERSION,'predicted_at':str(t),'path':'a'},
          {'model_version':VERSION,'predicted_at':str(t+pd.Timedelta(seconds=1)),'path':'b'},
          {'model_version':'different','predicted_at':str(t),'path':'c'}]
    assert select_snapshot(rows,t)['path']=='a'
    assert select_snapshot(rows,t-pd.Timedelta(seconds=1)) is None


def test_no_vig_requires_valid_two_sides():
    assert novig(-110,-110)==.5
    assert novig(-200,150)==pytest.approx((2/3)/(2/3+.4))
    for odds in [None,0,50,float('nan'),float('inf')]:
        assert novig(-110,odds) is None


def test_quote_known_before_decision_and_fresh():
    t=pd.Timestamp('2026-10-26T22:45Z');kick=t+pd.Timedelta(minutes=90)
    q={'home':'A','away':'B','kickoff':str(kick),'observed_at':str(t),'quote_time':None,'p_home':.6,'path':'a'}
    assert select_quote([q],'A','B',kick,t)==q
    assert select_quote([dict(q,observed_at=str(t+pd.Timedelta(seconds=1)))],'A','B',kick,t) is None
    assert select_quote([dict(q,quote_time=str(t+pd.Timedelta(seconds=1)))],'A','B',kick,t) is None
    assert select_quote([dict(q,quote_time=str(t-pd.Timedelta(minutes=61)))],'A','B',kick,t) is None
    assert select_quote([dict(q,observed_at=str(t-pd.Timedelta(minutes=61)))],'A','B',kick,t) is None
    assert select_quote([dict(q,in_play=True)],'A','B',kick,t) is None
    assert select_quote([q],'B','A',kick,t) is None
    assert select_quote([dict(q,kickoff=str(kick+pd.Timedelta(days=7)))],'A','B',kick,t) is None


def test_paired_metrics_identity_and_duplicate_guard():
    rows=[{'game_id':'a','week':1,'home_win':1,'p_champion':.8,'p_market':.6},
          {'game_id':'b','week':1,'home_win':0,'p_champion':.2,'p_market':.4}]
    r=compare(rows)
    assert r['champion_minus_market_log_loss']==pytest.approx(np.log(.6/.8))
    assert r['champion']['brier']==pytest.approx(.04)
    assert r['n']==2 and r['paired_game_ci95'][1]<0
    with pytest.raises(ValueError,match='duplicate'): compare(rows+rows)
    with pytest.raises(ValueError,match='binary'): compare([dict(rows[0],home_win=.5)])
    assert compare([])['n']==0


def test_power_is_planning_not_measured_effect():
    assert [r['required_n_for_0_010'] for r in power(26)]==[785,3140,12559]
    assert all(r['detectable_delta_at_n'] is None for r in power(0))
    y=[0,1];a=[.2,.8];b=[.4,.6];c=[.3,.7]
    assert np.allclose((losses(y,a)-losses(y,b))+(losses(y,b)-losses(y,c)),losses(y,a)-losses(y,c))


def test_injury_and_depth_evidence_are_not_starter_confirmation():
    decision=pd.Timestamp('2026-10-26T22:45Z')
    tables=[{'kind':'nflverse_injuries','observed_at':'2026-10-26T22:00Z','path':'old',
             'qb_rows':[{'team':'A','week':7,'gsis_id':'known','report_status':'Out'}]},
            {'kind':'nflverse_injuries','observed_at':'2026-10-26T23:00Z','path':'future',
             'qb_rows':[{'team':'A','week':7,'gsis_id':'known','report_status':None}]},
            {'kind':'sleeper_players','observed_at':'2026-10-26T22:00Z','path':'depth',
             'qb_rows':[{'team':'A','gsis_id':'backup','depth_chart_order':1,'status':'Active'}]}]
    result=qb_evidence('A','known',7,decision,tables)
    assert result['champion_identity_recorded']
    assert result['matched_injury_reports'][0]['path']=='old'
    assert result['matched_injury_reports'][0]['published_at'] is None
    assert result['projected_depth_one'][0]['gsis_id']=='backup'
    assert result['confirmed_starter_evidence'] is None
    assert not qb_evidence('A',None,7,decision,tables)['champion_identity_recorded']
    assert not qb_evidence('A','known',8,decision,tables)['matched_injury_reports']


def test_conflicting_injury_sources_remain_visible():
    sources=[{'kind':kind,'path':kind,'observed_at':'2026-10-26T22:00Z',
              'qb_rows':[{'team':'A','week':7,'gsis_id':'known','report_status':status}]}
             for kind,status in [('nflcom_injuries','Out'),('nflverse_injuries','Questionable')]]
    result=qb_evidence('A','known',7,pd.Timestamp('2026-10-26T22:45Z'),sources)
    assert result['report_status_conflict'] and len(result['matched_injury_reports'])==2
