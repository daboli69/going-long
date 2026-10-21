"""AppTest controls use synthetic schedules and mocked launches only."""
from streamlit.testing.v1 import AppTest


def test_manual_controls_do_not_launch_until_clicked(monkeypatch):
    from app import fpds_controls as C
    calls=[]
    monkeypatch.setattr(C,'weeks',lambda:[7,8])
    monkeypatch.setattr(C.jobs,'active',lambda:None)
    monkeypatch.setattr(C.jobs,'list_jobs',lambda:[])
    monkeypatch.setattr(C.jobs,'launch',lambda action,**kw:calls.append((action,kw)) or 'a'*32)
    at=AppTest.from_string('from app.fpds_controls import render\nrender()').run()
    assert not at.exception and not calls
    next(x for x in at.selectbox if x.label=='Forecast week').select(8).run()
    next(x for x in at.button if x.label=='Run projections').click().run()
    assert not at.exception and calls[0][0]=='project' and calls[0][1]['week']==8 and calls[0][1]['scope']=='all'
    assert calls[0][1]['sims']==10000


def test_active_job_disables_new_launches(monkeypatch):
    from app import fpds_controls as C
    monkeypatch.setattr(C,'weeks',lambda:[7])
    monkeypatch.setattr(C.jobs,'active',lambda:{'job':'a'*32,'pid':1})
    monkeypatch.setattr(C.jobs,'list_jobs',lambda:[])
    at=AppTest.from_string('from app.fpds_controls import render\nrender()').run()
    assert not at.exception
    assert all(x.disabled for x in at.button if x.label in ('Run projections','Compare FPDS','Prepare data'))


def test_compare_button_has_fixed_development_scope(monkeypatch):
    from app import fpds_controls as C
    calls=[]
    monkeypatch.setattr(C,'weeks',lambda:[7])
    monkeypatch.setattr(C.jobs,'active',lambda:None)
    monkeypatch.setattr(C.jobs,'list_jobs',lambda:[])
    monkeypatch.setattr(C.jobs,'launch',lambda action,**kw:calls.append(action) or 'b'*32)
    at=AppTest.from_string('from app.fpds_controls import render\nrender()').run()
    next(x for x in at.button if x.label=='Compare FPDS').click().run()
    assert not at.exception and calls==['compare']
    assert not any('season' in x.label.lower() for x in at.selectbox)
