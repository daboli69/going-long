import numpy as np
import pandas as pd
import pytest

from lab import players as PL

T0 = pd.Timestamp("2021-09-12 17:00", tz="UTC")


def synthetic_plays(n_games=60, plays_per_game=60, seed=0, star_effect=0.6):
    """Two teams' rotating lineups; player 'STAR' adds star_effect EPA when on offense."""
    rng = np.random.default_rng(seed)
    off_pool = [f"O{i}" for i in range(20)] + ["STAR"]
    def_pool = [f"D{i}" for i in range(20)]
    rows = []
    for gi in range(n_games):
        kick = T0 + pd.Timedelta(days=7 * gi)
        for k in range(plays_per_game):
            off = list(rng.choice(off_pool, 11, replace=False))
            de = list(rng.choice(def_pool, 11, replace=False))
            epa = rng.normal(0, 1.2) + (star_effect if "STAR" in off else 0.0)
            rows.append({"game_id": f"g{gi}", "play_id": k, "posteam": "AAA", "defteam": "BBB", "epa": epa, "down": 1, "ydstogo": 10,
                         "yardline_100": 50, "score_differential": 0, "qtr": 1, "offense_players": ";".join(off),
                         "defense_players": ";".join(de), "season": 2021 + gi // 30, "kickoff_utc": kick, "home_off": 1.0})
    return pd.DataFrame(rows)


def test_rapm_recovers_planted_player_and_shrinks():
    plays = synthetic_plays()
    r = PL.RAPM(plays, 300.0, progress=lambda m: None)
    cut = pd.DataFrame({"season": [2022], "week": [10], "cutoff_utc": [plays["kickoff_utc"].max() + pd.Timedelta(days=1)]})
    fit = r.fit_schedule(cut, progress=lambda m: None)[(2022, 10)]
    star = r.pid["STAR"]
    assert fit["off"][star] == max(fit["off"][: r.P])
    assert 0 < fit["off"][star] < 0.6              # shrunk toward zero, never larger than the truth here


def test_rapm_fit_ignores_later_plays():
    plays = synthetic_plays()
    cut_t = T0 + pd.Timedelta(days=7 * 20)
    cut = pd.DataFrame({"season": [2021], "week": [21], "cutoff_utc": [cut_t]})
    a = PL.RAPM(plays, 300.0).fit_schedule(cut, progress=lambda m: None)[(2021, 21)]
    later = plays.copy()
    m = later["kickoff_utc"] >= cut_t
    later.loc[m, "epa"] = 50.0                     # absurd future outcomes
    b = PL.RAPM(later, 300.0).fit_schedule(cut, progress=lambda m: None)[(2021, 21)]
    np.testing.assert_allclose(a["off"], b["off"], atol=1e-8)
    np.testing.assert_array_equal(a["exp_off"], b["exp_off"])


def test_coplay_counts_use_only_earlier_plays():
    plays = synthetic_plays(n_games=10)
    tpm = PL._team_play_matrices(plays)
    t = T0 + pd.Timedelta(days=7 * 5)
    c_before = PL._coplay_counts(tpm, "AAA", "off", t, 2021, [["O1", "O2"]])[0]
    manual = sum(1 for o, k in zip(plays["offense_players"], plays["kickoff_utc"]) if k < t and {"O1", "O2"} <= set(o.split(";")))
    assert c_before == manual
    assert PL._coplay_counts(tpm, "AAA", "off", t, 2021, [["NOBODY"]])[0] == 0.0


def test_adaptive_ensemble_never_sees_its_own_season():
    from lab import ensemble as ens
    from lab.study5 import adaptive_walk_forward
    rng = np.random.default_rng(1)
    n = 1200
    oof = pd.DataFrame({"season": np.repeat([2018, 2019, 2020, 2021], n // 4), "home_win": (rng.random(n) < 0.55).astype(float)})
    for k in ens.MODEL_KEYS:
        oof[f"p_{k}"] = np.clip(0.55 + rng.normal(0, 0.1, n), 0.05, 0.95)
    ctx = pd.DataFrame({"a": rng.normal(size=n), "b": (rng.random(n) < 0.3).astype(float)})
    p1, _ = adaptive_walk_forward(oof, ctx)
    flipped = oof.copy()
    m = flipped["season"] == 2021
    flipped.loc[m, "home_win"] = 1 - flipped.loc[m, "home_win"]
    p2, _ = adaptive_walk_forward(flipped, ctx)
    np.testing.assert_allclose(p1[m.to_numpy()], p2[m.to_numpy()])
    assert np.isnan(p1[(oof["season"] <= 2019).to_numpy()]).all()   # needs >= 2 earlier seasons


def test_challenger_registry_and_hypotheses(trained):
    from lab import prospective as P
    P.register_hypothesis("vX_test", "test design", "unit test")
    P.register_hypothesis("vX_test", "test design", "unit test")      # idempotent
    reg = P.challenger_registry()
    assert [h["version"] for h in reg["hypotheses"]].count("vX_test") == 1
    assert "vX_test" in P.challenger_versions() and "128" in reg["hypotheses"][0]["plan"]


def test_discovery_hypotheses_are_frozen_and_prospective_only(trained):
    from lab import discovery as D
    info = D.register_prospective_hypotheses(k=5, progress=lambda m: None)
    assert len(info["hypotheses"]) <= 5 and info["generated_from_seasons"][1] <= 2025
    with pytest.raises(FileExistsError):
        D.register_prospective_hypotheses(k=5, progress=lambda m: None)
    ev = D.evaluate_prospective_hypotheses()
    assert len(ev) and set(ev["status"]) <= {"no scored prospective games yet", "accumulating evidence", "not supported so far",
                                            "supported prospectively"}
