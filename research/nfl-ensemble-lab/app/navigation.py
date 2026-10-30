"""Compact navigation for the local lab; page functions and URLs stay intact."""
import streamlit as st


SECTIONS = {
    "Overview": ("Game Center", "Home", "Live Readiness & Schedule"),
    "This week": ("Projections", "Leans", "Weekly Predictions", "Player Props"),
    "Insights": ("Model Debate", "Advanced Football Intelligence", "Player Intelligence", "Upset Explorer"),
    "Models": ("Model Leaderboard", "Train Models", "Baseline Research"),
    "Research": ("Long-Run Research", "FPDS Research", "Home-Win Research", "Research Validation", "Research Runs", "Upset Discovery"),
    "Data & history": ("Data Manager", "Data Freshness", "Data Coverage & Gaps", "Prediction Archive", "Prospective Performance", "Reports"),
}
PAGES = [page for pages in SECTIONS.values() for page in pages]
DEFAULT_PAGE = "Game Center"
# Friendly names shown in the menu. The keys above stay the same so links and saved bookmarks keep working.
SECTION_LABELS = {"Overview": "Start here", "This week": "This week's games", "Insights": "Why the models think that", "Models": "The models",
                  "Research": "Research (advanced)", "Data & history": "Data & track record"}
LABELS = {
    "Game Center": "🏟️ Game Center", "Home": "🏠 System status", "Live Readiness & Schedule": "⏱️ Is everything up to date?",
    "Projections": "📊 Team & player projections", "Leans": "↔️ Where we differ from the market", "Weekly Predictions": "🗓️ Weekly win forecasts",
    "Player Props": "👤 Player stat projections", "Model Debate": "💬 How our models see a game", "Advanced Football Intelligence": "🧭 Team trends (advanced)",
    "Player Intelligence": "🔎 Player lookup", "Upset Explorer": "⚡ Upset watch", "Model Leaderboard": "🏆 Which model is best?",
    "Train Models": "🛠️ Re-train the models", "Baseline Research": "📏 Compared with simple rules", "Long-Run Research": "🔬 Long experiments",
    "FPDS Research": "🔬 FantasyPoints data tests", "Home-Win Research": "🔬 Winner, spread & total research", "Research Validation": "🔬 Honesty checks",
    "Research Runs": "🔬 Saved experiments", "Upset Discovery": "🔬 Upset patterns", "Data Manager": "⬇️ Update NFL data",
    "Data Freshness": "🕒 How fresh is the data?", "Data Coverage & Gaps": "🧩 What data is missing?", "Prediction Archive": "🗄️ Saved forecasts",
    "Prospective Performance": "✅ Report card", "Reports": "📄 Reports",
}
DESCRIPTIONS = {
    "Game Center": "Start here. This week's games in plain English: who is likely to win, by how much, and what each player might do.",
    "Home": "System status: when the data was last updated and which models are loaded.",
    "Live Readiness & Schedule": "Checks that everything is up to date before games and shows what runs automatically.",
    "Projections": "Projected stats for every player and team this week, with checks that the numbers add up.",
    "Leans": "Spots where our forecast and the market disagree, and how sure we are.",
    "Weekly Predictions": "The lab's weekly win-chance forecasts for each game.",
    "Player Props": "Projected player stats (yards, catches) for each game, with likely ranges.",
    "Model Debate": "See how each of our six models sees one game, and where they disagree.",
    "Advanced Football Intelligence": "A deeper look at the team and player trends behind the forecasts.",
    "Player Intelligence": "Look up a player's role, workload and recent trend.",
    "Upset Explorer": "Games where the underdog has a real chance, and why.",
    "Model Leaderboard": "Which of our models has been the most accurate, ranked.",
    "Train Models": "Re-train the models on the latest results. This takes a while.",
    "Baseline Research": "How much better our models are than simple rules like \"always pick the home team\".",
    "Long-Run Research": "Long experiments that run in the background, and what they found.",
    "FPDS Research": "Advanced: tests of whether FantasyPoints data improves projections.",
    "Home-Win Research": "Advanced: how well each method forecasts winners, spreads and totals compared with the betting market.",
    "Research Validation": "Advanced: checks that our results are honest and not accidents.",
    "Research Runs": "Advanced: saved experiments and their settings.",
    "Upset Discovery": "Advanced: patterns in games where underdogs won.",
    "Data Manager": "Download or refresh the NFL data the lab uses.",
    "Data Freshness": "How recent each data source is.",
    "Data Coverage & Gaps": "What data we have and what is missing.",
    "Prediction Archive": "Every forecast we have saved, kept unchanged so we can grade ourselves fairly.",
    "Prospective Performance": "Report card: how forecasts saved before games actually did.",
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
        st.header("NFL Ensemble Lab")
        st.caption("New here? Start with **Game Center**.")
        section = st.selectbox("Where do you want to go?", list(SECTIONS), key="lab_nav_section", on_change=_change_section,
                               format_func=lambda x: SECTION_LABELS.get(x, x))
        page = st.radio("Page", SECTIONS[section], key="lab_nav_page", on_change=_remember_page, format_func=lambda x: LABELS.get(x, x))
        st.caption(DESCRIPTIONS[page])
        st.divider()
        st.caption("Local research · not betting advice")
    return page
