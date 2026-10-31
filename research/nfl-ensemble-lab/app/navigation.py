"""Compact navigation for the local lab; page functions and URLs stay intact."""
import streamlit as st


SECTIONS = {
    "This week": ("Game Center", "Weekly Predictions", "Player Props", "Upset Explorer"),
    "Track record": ("Prospective Performance", "Prediction Archive", "Model Leaderboard", "Baseline Research"),
    "Data": ("Data Manager", "Data Freshness", "Data Coverage & Gaps", "Live Readiness & Schedule", "Home", "Reports"),
    "Research": ("Home-Win Research", "FPDS Research", "Research Validation", "Research Runs", "Long-Run Research", "Upset Discovery"),
    "Research tools": ("Projections", "Leans", "Model Debate", "Advanced Football Intelligence", "Player Intelligence", "Train Models"),
}
PAGES = [page for pages in SECTIONS.values() for page in pages]
DEFAULT_PAGE = "Game Center"
# Menu names. The keys above stay the same so links and saved bookmarks keep working.
SECTION_LABELS = {}
LABELS = {
    "Game Center": "Game Center", "Weekly Predictions": "Lab win forecasts", "Player Props": "Player projections", "Upset Explorer": "Upset watch",
    "Prospective Performance": "Report card", "Prediction Archive": "Saved forecasts", "Model Leaderboard": "Model rankings",
    "Baseline Research": "Versus simple rules", "Data Manager": "Update data", "Data Freshness": "Data freshness",
    "Data Coverage & Gaps": "Missing data", "Live Readiness & Schedule": "Pre-game checklist", "Home": "System status", "Reports": "Reports",
    "Home-Win Research": "Winners, spreads and totals", "FPDS Research": "FantasyPoints data tests", "Research Validation": "Result checks",
    "Research Runs": "Saved experiments", "Long-Run Research": "Long experiments", "Upset Discovery": "Upset patterns",
    "Projections": "Phase 10 sheets (archived)", "Leans": "Model vs market gaps", "Model Debate": "Six models on one game",
    "Advanced Football Intelligence": "Team trends", "Player Intelligence": "Player lookup", "Train Models": "Retrain models",
}
DESCRIPTIONS = {
    "Game Center": "This week's games: win chances, expected score, player projections and injuries.",
    "Weekly Predictions": "Win chances from the lab's own models, saved each week before kickoff.",
    "Player Props": "Player stat projections with likely ranges, adjusted for injuries.",
    "Upset Explorer": "Underdogs with a real chance this week, and why.",
    "Prospective Performance": "How forecasts saved before kickoff did once the games were played.",
    "Prediction Archive": "Every saved forecast, unchanged, so results can be graded fairly.",
    "Model Leaderboard": "The lab's models ranked by past accuracy.",
    "Baseline Research": "How the models compare with simple rules such as always picking the home team.",
    "Data Manager": "Download or refresh the NFL data the lab uses.",
    "Data Freshness": "When each data source was last updated.",
    "Data Coverage & Gaps": "Which data is present and which is missing.",
    "Live Readiness & Schedule": "What has to be up to date before kickoff, and what runs on a schedule.",
    "Home": "Last data refresh, loaded models and current warnings.",
    "Reports": "Browse and download saved reports.",
    "Home-Win Research": "How each method forecasts winners, spreads and totals against the betting market.",
    "FPDS Research": "Tests of whether FantasyPoints data improves projections.",
    "Research Validation": "Checks that research results are not accidents.",
    "Research Runs": "Saved experiments and their settings.",
    "Long-Run Research": "Experiments that run in the background, and what they found.",
    "Upset Discovery": "Patterns in games the underdog won.",
    "Projections": "Archived Phase 10 forecast sheets. None passed its tests; kept for the record.",
    "Leans": "Where the model and the market disagree. In testing these gaps have not beaten the market.",
    "Model Debate": "How each of the six models sees one game.",
    "Advanced Football Intelligence": "Team trends behind the forecasts.",
    "Player Intelligence": "A player's role, workload and recent trend.",
    "Train Models": "Retrain the models on the latest results. This takes a while.",
}


def _remember_page():
    page = st.session_state["lab_nav_page"]
    st.session_state.setdefault("lab_nav_history", {})[st.session_state["lab_nav_section"]] = page
    st.query_params["page"] = page
    st.session_state["lab_nav_url"] = page


def _change_section():
    section = st.session_state["lab_nav_section"]
    st.session_state["lab_nav_page"] = st.session_state.get("lab_nav_history", {}).get(section, SECTIONS[section][0])
    _remember_page()


def render_navigation():
    requested = st.query_params.get("page", DEFAULT_PAGE)
    requested = requested if requested in PAGES else "Home"
    # Honor direct links, including external changes to the URL within a session.
    if st.session_state.get("lab_nav_url") != requested:
        section = next(section for section, pages in SECTIONS.items() if requested in pages)
        st.session_state["lab_nav_section"] = section
        st.session_state["lab_nav_page"] = requested
        st.session_state["lab_nav_url"] = requested
        st.session_state.setdefault("lab_nav_history", {})[section] = requested
    with st.sidebar:
        st.header("NFL Lab")
        section = st.selectbox("Section", list(SECTIONS), key="lab_nav_section", on_change=_change_section,
                               format_func=lambda x: SECTION_LABELS.get(x, x))
        page = st.radio("Page", SECTIONS[section], key="lab_nav_page", on_change=_remember_page, format_func=lambda x: LABELS.get(x, x))
        st.caption(DESCRIPTIONS[page])
    return page
