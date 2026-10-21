"""Compact navigation for the local lab; page functions and URLs stay intact."""
import streamlit as st


SECTIONS = {
    "Overview": ("Home", "Live Readiness & Schedule"),
    "This week": ("Projections", "Leans", "Weekly Predictions", "Player Props"),
    "Insights": ("Model Debate", "Advanced Football Intelligence", "Player Intelligence", "Upset Explorer"),
    "Models": ("Model Leaderboard", "Train Models", "Baseline Research"),
    "Research": ("Long-Run Research", "Research Validation", "Research Runs", "Upset Discovery"),
    "Data & history": ("Data Manager", "Data Freshness", "Data Coverage & Gaps", "Prediction Archive", "Prospective Performance", "Reports"),
}
PAGES = [page for pages in SECTIONS.values() for page in pages]
DESCRIPTIONS = {
    "Home": "Lab overview and current status.",
    "Live Readiness & Schedule": "Check readiness and upcoming scheduled work.",
    "Projections": "Game and player projections, scenarios and coherence checks.",
    "Leans": "Review flagged comparisons and their uncertainty.",
    "Weekly Predictions": "Weekly game forecasts from the game ensemble.",
    "Player Props": "Player forecasts from the play-by-play simulator.",
    "Model Debate": "Compare how the game models see a matchup.",
    "Advanced Football Intelligence": "Explore team context and advanced football features.",
    "Player Intelligence": "Explore player roles and supporting data.",
    "Upset Explorer": "Inspect potential upsets and supporting patterns.",
    "Model Leaderboard": "Compare saved model performance.",
    "Train Models": "Fit and review the lab's game models.",
    "Baseline Research": "Compare models against simple benchmarks.",
    "Long-Run Research": "Manage and inspect longer research runs.",
    "Research Validation": "Review validation evidence and limitations.",
    "Research Runs": "Inspect saved research experiments.",
    "Upset Discovery": "Explore research into upset patterns.",
    "Data Manager": "Refresh and manage the lab's source data.",
    "Data Freshness": "Check source timestamps and freshness.",
    "Data Coverage & Gaps": "See which inputs are available or missing.",
    "Prediction Archive": "Browse saved forecasts.",
    "Prospective Performance": "Review results of forecasts archived before games.",
    "Reports": "Browse and download saved reports.",
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
    requested = st.query_params.get("page", "Home")
    requested = requested if requested in PAGES else "Home"
    # Honor direct links, including external changes to the URL within a session.
    if st.session_state.get("lab_nav_url") != requested:
        section = next(section for section, pages in SECTIONS.items() if requested in pages)
        st.session_state["lab_nav_section"] = section
        st.session_state["lab_nav_page"] = requested
        st.session_state["lab_nav_url"] = requested
        st.session_state.setdefault("lab_nav_history", {})[section] = requested
    with st.sidebar:
        st.header("NFL Ensemble Lab")
        section = st.selectbox("Section", list(SECTIONS), key="lab_nav_section", on_change=_change_section)
        page = st.radio("Page", SECTIONS[section], key="lab_nav_page", on_change=_remember_page)
        st.caption(DESCRIPTIONS[page])
        st.divider()
        st.caption("Local research · not betting advice")
    return page
