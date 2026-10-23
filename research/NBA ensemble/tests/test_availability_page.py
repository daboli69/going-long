import pandas as pd
from nba_lab import config as C


def test_today_renders_nonempty_availability_and_source_details(tmp_path,monkeypatch):
    for name in ('DATA','CACHE','MODELS','REPORTS','ARCHIVES'):monkeypatch.setattr(C,name,tmp_path/name)
    time=pd.Timestamp.now(tz='UTC')
    C.once(C.DATA/'AVAILABILITY.json',{'created_at':time.isoformat(),'date':str(time.tz_convert('America/New_York').date()),
        'issues':[],'teams':[{'team':'ONE','released_current_season_games':1,'history_games':20,
                             'roster_retained_minutes_share':.6,'known_out_last20_minutes_share':None,'continuity_status':'available'}],
        'rows':[{'team':'ONE','player':'Fixture','status':'Out','injury_published_at':time.isoformat(),
                 'retrieved_at':time.isoformat(),'conflict':False,'verification':'current_source_entry'}],
        'reports':[{'team_id':'1','report_status':'entries_returned'}]})
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_file(str(C.ROOT/'app.py')).run(timeout=30)
    assert not at.exception
    details=next(c for c in at.checkbox if c.label=='Show report completeness / source errors')
    details.check().run(timeout=30)
    assert not at.exception and len(at.dataframe)>=3
