"""Synthetic fixtures only: never load subscription CSVs in tests."""
import csv
import json
from pathlib import Path
import pandas as pd
import numpy as np
from lab import fpds_ingest as F


def fixture_source(tmp_path,rows=None):
    source=tmp_path/'Inbox';source.mkdir()
    path=source/'receivingAdvancedExport.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['Player Details','','','','','','Receiving','',''])
        w.writerow(['Name','Team','POS','Season','Week','G','RTE','RTE %','YPRR'])
        w.writerows(rows or [['Test Alpha','NE','WR',2021,1,1,10,'50%',2],['Test Alpha','NE','WR',2021,2,1,20,'75%',3]])
    return source,path


def players():
    return pd.DataFrame([dict(gsis_id='00-test',display_name='Test Alpha',first_name='Test',last_name='Alpha')])


def games():
    return pd.DataFrame([dict(season=2021,week=w,game_id=f'2021_{w:02d}_NE_NYJ',game_type='REG',home_team='NE',away_team='NYJ',kickoff_utc=pd.Timestamp('2021-09-01',tz='UTC')+pd.Timedelta(days=7*w)) for w in (1,2,3)])


def test_copy_idempotent_private_and_metadata_only(tmp_path):
    source,path=fixture_source(tmp_path);original=path.read_bytes();mtime=path.stat().st_mtime_ns
    report=tmp_path/'coverage.md'
    a=F.run(source,tmp_path/'raw',tmp_path/'cache',players(),games(),report)
    b=F.run(source,tmp_path/'raw',tmp_path/'cache',players(),games(),report)
    assert a['revision']==b['revision']
    assert path.read_bytes()==original and path.stat().st_mtime_ns==mtime
    copied=tmp_path/'raw/2021/receiving_advanced.csv'
    assert copied.read_bytes()==original
    assert len(list((tmp_path/'cache/imports').iterdir()))==1
    text=report.read_text()
    assert 'RTE %' in text and 'Test Alpha' not in text and '00-test' not in text
    cache=pd.read_parquet(Path(a['directory'])/'receiving_advanced.parquet')
    assert cache['fp_receiving_advanced__receiving__rte_pct'].tolist()==[.5,.625]


def test_asof_excludes_current_future_and_unobserved(tmp_path):
    source,path=fixture_source(tmp_path)
    a=F.run(source,tmp_path/'raw',tmp_path/'cache',players(),games())
    obs=pd.read_parquet(Path(a['directory'])/'receiving_advanced.parquet')
    target=pd.DataFrame([dict(season=2021,week=2,pid='00-test',team='NE',game_id='target',kickoff_utc=pd.Timestamp('2021-09-15',tz='UTC'))])
    before=F.asof_features(target,{'receiving_advanced':obs})
    col='fp_receiving_advanced__receiving__rte'
    changed=obs.copy();changed.loc[changed.source_week.eq(2),col]=999999
    after=F.asof_features(target,{'receiving_advanced':changed})
    assert before[col].iloc[0]==after[col].iloc[0]==10
    strict=F.asof_features(target,{'receiving_advanced':obs},strict_observation=True)
    assert strict[col].isna().all()
    early=target.copy();early.kickoff_utc=pd.Timestamp('2021-09-08T12:00Z')
    assert F.asof_features(early,{'receiving_advanced':obs})[col].isna().all()


def test_ambiguous_names_and_teams_never_guessed(tmp_path):
    source,path=fixture_source(tmp_path,[['Test Alpha','NE','WR',2021,1,1,10,'50%',2],['Unknown Source','BAD','WR',2021,1,1,10,'50%',2]])
    p=pd.concat([players(),players().assign(gsis_id='00-other')],ignore_index=True)
    d,m=F.parse(path);m['imported_at']='2026-10-20T00:00Z'
    normalized,unmatched=F.normalize(d,m,F.player_map(p),set(p.gsis_id))
    assert normalized.empty and len(unmatched)==2


def test_conflicting_duplicates_excluded(tmp_path):
    source,path=fixture_source(tmp_path,[['Test Alpha','NE','WR',2021,1,1,10,'50%',2],['Test Alpha','NE','WR',2021,1,1,20,'50%',2]])
    d,m=F.parse(path);m['imported_at']='2026-10-20T00:00Z'
    normalized,_=F.normalize(d,m,F.player_map(players()),{'00-test'})
    cache,report=F.weekly_cache(normalized,games())
    assert cache.empty and report['conflicting_rows']==2


def test_season_summary_is_not_weekly_history(tmp_path):
    source,path=fixture_source(tmp_path)
    rows=list(csv.reader(path.open()))
    for row in rows:row.pop(4)
    with path.open('w',newline='') as f:csv.writer(f).writerows(rows)
    d,m=F.parse(path);m['imported_at']='2026-10-20T00:00Z'
    assert m['season_to_date']
    normalized,_=F.normalize(d,m,F.player_map(players()),{'00-test'})
    cache,_=F.weekly_cache(normalized,games())
    assert cache.empty


def test_duplicate_headers_preserve_group_meaning(tmp_path):
    p=tmp_path/'efficiencyExport.csv'
    with p.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Player Details','','','','','Rushing','Receiving']);w.writerow(['Name','Team','POS','Season','Week','YDS','YDS']);w.writerow(['Test Alpha','NE','WR',2021,1,1,2])
    d,m=F.parse(p)
    assert 'rushing__yds' in d and 'receiving__yds' in d
    assert F.number('25%',True)==.25 and F.number('25',True)==.25
    assert np.isnan(F.number('not numeric'))


def test_private_report_serializes_missing_period_without_raw_stdout(tmp_path,capsys):
    source,path=fixture_source(tmp_path,[['Unknown Source','NE','WR',2021,'',1,10,'50%',2]])
    result=F.run(source,tmp_path/'raw',tmp_path/'cache',players(),games())
    assert result['unmatched_rows']==1
    private=json.loads((Path(result['directory'])/'unmatched.json').read_text())
    assert private['rows'][0]['week'] is None
    assert capsys.readouterr().out==''


def test_only_verified_header_glossary_is_not_a_data_row(tmp_path):
    _,path=fixture_source(tmp_path)
    with path.open('a',newline='') as f:
        w=csv.writer(f);w.writerow([]);w.writerow(['RTE','Synthetic column definition'])
    d,m=F.parse(path)
    assert len(d)==2 and m['footer_glossary_rows']==1 and m['malformed_rows']==0
    with path.open('a',newline='') as f:csv.writer(f).writerow(['Unknown marker','not a verified header'])
    _,m=F.parse(path)
    assert m['malformed_rows']==2


def test_exact_team_code_fallback_not_nickname_guess(tmp_path):
    p=tmp_path/'runPassReportExport.csv'
    with p.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Team Details','','','','','Overall','']);w.writerow(['Name','Team Name','Season','Week','G','PASS %','RUSH %']);w.writerow(['NE','Unrecognized nickname',2021,1,1,'60%','40%'])
    d,m=F.parse(p);m['imported_at']='2026-10-20T00:00Z'
    normalized,unmatched=F.normalize(d,m,{},set())
    assert normalized.team.tolist()==['NE'] and not unmatched
    assert normalized.entity_kind.eq('team').all()


def test_changed_source_appends_without_overwriting_imports(tmp_path):
    source,path=fixture_source(tmp_path)
    a=F.run(source,tmp_path/'raw',tmp_path/'cache',players(),games())
    saved=(tmp_path/'raw/2021/receiving_advanced.csv').read_bytes()
    with path.open('a',newline='') as f:csv.writer(f).writerow(['Test Alpha','NE','WR',2021,3,1,30,'90%',4])
    b=F.run(source,tmp_path/'raw',tmp_path/'cache',players(),games())
    assert a['revision']!=b['revision']
    assert (tmp_path/'raw/2021/receiving_advanced.csv').read_bytes()==saved
    assert len(list((tmp_path/'raw/2021').glob('receiving_advanced*.csv')))==2
