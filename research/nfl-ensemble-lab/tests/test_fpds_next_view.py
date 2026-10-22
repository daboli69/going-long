import json
from streamlit.testing.v1 import AppTest


def test_target_simulation_view_empty(tmp_path):
    app=AppTest.from_string(f'from app.fpds_next_view import render\nrender({str(tmp_path)!r})').run()
    assert not app.exception


def test_target_simulation_view_aggregate_only(tmp_path):
    folder=tmp_path/'20261022T000000Z';folder.mkdir()
    (folder/'STATUS.json').write_text(json.dumps({'phase':'complete'}))
    row={'family':'role','stat':'rec','metric':'point','n':20,'games':10,'control_loss':1.,'new_loss':.99,
         'relative_reduction':.01,'corrected_ci95':[-.02,.02],'nomination':False}
    (folder/'SUMMARY.json').write_text(json.dumps({'rows':[row],'limitations':'Shadow only','trials':{}}))
    app=AppTest.from_string(f'from app.fpds_next_view import render\nrender({str(tmp_path)!r})').run()
    assert not app.exception and len(app.dataframe)==1
    assert len(app.button)==0
    app.selectbox[0].select('role').run()
    assert not app.exception
