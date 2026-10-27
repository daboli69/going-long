import numpy as np
import pandas as pd
from nba_lab import kotc as K


def test_debut_season_from_espn_experience():
    assert K.debut_season(0,2027)==2027 and K.debut_season(2,2027)==2026 and K.debut_season(6,2027)==2022
    assert K.debut_season(None,2027) is None


def test_prize_share_splits_pool_across_tied_leaders_crowds():
    ids=['a','b','c']
    # Draw 1: a alone; draw 2: a and b tie; draw 3: c alone.
    pra=np.array([[40,30,20],[35,35,20],[20,25,30]])
    out=K.prize_share(ids,pra,{'a':.5,'b':.5},entrants=9,pool=100).set_index('player_id')
    # a: 100/(1+4.5) in draw 1, 100/(1+9) in draw 2 -> mean over 3 draws
    assert np.isclose(out.loc['a','expected_share'],(100/5.5+100/10)/3)
    assert np.isclose(out.loc['c','expected_share'],100/3)  # nobody else picked c
    assert np.isclose(out.loc['b','leader_probability'],1/3)


def test_fair_crowd_gives_every_player_the_same_expected_share():
    rng=np.random.default_rng(1);pra=rng.normal([30,28,25],6,size=(20000,3)).round()
    lead=(pra==pra.max(axis=1,keepdims=True)).mean(axis=0)
    out=K.prize_share(['a','b','c'],pra,dict(zip('abc',lead)),entrants=1000,pool=1000)
    # Ties after rounding blur it slightly; each is near pool / entrants.
    assert np.ptp(out.expected_share)<.15*out.expected_share.mean() and abs(out.expected_share.mean()-1)<.1


def test_expected_minutes_uses_current_rotation_and_drops_inactive_players():
    history={'own':{'star':[36]*15,'bench':[25]*15,'new':[]},
             'team':{'LAL':[{'star':37},{'star':35,'bench':0},{'star':36}]}}
    star=K.expected_minutes('star','LAL',history,'2026-10-27T20:00:00+00:00')
    bench=K.expected_minutes('bench','LAL',history,'2026-10-27T20:00:00+00:00')
    assert 35<star['mean']<37 and bench['mean']==.5 and 'No minutes' in bench['source']
    assert K.expected_minutes('new','LAL',history,'2026-10-27T20:00:00+00:00') is None
