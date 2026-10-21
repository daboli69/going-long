"""Offline Amendment 6 safety/availability regressions; entirely synthetic rows."""
import csv
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from lab.fpds_research import ingest as I, features as F
from lab.fpds_research.protocol import title, manifest


def test_export_markers_and_canonical_table():
    assert title(Path('receiving-stats week 7.csv'))==('receiving_stats',7)
    assert title(Path('receiving-stats Weeks 1-8.csv'))==('receiving_stats',8)
    assert title(Path('receiving-stats_week_9.csv'))==('receiving_stats',9)


def test_body_season_over_export_selector(tmp_path):
    p=tmp_path/'shadow-index week 6.csv'
    with p.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Season','SEA','WK','Receiver','OFF','POS','YDS']);w.writerow([2026,2021,1,'Synthetic Person','BUF','WR',20])
    d,m=I.parsed(p)
    assert d._season.tolist()==[2021]
    assert m['selector_conflicts']==1
    assert m['coverage']=={'2021':[1]}


def test_summary_and_future_rows_quarantined(tmp_path):
    p=tmp_path/'receiving-basic week 6.csv'
    with p.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Name','TEAM','SEASON','WEEK','YDS']);w.writerows([['A','BUF',2026,6,3],['B','BUF',2026,7,5],['Summary','','','',8]])
    d,m=I.parsed(p)
    assert len(d)==1 and m['invalid_calendar_rows']==2


@pytest.mark.parametrize('header',['FP','Salary','Ownership','Projection','Rank'])
def test_forbidden_source_columns(header):
    cls,rule=I.column_class(header,I.old.slug(header))
    assert cls!='pregame-valid' or header=='Rank'
    assert I.FORBIDDEN.search(I.old.slug(header))


def test_no_automatic_gsis_for_native_id():
    assert I.key_index({'header':['player_id','Name','TEAM']},'native_id')==0
    assert I.key_index({'header':['player_id','Name','TEAM']},'game_id') is None


def test_revision_diff_reports_counts_not_values():
    a=pd.DataFrame({'season':[2021],'week':[1],'entity':['private-id'],'metric':['1']})
    b=a.copy();b['metric']='3'
    out=I.revision(a,b,{'columns':[{'column':'metric'}]})
    assert out['changed_values']==1 and out['columns'][0]['mean_absolute_revision']==2
    assert 'private-id' not in str(out)


def fixture():
    g=pd.DataFrame({'season':[2021]*4,'week':[1,2,3,4],
                    'kickoff_utc':pd.to_datetime(['2021-09-13T00:00Z','2021-09-20T00:00Z','2021-09-27T00:00Z','2021-10-04T00:00Z'])})
    obs=pd.DataFrame({'season':[2021]*3,'week':[1,3,4],'entity':['x']*3,'metric':[2.,8.,999.]})
    return g,obs


def test_games_played_windows_skip_byes():
    g,obs=fixture();p=F.rolling_panel(obs,['metric'],g)
    assert p.iloc[1]['metric__last3']==5
    assert p.iloc[1]['observed_games']==2


def test_final_kickoff_plus24_and_strict_week():
    g,obs=fixture();p=F.rolling_panel(obs,['metric'],g)
    c=pd.DataFrame({'season':[2021]*3,'week':[2,2,1],'pid':['x']*3,
                    'kickoff_utc':pd.to_datetime(['2021-09-13T23:59Z','2021-09-14T00:01Z','2021-09-14T01:00Z'])})
    values,_,_=F.join_asof(c,p,['metric__last1'],'pid')
    assert np.isnan(values[0,0]) and values[1,0]==2 and np.isnan(values[2,0])


def test_future_mutation_and_shifted_week_canary():
    g,obs=fixture();c=pd.DataFrame({'season':[2021],'week':[2],'pid':['x'], 'kickoff_utc':pd.to_datetime(['2021-09-20T00:00Z'])})
    p=F.rolling_panel(obs,['metric'],g);a=F.join_asof(c,p,['metric__last1'],'pid')[0]
    obs.loc[obs.week>=3,'metric']=-100000
    q=F.rolling_panel(obs,['metric'],g);b=F.join_asof(c,q,['metric__last1'],'pid')[0]
    np.testing.assert_array_equal(a,b)
    shifted=obs.copy();shifted['week']+=1
    q=F.rolling_panel(shifted,['metric'],g)
    assert np.isnan(F.join_asof(c,q,['metric__last1'],'pid')[0]).all()


def test_shuffled_week_never_uses_same_week():
    g,obs=fixture();obs['week']=obs.week.sample(frac=1,random_state=17).to_numpy()
    p=F.rolling_panel(obs,['metric'],g)
    c=pd.DataFrame({'season':[2021],'week':[3],'pid':['x'],'kickoff_utc':pd.to_datetime(['2021-09-27T23:59Z'])})
    _,s,w=F.join_asof(c,p,['metric__last1'],'pid')
    assert np.isnan(w[0]) or w[0]<3


def test_prospective_requires_actual_import_time():
    g,obs=fixture();p=F.rolling_panel(obs,['metric'],g)
    c=pd.DataFrame({'season':[2021],'week':[2],'pid':['x'],'kickoff_utc':pd.to_datetime(['2021-09-20T00:00Z'])})
    assert np.isnan(F.join_asof(c,p,['metric__last1'],'pid',True,'2026-10-20T00:00Z')[0]).all()


def test_trial_inventory_unique_finite_and_no_prices():
    m=manifest(['receiving_stats','pace'])
    assert len({x['id'] for x in m['trials']})==m['trial_budget']
    assert not any('market' in x['group'] for x in m['trials'])


def test_team_name_field_is_not_a_player(tmp_path):
    p=tmp_path/'pace week 6.csv'
    with p.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Name','SEASON','WEEK','PACE']);w.writerow(['BUF',2021,1,25])
    d,m=I.parsed(p)
    r=pd.DataFrame(columns=['season','week','team','normal','gsis_id'])
    allrows,usable=I.resolve(d,m,r,{})
    assert m['entity_kind']=='team' and usable.entity.tolist()==['BUF']


def test_forecast_revision_never_overwrites(monkeypatch,tmp_path):
    from lab.fpds_research import weekly
    monkeypatch.setattr(weekly,'ROOT',tmp_path)
    first=weekly.revision_directory(7);(first/'sentinel').write_text('original')
    second=weekly.revision_directory(7)
    assert first!=second and '_r002_' in second.name and (first/'sentinel').read_text()=='original'


def test_group_feature_selection_is_predeclared():
    from lab.fpds_research.walkforward import columns_for
    meta={'base_columns':['hist_rec'],'groups':{'receiving_stats':{'family':'H1','columns':['fp__receiving_stats__tgt__last3']},'rushing_stats':{'family':'H2','columns':['fp__rushing_stats__att__last3']}}}
    spec={'stat':'rec','arm':'add','group':'receiving_stats'}
    assert columns_for(spec,meta)==['hist_rec','fp__receiving_stats__tgt__last3']


def test_cluster_bootstrap_uses_whole_games():
    from lab.fpds_research.report import paired
    d=pd.DataFrame({'game_id':['a']*20+['b']*20,'delta':[-1.]*20+[1.]*20})
    r=paired(d,4)
    assert r['games']==2 and r['n']==40 and r['ci95']==[-1.,1.]
    assert r['corrected_ci95'][0]<=r['ci95'][0]


def test_first_td_probability_simplex():
    from lab.fpds_research.first_td import probabilities
    ids,p=probabilities(['synthetic-a','synthetic-b'],[.2,.3],.1,.2)
    assert ids[-2:]==['OTHER_PLAYERS','NO_OFFENSIVE_TD']
    assert (p>=0).all() and abs(p.sum()-1)<1e-12


def test_models_do_not_accept_unknown_family():
    from lab.fpds_research.models import estimator
    with pytest.raises(ValueError):estimator('rec','unregistered')


def test_checkpoint_and_cutoff_with_synthetic_fit(tmp_path,monkeypatch):
    from lab.fpds_research import walkforward as W
    games=[];rows=[]
    for season in (2021,2022):
        for week in range(1,19):
            kickoff=pd.Timestamp(f'{season}-09-01',tz='UTC')+pd.Timedelta(days=7*(week-1))
            game_id=f'{season}_{week}'
            games.append(dict(game_id=game_id,season=season,week=week,kickoff_utc=kickoff))
            for player in range(10):
                rows.append(dict(game_id=game_id,season=season,week=week,kickoff_utc=kickoff,pid=str(player),
                    team='BUF',position='WR',hist_games=8.,hist_rec=3.+player/10,rec=float(player%5)))
    data=pd.DataFrame(rows);g=pd.DataFrame(games)
    spec={'id':'rec__control__all__linear','stat':'rec','model':'linear','arm':'control','group':'all'}
    meta={'base_columns':['hist_games','hist_rec'],'groups':{}}
    result=W.run_block(tmp_path,spec,data,g,meta,2022,1,1)
    p=pd.read_parquet(tmp_path/'blocks'/spec['id']/'2022_w01.parquet')
    assert result['status']=='complete' and p.training_last_season.max()==2021 and (p.q10>=0).all()
    monkeypatch.setattr(W.M,'fit_predict',lambda *a,**kw:pytest.fail('Checkpoint unexpectedly refitted'))
    assert W.run_block(tmp_path,spec,data,g,meta,2022,1,1)['status']=='checkpoint'


def test_cumulative_unknown_metrics_blocked():
    assert F.selected_metrics({'valid_rows_games_gt_one':2,'columns':[{'laggable_numeric':True,'column':'x'}]})==[]


def test_regular_player_keeps_verified_id_without_shadow_columns(tmp_path,monkeypatch):
    monkeypatch.setattr(I,'_KNOWN',None);monkeypatch.setattr(I,'_EXACT',None)
    p=tmp_path/'receiving-stats week 6.csv'
    with p.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Name','TEAM','POS','SEASON','WEEK','YDS']);w.writerow(['Synthetic Person','BUF','WR',2021,1,20])
    d,m=I.parsed(p)
    r=pd.DataFrame({'season':[2021],'week':[1],'team':['BUF'],'normal':[I.normalized_name('Synthetic Person')],'gsis_id':['00-synthetic']})
    complete,usable=I.resolve(d,m,r,{})
    assert m['mapped_rows']==1 and usable.pid.tolist()==['00-synthetic']


@pytest.mark.parametrize('key',['linear','hist','xgboost','mlp'])
@pytest.mark.parametrize('stat',['rec','rec_yds','anytime_td'])
def test_registered_factories_accept_weighted_synthetic_rows(key,stat):
    from lab.fpds_research import models as M
    rng=np.random.default_rng(17);n=120
    d=pd.DataFrame({'x':rng.normal(size=n),'missing':np.nan,'position':['WR']*n,'hist_games':[8.]*n})
    d[stat]=rng.integers(0,2 if stat=='anytime_td' else 5,n).astype(float)
    p,model=M.fit_predict(d,d.iloc[:3],stat,['x','missing'],key,1,np.ones(n))
    assert len(p)==3 and np.isfinite(p).all() and (p>=0).all()
