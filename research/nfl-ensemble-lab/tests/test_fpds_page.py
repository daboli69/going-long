"""Synthetic aggregate JSONs only. No source CSVs, fitting or live network."""
import json
from streamlit.testing.v1 import AppTest


def app(path):
    return AppTest.from_string(f'from app.fpds_page import render\nrender({str(path)!r})').run(timeout=30)


def test_missing_saved_reports_has_message(tmp_path,monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session,'request',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('Network not allowed')))
    at=app(tmp_path)
    assert not at.exception and at.warning and at.info
    assert 'No saved FPDS audit' in at.info[0].value
    assert not at.button


def test_aggregate_page_coverage_and_filters(tmp_path,monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session,'request',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('Network not allowed')))
    audit={'tables':[{'table':'synthetic_role','valid_rows':100,'usable_entity_week_rows':98,'unmatched_rows':2,'coverage':{'2021':[1,2]},'possible_export_cap':True}]}
    rows=[]
    for family,stat in [('H1','rec'),('H2','rush_yds')]:
        rows.append({'configuration':{'family':family,'stat':stat,'arm':'add','group':'synthetic','model':'linear'},
                     'n':100,'games':20,'control_loss':2.,'new_loss':1.9,'delta':-.1,'corrected_ci95':[-.2,.1],'seasons_agreeing':2,'discovery_gate':False})
    (tmp_path/'FPDS_A6_AUDIT.json').write_text(json.dumps(audit))
    (tmp_path/'FPDS_A6_RESULTS.json').write_text(json.dumps({'trial_count':2,'trial_ceiling':269,'failed_configurations':0,'accepted_shadow_count':0,'discovery':rows}))
    at=app(tmp_path)
    assert not at.exception and len(at.tabs)==3 and len(at.dataframe)==2
    next(x for x in at.selectbox if x.label=='Family').select('H2').run()
    assert not at.exception and at.dataframe[-1].value.Family.tolist()==['H2']
    next(x for x in at.selectbox if x.label=='Split').select('Frozen confirmation (2025)').run()
    assert not at.exception and any('No completed rows' in x.value for x in at.info)
    assert not at.button
