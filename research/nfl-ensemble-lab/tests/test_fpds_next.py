"""Synthetic offline target, source-clock and joint-distribution regressions."""
import numpy as np
import pandas as pd
from lab.fpds_next import targets as T,roles as R,simulation as D,drives as V


def plays():
    rows=[]
    for q,kind,pid,y in [(4,'run','p',-1),(5,'pass','q',10)]:
        d={c:0. for c in ['two_point_attempt','play_deleted','sack','qb_kneel','qb_spike','pass_attempt','rush_attempt','pass_touchdown','rush_touchdown','return_touchdown','complete_pass']}
        d.update(game_id='g',season=2022,week=1,season_type='REG',posteam='BUF',defteam='NYJ',qtr=q,play_type=kind,
                 passer_player_id='q' if kind=='pass' else None,receiver_player_id='p' if kind=='pass' else None,
                 rusher_player_id='p' if kind=='run' else None,passing_yards=y if kind=='pass' else np.nan,
                 receiving_yards=y if kind=='pass' else np.nan,rushing_yards=y if kind=='run' else np.nan,
                 td_player_id=None,td_team=None,lateral_receiver_player_id=None,lateral_rusher_player_id=None,
                 lateral_receiving_yards=np.nan,lateral_rushing_yards=np.nan)
        d['pass_attempt']=int(kind=='pass');d['rush_attempt']=int(kind=='run');d['qb_kneel']=int(kind=='run');d['complete_pass']=int(kind=='pass')
        rows.append(d)
    return pd.DataFrame(rows)


def roster():
    return pd.DataFrame({'season':[2022]*3,'week':[1]*3,'team':['BUF']*3,'gsis_id':['p','q','z'],
                         'pfr_id':['P','Q','Z'],'position':['WR','QB','WR']})


def snaps():
    return pd.DataFrame({'game_id':['g'],'season':[2022],'week':[1],'team':['BUF'],'game_type':['REG'],
                         'pfr_player_id':['Z'],'offense_snaps':[2]})


def test_targets_include_overtime_kneels_and_verified_zero():
    out,report=T.reconstruct(plays(),roster(),snaps());d=out.set_index('pid')
    assert d.loc['p','rush_yds']==-1 and d.loc['p','rec_yds']==10
    assert d.loc['q','pass_yds']==10 and d.loc['z','rec']==0
    assert report['unmatched_snap_rows']==0


def test_roster_only_unknown_is_never_zero_and_wrong_team_not_reassigned():
    out,_=T.reconstruct(plays(),roster(),snaps().iloc[:0])
    c=pd.DataFrame({'game_id':['g','g'],'pid':['z','p'],'team':['BUF','NYJ']})
    d=T.join_targets(c,out)
    assert d['rec'].isna().all()
    assert d.team.tolist()==['BUF','NYJ']


def test_unknown_team_is_quarantined_without_guessing():
    p=plays();p.loc[0,'posteam']=None
    out,r=T.reconstruct(p,roster(),snaps())
    assert r['unknown_team_play_rows']==1
    assert out.team.notna().all()


def test_lateral_yards_and_missing_td_ids_are_quarantined():
    p=plays();p.loc[1,'lateral_receiver_player_id']='z';p.loc[1,'lateral_receiving_yards']=5
    p.loc[1,'pass_touchdown']=1
    out,r=T.reconstruct(p,roster(),snaps())
    assert out.rec_yds.isna().all() and out.anytime_td.isna().all()
    assert r['quarantined_games']['missing_scorer_id']==1


def test_pfr_ambiguity_does_not_guess_gsis():
    ros=roster();ros.loc[2,'pfr_id']='P'
    sn=snaps();sn.loc[0,'pfr_player_id']='P'
    out,r=T.reconstruct(plays(),ros,sn)
    assert r['unmatched_snap_rows']==1 and 'z' not in set(out.pid)


def role_fixture():
    games=pd.DataFrame({'season':[2021,2022,2022],'week':[18,1,2],
                        'kickoff_utc':pd.to_datetime(['2022-01-09','2022-09-11','2022-09-18'],utc=True)})
    obs=pd.DataFrame({'game_id':['old','new'],'season':[2022,2022],'week':[1,2],'team':['BUF','BUF'],
                     'pid':['p','p'],'targets':[5,999],'carries':[0,0],'dropbacks':[0,0]})
    candidate=pd.DataFrame({'pid':['p'],'team':['BUF'],'season':[2022],'week':[2],
                            'kickoff_utc':pd.to_datetime(['2022-09-18'],utc=True)})
    inj=pd.DataFrame({'gsis_id':['p'],'team':['BUF'],'season':[2022],'week':[2],'report_status':['Out'],
                      'available_at':pd.to_datetime(['2022-09-19'],utc=True)})
    return candidate,obs,games,inj


def test_role_and_injury_future_canaries():
    c,o,g,i=role_fixture();d=R.enrich(c,o,g,i)
    assert d.r10_last1.iloc[0]==5 and d.r10_out.iloc[0]==0
    i['available_at']=pd.to_datetime(['2022-09-17'],utc=True)
    assert R.enrich(c,o,g,i).r10_out.iloc[0]==1
    assert R.enrich(c,o,g,i,asof=pd.Timestamp('2022-09-16',tz='UTC')).r10_out.iloc[0]==0


def test_scenario_probabilities_unknown_and_other_mass_explicit():
    c,o,g,i=role_fixture();r=R.enrich(c,o,g,i).iloc[0]
    rows=R.scenario_rows(r)
    assert len(rows)==3 and all(x['occurrence_probability'] is None for x in rows)
    assert all('other players' in x['label'] for x in rows)


def test_copula_future_rows_cannot_change_correlation():
    histories={}
    for j,s in enumerate(D.ORDER):
        histories[s]=pd.DataFrame({'game_id':np.arange(101),'actual':np.arange(101)+j,'pred':np.zeros(101),
                                   'available_at':pd.to_datetime(['2022-01-01']*100+['2025-01-01'],utc=True)})
    a,n=D.correlation(histories,pd.Timestamp('2023-01-01',tz='UTC'))
    for d in histories.values():d.loc[100,'actual']=-999999
    b,_=D.correlation(histories,pd.Timestamp('2023-01-01',tz='UTC'))
    assert n==100 and np.allclose(a,b) and np.linalg.eigvalsh(a).min()>=.49


def test_distribution_support_and_td_intensity_role_scaling():
    u=np.full((1,100),.7)
    p=D.draws('anytime_td',[.5],u,[0],role=np.full_like(u,2))
    assert p.mean()==1
    assert (D.draws('rec',[3],u,[0])>=0).all()
    assert (D.draws('rush_yds',[0],u,[-1])==-1).all()


def test_group_interval_fallback_and_negative_yard_support():
    h=pd.DataFrame({'actual':np.arange(200),'q10':np.zeros(200),'q90':np.ones(200),
                    'position':['WR']*200,'r10_changed':np.zeros(200)})
    c=h.iloc[:1].copy();c['pred']=2
    d=D.calibrate(c,h,True)
    assert d.q10.iloc[0]<0 and d.pred.iloc[0]==2
    c['position']='RB'
    assert np.allclose(D.calibrate(c,h,True).q10,D.calibrate(c,h,False).q10)


def test_energy_score_deterministic_truth_is_zero():
    a=np.zeros((100,9))
    assert D.energy(a,np.zeros(9),np.ones(9))==0
    assert D.energy(a,np.ones(9),np.ones(9))>0


def drive_fixture():
    return pd.DataFrame({'game_id':['g']*3,'play_id':[1,2,3],'season':[2022]*3,'week':[1]*3,'season_type':['REG']*3,
                         'qtr':[1,2,5],'fixed_drive':[1,2,3],'posteam':['BUF','NYJ','BUF'],
                         'home_team':['BUF']*3,'away_team':['NYJ']*3,'total_home_score':[7,7,10],
                         'total_away_score':[0,7,7],'home_score':[10]*3,'away_score':[7]*3,'play_deleted':[0]*3})


def test_drive_scoreboard_reconciliation_includes_overtime():
    rows,a=V.extract(drive_fixture())
    assert a['verified_games']==1 and rows.home_points.sum()==10 and rows.away_points.sum()==7
    assert (rows.period=='OT').sum()==1
    p=drive_fixture();p['home_score']=100
    assert V.extract(p)[1]['quarantined_games']==1


def test_drive_scoreboard_does_not_forward_fill_between_games():
    a=drive_fixture();b=a.copy();b['game_id']='other';b['total_home_score']=np.nan;b['home_score']=0;b['total_away_score']=0;b['away_score']=0
    rows,audit=V.extract(pd.concat([a,b],ignore_index=True))
    assert audit['quarantined_games']==0
    assert rows.loc[rows.game_id.eq('other'),'home_points'].sum()==0


def test_drive_simulations_have_discrete_nonnegative_scores():
    d,_=V.extract(drive_fixture());parts=[]
    for i in range(32):
        p=d.copy();p['game_id']=str(i);parts.append(p)
    values,info=V.simulate(pd.concat(parts,ignore_index=True),'BUF','NYJ',100,np.random.default_rng(1))
    assert values.shape==(100,2) and np.all(values>=0) and np.all(values==values.astype(int))
    assert info['earlier_ot_games']==32
