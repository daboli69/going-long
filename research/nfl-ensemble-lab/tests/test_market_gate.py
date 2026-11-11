import numpy as np
import pandas as pd

from lab import market_gate as G


def test_hold_bounds_reject_broken_odds():
    assert G.valid_hold(G.hold(-110, -110))
    assert not G.valid_hold(G.hold(120, 110))      # negative hold
    assert not G.valid_hold(G.hold(-300, -300))    # absurd hold
    assert not G.valid_hold(G.hold(None, -110))


def _frames(model_p, n=400, seed=1):
    rng = np.random.default_rng(seed)
    truth = rng.uniform(0.2, 0.8, n)
    y = (rng.uniform(size=n) < truth).astype(float)
    oof = pd.DataFrame({"game_id": [f"2024_{i + 1:02d}_BUF_KC" for i in range(n)], "season": 2024, "home_win": y,
                        "market_p_home_novig": truth, "p_weighted_average": model_p(truth, rng)})
    games = pd.DataFrame({"season": 2024, "week": [i + 1 for i in range(n)], "away_team": "BUF", "home_team": "KC", "home_moneyline": -115.0, "away_moneyline": -105.0})
    return oof, games


def test_noisy_model_is_retired_as_price_signal():
    oof, games = _frames(lambda t, rng: np.clip(t + rng.normal(0, 0.2, len(t)), 0.02, 0.98))
    r = G.evaluate(oof, games)
    assert r["gate"]["lo"] > 0 and r["price_signal"] is False and "RETIRED" in r["status"]
    assert r["eras"]["2016-2022"]["n"] == 0 and r["eras"]["2023+"]["n"] == 400


def test_invalid_hold_rows_are_excluded_and_listed():
    oof, games = _frames(lambda t, rng: t)
    games.loc[0, ["home_moneyline", "away_moneyline"]] = [120.0, 110.0]
    r = G.evaluate(oof, games)
    assert r["excluded_invalid_hold"] == [oof.game_id[0]] and r["gate"]["n"] == 399
    assert r["price_signal"] is False  # a tie with the market is not a pass
