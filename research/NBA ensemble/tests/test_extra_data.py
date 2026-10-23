import pandas as pd
import pytest
from test_nba import games
from nba_lab.extra_data import injury_index,player_boxes
from nba_lab.sources import ending_season


def test_injury_index_ignores_future_reports_and_does_not_parse_statuses():
    prefix='https://ak-static.cms.nba.com/referee/injury/'
    html=''.join(f'<a href="{prefix}Injury-Report_2026-10-23_{hour}_00PM.pdf">report</a>' for hour in ('01','03'))
    report=injury_index(html,'2026-10-23T18:00Z')
    assert report['links']==1 and report['latest_report']['report_time']=='2026-10-23T17:00:00+00:00'
    assert report['age_hours']==1 and not report['model_input']
    with pytest.raises(ValueError,match='No timestamped'):injury_index('<html>Unavailable</html>')


def test_player_identity_coverage_and_duplicate_quarantine():
    g=games(1)
    row={'game_id':'0','season':2024,'season_type':2,'athlete_id':'123','team_id':'1','minutes':30,'points':12,'rebounds':5,'assists':3}
    d=pd.DataFrame([row,row|{'athlete_id':'bad'},row|{'athlete_id':'456','team_id':'unknown'}])
    out,report=player_boxes(d,g)
    assert len(out)==1 and report['unmatched_id_rows']==1 and report['wrong_team_rows']==1
    assert out.available_at.iloc[0]==g.tipoff.iloc[0]+pd.Timedelta(hours=24)
    with pytest.raises(ValueError,match='Conflicting'):player_boxes(pd.DataFrame([row,row|{'points':99}]),g)


def test_ending_season_does_not_freeze_current_year_after_january():
    assert ending_season('2026-10-23')==2027
    assert ending_season('2027-01-10')==2027
    assert ending_season('2027-07-10')==2028


def test_float_encoded_integer_ids_are_normalized_without_rounding():
    row={'game_id':0.,'season':2024,'season_type':2,'athlete_id':123.,'team_id':1.,'minutes':30,'points':12,'rebounds':5,'assists':3}
    out,meta=player_boxes(pd.DataFrame([row,row|{'athlete_id':123.5}]),games(1))
    assert out.athlete_id.tolist()==['123'] and meta['unmatched_id_rows']==1


def test_lightweight_official_index_refresh_preserves_actual_retrieval_time(tmp_path,monkeypatch):
    from nba_lab import extra_data as E
    from nba_lab.config import atomic
    monkeypatch.setattr(E,'DATA',tmp_path)
    html=tmp_path/'fixture.html';html.write_text('<a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-10-23_01_00PM.pdf">report</a>')
    monkeypatch.setattr(E,'fetch',lambda *a,**k:html)
    atomic(tmp_path/'SOURCES.json',{'official_injury_index_2027':{'checked_at':'2026-10-23T18:00:00+00:00'}})
    result=E.refresh_injury_index(2027)
    assert result['retrieved_at']=='2026-10-23T18:00:00+00:00' and not result['model_input']
