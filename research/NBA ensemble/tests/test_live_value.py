import numpy as np
import pandas as pd
import pytest
from scipy import stats
from nba_xgb import live_state as LS, live_value as LV, live_model as M, fair_value as FV


def params():
    return M.Params(a1=1.0, am=-0.5, av=0.1, sm=(1.8, 5.2), k=(0.0, 1.0, 0.0, 0.0, 0.0), st=(1.8, 5.0), nu_m=40.0, nu_t=80.0)


def test_state_row_clock_arithmetic_and_overtime():
    r = LV.state_row(3, '6:00', 60, 50, {'mu_close': 3.0}, 224.0)
    assert r.t == pytest.approx(1440 + 360) and r.tau == pytest.approx(1080) and r.m == 10 and r.S == 110
    assert LV.state_row(4, '0:00', 100, 100, {}, 224.0).tau == 0
    assert LV.state_row(5, '3:00', 100, 100, {}, 224.0) is None          # overtime is not priced
    assert LV.state_row(0, '12:00', 0, 0, {}, 224.0) is None             # before tipoff
    assert LV.clock_to_seconds('5:32.4') == pytest.approx(332.4)


def test_close_probability_maps_to_margin_and_back():
    mu = LV.mu_from_close_prob(0.65, 12.6)
    assert stats.norm.cdf(mu / 12.6) == pytest.approx(0.65, abs=1e-9)
    assert LV.mu_from_close_prob(0.5, 12.6) == pytest.approx(0.0)
    assert LV.mu_from_close_prob(0.999, 12.6) == LV.mu_from_close_prob(0.98, 12.6)       # clipped, no infinities


def test_contract_event_definitions():
    margin = np.array([-8, -3, 0, 2, 9])
    total = np.array([200, 210, 220, 230, 240])
    assert LV.contract_event('moneyline', 'home', None, margin, total).tolist() == [False, False, False, True, True]
    assert LV.contract_event('moneyline', 'away', None, margin, total).tolist() == [True, True, False, False, False]
    assert LV.contract_event('spread', 'home', 1.5, margin, total).tolist() == [False, False, False, True, True]       # home wins by more than 1.5
    assert LV.contract_event('spread', 'away', 2.5, margin, total).tolist() == [True, True, False, False, False]      # away wins by more than 2.5
    assert LV.contract_event('total', None, 219.5, margin, total).tolist() == [False, False, True, True, True]


def test_knicks_style_example_is_internally_consistent():
    p = params()
    row = LV.state_row(2, '0:00', 46, 59, {'mu_close': 4.5}, 224.0)
    p.mu_col = 'mu_close'
    margin, total = M.simulate(p, row, n=300_000, seed=5)
    ml_h = FV.side_probabilities(margin, total, 'home_ml')['win']
    ml_a = FV.side_probabilities(margin, total, 'away_ml')['win']
    assert ml_h + ml_a == pytest.approx(1.0, abs=1e-9)                            # no ties survive overtime
    live = FV.side_probabilities(margin, total, ('home_spread', 4.5))['win']
    orig = FV.side_probabilities(margin, total, ('home_spread', -4.5))['win']
    assert orig < ml_h < live                                                    # three different bets, three different probabilities
    assert LV.mc_error(0.5, 200_000) == pytest.approx(0.001118, abs=1e-5)


def test_state_lookup_never_sees_a_later_event():
    ev = {'wc': np.array([100.0, 160.0, 220.0, 400.0]), 'el': np.array([10.0, 70.0, 130.0, 310.0]),
          'h': np.array([2.0, 4.0, 7.0, 20.0]), 'a': np.array([0.0, 3.0, 3.0, 18.0]), 'period': np.array([1, 1, 1, 2])}
    assert LS.state_at_wallclock(ev, 99.0) is None                                # before the first event
    assert LS.state_at_wallclock(ev, 219.9)[1] == 4.0                             # the event stamped 220 is not visible at 219.9
    assert LS.state_at_wallclock(ev, 220.0)[1] == 7.0
    assert LS.state_at_wallclock(ev, 1e9)[1] == 20.0


def test_uncertainty_margin_never_below_calibration_slack():
    fz = {'se': {'B_close': {0: 0.001, 1: 0.002, 2: 0.003, 3: 0.004, 4: 0.005}}, 'slack': {'B_close': 0.014}}
    for tau in (10, 500, 1500, 2800):
        assert LV.se_total(fz, 'B_close', tau) >= 0.014


def test_value_contracts_statuses():
    p = params()
    row = LV.state_row(3, '6:00', 70, 60, {'mu_close': 2.0}, 224.0)
    p.mu_col = 'mu_close'
    margin, total = M.simulate(p, row, n=100_000, seed=2)
    fz = {'se': {'B_close': {i: 0.002 for i in range(5)}}, 'slack': {'B_close': 0.014}}
    c = [{'ticker': 'x', 'kind': 'moneyline', 'team_side': 'home', 'strike': None, 'bid': 0.40, 'ask': 0.42},
         {'ticker': 'y', 'kind': 'moneyline', 'team_side': 'home', 'strike': None, 'bid': None, 'ask': None}]
    fresh = LV.value_contracts(c, margin, total, 'B_close', fz, float(row.tau), 5.0)
    assert fresh.loc[fresh.ticker == 'x', 'status'].iloc[0] in ('actionable', 'no edge')
    assert fresh.loc[fresh.ticker == 'y', 'status'].iloc[0] == 'theoretical'
    stale = LV.value_contracts(c[:1], margin, total, 'B_close', fz, float(row.tau), 900.0)
    assert stale.status.iloc[0] == 'theoretical'
