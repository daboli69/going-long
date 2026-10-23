from types import SimpleNamespace
import json
import pandas as pd
import pytest
from nba_lab import availability as A


TIME=pd.Timestamp('2026-10-23T18:00Z')


def game():return SimpleNamespace(game_id='123',tipoff=pd.Timestamp('2026-10-23T20:00Z'),home_id='1',away_id='2',home='H',away='A',season=2027)


def injury(status='Out',date='2026-10-22T12:00Z',id='100'):
    return {'status':status,'date':date,'athlete':{'id':id,'displayName':'Player'},'secret_unselected':'discard'}


def test_summary_exact_ids_and_empty_unknown():
    rows,reports=A.parse_summary({'injuries':[{'team':{'id':'1'},'injuries':[injury(),injury(id='bad')]}],
                                 'odds':[{'do_not_save':True}]},game(),TIME)
    assert len(rows)==1 and rows[0]['player_id']=='100'
    assert reports[1]['report_status']=='unknown_no_entries'
    assert 'odds' not in str(rows) and 'secret_unselected' not in str(rows)


def test_future_injury_is_unknown_not_current_verified():
    row=A.injury_row(injury(date='2026-10-24T12:00Z'),{'id':'100'},game(),'1',TIME,'fixture')
    assert row['status']=='Unknown' and row['future_dated']
    assert row['verification']=='future_timestamp'


def test_roster_filters_fields_and_refuses_wrong_team_duplicates_future():
    source={'team':{'id':'1'},'timestamp':TIME.isoformat(),'athletes':[{'id':'100','displayName':'P','salary':999,'injuries':[]}], 'odds':'discard'}
    result=A.parse_roster(source,'1',TIME)
    assert set(result['athletes'][0])=={'id','displayName','injuries'}
    with pytest.raises(ValueError,match='team ID'):A.parse_roster(source,'2',TIME)
    with pytest.raises(ValueError,match='duplicate'):A.parse_roster(source|{'athletes':source['athletes']*2},'1',TIME)
    with pytest.raises(ValueError,match='Future'):A.parse_roster(source|{'timestamp':'2026-10-24T00:00Z'},'1',TIME)


def test_conflicts_are_unknown_without_guessed_name_join():
    one=A.injury_row(injury(),{'id':'100','displayName':'Same Name'},game(),'1',TIME,'summary')
    two=one|{'status':'Available','source':'roster'}
    three=one|{'player_id':'200'}
    out=A.reconcile([one,two,three])
    assert len(out)==2 and out[0]['status']=='Unknown' and out[0]['conflict']
    assert out[1]['player_id']=='200'


def test_continuity_uses_released_rows_positive_minutes_and_exact_ids():
    rows=[]
    for player,minutes in [('100',30),('200',10),('300',-5),('400',None)]:
        rows.append({'team_id':'1','athlete_id':player,'minutes':minutes,'game_id':'prior','tipoff':TIME-pd.Timedelta(days=3),
                     'available_at':TIME-pd.Timedelta(days=2),'season':2027})
    rows.append(rows[0]|{'minutes':100,'game_id':'future','available_at':TIME+pd.Timedelta(hours=1)})
    result=A.continuity(pd.DataFrame(rows),'1',{'100'},TIME,2027,{'200'})
    assert result['last20_minutes']==40 and result['roster_retained_minutes_share']==.75
    assert result['released_current_season_games']==1 and result['history_games']==1
    assert result['known_out_last20_minutes_share']==.25
    unknown=A.continuity(pd.DataFrame(rows),'1',None,TIME,2027)
    assert unknown['roster_retained_minutes_share'] is None and unknown['known_out_last20_minutes_share'] is None


def test_collect_skips_started_games_and_archives_only_selected(tmp_path,monkeypatch):
    cache=tmp_path/'cache';cache.mkdir()
    monkeypatch.setattr(A,'CACHE',cache);monkeypatch.setattr(A,'DATA',tmp_path)
    monkeypatch.setattr(A,'RAW',tmp_path/'raw');monkeypatch.setattr(A,'now',lambda:TIME.isoformat())
    games=pd.DataFrame([game().__dict__|{'completed':False},game().__dict__|{'game_id':'started','tipoff':TIME-pd.Timedelta(minutes=1),'completed':False}])
    games.to_parquet(cache/'games.parquet',index=False)
    calls=[]
    def get(path,session):
        calls.append(path)
        if path.startswith('summary'):return {'injuries':[],'odds':{'forbidden':'do not archive'}}
        team=path.split('/')[1]
        return {'team':{'id':team},'timestamp':TIME.isoformat(),'athletes':[{'id':team+'00','displayName':'P','injuries':[]}], 'other':'discard'}
    monkeypatch.setattr(A,'_get',get)
    result=A.collect('2026-10-23')
    assert result['games']==1 and all('started' not in call for call in calls)
    assert not result['rows'] and not result['lineup_verified']
    snapshot=json.loads(open(result['snapshot_path']).read())
    assert 'odds' not in str(snapshot) and 'forbidden' not in str(snapshot)
    assert len(result['reports'])==2 and all(r['report_status']=='unknown_no_entries' for r in result['reports'])
    assert pd.read_csv(cache/'availability.csv').empty
    assert len(result['teams'])==2
    assert all(r['continuity_status']=='player_history_unavailable' and r['roster_retained_minutes_share'] is None for r in result['teams'])
    second=A.collect('2026-10-23')
    assert result['snapshot_path']!=second['snapshot_path']


def test_collect_source_errors_remain_visible(tmp_path,monkeypatch):
    cache=tmp_path/'cache';cache.mkdir()
    monkeypatch.setattr(A,'CACHE',cache);monkeypatch.setattr(A,'DATA',tmp_path);monkeypatch.setattr(A,'RAW',tmp_path/'raw')
    monkeypatch.setattr(A,'now',lambda:TIME.isoformat())
    pd.DataFrame([game().__dict__|{'completed':False}]).to_parquet(cache/'games.parquet',index=False)
    def fail(*args):raise TimeoutError('fixture')
    monkeypatch.setattr(A,'_get',fail)
    result=A.collect('2026-10-23')
    assert len(result['issues'])==3 and result['rows']==[]
    assert len(result['reports'])==2 and all(r['report_status']=='source_unavailable' for r in result['reports'])
    assert len(result['teams'])==2 and all(r['continuity_status']=='roster_unavailable' for r in result['teams'])
