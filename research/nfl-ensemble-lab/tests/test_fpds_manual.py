"""Synthetic fixtures only; no subscription files, network, or real model fits."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from lab.fpds_sources import select_sources,HISTORY_FOLDER
from lab.fpds_manual import engine as E
from lab.fpds_manual.features import matched_windows,capped_candidates
from lab.fpds_manual import jobs


def metadata(path):
    contents=path.read_text().splitlines()
    return None,{'header':['SEASON','WEEK','YDS'],'group_header':[],
                 'coverage':{'2021':[1,2],'2026':[1,2,3,4,5,6]} if contents[0]=='complete' else {'2026':[6]}}


def test_full_history_beats_even_newer_modified_same_week_loose_export(tmp_path):
    folder=tmp_path/HISTORY_FOLDER;folder.mkdir()
    base=folder/'receiving-stats.csv';base.write_text('complete')
    loose=tmp_path/'receiving-stats week 6.csv';loose.write_text('partial')
    assert select_sources(tmp_path,metadata)==[base]


def test_later_full_history_is_append_only_replacement(tmp_path):
    folder=tmp_path/HISTORY_FOLDER;folder.mkdir()
    base=folder/'receiving-stats.csv';base.write_text('complete')
    future=tmp_path/'receiving-stats week 7.csv';future.write_text('complete')
    files=select_sources(tmp_path,metadata)
    assert set(files)=={base,future} and base.read_text()=='complete'


def test_later_partial_export_cannot_discard_historical_seasons(tmp_path):
    folder=tmp_path/HISTORY_FOLDER;folder.mkdir()
    (folder/'receiving-stats.csv').write_text('complete')
    (tmp_path/'receiving-stats week 7.csv').write_text('partial')
    with pytest.raises(ValueError,match='incomplete'):select_sources(tmp_path,metadata)


def test_missing_authoritative_folder_never_falls_back_to_legacy(tmp_path):
    (tmp_path/'receiving-stats week 7.csv').write_text('partial')
    with pytest.raises(FileNotFoundError,match='not a fallback'):select_sources(tmp_path,metadata)


def test_future_candidate_is_capped_at_creation_not_later_kickoff():
    now=pd.Timestamp('2026-10-20T12:00Z')
    d=pd.DataFrame({'kickoff_utc':pd.to_datetime(['2026-10-18T12:00Z','2026-10-29T12:00Z'],utc=True)})
    result=capped_candidates(d,now)
    assert result.kickoff_utc.tolist()==[d.kickoff_utc.iloc[0],now]
    assert d.kickoff_utc.iloc[1]>now


def test_training_uses_all_earlier_years_and_waits_for_source_week_plus24h():
    games=pd.DataFrame({'season':[2021,2022,2023,2024,2025,2026,2026],
        'week':[1,1,1,1,1,6,7],'kickoff_utc':pd.to_datetime(['2021-09-13T00:00Z','2022-09-12T00:00Z','2023-09-11T00:00Z','2024-09-09T00:00Z','2025-09-08T00:00Z','2026-10-20T00:00Z','2026-10-25T17:00Z'],utc=True)})
    d=games.copy();d['rec_yds']=10;d['game_id']=range(len(d))
    now=pd.Timestamp('2026-10-20T12:00Z')
    result=E.training_rows(d,games,now,2026,7,'rec_yds')
    assert result.season.tolist()==[2021,2022,2023,2024,2025]
    later=E.training_rows(d,games,pd.Timestamp('2026-10-21T12:00Z'),2026,7,'rec_yds')
    assert later.season.tolist()==[2021,2022,2023,2024,2025,2026] and later.week.max()==6


def test_manual_game_members_reuse_all_six_existing_families():
    from lab.ensemble import MODEL_KEYS
    assert E.members('win')==E.members('margin')==E.members('total')==MODEL_KEYS
    assert E.members('rec')==('linear','hist','xgboost','mlp')
    assert sum((len(E.members(s))+1)*2 for s in E.targets('all'))+2==104


def test_controls_and_fpds_share_all_base_columns_and_only_fpds_adds_features():
    meta={'base_columns':['hist_rec','nflw_rec__last1'],'game_base_columns':['ctx_home_field','nflw_home__rec__last1'],
          'groups':{'role':{'columns':['fp__role__share__last3']}},'game_fp_columns':['fpg__pace__home__pace__last3']}
    assert set(E.columns(meta,'rec','control'))<set(E.columns(meta,'rec','fpds'))
    assert set(E.columns(meta,'win','fpds'))-set(E.columns(meta,'win','control'))=={'fpg__pace__home__pace__last3'}


@pytest.mark.parametrize('stat',['win','margin','rec_yds','rec','anytime_td'])
def test_simulations_are_reproducible_nonnegative_and_keep_point_mean(stat):
    d=pd.DataFrame({'game_id':['synthetic'],'pid':['synthetic'],'stat':[stat],'mean':[.3 if stat in ('win','anytime_td') else 10.],
                    'q10':[0.],'q50':[1.],'q90':[2.],'median':[1.]})
    a=E.simulate(d,np.array([-20.,0.,10.]),sims=1000,seed=17)
    b=E.simulate(d,np.array([-20.,0.,10.]),sims=1000,seed=17)
    pd.testing.assert_frame_equal(a,b)
    assert a['mean'].equals(d['mean']) and a.q10.iloc[0]<=a.q50.iloc[0]<=a.q90.iloc[0]
    if stat!='margin':assert a.q10.iloc[0]>=0


def test_seed_changes_draws_not_model_point_projection():
    d=pd.DataFrame({'game_id':['synthetic'],'stat':['rec_yds'],'mean':[30.]})
    a=E.simulate(d,np.arange(-20,21),1000,17);b=E.simulate(d,np.arange(-20,21),1000,18)
    assert a['mean'].equals(b['mean']) and a.simulated_mean.iloc[0]!=b.simulated_mean.iloc[0]


def test_same_families_and_recency_weights_are_used_without_fitting_real_data():
    train=pd.DataFrame({'season':[2021,2022,2023,2024,2025,2026]*20,'week':[1]*120,'rec':np.tile([1.,2.,3.],40),'x':np.arange(120.)})
    target=pd.DataFrame({'season':[2026],'week':[7],'game_id':['synthetic'],'rec':[np.nan],'x':[1.]})
    seen=[]
    def fake(train,test,stat,cols,key,threads,weights):
        seen.append((key,cols,weights.copy()));return np.full(len(test),2.),{}
    out,bank=E.fit_matched(train,target,'rec',['x'],pd.DataFrame(),fit=fake)
    assert [x[0] for x in seen]==list(E.MEMBERS)
    assert all(np.array_equal(seen[0][2],x[2]) for x in seen)
    assert seen[0][2][5]>seen[0][2][0] and out['mean'].iloc[0]==2


def test_whole_game_bootstrap_is_deterministic_and_counts_games():
    a=E.paired(np.array([-1.,-2.,1.]),['a','a','b'],30)
    assert a==E.paired(np.array([-1.,-2.,1.]),['a','a','b'],30)
    assert a['n']==3 and a['games']==2


def test_job_ids_and_duplicate_active_jobs_are_guarded(tmp_path,monkeypatch):
    monkeypatch.setattr(jobs,'ROOT',tmp_path)
    with pytest.raises(ValueError,match='Invalid'):jobs.directory('../escape')
    monkeypatch.setattr(jobs,'registered',lambda:({},'fixed'))
    monkeypatch.setattr(jobs,'active',lambda:{'job':'existing','pid':1})
    with pytest.raises(ValueError,match='already running'):jobs.launch('project',week=7)


def test_manual_compare_protocol_has_no_holdout_selector():
    PROTOCOL=Path(__file__).resolve().parents[1]/'docs/FPDS_MANUAL_PROTOCOL.json'
    p=json.loads(PROTOCOL.read_text())
    assert p['discovery_seasons']==[2022,2023,2024] and p['configuration_budget']==104
    assert '2025' in p['confirmation'] and 'No new' in p['confirmation']


@pytest.mark.parametrize('team_column',['team','posteam'])
def test_matched_windows_exclude_a_finished_week_until_plus24h(team_column):
    now=pd.Timestamp('2026-09-21T12:00Z')
    games=pd.DataFrame({'season':[2026]*3,'week':[1,2,3],
        'kickoff_utc':pd.to_datetime(['2026-09-13T20:20Z','2026-09-20T20:20Z','2026-09-27T20:20Z'],utc=True),
        'home_team':['BUF']*3,'away_team':['KC']*3})
    players=pd.DataFrame({'season':[2026],'week':[3],'pid':['synthetic'],'kickoff_utc':[games.kickoff_utc.iloc[-1]]})
    obs=pd.DataFrame({'season':[2026]*2,'week':[1,2],'game_id':['a','b'],'pid':['synthetic']*2,'team':['BUF']*2,
        'snap_share':[1.,1.],'targets':[1.,999.],'carries':[0.,0.],'dropbacks':[0.,0.],'rec':[1.,999.]})
    obs=obs.rename(columns={'team':team_column})
    a,g,_,_=matched_windows(players,games,obs,now)
    assert a.nflw__rec__last1.iloc[0]==1
    assert g.loc[g.week.eq(3),'nflw_home__rec__last1'].iloc[0]==1
    changed=obs.copy();changed.loc[changed.week.eq(2),'rec']=-999
    b,_,_,_=matched_windows(players,games,changed,now)
    assert a.nflw__rec__last1.equals(b.nflw__rec__last1)


def test_plan_parser_errors_do_not_print_source_values(tmp_path,monkeypatch,capsys):
    from lab.fpds_manual import __main__ as cli
    import lab.fpds_sources as sources
    monkeypatch.setattr(jobs,'ROOT',tmp_path)
    monkeypatch.setattr(sys,'argv',['manual','plan'])
    def bad_source():raise ValueError('sensitive-synthetic-row-value')
    monkeypatch.setattr(sources,'select_sources',bad_source)
    assert cli.main()==1
    assert 'sensitive-synthetic-row-value' not in capsys.readouterr().out
    assert list((tmp_path/'errors').glob('*PRIVATE.log'))


def test_probability_reliability_counts_exact_edges_and_one():
    from lab.fpds_manual.run import score_diagnostics
    d=pd.DataFrame({'game_id':['a','b','c'],'actual':[1.,0.,1.],'pred':[.6,0.,1.]})
    result=score_diagnostics(d,'win')
    assert sum(x['n'] for x in result['reliability'])==3


def fake_game_fit(train,target,stat,cols,key,threads,weights):
    return np.full(len(target),.6 if stat=='win' else 3. if stat=='margin' else 45.),{}


def test_matched_game_comparison_finishes_with_mocked_factories(tmp_path,monkeypatch):
    from lab.fpds_manual import run as R
    monkeypatch.setattr(jobs,'PROTOCOL',Path(__file__).resolve().parents[1]/'docs/FPDS_MANUAL_PROTOCOL.json')
    games=pd.DataFrame({'season':[2021,2022,2023,2024],'week':[1]*4,'game_id':['a','b','c','d'],
        'kickoff_utc':pd.to_datetime(['2021-09-12T17:00Z','2022-09-11T17:00Z','2023-09-10T17:00Z','2024-09-08T17:00Z'],utc=True),
        'win':[1.,0.,1.,0.],'margin':[3.]*4,'total':[45.]*4,'ctx_week':[1.]*4,'fp_game':[1.]*4,
        'market_p_home_novig':[.5]*4,'spread_line':[2.]*4,'total_line':[44.]*4})
    monkeypatch.setattr(R,'load',lambda meta:(pd.DataFrame(),games))
    def train(data,games,decision,season,week,stat):
        return pd.DataFrame({'season':[2021]*120,'week':[1]*120,stat:np.tile([0.,1.],60) if stat=='win' else [3. if stat=='margin' else 45.]*120})
    monkeypatch.setattr(E,'training_rows',train);monkeypatch.setattr(E,'fit_member',fake_game_fit)
    meta={'base_columns':[],'game_base_columns':['ctx_week'],'groups':{},'game_fp_columns':['fp_game'],'history_windows':'matched'}
    R.compare(tmp_path,{'scope':'games','seed':17,'signature':'fixed'},meta,pd.Timestamp.now(tz='UTC')+pd.Timedelta(hours=1))
    result=json.loads((tmp_path/'SUMMARY.json').read_text())
    assert len(result['rows'])==21 and len(result['trials']['configurations'])==42
    assert not result['failures'] and all(r['identical_sample'] for r in result['rows'])
    assert not any(r['discovery_nomination'] for r in result['rows'])


def test_manual_game_projection_writes_private_new_revision_without_market_input(tmp_path,monkeypatch):
    from lab.fpds_manual import run as R
    from lab.fpds_research import weekly
    now=pd.Timestamp.now(tz='UTC')
    times=[now-pd.Timedelta(days=60-7*i) for i in range(6)]+[now+pd.Timedelta(days=3)]
    games=pd.DataFrame({'season':[2026]*7,'week':list(range(1,8)),'game_id':[f'synthetic{i}' for i in range(7)],
        'game_type':['REG']*7,'completed':[True]*6+[False],'kickoff_utc':times,'gameday':[t.date() for t in times],
        'home_team':['BUF']*7,'away_team':['KC']*7,'win':[1.]*6+[np.nan],'margin':[3.]*6+[np.nan],'total':[45.]*6+[np.nan]})
    monkeypatch.setattr(R,'load',lambda meta:(pd.DataFrame(),games))
    monkeypatch.setattr(jobs,'list_jobs',lambda:[])
    def train(data,games,decision,season,week,stat):return pd.DataFrame({'season':[2021,2022,2023,2024,2025,2026]*20,'week':[1]*120,stat:[.5 if stat=='win' else 3.]*120})
    monkeypatch.setattr(E,'training_rows',train);monkeypatch.setattr(E,'fit_member',fake_game_fit)
    def benchmark(rows,games,asof):
        d=rows.copy();d['consensus_line']=np.nan;d['gap']=np.nan;d['line_status']='unavailable';return d
    monkeypatch.setattr(weekly,'game_comparison',benchmark)
    meta={'requested_week':7,'source_observed_at':(now-pd.Timedelta(days=1)).isoformat(),'fingerprint':'fixed','discovery_fingerprint':'fixed',
          'base_columns':[],'game_base_columns':['ctx_week'],'groups':{},'game_fp_columns':['fp_game']}
    R.project(tmp_path,{'scope':'games','sims':1000,'seed':17,'signature':'fixed'},meta,now+pd.Timedelta(hours=1))
    summary=json.loads((tmp_path/'SUMMARY.json').read_text())
    output=Path(summary['path']);d=pd.read_csv(output/'projections.csv')
    assert summary['games']==1 and summary['training_last_completed_week']==6
    assert set(d.arm)=={'control','fpds'} and len(d)==6 and d.gap.isna().all()
    assert all(x['seasons']==[2021,2022,2023,2024,2025,2026] for x in summary['training'])
    assert set(d.confidence_tier)=={'C'} and not (tmp_path/'models/CURRENT.json').exists()


def test_manual_props_include_all_six_stats_and_normalized_first_td(tmp_path,monkeypatch):
    from lab.fpds_manual import run as R
    from lab.fpds_research import weekly,first_td
    from lab.props.ensemble import features as F
    now=pd.Timestamp.now(tz='UTC')
    times=[now-pd.Timedelta(days=60-7*i) for i in range(6)]+[now+pd.Timedelta(days=3)]
    games=pd.DataFrame({'season':[2026]*7,'week':list(range(1,8)),'game_id':[f'synthetic{i}' for i in range(7)],
        'game_type':['REG']*7,'completed':[True]*6+[False],'kickoff_utc':times,'gameday':[t.date() for t in times],
        'home_team':['BUF']*7,'away_team':['KC']*7})
    players=pd.DataFrame({'season':[2026],'week':[7],'game_id':['synthetic6'],'pid':['synthetic'],'team':['BUF'],'name':['Synthetic Player'],
        'position':['WR'],'kickoff_utc':[times[-1]],**{s:[np.nan] for s in E.PROP_STATS}})
    monkeypatch.setattr(R,'load',lambda meta:(players,games));monkeypatch.setattr(jobs,'list_jobs',lambda:[])
    monkeypatch.setattr(E,'data_for',lambda stat,p,g:p.copy())
    monkeypatch.setattr(F,'eligible',lambda frame,stat:pd.Series(True,index=frame.index))
    def train(data,games,decision,season,week,stat):return pd.DataFrame({'season':[2021,2022,2023,2024,2025,2026]*20,'week':[1]*120,stat:np.tile([0.,1.],60) if stat=='anytime_td' else [2. if stat in ('rec','pass_tds') else 20.]*120})
    monkeypatch.setattr(E,'training_rows',train)
    calls=[]
    def fake(train,target,stat,cols,key,threads,weights):
        calls.append((stat,key));return np.full(len(target),.3 if stat=='anytime_td' else 2. if stat in ('rec','pass_tds') else 20.),{}
    monkeypatch.setattr(E,'fit_member',fake)
    monkeypatch.setattr(first_td,'labels',lambda seasons:pd.DataFrame({'game_id':games.game_id.iloc[:6],'scorer':['other_synthetic']*6}))
    def prices(rows,asof):
        assert len(calls)==48  # Lines are not read until independent fitting is over.
        d=rows.copy();d['consensus_line']=np.nan;d['gap']=np.nan;d['line_status']='unavailable';d['line_type']='unavailable'
        d.loc[d.stat.eq('rec_yds'),['consensus_line','line_type','line_status']]=[18.5,'consensus','current']
        return d
    monkeypatch.setattr(weekly,'quote_comparison',prices)
    meta={'requested_week':7,'source_observed_at':(now-pd.Timedelta(days=1)).isoformat(),'fingerprint':'fixed','discovery_fingerprint':'fixed',
          'base_columns':['nflw_rec__last1'],'game_base_columns':[],'groups':{},'game_fp_columns':[]}
    R.project(tmp_path,{'scope':'props','sims':1000,'seed':17,'signature':'fixed'},meta,now+pd.Timedelta(hours=1))
    summary=json.loads((tmp_path/'SUMMARY.json').read_text());d=pd.read_csv(Path(summary['path'])/'projections.csv')
    assert set(d.stat)==set(E.PROP_STATS)|{'first_td'}
    td=d[d.stat.eq('first_td')]
    assert np.allclose(td.groupby(['game_id','arm'])['mean'].sum(),1)
    assert set(td.pid)=={'synthetic','OTHER_PLAYERS','NO_OFFENSIVE_TD'} and td.member_min.isna().all()
    assert d.loc[d.stat.eq('rec_yds'),'gap'].eq(1.5).all()
    assert d.loc[d.stat.isin(['anytime_td','first_td']),'gap'].isna().all()
