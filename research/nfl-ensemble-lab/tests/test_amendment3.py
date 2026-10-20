import numpy as np
import pandas as pd
import pytest
from lab.props.amendment3.research import rolling_lines,allocate,scale_scorers
from lab.props.weekly10 import execute,outputs,select_slate
from lab.props.amendment2.simulation import anonymous_replacement


def test_pseudo_line_excludes_same_week_and_future():
    p=pd.DataFrame([dict(season=2022,week=4,pid='p',stat='rush_yds')])
    h=pd.DataFrame([dict(season=2022,week=w,pid='p',rush_yds=y) for w,y in ((1,10),(2,20),(3,30),(4,999),(5,1000))])
    first=rolling_lines(p,h).pseudo_line.iloc[0]
    h.loc[h.week.ge(4),'rush_yds']=-999
    assert first==rolling_lines(p,h).pseudo_line.iloc[0]==20
    h['season']=2023
    with pytest.raises(ValueError):rolling_lines(p,h)


def test_allocate_retains_other_mass_and_conserves():
    values,other,scale=allocate([10,30],[20,40],100.)
    assert np.allclose(values,[15,45])
    assert other==40 and abs(values.sum()+other-100)<1e-8
    values,other,_=allocate([0,0],[20,40],100.)
    assert values.sum()==0 and other==100


def test_distinct_scorer_scaling_caps_and_preserves_other():
    probabilities=scale_scorers([.9,.1,.1],2.,.5)
    assert np.all((probabilities>=0)&(probabilities<=1))
    assert abs(probabilities.sum()+.5-2)<1e-8
    with pytest.raises(ValueError):scale_scorers([0.,.2],3.,0.)


def test_pipeline_stops_before_downstream_on_failure(tmp_path):
    calls=[]
    def first():calls.append('first');return {'ok':True}
    def failed():calls.append('failed');raise ValueError('fixture failure')
    def forbidden():calls.append('forbidden')
    with pytest.raises(RuntimeError,match='STOPPED at fail'):
        execute([('first',1,first),('fail',1,failed),('never',1,forbidden)],tmp_path,pd.Timestamp.now(tz='UTC')+pd.Timedelta(minutes=1))
    assert calls==['first','failed']
    assert (tmp_path/'FAILURE.json').exists()


def test_pipeline_budget_guard_and_existing_revision(tmp_path):
    calls=[]
    with pytest.raises(RuntimeError,match='STOPPED'):
        execute([('fit',60,lambda:calls.append('fit'))],tmp_path,pd.Timestamp.now(tz='UTC'))
    assert not calls


def test_isolated_output_restores_all_modules_even_on_failure(tmp_path):
    from lab.props.ensemble import data,production,structural
    from lab.props import projections10
    modules=[data,production,structural,projections10]
    previous=[m.OUT for m in modules]
    with pytest.raises(ValueError):
        with outputs(tmp_path):
            assert all(m.OUT==tmp_path for m in modules)
            raise ValueError('fixture')
    assert [m.OUT for m in modules]==previous


def test_anonymous_replacement_keeps_identity_unknown():
    original={'NE':pd.DataFrame([{'pid':'real','position':'QB'}])}
    changed,pid=anonymous_replacement(original,'NE','QB')
    assert pid=='assumption:QB:NE' and not pid.startswith('00-')
    assert list(original['NE'].pid)==['real']
    assert len(changed['NE'])==2


def test_standalone_inactives_cli_is_read_only(monkeypatch):
    from lab import inactives10
    future=pd.Timestamp.now(tz='UTC')+pd.Timedelta(days=2)
    frame=pd.DataFrame([dict(season=2026,week=8,completed=False,kickoff_utc=future)])
    monkeypatch.setattr(inactives10.pd,'read_parquet',lambda p:frame)
    monkeypatch.setattr(inactives10,'parser_module',lambda:pytest.fail('No game in T90; must not retrieve'))
    assert inactives10.main(['collect','--week','8'])==0


def test_exact_cdf_residual_pool_never_uses_current_or_future_outcomes():
    from lab.props.amendment3.exact_calibration import exact_rows
    history=[dict(game_id=f'h{i}',pid=f'h{i}',team='NE',season=2022,week=1,stat='pass_yds',actual=200+i-75,equal=200.,logreg=200.,members='logreg') for i in range(150)]
    target=dict(game_id='target',pid='p',team='NE',season=2022,week=4,stat='pass_yds',actual=220.,equal=200.,logreg=200.,members='logreg')
    predictions=pd.DataFrame(history+[target])
    observations=pd.DataFrame([dict(season=2021,week=w,pid='p',pass_yds=20+w) for w in (1,2,3)])
    structural=pd.DataFrame(columns=['game_id','pid','stat','member','samples'])
    first,_=exact_rows(predictions,observations,structural)
    predictions.loc[predictions.game_id.eq('target'),'actual']=9999
    second,_=exact_rows(predictions,observations,structural)
    assert first.p_over.equals(second.p_over)
    assert (first.max_residual_week<first.week).all()


def test_explicit_future_week_plan_keeps_completed_cutoff():
    now=pd.Timestamp.now(tz='UTC')
    rows=[dict(season=2026,week=w,game_type='REG',completed=True,kickoff_utc=now-pd.Timedelta(days=7),gameday='2026-10-19') for w in range(1,7)]
    rows.append(dict(season=2026,week=8,game_type='REG',completed=False,kickoff_utc=now+pd.Timedelta(days=12),gameday='2026-11-01'))
    week,slate,cutoff=select_slate(pd.DataFrame(rows),2026,8,now)
    assert week==8 and len(slate)==1 and cutoff['training_last_completed_week']==6


def test_week8_diagnostics_keep_assumption_sensitivity_unknown(tmp_path):
    from lab.props.amendment2.simulation import analyze,SEEDS,SCENARIOS
    base=dict(game_id='2026_08_NE_CHI',pid='p',stat='pass_yds',mode='sim_independent',mean=100.,q50=100.)
    rows=[base|dict(scenario='expected',seed=s) for s in SEEDS]
    rows += [base|dict(scenario=s,seed=SEEDS[0],assumption_based=(i==0)) for i,s in enumerate(SCENARIOS)]
    pd.DataFrame(rows).to_parquet(tmp_path/'2026_08_NE_CHI.parquet',index=False)
    result=analyze(tmp_path,week=8)
    assert result['games']==1
    flags=pd.read_csv(tmp_path/'scenario_summary.csv')
    assert flags.scenario_sensitivity.eq('unknown: assumption-based replacement').all()


def test_full_allocation_retains_unmatched_players_and_marks_unknown():
    from lab.props.amendment3.research import reconcile
    p=pd.DataFrame([dict(game_id='g',team='NE',pid=pid,stat='rush_yds',equal=value,q10=0.,q50=value,q90=value*2) for pid,value in [('known',30.),('unresolved',10.)]])
    s=pd.DataFrame([dict(game_id='g',pid='known',stat='rush_yds',mean=60.)])
    out,teams,errors=reconcile(p,s,{'g':{'NE':{'rush_yds':100.}}},include_unmatched=True)
    assert not errors and len(out)==2
    assert out.structural_eligibility_missing.sum()==1
    assert abs(out.reconciled.sum()+teams.other_players_projection.iloc[0]-100)<1e-8
    assert teams.other_players_projection.iloc[0]==40.
    assert out.reconciliation_coverage.str.startswith('assumption:').all()


def test_td_count_cannot_trigger_distinct_scorer_coherence_failure():
    from lab.props.amendment2.sheets import coherence,leans
    totals=dict(pass_yds=200.,rec_yds=200.,rush_yds=100.,rec=20.,pass_tds=2.,rec_tds=2.,rush_tds=1.,anytime_td=1.5)
    frame=pd.DataFrame([dict(row_type='player',game_id='g',team='NE',pid='p',stat=s,projection=v) for s,v in [('pass_yds',200),('rec_yds',200),('rush_yds',100),('rec',20),('pass_tds',2),('anytime_td',1.5)]])
    _,table=coherence(frame,{'g':{'NE':totals}})
    assert table.atd_vs_td_count_gap.iloc[0]==-1.5
    assert table.atd_vs_distinct_scorer_gap.iloc[0]==0.
    assert table.coherence_flag.iloc[0]=='coherent'
    row=pd.DataFrame([dict(game_id='g',pid='p',stat='rec',projection=6.,q10=2.,q50=5.,q90=9.,market_line=3.5,line_type='consensus',line_status='current',gap=2.5,member_min=4.,member_max=7.,coherence_flag='coherent',reconciliation_coverage='assumption: incomplete structural eligibility')])
    result=leans(row,{('g','p','rec'):'stable'},{('g','p','rec'):'robust'})
    assert result.confidence_tier.iloc[0]=='B'


def test_no_eligible_players_places_entire_team_quantity_in_other():
    from lab.props.amendment3.research import reconcile
    p=pd.DataFrame([dict(game_id='g',team='NE',pid='p',stat='rush_yds',equal=10.,q10=0.,q50=10.,q90=20.)])
    s=pd.DataFrame([dict(game_id='g',pid='p',stat='rush_yds',mean=10.)])
    out,teams,errors=reconcile(p,s,{'g':{'NE':{'rush_yds':20.,'pass_yds':200.},'CHI':{'pass_yds':240.}}},include_unmatched=True)
    assert not errors and len(out)==1
    passing=teams[teams.stat.eq('pass_yds')]
    assert len(passing)==2 and (passing.other_players_projection==passing.team_total).all()
    assert (passing.reconciled_eligible_sum==0).all()
