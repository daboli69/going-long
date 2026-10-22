"""Synthetic source reconciliation, no network or real subscription data."""
from contextlib import nullcontext
import json
from pathlib import Path
from unittest.mock import Mock
import pandas as pd
import pytest

from lab import fpds_injury_confirmation as C

NOW=pd.Timestamp('2026-10-22T12:00Z')
GAMES=pd.DataFrame({'game_id':['g'],'season':[2026],'week':[7],'home_team':['BUF'],'away_team':['MIA'],
                    'kickoff_utc':[NOW+pd.Timedelta(hours=8)]})


def row(source,status,minutes=60,pid='p'):
    return {'source':source,'status':status,'available_at':NOW-pd.Timedelta(minutes=minutes),'team':'BUF','pid':pid}


def compare(*rows):return C.reconcile(pd.DataFrame(rows),GAMES,NOW)


def test_original_official_remains_primary_and_csv_confirms():
    d,m=compare(row('official_nflverse','Out'),row('fpds','out',30),row('espn','Out',20))
    assert d.iloc[0].effective_status=='out' and d.iloc[0].selected_source=='official_nflverse'
    assert m['confirmed']==1 and m['conflicts']==0 and not d.model_input.any()


def test_newer_csv_never_blindly_overwrites_official_conflict():
    d,m=compare(row('official_nflverse','Out',120),row('fpds','Active',5))
    assert d.iloc[0].effective_status=='out' and m['conflicts']==1 and m['confirmed']==0
    assert set(d.iloc[0].sources)=={'official_nflverse','fpds'}


def test_new_official_snapshot_replaces_older_status_without_deleting_evidence():
    d,m=compare(row('official_nflverse','Questionable',120),row('official_nflverse','Out',10),row('fpds','Out',5))
    assert d.iloc[0].effective_status=='out' and m['confirmed']==1


def test_csv_fills_missing_context_provisionally_not_model_input():
    d,m=compare(row('fpds','Questionable'))
    assert d.iloc[0].effective_status=='questionable' and m['fpds_only']==1
    assert 'provisional' in d.iloc[0].reason and not d.model_input.any()


def test_espn_and_csv_agreement_is_secondary_when_official_missing():
    d,m=compare(row('espn','Out'),row('fpds','Out',10))
    assert d.iloc[0].selected_source=='secondary agreement' and m['confirmed']==1


def test_secondary_conflict_is_unresolved():
    d,m=compare(row('espn','Out'),row('fpds','Active',10))
    assert d.iloc[0].effective_status=='unknown' and m['conflicts']==1


def test_unknown_is_not_active_and_absence_is_not_a_healthy_row():
    d,m=compare(row('fpds','not specified'))
    assert d.iloc[0].effective_status=='unknown' and m['fpds_only']==0
    assert C.reconcile(pd.DataFrame(),GAMES,NOW)[1]['players']==0


def test_future_postkickoff_and_unknown_ids_are_excluded():
    d,m=compare(row('fpds','Out',-30),row('fpds','Out',10,pid=None))
    assert d.empty and m['excluded_rows']==2
    assert C.reconcile(pd.DataFrame([row('fpds','Out')]),GAMES,NOW+pd.Timedelta(days=1))[0].empty


def test_conflicting_same_timestamp_rows_are_not_arbitrarily_chosen():
    d,m=compare(row('fpds','Out'),row('fpds','Active'))
    assert d.iloc[0].effective_status=='unknown' and m['conflicts']==1


def test_stale_agreement_is_flagged_and_source_times_retained():
    d,m=compare(row('fpds','Out',1500),row('official_nflverse','Out',1600))
    assert m['confirmed']==1 and m['stale_source_rows']==2
    assert d.iloc[0].oldest_source_age_hours>24


@pytest.mark.parametrize('raw,expected',[('Injured Reserve','ir'),('OUT','out'),('PUP','pup'),('', 'unknown')])
def test_status_normalization(raw,expected):assert C.normalize_status(raw)==expected


def test_no_imported_csv_means_original_refresh_does_no_extra_work(tmp_path,monkeypatch):
    from lab import fpds_drop
    monkeypatch.setattr(fpds_drop,'STATE',tmp_path)
    assert C.update_imported_weeks()==[]


def test_injury_button_refreshes_original_feeds_then_imports_and_compares(tmp_path,monkeypatch,capsys):
    from lab import fpds_drop as D,live
    (tmp_path/'injury-reports.csv').write_text('not read; all actions mocked')
    order=[]
    monkeypatch.setattr(D.subprocess,'check_output',lambda *a,**kw:'codex/projections-20261019')
    monkeypatch.setattr(D,'target_week',lambda w:7)
    monkeypatch.setattr(D,'workflow_lock',nullcontext)
    monkeypatch.setattr(D,'drop_folder',lambda w:tmp_path)
    monkeypatch.setattr(live,'refresh_live',lambda **kw:order.append('original feeds') or {'failed':{}})
    monkeypatch.setattr(live,'record_live_refresh',lambda r:order.append('record original status'))
    monkeypatch.setattr(D,'archive_injuries',lambda w:order.append('CSV import') or {'current_week_rows':2,'unmatched_rows':0})
    monkeypatch.setattr(C,'update_week',lambda *a,**kw:order.append('compare') or {'confirmed':1,'conflicts':0,'fpds_only':1})
    monkeypatch.setattr(D.sys,'argv',['fpds_drop','injuries','--week','7'])
    assert D.main()==0
    assert order==['original feeds','record original status','CSV import','compare']
    assert '1 confirmed' in capsys.readouterr().out


def test_cached_source_loading_requires_exact_week_roster_and_filters_other_weeks(tmp_path,monkeypatch):
    from lab import availability as A,live,extra_sources as X,config
    monkeypatch.setattr(config,'RAW_DIR',tmp_path)
    pd.DataFrame({'week':[7],'team':['BUF'],'full_name':['Fixture'],'gsis_id':['p']}).to_parquet(tmp_path/'roster_weekly_2026.parquet')
    pd.DataFrame({'pid':['p'],'team':['BUF'],'status':['out']}).to_parquet(tmp_path/'CONTEXT_PRIVATE.parquet')
    summary={'path':str(tmp_path),'created_at':NOW.isoformat(),'source_first_observed_at':(NOW-pd.Timedelta(hours=1)).isoformat()}
    monkeypatch.setattr(A,'load_injury_rows',lambda _:pd.DataFrame())
    monkeypatch.setattr(X,'nflcom_latest',lambda:(pd.DataFrame({'season':[2026],'week':[6],'team':['BUF'],'full_name':['Fixture'],'report_status':['Out']}),NOW))
    monkeypatch.setattr(live,'espn_full',lambda:(pd.DataFrame({'team':['BUF','BUF'],'player':['Fixture','Unmatched'],'status':['Out','Out']}),'20261022T110000Z'))
    rows,errors=C.source_rows(7,summary,GAMES)
    assert not errors and len(rows)==3 and set(rows.source)=={'fpds','espn'}
    assert rows[rows.source.eq('espn')].pid.notna().sum()==1
    assert rows[rows.source.eq('fpds')].iloc[0].available_at==summary['source_first_observed_at']


def test_comparison_revisions_append_and_do_not_modify_imported_context(tmp_path,monkeypatch):
    pointer=tmp_path/'INJURIES_W07.json'
    pointer.write_text(json.dumps({'source_sha256':'fixture-hash'}))
    original=pointer.read_bytes()
    monkeypatch.setattr(C,'source_rows',lambda *a:(pd.DataFrame([row('official_nflverse','Out'),row('fpds','Out')]),[]))
    monkeypatch.setattr(C.pd.Timestamp,'now',lambda **kw:NOW)
    a=C.update_week(7,state=tmp_path,games=GAMES)
    b=C.update_week(7,state=tmp_path,games=GAMES)
    assert a['path']!=b['path'] and a['confirmed']==1 and b['confirmed']==1
    assert pointer.read_bytes()==original and Path(a['path']).exists()
    assert json.loads((tmp_path/'LATEST_CONFIRMATION.json').read_text())['path']==b['path']


def test_summary_is_visible_without_displaying_private_source_rows(tmp_path):
    from streamlit.testing.v1 import AppTest
    (tmp_path/'LATEST_CONFIRMATION.json').write_text(json.dumps({'forecast_week':7,'created_at':NOW.isoformat(),
        'confirmed':3,'conflicts':1,'fpds_only':2,'excluded_rows':1,'policy':'Official first; secondary context only.',
        'by_team':[{'team':'BUF','players':6,'confirmed':3,'conflicts':1}],'source_errors':[],'stale_source_rows':2}))
    at=AppTest.from_string(f'from app.fpds_drop_view import render\nrender({str(tmp_path)!r})').run()
    assert not at.exception and len(at.dataframe)==1
    assert any('Injury sources disagree' in x.value for x in at.warning)
    assert list(at.dataframe[0].value.columns)==['team','players','confirmed','conflicts']


def test_supplement_failure_never_marks_original_feeds_failed(monkeypatch):
    from lab import live,availability as A,extra_sources as X,data_pipeline
    monkeypatch.setattr(data_pipeline,'current_season',lambda:2026)
    monkeypatch.setattr(live.sources,'download',lambda *a,**kw:None)
    monkeypatch.setattr(live,'fetch_scoreboard',lambda:0)
    monkeypatch.setattr(live,'fetch_transactions',lambda:0)
    monkeypatch.setattr(A,'refresh_sources',lambda *a,**kw:{})
    monkeypatch.setattr(A,'load_injury_rows',lambda *a:pd.DataFrame())
    monkeypatch.setattr(A,'depth_chart_qb1',lambda *a:({},None))
    for name in ('fetch_nflcom','fetch_weekly_rosters','fetch_sleeper'):
        monkeypatch.setattr(X,name,lambda *a,**kw:{'ok':True})
    monkeypatch.setattr(live,'espn_full',lambda:(pd.DataFrame(),None))
    monkeypatch.setattr(live,'track_changes',lambda *a:0)
    monkeypatch.setattr(C,'update_imported_weeks',Mock(side_effect=RuntimeError('synthetic supplemental error')))
    result=live.refresh_live(progress=lambda _:None)
    assert not result['failed'] and len(result['ok'])==7
    assert result['fpds_injury_confirmation_error']=='RuntimeError'
