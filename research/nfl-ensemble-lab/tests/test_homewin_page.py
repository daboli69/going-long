"""Home-Win Research page: offline render against synthetic archives (no downloads, no subprocesses)."""
import json

from streamlit.testing.v1 import AppTest

from app import homewin_page as hp
from lab.archive10 import save


def _fixture(tmp_path):
    arch, cache = tmp_path / "archive", tmp_path / "cache"
    games = [{"gid": "2026_08_CAR_GB", "kickoff_utc": "2026-10-30T00:15:00+00:00", "home": "GB", "away": "CAR",
              "p_elo": 0.68, "p_xgb_v1": 0.6, "p_margin_platt": 0.59, "p_xgb_deep_platt": 0.62,
              "market_p_home_at_freeze": 0.64, "fpi_p_home": 0.65, "pred_margin": 3.0}]
    save("homewin_deep", "2026_w08", {"season": 2026, "week": 8, "games": games}, {"frozen_at": "2026-10-28T21:00:00+00:00"}, root=arch)
    sim = [{"gid": "2026_08_CAR_GB", "kickoff_utc": "2026-10-30T00:15:00+00:00", "p_home": 0.66, "p_tie": 0.004,
            "median_margin": 4.0, "median_total": 44.0, "margin_pmf": {"3": 0.1, "7": 0.08, "-3": 0.07}, "total_pmf": {"44": 0.05}}]
    save("homewin_sim", "2026_w08", {"season": 2026, "week": 8, "games": sim}, {"frozen_at": "2026-10-29T01:00:00+00:00"}, root=arch)
    (cache / "xgb_api_games").mkdir(parents=True)
    (cache / "xgb_api_games" / "2026.json").write_text(json.dumps([
        {"season": 2026, "week": 8, "game_type": "REG", "home_team": "GB", "away_team": "CAR", "home_score": 27, "away_score": 20}]))
    return arch, cache


def test_frozen_table_and_scoring(tmp_path):
    arch, cache = _fixture(tmp_path)
    a = hp.load_archives(arch)
    assert all(d["_hash_ok"] for rows in a.values() for d in rows)
    df = hp.frozen_table(a)
    assert len(df) == 1 and df.loc[0, "p_sim"] == 0.66 and df.loc[0, "p_elo"] == 0.68
    sc = hp.score(df, hp.load_results(cache))
    assert set(sc["Model"]) >= {"Elo", "Simulator", "Market at freeze"} and (sc["Games"] == 1).all()


def test_page_renders_offline(tmp_path):
    arch, cache = _fixture(tmp_path)
    at = AppTest.from_string(f"from pathlib import Path\nfrom app.homewin_page import render\n"
                             f"render(Path(r'{arch}'), Path(r'{cache}'))").run(timeout=60)
    assert not at.exception
    assert at.title[0].value == "Home-Win Research"
    assert len(at.dataframe) >= 2


def test_tampered_archive_is_flagged(tmp_path):
    arch, _ = _fixture(tmp_path)
    p = next((arch / "homewin_deep").glob("*.json"))
    p.chmod(0o666)
    d = json.loads(p.read_text())
    d["content"]["games"][0]["p_elo"] = 0.99
    p.write_text(json.dumps(d))
    assert not hp.load_archives(arch)["homewin_deep"][0]["_hash_ok"]


def test_integer_key_pmf_archive_verifies(tmp_path):
    arch = tmp_path / "archive"
    sim = [{"gid": "2026_08_CAR_GB", "kickoff_utc": "2026-10-30T00:15:00+00:00", "p_home": 0.6, "p_tie": 0.0,
            "median_margin": 3.0, "median_total": 40.0, "margin_pmf": {-10: 0.5, 3: 0.5}, "total_pmf": {40: 1.0}}]
    save("homewin_sim", "2026_w08", {"season": 2026, "week": 8, "games": sim}, {"frozen_at": "2026-10-29T01:00:00+00:00"}, root=arch)
    assert hp.load_archives(arch)["homewin_sim"][0]["_hash_ok"]
