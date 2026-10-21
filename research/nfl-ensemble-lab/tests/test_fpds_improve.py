import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from lab.fpds_improve import core as C,features as F,opportunity as O
from lab.fpds_improve.run import specs,pseudo_lines,add_intervals


def test_task_groups_schema_only_and_control_unchanged():
    meta={'base_columns':['hist_rec'],'game_base_columns':['ctx_week'],
          'groups':{'r':{'family':'H1','columns':['receiver']},'q':{'family':'H4','columns':['passer']}},
          'game_fp_columns':['fpg__r__home__value','fpg__q__home__value']}
    protocol={'target_groups':{'rec':['H1']},'game_groups':{'total':['H4']}}
    assert C.task_columns(meta,'rec',protocol)==['hist_rec','receiver']
    assert C.task_columns(meta,'total',protocol)==['ctx_week','fpg__q__home__value']
    assert C.task_columns(meta,'rec',protocol,'control')==['hist_rec']


def test_future_prediction_labels_do_not_enter_combination():
    current=pd.DataFrame({'member_linear':[10.,20.],'member_hist':[12.,22.],'member_xgboost':[14.,24.],'member_mlp':[16.,26.],'actual':[999.,999.]})
    p,_=C.combine(current,pd.DataFrame(),'rec_yds','weighted')
    current.actual=-999
    q,_=C.combine(current,pd.DataFrame(),'rec_yds','weighted')
    np.testing.assert_array_equal(p,q)
    np.testing.assert_array_equal(p,[13.,23.])


def test_history_availability_strictly_earlier():
    h=pd.DataFrame({'available_at':pd.to_datetime(['2022-09-01','2022-09-02','2022-09-03'],utc=True),'actual':[1,2,999]})
    assert C.earlier(h,pd.Timestamp('2022-09-02',tz='UTC')).actual.tolist()==[1]


def test_conservative_weights_and_signed_margin_stack():
    columns=['member_'+k for k in ('logreg','xgboost','decision_tree','random_forest','mlp','single_layer')]
    history=pd.DataFrame({c:np.linspace(-20,20,200)+(i*5) for i,c in enumerate(columns)})
    history['actual']=np.linspace(-20,20,200)
    current=pd.DataFrame({c:[-25.] for c in columns})
    p,state=C.combine(current,history,'margin','weighted')
    assert min(state['weights'])>=.5/6
    assert p[0]<0
    p,_=C.combine(current,history,'margin','stacked')
    assert p[0]<0


def test_quantile_crossing_sorted_and_floor_only_nonnegative():
    train=pd.DataFrame({'x':range(20),'rec_yds':range(20),'margin':range(20)})
    def fake(model,*args,**kwargs):return np.array([{.1:5,.5:-2,.9:1}[model.quantile]]),None
    with patch('lab.fpds_improve.core.predict_model',side_effect=fake):
        q=C.quantiles(train,train.iloc[:1],'rec_yds',['x'],np.ones(20))
        np.testing.assert_array_equal(q,[[0,1,5]])
        q=C.quantiles(train,train.iloc[:1],'margin',['x'],np.ones(20))
        np.testing.assert_array_equal(q,[[-2,1,5]])


def test_count_distribution_probability_definitions():
    assert C.count_over([.5],[2.],'hurdle',gate=[.3],positive_mu=[1.])[0]==pytest.approx(.3)
    assert C.count_over([-.5],[2.],'hurdle',gate=[.3],positive_mu=[1.])[0]==1
    assert 0<C.count_over([2.5],[2.],'nb',alpha=1)[0]<1
    assert C.nb_dispersion(pd.DataFrame())==.001


def test_reconciliation_and_distinct_scorer_definition():
    p,other=F.reconcile([20,10],10,100)
    assert p.sum()+other==100
    p,other=F.reconcile([0,0],0,40)
    assert p.sum()==0 and other==40
    probabilities,remainder=F.scorer_probabilities([2.,1.],1.)
    assert probabilities.sum()+remainder<4  # distinct scorers are not TD counts


def fixtures():
    from lab import features as base
    games=[];team=[];qb=[]
    for season in (2021,2022):
        for week in range(1,19):
            for pair,(home,away) in enumerate([('A','B'),('C','D')]):
                gid=f'{season}_{week:02d}_{away}_{home}'
                kickoff=pd.Timestamp(f'{season}-09-01',tz='UTC')+pd.Timedelta(weeks=week,days=pair)
                games.append(dict(game_id=gid,season=season,week=week,kickoff_utc=kickoff,completed=True,game_type='REG',home_team=home,away_team=away,home_score=24,away_score=17,margin=7,total=41,win=1,neutral_site=0))
                for side,t in enumerate([home,away]):
                    row={c:float(week+side) for c in base.STATS if c!='points'}
                    team.append(dict(row,game_id=gid,team=t,season=season))
                    qb.append(dict(game_id=gid,season=season,team=t,qb_id=t+'_QB',qb_dropbacks=30,qb_epa_sum=week))
    injuries=pd.DataFrame(columns=['game_id','team','gsis_id','report_status','position','available_at'])
    injuries['available_at']=pd.to_datetime(injuries.available_at,utc=True)
    return pd.DataFrame(games),pd.DataFrame(team),pd.DataFrame(qb),injuries


def test_strong_game_source_week_canary_and_qb_asof():
    games,team,qb,injuries=fixtures()
    target=games[games.season.eq(2022)&games.week.eq(1)].copy()
    a,cols=F.strong_games(target,games,team,qb,injuries)
    ids=games.loc[games.season.eq(2022),'game_id']
    later=team.game_id.isin(ids);changed=team.copy();changed.loc[later,'epa_pp']=99999
    changedqb=qb.copy();changedqb.loc[changedqb.game_id.isin(ids),'qb_epa_sum']=999999
    mutated=games.copy();mutated.loc[mutated.season.eq(2022),'margin']=9999
    b,_=F.strong_games(target,mutated,changed,changedqb,injuries)
    np.testing.assert_allclose(a[cols].to_numpy(float),b[cols].to_numpy(float),equal_nan=True)
    assert (pd.to_datetime(a.s8_source_available_max,utc=True)<a.kickoff_utc).all()
    assert a.s8_home_qb_known.eq(1).all()


def test_pseudo_lines_skip_unknown_source_week_and_byewindows():
    games=pd.DataFrame({'game_id':['a','b','c'],'season':[2022]*3,'week':[1,3,4],
                        'kickoff_utc':pd.to_datetime(['2022-09-01','2022-09-15','2022-09-22'],utc=True)})
    obs=pd.DataFrame({'pid':['p']*3,'game_id':['a','b','c'],'season':[2022]*3,'week':[1,3,4],
                      **{k:[10,20,999] for k in ('pass_yds','pass_tds','rec','rec_yds','rush_yds')}})
    players=pd.DataFrame({'pid':['p'],'kickoff_utc':pd.to_datetime(['2022-09-22'],utc=True)})
    p=pseudo_lines(players,obs,games)
    assert p.pseudo_rec.iloc[0]==15.5


def test_spec_budget_and_no_holdout_selection():
    entries=specs()
    assert len(entries)==len({s['id'] for s in entries})==77
    assert sum(s['family']=='combination' for s in entries)==36
    assert sum(s['kind']=='quantile' for s in entries)==5
    budget=sum(7 if s['family']=='strong_games' else 5 if s['family']=='target_features' else 3 if s['kind']=='quantile' else 1 for s in entries)
    assert budget==147


def test_binary_calibrator_uses_only_supplied_earlier_history():
    history=pd.DataFrame({'raw':np.tile([.2,.8],150),'actual':np.tile([0.,1.],150)})
    for kind in ('sigmoid','isotonic'):
        p,state=C.calibrate(np.array([.1,.5,.9]),history,kind)
        assert len(p)==3 and np.isfinite(p).all()
        assert np.all(np.diff(p)>=0)
        assert state['history_rows']==300


def test_aggregate_view_has_no_training_actions(tmp_path):
    import json
    from streamlit.testing.v1 import AppTest
    folder=tmp_path/'20261021T120000Z';folder.mkdir()
    (folder/'STATUS.json').write_text(json.dumps({'phase':'complete'}))
    (folder/'SUMMARY.json').write_text(json.dumps({'rows':[{'family':'combination','stat':'rec','arm':'fpds','kind':'weighted','n':100,'games':25,'reference':'A7/rec/fpds','control_loss':1.2,'new_loss':1.1,'relative_reduction':.083,'corrected_ci95':[-.2,.1],'discovery_nomination':False}],'trials':{},'failures':[]}))
    script=f"from app.fpds_improvement_view import render\nrender({str(tmp_path)!r})"
    app=AppTest.from_string(script).run()
    assert not app.exception
    assert len(app.dataframe)==1
    assert not app.button


def test_opportunity_actual_target_labels_not_used_and_coherence():
    n=120
    train=pd.DataFrame({'x':np.arange(n)%5,'game_id':[f'g{i//2}' for i in range(n)],'team':['A']*n,
                        'actual_targets':np.ones(n)*5,'actual_carries':np.ones(n)*2,'actual_dropbacks':np.ones(n)*10,
                        'actual_team_targets':np.ones(n)*20,'actual_team_carries':np.ones(n)*10,
                        'actual_team_dropbacks':np.ones(n)*30,'actual_team_opportunities':np.ones(n)*30,
                        'actual_off_td':np.arange(n)%2,'rec_yds':np.arange(n)%20+20})
    teams=pd.DataFrame({'x':np.arange(60)%5,'is_home':1,'game_id':[f'g{i}' for i in range(60)],'team':'A',
                        'actual_team_targets':20.,'actual_team_carries':10.,'actual_team_dropbacks':30.,'actual_team_pass_yds':200.})
    target=pd.DataFrame({'game_id':['future']*2,'team':['A']*2,'x':[1,2],'rec_yds':[9999,9999]})
    tt=teams.iloc[:1].copy();tt['game_id']='future'
    def fake(model,tr,ta,cols,y,w,binary=False):return np.full(len(ta),float(np.mean(y))),None
    with patch('lab.fpds_improve.opportunity.predict_model',side_effect=fake):
        p,raw,diag=O.predict(train,target,teams,tt,'rec_yds',['x'],['x'],np.ones(n),np.ones(60),lambda _:None)
        target.rec_yds=-9999
        q,_,_=O.predict(train,target,teams,tt,'rec_yds',['x'],['x'],np.ones(n),np.ones(60),lambda _:None)
    np.testing.assert_allclose(p,q)
    assert diag.coherence_error.abs().max()<1e-8
    assert diag.other_players.iloc[0]>=0
