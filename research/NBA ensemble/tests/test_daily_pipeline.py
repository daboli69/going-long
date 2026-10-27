import sys
from nba_lab import cli,sources,features,engine,outcomes,shadow_results,extra_data,score_models,winner_shadow,availability,context_research,codex_research


def test_daily_runs_archives_and_refits_frozen_shadows_without_research(tmp_path,monkeypatch):
    calls=[]
    def action(name,result=None):
        def invoke(*a,**k):calls.append(name);return result
        return invoke
    monkeypatch.setattr(cli,'low_priority',lambda:1);monkeypatch.setattr(cli,'REPORTS',tmp_path/'reports');monkeypatch.setattr(cli,'ROOT',tmp_path)
    docs=tmp_path/'docs';docs.mkdir()
    for filename in ('SCORE_FROZEN_CONFIG.json','INDIVIDUAL_SHADOW_CONFIG.json','PREGAME_CONTEXT_FROZEN.json'):(docs/filename).write_text('{}')
    for module,name,label,result in [
        (sources,'refresh','refresh',{}),(outcomes,'score','original-results',{}),
        (shadow_results,'score','shadow-results',{}),(features,'run','features',None),
        (engine,'train','original-refit',{}),(engine,'predict','original-archive',(None,{'fixture':True})),
        (extra_data,'collect','extra-data',{}),(availability,'collect','availability',{}),(score_models,'archive','score-archive',{}),
        (winner_shadow,'archive','individual-archive',{}),(context_research,'archive','context-archive',{}),
        (codex_research,'forecast','codex-forecast',None)]:
        monkeypatch.setattr(module,name,action(label,result))
    def forbid(*a,**k):raise AssertionError('Daily workflow must not rerun research/confirmation')
    monkeypatch.setattr(engine,'develop',forbid);monkeypatch.setattr(engine,'confirm',forbid)
    monkeypatch.setattr(score_models,'research',forbid)
    monkeypatch.setattr(sys,'argv',['nba_lab.cli','daily'])
    assert cli.main()==0
    assert calls==['refresh','original-results','shadow-results','features','original-refit','original-archive','extra-data','availability','score-archive','individual-archive','context-archive','codex-forecast']


def test_codex_failure_does_not_stop_daily_forecasts(tmp_path,monkeypatch):
    monkeypatch.setattr(cli,'low_priority',lambda:1);monkeypatch.setattr(cli,'REPORTS',tmp_path/'reports');monkeypatch.setattr(cli,'ROOT',tmp_path)
    (tmp_path/'docs').mkdir()
    for module,name in [(sources,'refresh'),(outcomes,'score'),(shadow_results,'score'),(features,'run'),(engine,'train'),
                        (extra_data,'collect'),(availability,'collect')]:
        monkeypatch.setattr(module,name,lambda *a,**k:{})
    monkeypatch.setattr(engine,'predict',lambda *a,**k:(None,{'fixture':True}))
    monkeypatch.setattr(codex_research,'PYTHON',tmp_path)
    def broken():raise RuntimeError('upstream timeout')
    monkeypatch.setattr(codex_research,'forecast',broken)
    monkeypatch.setattr(sys,'argv',['nba_lab.cli','daily'])
    assert cli.main()==0
