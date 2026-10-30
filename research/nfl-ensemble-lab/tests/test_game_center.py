"""Game Center: pure helpers and an offline page smoke test (no network, no real data)."""
import re

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from app import game_center as gc
from app import ui

JARGON = ["crps", "log loss", "logit", "bonferroni", "conformal", "nats", "kappa", "bootstrap", "permutation", "brier", "isotonic"]


def _row(**kw):
    base = {"home_team": "GB", "away_team": "CAR", "market_p_home_novig": np.nan, "spread_line": np.nan, "total_line": np.nan}
    return pd.Series(base | kw)


FZ = {"kalshi_winner_p_home": 0.65, "model": {"p_win": 0.59, "p_elo": 0.69, "mu_m": 3.0, "mu_t": 46.0, "sd_m": 13.0, "sd_t": 10.0},
      "margin": {"mu_kalshi": 4.0, "mu_model": 3.0, "abstain": True, "thresholds": []}, "total": None}


def test_headline_prefers_the_market_then_falls_back_with_a_plain_label():
    b = gc.best_numbers(_row(), FZ)
    assert b["p_home"] == 0.65 and "Kalshi" in b["p_label"] and b["mu_m"] == 4.0
    assert b["mu_t"] == 46.0 and b["t_label"] == "our model"          # no market total saved: say so
    sb = gc.best_numbers(_row(market_p_home_novig=0.6, spread_line=3.5, total_line=47.5), None)
    assert sb["p_home"] == 0.6 and sb["mu_m"] == 3.5 and sb["p_label"] == "sportsbook lines"
    assert gc.best_numbers(_row(), None)["p_home"] is None


def test_probability_helpers():
    assert abs(gc.p_over(0.0, 13.5, 0.0) - 0.5) < 1e-9
    assert gc.pct(0.654) == "65%" and gc.pct(None) == "—" and gc.pct(float("nan")) == "—"


def test_team_summary_record_and_last_games():
    g = pd.DataFrame({"home_team": ["GB", "CHI"], "away_team": ["CAR", "GB"], "home_score": [27.0, 20.0], "away_score": [19.0, 24.0], "completed": [True, True],
                      "kickoff_utc": pd.to_datetime(["2026-09-13", "2026-09-20"], utc=True)})
    s = gc.team_summary(g, "GB")
    assert s["record"] == "2-0" and s["games"] == 2 and s["last"][0] == "W 24-20 at CHI" and abs(s["pf"] - 25.5) < 1e-9


def test_ui_html_is_escaped_and_bar_sums_to_one():
    assert "&lt;script&gt;" in ui.card("<script>", "1")
    bar = ui.prob_bar("CAR", 0.35, "GB", 0.65)
    assert "35%" in bar and "65%" in bar and "width:35.0%" in bar
    assert len(ui.TEAM_NAMES) == 32 and set(ui.TEAM_COLORS) == set(ui.TEAM_NAMES)


def test_glossary_and_labels_use_plain_words():
    text = " ".join(t + " " + d for t, d in ui.GLOSSARY).lower()
    assert not [w for w in JARGON if w in text]
    from app.navigation import DESCRIPTIONS, LABELS, PAGES
    assert set(LABELS) == set(PAGES) and set(DESCRIPTIONS) == set(PAGES)
    assert not [w for w in JARGON for d in DESCRIPTIONS.values() if w in d.lower()]


def test_page_without_data_shows_a_friendly_message(tmp_path):
    at = AppTest.from_string(f"from pathlib import Path\nfrom app.game_center import render\nrender(Path(r'{tmp_path}'), Path(r'{tmp_path}') / 'none.parquet')").run(timeout=60)
    assert not at.exception
    assert any("games table is missing" in w.value for w in at.warning)
