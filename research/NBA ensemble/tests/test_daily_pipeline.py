import sys
from nba_lab import cli,sources,features,engine,outcomes,shadow_results,extra_data,score_models,winner_shadow


def test_daily_runs_archives_and_refits_frozen_shadows_without_research(tmp_path,monkeypatch):
    calls=[]
    def action(name,result=None):
        def invoke(*a,**k):calls.append(name);return result
        return invoke
    monkeypatch.setattr(cli,'low_priority',lambda:1);monkeypatch.setattr(cli,'REPORTS',tmp_path/'reports');monkeypatch.setattr(cli,'ROOT',tmp_path)
    docs=tmp_path/'docs';docs.mkdir()
    for filename in ('SCORE_FROZEN_CONFIG.json','INDIVIDUAL_SHADOW_CONFIG.json'):(docs/filename).write_text('{}')
    for module,name,label,result in [
        (sources,'refresh','refresh',{}),(outcomes,'score','original-results',{}),
        (shadow_results,'score','shadow-results',{}),(features,'run','features',None),
        (engine,'train','original-refit',{}),(engine,'predict','original-archive',(None,{'fixture':True})),
        (extra_data,'collect','extra-data',{}),(score_models,'archive','score-archive',{}),
        (winner_shadow,'archive','individual-archive',{})]:
        monkeypatch.setattr(module,name,action(label,result))
    def forbid(*a,**k):raise AssertionError('Daily workflow must not rerun research/confirmation')
    monkeypatch.setattr(engine,'develop',forbid);monkeypatch.setattr(engine,'confirm',forbid)
    monkeypatch.setattr(score_models,'research',forbid)
    monkeypatch.setattr(sys,'argv',['nba_lab.cli','daily'])
    assert cli.main()==0
    assert calls==['refresh','original-results','shadow-results','features','original-refit','original-archive','extra-data','score-archive','individual-archive']
