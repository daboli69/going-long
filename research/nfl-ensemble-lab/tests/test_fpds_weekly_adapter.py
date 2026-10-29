"""Single-week FantasyPoints drop adapter (synthetic files only)."""
import csv

import pytest

from lab import fpds_weekly_adapter as A
from lab.fpds_sources import HISTORY_FOLDER

AUTH = [["", "Player", "Player", "Player", "Player", "Player", "Player", "Passing", "Passing", "Rushing"],
        ["Name", "Team", "G", "SEASON", "WEEK", "OPP", "DB %", "ATT", "YDS", "ATT"]]
DROP = [["", "Player", "Player", "Player", "Passing", "Passing", "Rushing"],
        ["Season", "Name", "Team", "G", "ATT", "YDS", "ATT"]]


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)


def _read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    root = tmp_path / "Inbox"
    _write(root / HISTORY_FOLDER / "passing-stats.csv", AUTH + [["Old QB", "ARZ", "1", "2026", "6", "HST", "100", "30", "250", "2"]])
    monkeypatch.setattr(A, "CONVERTED_ROOT", tmp_path / "converted")
    monkeypatch.setattr(A, "_opponents", lambda week: {"ARI": "HOU", "HOU": "ARI"})
    return root


def test_converts_to_authority_layout_with_week_opp_and_blank_share(inbox):
    _write(inbox / HISTORY_FOLDER / "Week 7" / "passing-stats.csv", DROP + [["2026", "New QB", "ARZ", "1", "33", "280", "4"]])
    rep = A.convert_week(7, inbox)
    out = _read(A.CONVERTED_ROOT / HISTORY_FOLDER / "Week 8" / "passing-stats.csv")
    assert out[:2] == AUTH  # exact authority headers, so the importer's schema checks pass
    assert out[2] == ["New QB", "ARZ", "1", "2026", "7", "HST", "", "33", "280", "4"]  # OPP in authority style; DB % blank
    t = rep["tables"]["passing_stats"]
    assert t["blank_columns"] == ["DB %"] and t["rows_without_opponent"] == 0
    assert rep["forecast_week"] == 8 and "passing_stats" not in rep["missing_tables"]
    assert (inbox / HISTORY_FOLDER / "Week 7" / "passing-stats.csv").exists()  # Inbox untouched


def test_refuses_multi_week_summary(inbox):
    _write(inbox / HISTORY_FOLDER / "Week 7" / "passing-stats.csv", DROP + [["2026", "QB", "ARZ", "7", "200", "1800", "20"]])
    with pytest.raises(A.ConversionError, match="multi-week"):
        A.convert_week(7, inbox)


def test_unregistered_tables_are_skipped_and_reported(inbox):
    _write(inbox / HISTORY_FOLDER / "Week 7" / "brand-new-table.csv", DROP)
    rep = A.convert_week(7, inbox)
    assert rep["unregistered_skipped"] == ["brand-new-table.csv"] and rep["missing_tables"] == ["passing_stats"]
