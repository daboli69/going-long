"""Offline navigation checks: no training, downloads or real page actions."""
import ast
from pathlib import Path
from streamlit.testing.v1 import AppTest
from app.navigation import SECTIONS, PAGES, DESCRIPTIONS


def app(page=None):
    at = AppTest.from_string("from app.navigation import render_navigation\nimport streamlit as st\nst.write('Selected: ' + render_navigation())")
    if page:
        at.query_params["page"] = page
    return at.run()


def test_every_existing_page_is_available_once():
    tree = ast.parse(Path("app/streamlit_app.py").read_text(encoding="utf-8"))
    # Compare against the actual dispatch map, not a second copy of the menu.
    maps = [n for n in ast.walk(tree) if isinstance(n, ast.Dict) and all(isinstance(k, ast.Constant) for k in n.keys)]
    dispatch = next(n for n in maps if "Projections" in [k.value for k in n.keys])
    assert set(PAGES) == {k.value for k in dispatch.keys}
    assert len(PAGES) == len(set(PAGES)) == 24
    assert set(DESCRIPTIONS) == set(PAGES)
    assert max(map(len, SECTIONS.values())) <= 6


def test_section_switch_remembers_page_and_updates_link():
    at = app("Leans")
    assert not at.exception
    assert at.sidebar.selectbox[0].value == "This week"
    assert at.sidebar.radio[0].value == "Leans"
    at.sidebar.selectbox[0].select("Data & history").run()
    assert not at.exception
    assert at.sidebar.radio[0].value == "Data Manager"
    at.sidebar.radio[0].set_value("Reports").run()
    assert at.query_params["page"] == ["Reports"]
    at.sidebar.selectbox[0].select("This week").run()
    assert at.sidebar.radio[0].value == "Leans"
    at.sidebar.selectbox[0].select("Data & history").run()
    assert at.sidebar.radio[0].value == "Reports"
    assert not at.exception


def test_all_direct_links_and_invalid_link():
    for page in PAGES:
        at = app(page)
        assert not at.exception
        assert at.sidebar.radio[0].value == page
        assert len(at.sidebar.radio[0].options) <= 6
    at = app("Unknown page")
    assert not at.exception
    assert at.sidebar.radio[0].value == "Home"
