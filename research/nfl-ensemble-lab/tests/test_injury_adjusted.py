"""Synthetic future-game scenarios. No live feeds or historical evaluation."""
from types import SimpleNamespace
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from lab.props import injury_adjusted as I,players as P

NOW=pd.Timestamp('2026-10-22T20:00Z')
GAME=SimpleNamespace(game_id='2026_07_NE_CHI',season=2026,week=7,home_team='CHI',away_team='NE',
                     gameday='2026-10-22',gametime='20:15',home_score=np.nan,away_score=np.nan)


def evidence(status='out',conflict=False):
    return pd.DataFrame([{'game_id':GAME.game_id,'team':t,'pid':pid,'effective_status':s,'conflict':conflict,
                         'selected_source':'official_nflcom','sources':json.dumps({'official_nflcom':
                        {'status':s,'available_at':(NOW-pd.Timedelta(minutes=10)).isoformat()},**({'espn':
                        {'status':'active','available_at':(NOW-pd.Timedelta(minutes=5)).isoformat()}} if conflict else {})})}
                        for t,pid,s in [('CHI','missing',status),('NE','other','questionable')]])


def save_context(tmp_path,rows,created=None):
    directory=tmp_path/'immutable';directory.mkdir()
    rows.to_parquet(directory/'CONFIRMATION_PRIVATE.parquet',index=False)
    pointer={'created_at':(created or NOW-pd.Timedelta(minutes=1)).isoformat(),'path':str(directory)}
    (tmp_path/'CONFIRMATION_W07.json').write_text(json.dumps(pointer))


def test_unavailable_removed_and_existing_redistribution_conserves_shares():
    av=pd.DataFrame({'pid':['qb','missing','starter','backup'],'position':['QB','RB','RB','RB']})
    adjusted,_=I.adjuster(evidence())(GAME,'CHI',av,'qb')
    assert 'missing' not in set(adjusted.pid)
    a=pd.DataFrame({'cur_team':['CHI']*4,'last_team':['CHI']*4,'position':av.position.tolist(),
                    'tshare':[0,.2,.3,.1],'cshare':[0,.6,.3,.1]},index=av.pid)
    original=P.team_inputs(a,av,'CHI',pd.DataFrame(),pd.DataFrame(),7,'qb')
    updated=P.team_inputs(a,adjusted,'CHI',pd.DataFrame(),pd.DataFrame(),7,'qb')
    assert updated['rush'].loc['starter','share']>original['rush'].loc['starter','share']
    assert updated['rush']['share'].sum()==pytest.approx(1)
    assert updated['recv']['share'].sum()==pytest.approx(1)


@pytest.mark.parametrize('status',['questionable','doubtful','unknown'])
def test_uncertain_not_silently_removed(status):
    av=pd.DataFrame({'pid':['qb','missing','wr'],'position':['QB','RB','WR']})
    result,_=I.adjuster(evidence(status))(GAME,'CHI',av,'qb')
    assert 'missing' in set(result.pid)


def test_missing_qb_blocks_without_guess():
    av=pd.DataFrame({'pid':['missing','wr'],'position':['RB','WR']})
    with pytest.raises(ValueError,match='QB'):I.adjuster(evidence())(GAME,'CHI',av,'qb')


def test_frozen_context_and_conflict_stale_identity_gates(tmp_path):
    save_context(tmp_path,evidence())
    rows,meta=I.context(GAME,NOW,state=tmp_path)
    assert len(rows)==2 and len(meta['comparison_sha256'])==64
    with pytest.raises(ValueError,match='24 hours'):I.context(GAME,NOW+pd.Timedelta(days=2),state=tmp_path)
    path=tmp_path/'immutable'/'CONFIRMATION_PRIVATE.parquet'
    evidence(conflict=True).to_parquet(path,index=False)
    with pytest.raises(ValueError,match='conflict'):I.context(GAME,NOW,state=tmp_path)
    evidence().iloc[:1].to_parquet(path,index=False)
    with pytest.raises(ValueError,match='NE'):I.context(GAME,NOW,state=tmp_path)


def test_postkickoff_and_unfinished_prior_week_refused(monkeypatch):
    monkeypatch.setattr(I.W,'load_games',lambda:pd.DataFrame([vars(GAME)]))
    with pytest.raises(ValueError,match='started'):I.game_row(GAME.game_id,NOW+pd.Timedelta(days=1))
    prior=vars(GAME)|{'game_id':'prior','week':6,'gameday':'2026-10-19'}
    monkeypatch.setattr(I.W,'load_games',lambda:pd.DataFrame([vars(GAME),prior]))
    with pytest.raises(ValueError,match='complete'):I.game_row(GAME.game_id,NOW)


def test_out_and_ir_are_compatible_unavailability_but_conflict_flag_retained(tmp_path):
    rows=evidence();rows.loc[0,'conflict']=True
    sources=json.loads(rows.loc[0,'sources']);sources['espn']={'status':'ir','available_at':(NOW-pd.Timedelta(minutes=5)).isoformat()}
    rows.loc[0,'sources']=json.dumps(sources)
    save_context(tmp_path,rows)
    admitted,_=I.context(GAME,NOW,state=tmp_path)
    assert admitted.loc[0,'conflict'] and admitted.loc[0,'effective_status']=='out'


def test_run_writes_new_revision_and_leaves_original_bytes(tmp_path,monkeypatch):
    original=tmp_path/'original.parquet';original.write_bytes(b'immutable original')
    job=tmp_path/'job';job.mkdir()
    (job/'REQUEST.json').write_text(json.dumps({'game_id':GAME.game_id,'created_at':pd.Timestamp.now(tz='UTC').isoformat(),
                                              'comparison_sha256':'fixture'}))
    evidence().to_parquet(job/'AVAILABILITY.parquet',index=False)
    pd.DataFrame({'week':[7],'gsis_id':['starter'],'full_name':['Synthetic Runner'],'position':['RB']}).to_parquet(job/'ROSTER.parquet',index=False)
    monkeypatch.setattr(I,'game_row',lambda *a:GAME)
    monkeypatch.setattr(I.W,'kickoff',lambda *a:pd.Timestamp.now(tz='UTC')+pd.Timedelta(hours=1))
    def archive(**kw):
        assert kw['only']==[GAME.game_id] and kw['n_sims']==10000
        frame=pd.DataFrame({'pid':['qb','missing','starter'],'position':['QB','RB','RB']})
        adjusted,_=kw['availability_adjuster'](GAME,'CHI',frame,'qb')
        assert 'missing' not in set(adjusted.pid)
        inputs={'rush':pd.DataFrame({'share':[1.]},index=['starter']),
                'recv':pd.DataFrame({'share':[1.]},index=['starter'])}
        history=pd.DataFrame({'games_total':[6]},index=['starter'])
        kw['input_observer'](GAME,[('CHI','qb',inputs)],history)
        directory=kw['out']/'2026_w07';directory.mkdir(parents=True)
        pd.DataFrame([{'team':'CHI','pid':'starter','name':'Synthetic Runner','stat':'rush_yds','version':'v1',
                       'mean':60,'q10':10,'q50':55,'q90':100}]).to_parquet(directory/(GAME.game_id+'.parquet'))
        return {'archived':[GAME.game_id]}
    monkeypatch.setattr(I.W,'archive',archive)
    assert I.run(job)==0
    assert I.read(job/'STATUS.json')['state']=='complete'
    assert original.read_bytes()==b'immutable original' and (job/'PROJECTIONS.csv').exists()
    assert I.read(job/'RESULT.json')['workload_path']
    assert pd.read_csv(job/'PROJECTIONS.csv').carry_share.iloc[0]==1
    saved=(job/'RESULT.json').read_bytes(),(job/'PROJECTIONS.csv').read_bytes()
    assert I.run(job)==0
    assert saved==((job/'RESULT.json').read_bytes(),(job/'PROJECTIONS.csv').read_bytes())


def test_launch_freezes_base_roster_and_injury_files(tmp_path,monkeypatch):
    raw=tmp_path/'raw';raw.mkdir()
    (raw/'roster_weekly_2026.parquet').write_bytes(b'synthetic roster snapshot')
    (raw/'injuries_2026.parquet').write_bytes(b'synthetic injury snapshot')
    monkeypatch.setattr(I.W,'RAW_DIR',raw)
    monkeypatch.setattr(I,'game_row',lambda *a:GAME)
    monkeypatch.setattr(I,'context',lambda *a:(evidence(),{'comparison_sha256':'fixture'}))
    monkeypatch.setattr(I.subprocess,'Popen',lambda *a,**kw:SimpleNamespace(pid=123))
    monkeypatch.setattr(I.psutil,'Process',lambda *a:SimpleNamespace(create_time=lambda:12345))
    request=I.launch(GAME.game_id,root=tmp_path/'jobs')
    job=Path(request['path'])
    (raw/'roster_weekly_2026.parquet').write_bytes(b'later update')
    assert (job/'ROSTER.parquet').read_bytes()==b'synthetic roster snapshot'
    assert (job/'INJURIES.parquet').read_bytes()==b'synthetic injury snapshot'
    assert len(request['availability_input_hashes']['ROSTER.parquet'])==64


def test_page_has_manual_controls_and_empty_message(tmp_path):
    from streamlit.testing.v1 import AppTest
    at=AppTest.from_string(f'from app.props_injury_view import render\nrender({str(tmp_path)!r})').run()
    assert not at.exception
    assert any('No injury-adjusted simulation' in x.value for x in at.info)
    assert any(x.label=='Refresh simulation status' for x in at.button)


def test_reporting_includes_modeled_backup_below_original_cutoff():
    inputs={'rush':pd.DataFrame({'share':[.7,.108,.192]},index=['starter','backup','qb']),
            'recv':pd.DataFrame({'share':[1.]},index=['starter'])}
    rows=I.participants([('CHI','qb',inputs)],pd.DataFrame())
    assert ('CHI','backup','rush_yds') in rows
    assert sum(r==('CHI','qb','pass_yds') for r in rows)==1
    from lab.props.game import eligible
    assert ('CHI','backup','rush_yds') not in eligible([('CHI','qb',inputs)],pd.DataFrame(index=['starter','backup','qb']))


def test_main_game_table_uses_new_revision_and_collapses_original(tmp_path):
    from streamlit.testing.v1 import AppTest
    job=tmp_path/'revision';job.mkdir()
    table=pd.DataFrame({'Team':['CHI'],'Player':['Synthetic Backup'],'Stat':['Rushing yards'],'v1 median':[12.]})
    table.to_csv(job/'PROJECTIONS.csv',index=False)
    pd.DataFrame({'team':['CHI'],'pid':['backup'],'player':['Synthetic Backup'],'position':['RB'],
                  'carry_share':[.108],'target_share':[.02],'limited_history':[False]}).to_csv(job/'WORKLOAD.csv',index=False)
    result={'state':'complete','game_id':GAME.game_id,'created_at':NOW.isoformat(),'warning':'shadow scenario',
            'projection_path':str(job/'PROJECTIONS.csv'),'workload_path':str(job/'WORKLOAD.csv')}
    (job/'RESULT.json').write_text(json.dumps(result))
    old=[{'team':'CHI','pid':'missing','name':'Synthetic Out Runner','stat':'rush_yds','version':'v1',
          'mean':40,'q10':10,'q50':35,'q90':80}]
    at=AppTest.from_string(f'import pandas as pd\nfrom app.props_injury_view import render_game\nrender_game({GAME.game_id!r},pd.DataFrame({old!r}),root={str(tmp_path)!r})').run()
    assert not at.exception
    shown=[x.value for x in at.dataframe if 'Player' in x.value.columns]
    assert 'Synthetic Backup' in shown[0].Player.tolist()
    assert 'Synthetic Out Runner' not in shown[0].Player.tolist()
    assert at.dataframe[0].value.carry_share.iloc[0]==pytest.approx(.108)
    assert any('Original saved forecast' in x.label for x in at.expander)


def test_live_reload_recovers_backend_without_new_helper(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    # Reproduce an already-open server: page code updated, backend module cached.
    monkeypatch.delattr(I,'latest_completed')
    job=tmp_path/'revision';job.mkdir()
    pd.DataFrame({'Team':['CHI'],'Player':['Synthetic Backup'],'Stat':['Rushing yards'],'v1 median':[10]}).to_csv(job/'PROJECTIONS.csv',index=False)
    (job/'RESULT.json').write_text(json.dumps({'state':'complete','game_id':GAME.game_id,
        'created_at':NOW.isoformat(),'warning':'shadow copy','projection_path':str(job/'PROJECTIONS.csv')}))
    old=[{'team':'CHI','pid':'out','name':'Synthetic Out','stat':'rush_yds','version':'v1',
          'mean':40,'q10':10,'q50':35,'q90':80}]
    at=AppTest.from_string(f'import pandas as pd\nfrom app.props_injury_view import render_game\nrender_game({GAME.game_id!r},pd.DataFrame({old!r}),root={str(tmp_path)!r})').run()
    assert not at.exception and callable(I.latest_completed)
    assert at.dataframe[0].value.Player.tolist()==['Synthetic Backup']
