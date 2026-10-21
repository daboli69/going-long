"""Small synthetic checks; no FPDS source, fit, confirmation or holdout reads."""
import numpy as np
import pandas as pd
from lab.props.fpds_research import permute,calibrated


def test_group_permutation_preserves_team_context_and_player_positions():
    d=pd.DataFrame({'team':['A','A','B','B'],'position':['WR','RB','WR','RB'],'a':[1.,1.,2.,2.],'b':[3.,3.,4.,4.]})
    team=permute(d,['a','b'],'run_pass_report',20261020)
    assert team.groupby('team')[['a','b']].nunique().le(1).all().all()
    player=permute(d,['a','b'],'receiving_advanced',20261020)
    for pos in ['WR','RB']:
        assert sorted(player.loc[player.position.eq(pos),'a'])==sorted(d.loc[d.position.eq(pos),'a'])
    assert d.a.tolist()==[1.,1.,2.,2.]


def test_calibration_uses_only_prior_emitted_outcomes():
    prior=np.linspace(.1,.9,120);actual=np.tile([0,1],60);current=np.array([.2,.8])
    first,transform=calibrated(current,prior,[0,0],actual)
    second,_=calibrated(current,prior,[1,1],actual)
    assert np.array_equal(first,second)
    assert np.allclose(first,transform(current))
    warm,_=calibrated(current,prior[:5],[1,1],actual[:5])
    assert np.array_equal(warm,current)
