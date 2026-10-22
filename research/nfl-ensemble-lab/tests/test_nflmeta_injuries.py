"""Offline contract fixtures; never read a real credential or call the API."""
from contextlib import nullcontext
from unittest.mock import Mock
import json
import pandas as pd
import pytest
from lab import nflmeta_injuries as N

NOW=pd.Timestamp('2026-10-22T20:00Z')


def api(plan='free', rows=None, remaining=1000):
    usage=Mock(status_code=200)
    usage.json.return_value={'data':{'billing_plan':plan,'quota_remaining':100,'row_quota_remaining':remaining}}
    response=Mock(status_code=200)
    response.json.return_value={'data':rows if rows is not None else [
        {'season_year':2026,'week':7,'team_abbr':'CHI','display_name':'Synthetic Player',
         'report_status':'Out','source_observed_at':'2026-10-22T19:00Z'}]}
    client=Mock()
    client.get.side_effect=[usage,response]
    return client


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setattr(N,'_key',lambda:'synthetic-test-credential')


def test_missing_configuration_never_requests(tmp_path,monkeypatch):
    monkeypatch.setattr(N,'_key',lambda:'')
    client=Mock()
    assert N.refresh(2026,7,root=tmp_path,now=NOW,client=client)['state']=='not_configured'
    client.get.assert_not_called()


@pytest.mark.parametrize('plan,remaining,state',[('pro',1000,'blocked_nonfree_plan'),('free',0,'quota_insufficient')])
def test_cost_guards_stop_before_injuries(tmp_path,plan,remaining,state):
    client=api(plan,remaining=remaining)
    assert N.refresh(2026,7,root=tmp_path,now=NOW,client=client)['state']==state
    assert client.get.call_count==1 and not list(tmp_path.iterdir())


def test_archive_cache_exact_ids_and_no_secret(tmp_path):
    client=api()
    result=N.refresh(2026,7,root=tmp_path,now=NOW,client=client)
    assert result['state']=='archived'
    assert N.refresh(2026,7,root=tmp_path,now=NOW,client=client)['state']=='cached'
    assert client.get.call_count==2
    text=next(tmp_path.iterdir()).read_text()
    assert 'synthetic-test-credential' not in text and not json.loads(text)['model_input']
    from lab.props.lines import normalized_name
    rows=N.source_rows(2026,7,{('CHI',normalized_name('Synthetic Player')):'gsis-fixture'},root=tmp_path,asof=NOW+pd.Timedelta(minutes=1))
    assert len(rows)==1 and rows[0]['pid']=='gsis-fixture' and rows[0]['status']=='out'
    assert N.source_rows(2026,7,{},root=tmp_path,asof=NOW+pd.Timedelta(minutes=1))[0]['pid'] is None
    assert not N.source_rows(2026,7,{},root=tmp_path,asof=NOW-pd.Timedelta(minutes=1))
    assert not N.source_rows(2026,7,{},root=tmp_path,asof=NOW+pd.Timedelta(days=2))


def test_exceptions_cannot_echo_credentials(tmp_path,capsys):
    client=Mock()
    client.get.side_effect=RuntimeError('synthetic-test-credential')
    assert N.refresh(2026,7,root=tmp_path,now=NOW,client=client)=={'state':'request_or_archive_failed'}
    assert not capsys.readouterr().out and not list(tmp_path.iterdir())


def test_wrong_week_refused_and_no_redirects(tmp_path):
    client=api(rows=[{'season_year':2026,'week':8}])
    assert N.refresh(2026,7,root=tmp_path,now=NOW,client=client)['state']=='invalid_schema_or_wrong_week'
    assert all(not call.kwargs['allow_redirects'] for call in client.get.call_args_list)


def test_current_observation_required_not_just_fresh_download(tmp_path):
    client=api(rows=[{'season_year':2026,'week':7,'team_abbr':'CHI','display_name':'Synthetic Player',
                     'report_status':'Out','source_observed_at':'2026-10-20T19:00Z'}])
    N.refresh(2026,7,root=tmp_path,now=NOW,client=client)
    assert not N.source_rows(2026,7,{},root=tmp_path,asof=NOW+pd.Timedelta(minutes=1))


def test_no_csv_button_keeps_original_feeds_and_uses_fallback(tmp_path,monkeypatch,capsys):
    from lab import fpds_drop as D,live,fpds_injury_confirmation as C
    order=[]
    monkeypatch.setattr(D.subprocess,'check_output',lambda *a,**kw:'codex/projections-20261019')
    monkeypatch.setattr(D,'target_week',lambda w:7)
    monkeypatch.setattr(D,'workflow_lock',nullcontext)
    monkeypatch.setattr(D,'drop_folder',lambda w:tmp_path)
    monkeypatch.setattr(live,'refresh_live',lambda **kw:order.append('original') or {'failed':{}})
    monkeypatch.setattr(live,'record_live_refresh',lambda r:None)
    monkeypatch.setattr(N,'refresh',lambda *a:order.append('fallback') or {'state':'cached'})
    def compare(*a,**kw):
        assert kw['use_csv'] is False
        order.append('compare')
        return {'confirmed':0,'conflicts':0,'fpds_only':0}
    monkeypatch.setattr(C,'update_week',compare)
    monkeypatch.setattr(D.sys,'argv',['fpds_drop','injuries','--week','7'])
    assert D.main()==0 and order==['original','fallback','compare']
    assert 'No injury CSV' in capsys.readouterr().out
