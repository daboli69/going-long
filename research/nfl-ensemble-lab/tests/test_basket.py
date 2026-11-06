"""Basket: American odds convert, the power-method fair probability sums to one, the odds adjustment moves the line the right way."""
import numpy as np
import pandas as pd

from lab import basket as K


def test_american_odds_and_power_devig():
    assert abs(float(K.american_p(-110)) - 110 / 210) < 1e-9 and abs(float(K.american_p(150)) - 0.4) < 1e-9
    po, pu = float(K.american_p(-130)), float(K.american_p(110))
    p = K.power_fair(po, pu)
    k = np.log(p) / np.log(po)
    assert abs(po ** k + pu ** k - 1) < 1e-6 and 0.5 < p < po


def test_adjusted_line_moves_toward_the_favored_side_and_is_clipped():
    df = pd.DataFrame({"stat": ["pass_yds", "pass_yds", "rec_yds"], "line": [250.0, 250.0, 50.0], "p_over": [0.60, 0.99, 0.50]})
    a = K.adjusted(df, 0.3, 1.0)
    assert a["adj"][0] > 250.0 and a["adj"][2] == 50.0
    assert abs(a["adj"][1] - (250 + 0.3 * 250 * 0.6745)) < 0.5   # clipped at 0.75
