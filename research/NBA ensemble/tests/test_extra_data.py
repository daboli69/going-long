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
