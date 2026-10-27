import json
import pandas as pd
from nba_lab import codex_research as CR


def prediction(game,home,away,tip,p):
    models={k:{'home_probability':p+d,'pick':home if p+d>=.5 else away} for k,d in zip(CR.VOTERS,(-.1,-.05,0,.02,.05,.1))}
    return {'game_id':'espn:'+game,'season':2027,'tipoff':tip,'home':home,'away':away,'home_probability':p,'flags':['close_to_tossup'],'models':models}


def write(directory,name,origin,predictions):
    directory.mkdir(parents=True,exist_ok=True)
    (directory/name).write_text(json.dumps({'origin':origin,'predictions':predictions,'excluded':{}}),encoding='utf-8')


def test_saved_maps_teams_dates_and_keeps_latest_revision(tmp_path,monkeypatch):
    monkeypatch.setattr(CR,'WINNERS',tmp_path)
    write(tmp_path,'predictions-1.json','2026-11-03T15:00:00+00:00',[prediction('1','GSW','NYK','2026-11-04T00:00:00Z',.6),
                                                                     prediction('2','SAS','UTA','2026-11-05T01:00:00Z',.4)])
    write(tmp_path,'predictions-2.json','2026-11-03T18:00:00+00:00',[prediction('1','GSW','NYK','2026-11-04T00:00:00Z',.7)])
    frame=CR.saved('2026-11-03')  # 00:00 UTC on Nov 4 is the evening of Nov 3 in Eastern time
    assert list(frame.game_id)==['1'] and frame.iloc[0].home=='GS' and frame.iloc[0].away=='NY'
    assert frame.iloc[0].p_home==.7 and set(CR.VOTERS)<=set(frame.columns)
    assert CR.saved('2026-11-01').empty


def test_verify_reports_missing_package(tmp_path,monkeypatch):
    monkeypatch.setattr(CR,'PACKAGE',tmp_path/'absent')
    assert CR.verify()=={'installed':False,'problems':['package folder missing']}
