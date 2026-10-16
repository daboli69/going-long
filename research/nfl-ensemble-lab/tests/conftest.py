"""Tests run against a synthetic league in a temporary lab root: no network,
no real data, and nothing under the real data/models/reports folders."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="nfl_lab_test_")
os.environ["NFL_LAB_ROOT"] = _TMP
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from lab import ingest  # noqa: E402

TEAMS = ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE"]
STAT_COLS = ["plays", "dropbacks", "rushes", "pass_yds", "rush_yds", "total_yds", "pass_td", "rush_td", "turnovers",
             "epa_pp", "sr", "pass_epa", "rush_epa", "pass_sr", "rush_sr", "early_epa", "early_sr", "third_conv",
             "rz_td_rate", "explosive_rate", "sack_rate", "pass_rate", "sec_per_play"]


def make_league(seasons=range(2015, 2027), weeks=14, unplayed_from=(2026, 6), seed=0):
    """Round-robin-ish synthetic schedule with latent team strength driving results and stats."""
    rng = np.random.default_rng(seed)
    games, tstats, qbs = [], [], []
    strength = {t: rng.normal(0, 4) for t in TEAMS}
    for s in seasons:
        for t in TEAMS:
            strength[t] = 0.6 * strength[t] + rng.normal(0, 2.5)
        start = pd.Timestamp(f"{s}-09-10 17:00", tz="UTC")
        for w in range(1, weeks + 1):
            order = rng.permutation(TEAMS)
            for i in range(0, len(order), 2):
                home, away = order[i], order[i + 1]
                kick = start + pd.Timedelta(days=7 * (w - 1), hours=3 * i)
                played = (s, w) < unplayed_from
                margin = strength[home] - strength[away] + 2 + rng.normal(0, 10)
                hs = max(int(round(21 + margin / 2)), 0) if played else np.nan
                as_ = max(int(round(21 - margin / 2)), 0) if played else np.nan
                if played and hs == as_:
                    hs += 1
                gid = ingest.canonical_game_id(s, w, away, home)
                games.append({"game_id": gid, "source_game_id": gid, "season": s, "week": w, "game_type": "REG",
                              "gameday": str(kick.date()), "gametime": "13:00", "kickoff_utc": kick,
                              "home_team": home, "away_team": away, "home_score": hs, "away_score": as_,
                              "neutral_site": 0, "div_game": int(rng.random() < 0.3), "roof": "outdoors", "roof_type": "outdoors",
                              "stadium_id": f"{home}00",
                              "home_qb_id": f"QB_{home}", "away_qb_id": f"QB_{away}", "home_qb_name": f"{home} QB", "away_qb_name": f"{away} QB",
                              "spread_line": round((strength[home] - strength[away] + 2) * 2) / 2, "total_line": 44.5,
                              "home_moneyline": -150 if strength[home] + 2 > strength[away] else 130,
                              "away_moneyline": 130 if strength[home] + 2 > strength[away] else -150})
                if not played:
                    continue
                for team, sign in ((home, 1), (away, -1)):
                    e = 0.01 * sign * margin + rng.normal(0, 0.1)
                    row = {"game_id": gid, "team": team, **{c: rng.normal(1, 0.1) for c in STAT_COLS}}
                    row |= {"epa_pp": e, "pass_epa": e + rng.normal(0, .05), "rush_epa": e - 0.05, "sr": 0.45 + e / 3,
                            "turnovers": rng.poisson(1.3), "plays": 63 + rng.normal(0, 5), "sec_per_play": 31 + rng.normal(0, 1)}
                    tstats.append(row)
                    qbs.append({"game_id": gid, "team": team, "qb_id": f"QB_{team}", "qb_dropbacks": 35, "qb_epa_sum": 35 * e})
                    qbs.append({"game_id": gid, "team": team, "qb_id": f"QB2_{team}", "qb_dropbacks": 2, "qb_epa_sum": 0.0})
    g = pd.DataFrame(games)
    g["completed"] = g["home_score"].notna()
    g["margin"] = g["home_score"] - g["away_score"]
    g["home_win"] = np.where(g["completed"], (g["margin"] > 0).astype(float), np.nan)
    g["tie"] = False
    g["market_p_home_novig"] = [ingest.no_vig_home_prob(h, a) for h, a in zip(g["home_moneyline"], g["away_moneyline"])]
    return g, pd.DataFrame(tstats), pd.DataFrame(qbs)


@pytest.fixture(scope="session")
def league():
    return make_league()


@pytest.fixture(scope="session")
def feature_store(league):
    from lab import features
    g, t, q = league
    return features.build_feature_store(g, t, q)


@pytest.fixture(scope="session")
def trained(feature_store):
    """A full (tiny-grid) training run on the synthetic league."""
    from lab import data_pipeline, models, training
    for reg in (models.CLASSIFIERS, models.REGRESSORS):
        for k, (factory, grid) in list(reg.items()):
            reg[k] = (factory, grid[:1])
    feature_store.to_parquet(data_pipeline.FEATURE_STORE, index=False)
    make_league()[0].to_parquet(data_pipeline.GAMES_TABLE, index=False)
    res = training.run_training(progress=lambda m: None)
    return res
