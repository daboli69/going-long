import numpy as np
import pytest
from nba_xgb import fair_value as FV, live_model as M


def test_fee_rounds_up_and_peaks_at_half():
    assert FV.kalshi_fee(0.50, 1) == 0.02          # 0.0175 rounds up to 2 cents
    assert FV.kalshi_fee(0.50, 100) == 1.75
    assert FV.kalshi_fee(0.10, 100) == 0.63
    assert FV.kalshi_fee(0.99, 1) == 0.01
    assert FV.kalshi_fee(0.0, 1) == 0.0 and FV.kalshi_fee(1.0, 1) == 0.0


def test_binary_ev_identity():
    assert FV.ev_buy_yes(0.60, 0.50, 100) == pytest.approx(0.60 - 0.50 - 0.0175)
    # buying NO is the mirror image
    assert FV.ev_buy_no(0.40, 0.50, 100) == pytest.approx(FV.ev_buy_yes(0.60, 0.50, 100))


def test_max_price_is_exactly_the_break_even_cent():
    p = 0.62
    a = FV.max_yes_price(p, 0.0, 100)
    assert FV.ev_buy_yes(p, a, 100) >= 0 and FV.ev_buy_yes(p, a + 0.01, 100) < 0


def test_american_odds_round_trip_and_push():
    assert FV.ev_american(0.5, 0.0, -110) == pytest.approx(0.5 * (100 / 110) - 0.5)
    f = FV.fair_american(0.6)
    assert FV.ev_american(0.6, 0.0, f) == pytest.approx(0.0, abs=1e-9)
    f2 = FV.fair_american(0.45, 0.10)
    assert FV.ev_american(0.45, 0.10, f2) == pytest.approx(0.0, abs=1e-9)
    assert FV.min_american(0.55, 0.0, 0.02) > FV.fair_american(0.55)   # a required edge needs better odds


def test_side_probabilities_whole_and_half_lines():
    margin = np.array([-3, -1, 0, 1, 4, 7])
    total = np.array([200, 210, 220, 230, 240, 250])
    a = FV.side_probabilities(margin, total, ('home_spread', -4))   # push at margin == 4
    assert a['push'] == pytest.approx(1 / 6) and a['win'] == pytest.approx(1 / 6) and a['loss'] == pytest.approx(4 / 6)
    b = FV.side_probabilities(margin, total, ('home_spread', -4.5))
    assert b['push'] == 0
    assert FV.side_probabilities(margin, total, ('over', 225))['win'] == pytest.approx(0.5)
    assert FV.side_probabilities(margin, total, 'home_ml')['win'] == pytest.approx(3 / 6)
    # a spread of zero and the moneyline differ exactly by the zero-margin mass
    z = FV.side_probabilities(margin, total, ('home_spread', 0))
    assert z['push'] == pytest.approx(1 / 6)


def test_model_distribution_is_internally_consistent():
    p = M.Params(a1=1.0, sm=(1.8, 5.2), k=(0.0, 1.0, 0.0, 0.0, 0.0), st=(1.8, 5.0), nu_m=15.0, nu_t=15.0)
    import pandas as pd
    row = pd.Series({'tau': 1440.0, 't': 1440.0, 'm': -13.0, 'S': 110.0, 'L': 0.0, 'mu_base': 4.5, 'T_pre': 224.0})
    p.mu_col = 'mu_base'
    margin, total = M.simulate(p, row, n=200_000, seed=3)
    ml = FV.side_probabilities(margin, total, 'home_ml')['win']
    closed = float(M.p_home_win(p, pd.DataFrame([row]))[0])
    assert ml == pytest.approx(closed, abs=0.01)                 # simulation agrees with the closed form
    covers = [FV.side_probabilities(margin, total, ('home_spread', k))['win'] for k in (-6.5, -3.5, -0.5, 0.5, 3.5, 6.5)]
    assert all(a <= b + 1e-12 for a, b in zip(covers, covers[1:]))   # monotone in the line
    assert 0 < FV.side_probabilities(margin, total, ('over', 224.5))['win'] < 1


def test_value_requires_fresh_two_sided_quote():
    v = FV.value_kalshi_yes(0.60, 0.02, None, None, None)
    assert v.status == 'theoretical' and v.quote is None
    stale = FV.value_kalshi_yes(0.70, 0.01, 0.50, 0.52, 600.0)
    assert stale.status == 'theoretical'
    fresh = FV.value_kalshi_yes(0.70, 0.01, 0.50, 0.52, 5.0, contracts=100)
    assert fresh.status == 'actionable' and fresh.side == 'buy_yes' and fresh.ev_at_quote_conservative > 0
    none = FV.value_kalshi_yes(0.51, 0.02, 0.50, 0.52, 5.0, contracts=100)
    assert none.status == 'no edge'
