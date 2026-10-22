"""Synthetic weekly drops only. No paid source files, network or model fits."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from lab import fpds_drop as D
from lab.fpds_sources import HISTORY_FOLDER,select_sources
from lab.fpds_research import ingest as I


def source(tmp_path):
    root=tmp_path/'Inbox';base=root/HISTORY_FOLDER;base.mkdir(parents=True)
    original=base/'receiving-stats.csv'
    original.write_text('SEASON,WEEK,Player,TEAM,YDS\n2021,1,Fixture,BUF,20\n2026,6,Fixture,BUF,25\n')
    return root,base,original


def test_week8_means_stats_through7_with_original_names(tmp_path):
    root,base,original=source(tmp_path)
    folder=base/'Week 8';folder.mkdir()
    drop=folder/'receiving-stats.csv'
    drop.write_text('SEASON,WEEK,Player,TEAM,YDS\n2026,7,Fixture,BUF,30\n')
    d,m=I.parsed(drop)
    assert m['export_through_week']==7 and d._week.tolist()==[7]
    assert set(select_sources(root,week=8))=={original,drop}
    assert select_sources(root,week=7)==[original]
    assert original.read_text().endswith('25\n')


def test_future_folders_and_newer_mtime_cannot_leak_into_week8(tmp_path):
    root,base,original=source(tmp_path)
    for week in [9,18]:
        folder=base/f'Week {week}';folder.mkdir()
        (folder/'receiving-stats.csv').write_text('SEASON,WEEK,Player,TEAM,YDS\n2026,8,Fixture,BUF,999\n')
    assert select_sources(root,week=8)==[original]
    (root/'receiving-stats week 18.csv').write_text('future legacy export must not be read')
    assert select_sources(root,week=8)==[original]


def test_current_week_outcomes_and_wrong_filename_are_refused(tmp_path):
    root,base,_=source(tmp_path)
    folder=base/'Week 8';folder.mkdir()
    path=folder/'receiving-stats.csv'
    path.write_text('SEASON,WEEK,Player,TEAM,YDS\n2026,8,Fixture,BUF,999\n')
    with pytest.raises(ValueError,match='forecast-week'):I.parsed(path)
    path.unlink()
    (folder/'receiving-stats week 8.csv').write_text('synthetic')
    with pytest.raises(ValueError,match='filename'):select_sources(root,week=8)


def test_overlay_preserves_history_and_replaces_whole_source_week():
    old=pd.DataFrame({'season':[2021,2026,2026],'week':[1,7,7],'pid':['a','a','b'],'value':[1,2,3]})
    new=pd.DataFrame({'season':[2026],'week':[7],'pid':['a'],'value':[4]})
    result=I.overlay_weeks([(0,old),(1,new)])
    assert result.value.tolist()==[1,4]  # removed player b must not leak back from the old export
    assert old.value.tolist()==[1,2,3]


def test_weekly_drop_requires_all_tables_and_previous_week_coverage(tmp_path):
    root,base,_=source(tmp_path)
    (base/'pace.csv').write_text('SEASON,WEEK,TEAM,PACE\n2026,6,BUF,30\n')
    (base/'Week 8').mkdir()
    with pytest.raises(ValueError,match='Missing tables'):D.inspect_drop(8,root)
    for name in ['receiving-stats','pace']:(base/'Week 8'/f'{name}.csv').write_text('synthetic')
    fake=lambda p:(None,{'coverage':{'2026':[6]}})
    with pytest.raises(ValueError,match='lacks completed'):D.inspect_drop(8,root,parse=fake)


def test_week7_can_bootstrap_from_existing_history(tmp_path):
    root,_,_=source(tmp_path)
    result=D.inspect_drop(7,root)
    assert result['baseline_bootstrap'] and result['statistics_through_week']==6
    assert result['files']==0


def test_week_scope_restores_environment(monkeypatch):
    monkeypatch.setenv('NFL_FPDS_TARGET_WEEK','7')
    with D.scope_week(8):assert D.os.environ['NFL_FPDS_TARGET_WEEK']=='8'
    assert D.os.environ['NFL_FPDS_TARGET_WEEK']=='7'


def test_injury_update_excludes_outcomes_and_never_changes_forecasts(tmp_path,monkeypatch):
    root,base,_=source(tmp_path)
    header='SEASON,WEEK,Player,TEAM,STATUS,SNAPS\n'
    (base/'injury-reports.csv').write_text(header+'2026,6,Fixture,BUF,out,50\n')
    folder=base/'Week 8';folder.mkdir()
    drop=folder/'injury-reports week 8.csv';drop.write_text(header+'2026,8,Fixture,BUF,out,999\n')
    monkeypatch.setattr(D,'STATE',tmp_path/'state');monkeypatch.setattr(D,'LAB_ROOT',tmp_path/'lab')
    from lab import config
    monkeypatch.setattr(config,'RAW_DIR',tmp_path/'raw');config.RAW_DIR.mkdir()
    pd.DataFrame({'week':[8],'full_name':['Fixture'],'team':['BUF'],'gsis_id':['00-001']}).to_parquet(config.RAW_DIR/'roster_weekly_2026.parquet')
    games=pd.DataFrame({'season':[2026],'week':[8],'home_team':['BUF'],'away_team':['MIA'],'kickoff_utc':[pd.Timestamp.now(tz='UTC')+pd.Timedelta(days=7)]})
    before=drop.read_bytes()
    result=D.archive_injuries(8,root,games)
    private=pd.read_parquet(Path(result['path'])/'CONTEXT_PRIVATE.parquet')
    assert result['model_input'] is False and result['pregame_matched_rows']==1 and result['unmatched_rows']==0
    assert set(private)=={'pid','team','status','observed_at','pregame'} and 'SNAPS' not in private
    assert drop.read_bytes()==before
    again=D.archive_injuries(8,root,games)
    assert again['path']!=result['path'] and Path(result['path']).exists()
    _,parsed=I.parsed(drop)
    assert parsed['valid_rows']==0  # target-week outcomes never enter historical features
    from lab import fpds_ingest as old
    original_parse=old.parse
    def mutate_after_parse(path):
        result=original_parse(path)
        if Path(path)==drop:drop.write_text(header+'2026,8,Fixture,BUF,questionable,888\n')
        return result
    monkeypatch.setattr(old,'parse',mutate_after_parse)
    with pytest.raises(D.DropError,match='changed during parsing'):D.archive_injuries(8,root,games)


def test_workflow_lock_refuses_concurrent_updates_and_cleans_own_lock(tmp_path,monkeypatch):
    monkeypatch.setattr(D,'STATE',tmp_path)
    with D.workflow_lock():
        assert D.workflow_active()
        with pytest.raises(D.DropError,match='already running'):
            with D.workflow_lock():pass
    assert not D.workflow_active()


def test_frozen_schema_gate_compares_with_original_committed_contract(tmp_path,monkeypatch):
    lab=tmp_path/'lab';(lab/'docs').mkdir(parents=True)
    job=tmp_path/'job';job.mkdir();imported=tmp_path/'imported';imported.mkdir()
    (lab/'docs/FPDS_AMENDMENT6_FROZEN.json').write_text(json.dumps({'research_path':str(job)}))
    (job/'JOB.json').write_text(json.dumps({'feature_metadata':{'import_manifest_path':str(imported)}}))
    (imported/'MANIFEST.json').write_text(json.dumps({'working_tables':[{'table':'receiving_stats','header_rows':1,'header':['SEASON','WEEK','YDS']}]}))
    csv=tmp_path/'receiving-stats.csv';csv.write_text('SEASON,WEEK,YDS\n2026,7,10\n')
    monkeypatch.setattr(D,'LAB_ROOT',lab);monkeypatch.setattr(D,'select_sources',lambda:[csv])
    assert D.frozen_schema_check()==1
    csv.write_text('SEASON,WEEK,DIFFERENT\n2026,7,10\n')
    with pytest.raises(ValueError,match='header changed'):D.frozen_schema_check()


def test_previous_results_score_each_frozen_revision_and_exclude_postgame_archive(tmp_path,monkeypatch):
    monkeypatch.setattr(D,'ROOT',tmp_path/'root')
    games=pd.DataFrame({'season':[2026],'week':[7],'completed':[True],'game_id':['g'],
                        'kickoff_utc':[pd.Timestamp('2026-10-25T17:00Z')],'home_win':[1.],'margin':[7.],'total':[45.]})
    observations=tmp_path/'observations.parquet'
    pd.DataFrame({'game_id':['g'],'pid':['p'],'rec_yds':[50.]}).to_parquet(observations)
    for i,created in [(1,'2026-10-20T12:00Z'),(2,'2026-10-25T20:00Z')]:
        folder=D.ROOT/'weekly'/f'2026_w07_r{i:03d}_fixture';folder.mkdir(parents=True)
        (folder/'FORECAST.json').write_text(json.dumps({'created_at':created}))
        pd.DataFrame({'game_id':['g'],'pid':['p'],'stat':['rec_yds'],'arm':['frozen'],'mean':[40.]}).to_csv(folder/'projections.csv',index=False)
        pd.DataFrame({'game_id':['g'],'stat':['win'],'arm':['frozen'],'mean':[.6]}).to_csv(folder/'game_projections.csv',index=False)
    dest=tmp_path/'report';dest.mkdir()
    result=D.previous_results(dest,8,observations,games)
    assert len(result['rows'])==2
    assert {r['revision'] for r in result['rows']}=={'2026_w07_r001_fixture'}
    assert {r['stat']:r['loss'] for r in result['rows']}==pytest.approx({'rec_yds':10.,'win':.16})


def test_failure_stops_without_running_sheets_or_changing_earlier_forecasts(tmp_path,monkeypatch):
    from lab.fpds_manual import jobs
    from lab import data_pipeline,fpds_worker,fpds_weekly_guard,fpds_sheets
    from lab.fpds_research import weekly
    monkeypatch.setattr(D,'STATE',tmp_path/'state')
    monkeypatch.setattr(jobs,'active',lambda:None)
    monkeypatch.setattr(D,'inspect_drop',lambda w:{'forecast_week':w})
    monkeypatch.setattr(D,'frozen_inventory',lambda:{})
    monkeypatch.setattr(D,'frozen_schema_check',lambda:1)
    monkeypatch.setattr(fpds_worker,'install',lambda:None)
    monkeypatch.setattr(fpds_weekly_guard,'check',lambda *a:1)
    games=tmp_path/'games.parquet'
    pd.DataFrame({'kickoff_utc':[pd.Timestamp('2026-10-30T00:15Z')]}).to_parquet(games)
    monkeypatch.setattr(data_pipeline,'FEATURE_STORE',games)
    monkeypatch.setattr(weekly,'run',Mock(side_effect=RuntimeError('synthetic failure')))
    sheets=Mock();monkeypatch.setattr(fpds_sheets,'run',sheets)
    with pytest.raises(RuntimeError,match='synthetic'):D.run_weekly(8)
    sheets.assert_not_called()
    assert len(list(D.STATE.glob('weekly/*/FAILED.json')))==1
    assert not (D.STATE/'LATEST_WEEKLY.json').exists()


def test_injury_menu_routes_only_to_context_command():
    from lab.launcher import ACTIONS
    assert ACTIONS['injuries'][1].name=='update_fpds_injuries.bat'
    assert '-m lab.fpds_drop injuries' in ACTIONS['injuries'][1].read_text()


def test_cutoff_waits_for_entire_week_and_24h_after_final_kickoff():
    games=pd.DataFrame({'season':[2026]*7,'week':list(range(1,8)),'game_type':['REG']*7,'completed':[True]*7,
                        'kickoff_utc':pd.to_datetime(['2026-09-10T00:15Z','2026-09-18T00:15Z','2026-09-25T00:15Z',
                            '2026-10-02T00:15Z','2026-10-09T00:15Z','2026-10-20T00:15Z','2026-10-27T00:15Z'])})
    games['gameday']=games.kickoff_utc.dt.date
    with pytest.raises(D.DropError,match='24h'):D.validate_completed_week(games,8,pd.Timestamp('2026-10-28T00:00Z'))
    assert D.validate_completed_week(games,8,pd.Timestamp('2026-10-28T00:16Z'))['training_last_completed_week']==7
    games.loc[6,'completed']=False
    with pytest.raises(D.DropError,match='fully completed'):D.validate_completed_week(games,8,pd.Timestamp('2026-10-28T00:16Z'))


def test_working_overlay_retains_history_and_is_idempotent(tmp_path):
    files=[]
    for index,(season,week,value,drop) in enumerate([(2021,1,'10',None),(2026,7,'20',8)]):
        d=pd.DataFrame({'SEASON':[str(season)],'WEEK':[str(week)],'Player':['Fixture'],'TEAM':['BUF'],'YDS':[value],
                        '_season':[season],'_week':[week],'season':[season],'week':[week],'entity':['p'],'pid':['p'],'_name':['Fixture']})
        file=tmp_path/f'v{index}.parquet';d.to_parquet(file)
        m={'table':'receiving_stats','header':['SEASON','WEEK','Player','TEAM','YDS'],
            'qualified_header':['SEASON','WEEK','Player','TEAM','YDS'],'private_path':str(file),
            'export_through_week':6 if drop is None else 7,'modified_ns':index,'sha256':str(index),
            'first_observed_at':'2026-10-20T12:00Z','source_path':str(file),'possible_export_cap':False}
        if drop:m['drop_forecast_week']=drop
        files.append(m)
    result=I.weekly_working(files,{'receiving_stats':files[0]},tmp_path)['receiving_stats']
    assert pd.read_parquet(result['usable_path']).season.tolist()==[2021,2026]
    assert result['coverage']=={'2021':[1],'2026':[7]}
    assert result['valid_rows']==2
    again=I.weekly_working(files,{'receiving_stats':files[0]},tmp_path)['receiving_stats']
    assert again['working_hash']==result['working_hash']


def test_successful_weekly_sequence_preserves_files_and_only_then_advances_pointer(tmp_path,monkeypatch):
    from lab.fpds_manual import jobs
    from lab import data_pipeline,fpds_worker,fpds_weekly_guard,fpds_sheets,fpds_clv,prospective
    from lab.fpds_research import weekly
    monkeypatch.setattr(D,'STATE',tmp_path/'state');monkeypatch.setattr(D,'ROOT',tmp_path/'root')
    monkeypatch.setattr(jobs,'active',lambda:None)
    monkeypatch.setattr(D,'inspect_drop',lambda w:{'forecast_week':w})
    protected=tmp_path/'old_forecast.csv';protected.write_text('immutable fixture')
    monkeypatch.setattr(D,'frozen_inventory',lambda:{str(protected):D.sha(protected)})
    monkeypatch.setattr(D,'frozen_schema_check',lambda:1)
    monkeypatch.setattr(fpds_worker,'install',lambda:None)
    monkeypatch.setattr(fpds_weekly_guard,'check',lambda *a:1)
    games=tmp_path/'games.parquet'
    pd.DataFrame({'season':[2026],'week':[7],'completed':[True],'game_id':['g'],'kickoff_utc':[pd.Timestamp('2026-10-27T00:15Z')]}).to_parquet(games)
    monkeypatch.setattr(data_pipeline,'FEATURE_STORE',games)
    empty=tmp_path/'empty';empty.mkdir();monkeypatch.setattr(D,'drop_folder',lambda w:empty)
    order=[]
    def fit(args):
        assert args.strict_drop and args.week==8
        order.append('fit')
        forecast=tmp_path/'new_revision';(forecast/'base').mkdir(parents=True)
        pd.DataFrame({'game_id':[],'pid':[]}).to_parquet(forecast/'base/observations_production.parquet')
        return {'path':str(forecast),'training_last_completed_week':7}
    monkeypatch.setattr(weekly,'run',fit)
    monkeypatch.setattr(prospective,'score',lambda **kw:order.append('champion score'))
    monkeypatch.setattr(fpds_sheets,'run',lambda p:order.append('sheets') or {'path':str(p/'presentation')})
    monkeypatch.setattr(fpds_clv,'run',lambda:order.append('quote tracking'))
    result=D.run_weekly(8)
    assert order==['fit','champion score','sheets','quote tracking']
    assert result['old_forecasts_unchanged'] and protected.read_text()=='immutable fixture'
    assert (D.STATE/'LATEST_WEEKLY.json').exists()
    assert Path(result['previous_results']).exists()


def test_weekly_view_missing_and_completed_cases(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from lab.fpds_research import common
    root=tmp_path/'state';root.mkdir()
    code=f'from app.fpds_drop_view import render\nrender({str(root)!r})'
    missing=AppTest.from_string(code).run()
    assert not missing.exception and any('No completed Tuesday' in x.value for x in missing.info)
    private=tmp_path/'private';monkeypatch.setattr(common,'ROOT',private)
    presentation=private/'weekly'/'fixture'/'presentations';presentation.mkdir(parents=True)
    pd.DataFrame({'name':['Fixture game','Fixture player'],'stat':['win','rec_yds'],'arm':['frozen','frozen'],
                  'team':['GAME','BUF'],'mean':[.6,50.],'line_status':['unavailable','unavailable']}).to_csv(presentation/'projections.csv',index=False)
    report=root/'result.json';report.write_text(json.dumps({'week':7,'rows':[{'stat':'win','metric':'Brier','loss':.2}]}))
    (root/'LATEST_WEEKLY.json').write_text(json.dumps({'created_at':'2026-10-28T01:00Z','forecast_week':8,
        'forecast':{'training_last_completed_week':7},'presentation':{'path':str(presentation)},'previous_results':str(report)}))
    complete=AppTest.from_string(code).run()
    assert not complete.exception and len(complete.dataframe)==3
    next(x for x in complete.selectbox if x.label=='Weekly team').select('BUF').run()
    assert not complete.exception
