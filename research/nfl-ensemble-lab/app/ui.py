"""Shared look and plain-English helpers for the local dashboard (dark theme, cards, bars). No statistics jargon here."""
from __future__ import annotations

import html

import streamlit as st

from lab.gamecenter_meta import GLOSSARY, STAT_PLAIN, TEAM_COLORS, TEAM_NAMES  # noqa: E402,F401
GREEN, RED, BLUE, MUTED = "#34d399", "#f87171", "#60a5fa", "#9fb0cc"

CSS = """
.block-container {padding-top: 1.4rem; max-width: 1500px;}
[data-testid="stSidebar"] {background: #0a1020; border-right: 1px solid #1a2740;}
[data-testid="stSidebar"] h2 {font-size: 1.15rem; letter-spacing: .3px;}
.gc-card {background:#111b2e; border:1px solid #1e2b45; border-radius:14px; padding:14px 16px; height:100%;}
.gc-card .lbl {color:#9fb0cc; font-size:.82rem; margin-bottom:2px;}
.gc-card .val {font-size:1.75rem; font-weight:700; line-height:1.15; color:#ffffff;}
.gc-card .sub {color:#9fb0cc; font-size:.8rem; margin-top:5px; line-height:1.3;}
.gc-pos {color:#34d399;} .gc-neg {color:#f87171;} .gc-mut {color:#9fb0cc;}
.gc-bar {display:flex; height:18px; border-radius:9px; overflow:hidden; margin:8px 0 4px 0; background:#1a2740;}
.gc-bar > div {height:100%;}
.gc-row {display:flex; justify-content:space-between; align-items:center; gap:10px;}
.gc-team {display:flex; align-items:center; gap:12px;}
.gc-chip {display:inline-flex; align-items:center; justify-content:center; width:46px; height:46px; border-radius:50%; font-weight:800; color:#fff; font-size:.85rem; flex:none;}
.gc-chip.sm {width:26px; height:26px; font-size:.62rem;}
.gc-teamname {font-size:1.35rem; font-weight:800; line-height:1.1; color:#fff;}
.gc-meta {color:#9fb0cc; font-size:.85rem;}
.gc-call {border-left:4px solid #34d399; background:#0f1a2e; padding:12px 16px; border-radius:8px; margin:10px 0; line-height:1.5;}
.gc-call.warn {border-left-color:#fbbf24;}
.gc-call.info {border-left-color:#60a5fa;}
.gc-h {font-size:1.05rem; font-weight:700; color:#fff; margin:4px 0 2px 0;}
.gc-small {color:#9fb0cc; font-size:.82rem; line-height:1.4;}
.gc-src {display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #1a2740; font-size:.92rem;}
.gc-src:last-child {border-bottom:none;}
.gc-pill {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:600; background:#1a2740; color:#cbd5e1; margin-right:6px;}
/* horizontal radio groups (game picker, filters) look like pill buttons; the sidebar's vertical list is untouched */
div[role="radiogroup"][aria-orientation="horizontal"] {gap: .45rem; flex-wrap: wrap;}
div[role="radiogroup"][aria-orientation="horizontal"] > label {background:#111b2e; border:1px solid #1e2b45; border-radius:999px; padding:5px 14px; margin:0 !important; cursor:pointer;}
div[role="radiogroup"][aria-orientation="horizontal"] > label:hover {border-color:#34d399;}
div[role="radiogroup"][aria-orientation="horizontal"] > label:has(input:checked) {background:#0f2a22; border-color:#34d399;}
div[role="radiogroup"][aria-orientation="horizontal"] > label > div:first-child {display:none;}
.gc-pill.red {background:#3b1a1f; color:#fca5a5;} .gc-pill.amber {background:#3a2e12; color:#fcd34d;} .gc-pill.green {background:#10301f; color:#6ee7b7;}
"""


def inject_css() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape(str(x))


def team_chip(abbr: str, small: bool = False) -> str:
    c = TEAM_COLORS.get(abbr, "#475569")
    return f'<span class="gc-chip{" sm" if small else ""}" style="background:{c}">{esc(abbr)}</span>'


def card(label: str, value: str, sub: str = "", tone: str = "") -> str:
    tone_cls = {"pos": "gc-pos", "neg": "gc-neg", "mut": "gc-mut"}.get(tone, "")
    return f'<div class="gc-card"><div class="lbl">{esc(label)}</div><div class="val {tone_cls}">{esc(value)}</div><div class="sub">{esc(sub)}</div></div>'


def prob_bar(left_abbr: str, left_p: float, right_abbr: str, right_p: float) -> str:
    lc, rc = TEAM_COLORS.get(left_abbr, "#475569"), TEAM_COLORS.get(right_abbr, "#475569")
    return (f'<div class="gc-row"><div class="gc-teamname">{esc(left_abbr)} {left_p:.0%}</div><div class="gc-teamname">{right_p:.0%} {esc(right_abbr)}</div></div>'
            f'<div class="gc-bar"><div style="width:{left_p * 100:.1f}%;background:{lc}"></div><div style="width:{right_p * 100:.1f}%;background:{rc}"></div></div>')


def callout(text: str, kind: str = "") -> str:
    return f'<div class="gc-call {kind}">{text}</div>'


def pill(text: str, tone: str = "") -> str:
    return f'<span class="gc-pill {tone}">{esc(text)}</span>'


def show(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)
