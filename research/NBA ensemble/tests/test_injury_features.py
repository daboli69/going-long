import numpy as np
import pandas as pd
import pytest
from nba_lab import features as F,strength as S,injury_features as I
from tests.test_strength import games,boxes,players


def reports(d,rows):
    return pd.DataFrame([{'game_id':g,'team_id':t,'athlete_id':a,'status':s,'not_yet_submitted':s=='NOT YET SUBMITTED',
        'available_at':d.set_index('game_id').loc[g,'tipoff']-pd.Timedelta(hours=lead)} for g,t,a,s,lead in rows])


def make(d,r,p=None):
    base,_=F.build(d,boxes(d),asof='2025-01-01T00:00Z');base=S.build(base,d,players(d))
    return I.build(base,d,players(d) if p is None else p,r)


def test_out_player_value_uses_released_minutes_only():
    d=games(14);x=make(d,reports(d,[('13','1','1-0','Out',2),('13','2','2-0','Questionable',2)]))
    assert x.loc[13,'home_out_gmsc']>0 and x.loc[13,'away_out_gmsc']==0
    assert x.loc[13,'diff_out_gmsc']>0 and x.loc[13,'diff_questionable_gmsc']<0
    assert x.loc[12,'diff_out_gmsc']==0
    # Changing the target game's own box cannot change its injury value.
    p=players(d);p.loc[p.game_id.eq('13'),'points']=99
    pd.testing.assert_series_equal(make(d,reports(d,[('13','1','1-0','Out',2)]),p).diff_out_gmsc[:14],
                                   make(d,reports(d,[('13','1','1-0','Out',2)])).diff_out_gmsc[:14])


def test_late_report_and_unknown_team_are_refused_or_unknown():
    d=games(14)
    with pytest.raises(AssertionError):make(d,reports(d,[('13','1','1-0','Out',0)]))
    x=make(d,reports(d,[('13','1',None,'NOT YET SUBMITTED',2)]))
    assert np.isnan(x.loc[13,'home_out_gmsc']) and np.isnan(x.loc[13,'diff_out_gmsc'])
