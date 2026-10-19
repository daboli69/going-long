import json
from pathlib import Path

from lab import inactives10 as I


def test_read_only_official_parser_fixture_archives_complete_scoped_lists(tmp_path, monkeypatch):
    monkeypatch.setattr(I, "GOING_ROOT", Path(__file__).resolve().parents[3])
    I.parser_module.cache_clear()
    parser = I.parser_module()
    monkeypatch.setattr(parser, "fetch", lambda *a: (_ for _ in ()).throw(AssertionError("No network in fixture")))
    monkeypatch.setattr(parser, "update_inactives", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("No notifications path")))
    html = '''<script type="application/ld+json">{"@type":"NewsArticle","headline":"Monday inactives",
      "datePublished":"2026-10-19T22:45:00Z"}</script>
      <div class="story-part-rich-text-editor-wrapper"><p>WHEN: 8:15 p.m. ET</p>
      <h3>San Francisco 49ers</h3><ul><li>WR Fixture Receiver</li></ul>
      <h3>Washington Commanders</h3><ul><li>RB Fixture Runner</li></ul></div>'''
    event = {"event": "fixture", "home": "San Francisco 49ers", "away": "Washington Commanders", "kickoff": "2026-10-20T00:15:00Z"}
    result = I.archive_report(html, "https://www.nfl.com/news/fixture-inactives", event,
                              "2026-10-19T23:00:00Z", root=tmp_path)
    assert result["ok"] is True
    report = json.loads(Path(result["file"]).read_text())
    assert report["read_only_context"] is True
    assert len(report["content"]["teams"]) == 2
    assert {p for team in report["content"]["teams"] for p in team["inactive_players"]} == {"Fixture Receiver", "Fixture Runner"}
    incomplete = html.replace('<ul><li>RB Fixture Runner</li></ul>', '')
    assert I.archive_report(incomplete, "https://www.nfl.com/news/fixture-inactives", event,
                            "2026-10-19T23:00:00Z", root=tmp_path)["ok"] is False
