"""Compact sectioned navigation, same pattern as the NFL lab. Page keys stay the same so links and app.py branches keep working."""
import streamlit as st

SECTIONS = {
    "Today": ("Game Center", "Today", "Model Debate"),
    "Live": ("King of the Court", "Live Value"),
    "Research": ("Research & Calibration",),
    "Data": ("Data & Sources",),
}
PAGES = [page for pages in SECTIONS.values() for page in pages]
SECTION_OF = {page: section for section, pages in SECTIONS.items() for page in pages}
DEFAULT_PAGE = "Game Center"
LABELS = {"Today": "All games and tools", "Model Debate": "Six models on one game"}
DESCRIPTIONS = {
    "Game Center": "Each game's win chance, expected score and injury list, from saved forecasts.",
    "Today": "Every game on a date with all six model leans; refresh data and save forecasts here.",
    "Model Debate": "How each of the six models sees one game, and which inputs move it.",
    "King of the Court": "Simulate a Tuesday King of the Court slate.",
    "Live Value": "The lab's own prices beside saved Kalshi quotes. Comparison only.",
    "Research & Calibration": "Test results, calibration and sample sizes. Read the caveats first.",
    "Data & Sources": "Which sources were used, what is missing, and the feature audit.",
}


def _remember_page():
    page = st.session_state["nba_nav_page"]
    st.session_state.setdefault("nba_nav_history", {})[st.session_state["nba_nav_section"]] = page
    st.query_params["page"] = page
    st.session_state["nba_nav_url"] = page


def _change_section():
    section = st.session_state["nba_nav_section"]
    st.session_state["nba_nav_page"] = st.session_state.get("nba_nav_history", {}).get(section, SECTIONS[section][0])
    _remember_page()


def render_navigation():
    requested = st.query_params.get("page", DEFAULT_PAGE)
    requested = requested if requested in PAGES else DEFAULT_PAGE
    # Honor direct links, including external changes to the URL within a session.
    if st.session_state.get("nba_nav_url") != requested:
        section = SECTION_OF[requested]
        st.session_state["nba_nav_section"] = section
        st.session_state["nba_nav_page"] = requested
        st.session_state["nba_nav_url"] = requested
        st.session_state.setdefault("nba_nav_history", {})[section] = requested
    with st.sidebar:
        st.header("NBA Lab")
        section = st.selectbox("Section", list(SECTIONS), key="nba_nav_section", on_change=_change_section)
        page = st.radio("Page", SECTIONS[section], key="nba_nav_page", on_change=_remember_page, format_func=lambda x: LABELS.get(x, x))
        st.caption(DESCRIPTIONS[page])
    return page
