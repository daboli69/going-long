import pandas as pd
import pytest
from lab.fpds_improve_diagnostics import probability_diagnostics,benchmark_metrics


def test_probability_reliability_includes_exact_bin_edges_and_one():
    d=pd.DataFrame({'game_id':['g']*4,'pseudo_line':[.5]*4,'p_over':[0,.6,1,float('nan')],'actual':[0,1,1,0]})
    out=probability_diagnostics(d)
    assert out['n']==3
    assert sum(r['n'] for r in out['reliability'])==3
    assert out['brier']==pytest.approx(.16/3,abs=1e-6)


def test_no_line_rows_stay_unavailable():
    d=pd.DataFrame({'game_id':['g'],'pseudo_line':[float('nan')],'p_over':[.5],'actual':[1]})
    assert probability_diagnostics(d)=={}


def test_benchmark_uses_same_games_and_drops_only_unavailable_benchmark():
    d=pd.DataFrame({'game_id':['a','b','c'],'actual':[7,14,100],'pred':[8,11,0],'closing':[7,10,float('nan')]})
    out=benchmark_metrics(d,'margin','closing',30)
    assert out['n']==2 and out['games']==2
    assert out['model_loss']==2 and out['benchmark_loss']==2
    assert out['delta']==0
