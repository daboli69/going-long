"""Game Center: plain-English winners, spreads, totals and player projections. Local data only; no jargon; nothing is invented.

Headline numbers follow the betting market (Kalshi) when it exists, because in our tests the market has been at least as accurate as our model.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from scipy.stats import norm

from app import ui
from app.homewin_page import load_archives, read_json
from lab.archive10 import ARCHIVE
from lab.config import CACHE_DIR, LAB_ROOT, RAW_DIR
from lab.ingest import normalize_team

SEASON = 2026
ET = "America/New_York"
GAMES_PATH = CACHE_DIR / "games.parquet"
DEFAULT_SD = {"margin": 13.5, "total": 10.5}
STATUS_PLAIN = {"Out": ("Out", "red", "will not play"), "Injured Reserve": ("Out for weeks", "red", "on injured reserve"),
                "Doubtful": ("Doubtful", "amber", "very unlikely to play"), "Questionable": ("Questionable", "amber", "could go either way")}
STATUS_ORDER = {"Out": 0, "Injured Reserve": 1, "Doubtful": 2, "Questionable": 3}
POS_ORDER = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}
STAT_CODE = {"Passing yards": "pass_yds", "Rushing yards": "rush_yds", "Receiving yards": "rec_yds", "Receptions": "rec", "Catches": "rec"}


# --------------------------------------------------------------------------- loading (cached, local only)

@st.cache_data(show_spinner=False)
def _games(mtime: float) -> pd.DataFrame:
    g = pd.read_parquet(GAMES_PATH)
    g["kickoff_utc"] = pd.to_datetime(g["kickoff_utc"], utc=True)
    g["kickoff_et"] = g["kickoff_utc"].dt.tz_convert(ET)
    return g.sort_values("kickoff_utc").reset_index(drop=True)


def games_table(path: Path = GAMES_PATH) -> pd.DataFrame:
    return _games(path.stat().st_mtime) if path.exists() else pd.DataFrame()


def _fingerprint(root: Path) -> tuple:
    return tuple(sorted((p.name, p.stat().st_mtime_ns) for kind in ("forecast_games", "props_kalshi") for p in (root / kind).glob("*.json")))


@st.cache_data(show_spinner=False)
def _archives(root: str, fp: tuple) -> dict:
    return load_archives(Path(root))


def latest_by_week(arch: dict, kind: str) -> dict:
    out = {}
    for d in sorted(arch.get(kind, []), key=lambda x: x["frozen_at"]):
        out[(int(d["content"]["season"]), int(d["content"]["week"]))] = d
    return out


@st.cache_data(show_spinner=False)
def _injuries(path: str, mtime: float) -> pd.DataFrame:
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for t in c.get("injuries", []):
        for e in t.get("injuries", []):
            a = e.get("athlete", {})
            team = (a.get("team") or {}).get("abbreviation") if isinstance(a.get("team"), dict) else None
            pos = (a.get("position") or {}).get("abbreviation") if isinstance(a.get("position"), dict) else None
            try:
                team = normalize_team(team) if team else team
            except ValueError:
                pass
            rows.append({"team": team, "player": a.get("displayName"), "pos": pos, "status": e.get("status"), "note": e.get("shortComment") or "", "date": e.get("date")})
    return pd.DataFrame(rows)


def injuries_now(raw: Path = RAW_DIR) -> tuple[pd.DataFrame, str | None]:
    files = sorted(glob.glob(str(raw / "archive" / "espn_injuries_*.json")))
    if not files:
        return pd.DataFrame(), None
    f = files[-1]
    return _injuries(f, Path(f).stat().st_mtime), Path(f).name.split("_")[-1][:13]


@st.cache_data(show_spinner=False)
def _preview(fp: tuple) -> pd.DataFrame:
    from lab.props import weekly as W
    return W.load_archive(preview=True)


def preview_table() -> pd.DataFrame:
    try:
        from lab.props import weekly as W
        files = list((W.OUT / "preview").glob("*/*.parquet"))
        return _preview(tuple(sorted((f.name, f.stat().st_mtime_ns) for f in files))) if files else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def _kpis(fp: tuple) -> dict:
    out = {}
    try:
        bt = read_json(LAB_ROOT / "reports" / "homewin_deep" / "backtest.json")
        if bt:
            out["elo_acc_long"] = (bt["models"]["elo"]["accuracy"], bt["models"]["elo"]["n"], bt["window"])
    except Exception:
        pass
    try:
        hist = pd.read_parquet(CACHE_DIR / "homewin_deep" / "kalshi_history.parquet")
        g = pd.read_parquet(GAMES_PATH)
        g = g[g["completed"] & ~g["tie"].astype(bool)].set_index("game_id")
        h = hist[hist["ts"] <= hist["kickoff_utc"] - pd.Timedelta(minutes=90)].sort_values("ts")
        w = h.groupby(["gid", "side"])["mid"].last().unstack()
        p = (w["home"] / (w["home"] + w["away"])).dropna()
        p = p[p.index.isin(g.index)]
        y = g.loc[p.index, "home_win"].astype(float)
        wf = pd.read_parquet(CACHE_DIR / "homewin_deep" / "walk_forward.parquet").set_index("gid")
        common = p.index.intersection(wf.index)
        out["market_acc"] = (float(((p[common] >= 0.5) == (y[common] == 1)).mean()), int(len(common)))
        out["elo_acc_same"] = float(((wf.loc[common, "p_elo"] >= 0.5) == (y[common] == 1)).mean())
    except Exception:
        pass
    fr = read_json(LAB_ROOT / "reports" / "forecast" / "results.json")
    if fr:
        pn = fr.get("pinnacle_descriptive")
        if pn:
            out["margin_miss"] = (pn["margin_mae"]["kalshi"], pn["margin_mae"]["model"], pn["games"])
            out["total_miss"] = (pn["total_mae"]["kalshi"], pn["total_mae"]["model"])
        cov = fr.get("prop_interval_coverage")
        if cov:
            out["range_hit"] = {k: v["raw_80_coverage"] for k, v in cov.items()}
    return out


# --------------------------------------------------------------------------- small helpers

def kickoff_label(ts: pd.Timestamp) -> str:
    return ts.strftime("%a %I:%M %p").replace(" 0", " ")


def p_over(mu: float, sd: float, line: float) -> float:
    return float(1 - norm.cdf((line - mu) / sd))


def pct(x) -> str:
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.0%}"


def team_summary(g: pd.DataFrame, team: str) -> dict:
    d = g[g["completed"] & ((g["home_team"] == team) | (g["away_team"] == team))].sort_values("kickoff_utc")
    w = l = t = 0
    pf = pa = 0.0
    last = []
    for r in d.itertuples(index=False):
        mine, theirs = (r.home_score, r.away_score) if r.home_team == team else (r.away_score, r.home_score)
        pf, pa = pf + mine, pa + theirs
        res = "W" if mine > theirs else "L" if mine < theirs else "T"
        w, l, t = w + (res == "W"), l + (res == "L"), t + (res == "T")
        opp = r.away_team if r.home_team == team else r.home_team
        last.append(f"{res} {int(mine)}-{int(theirs)} {'vs' if r.home_team == team else 'at'} {opp}")
    n = len(d)
    return {"record": f"{w}-{l}" + (f"-{t}" if t else ""), "games": n, "pf": pf / n if n else None, "pa": pa / n if n else None, "last": last[-5:][::-1]}


def best_numbers(row: pd.Series, fz: dict | None) -> dict:
    """The headline win chance, margin and total, with a plain label of where each came from."""
    out = {"p_home": None, "p_label": None, "mu_m": None, "m_label": None, "mu_t": None, "t_label": None, "sd_m": DEFAULT_SD["margin"], "sd_t": DEFAULT_SD["total"]}
    if fz:
        mod = fz["model"]
        out["sd_m"], out["sd_t"] = float(mod["sd_m"]), float(mod["sd_t"])
        if fz.get("kalshi_winner_p_home") is not None:
            out["p_home"], out["p_label"] = float(fz["kalshi_winner_p_home"]), "the Kalshi betting market"
        if fz.get("margin"):
            out["mu_m"], out["m_label"] = float(fz["margin"]["mu_kalshi"]), "the Kalshi betting market"
        if fz.get("total"):
            out["mu_t"], out["t_label"] = float(fz["total"]["mu_kalshi"]), "the Kalshi betting market"
    if out["p_home"] is None and pd.notna(row.get("market_p_home_novig")):
        out["p_home"], out["p_label"] = float(row["market_p_home_novig"]), "sportsbook lines"
    if out["mu_m"] is None and pd.notna(row.get("spread_line")):
        out["mu_m"], out["m_label"] = float(row["spread_line"]), "sportsbook lines"
    if out["mu_t"] is None and pd.notna(row.get("total_line")):
        out["mu_t"], out["t_label"] = float(row["total_line"]), "sportsbook lines"
    if fz:
        mod = fz["model"]
        if out["p_home"] is None:
            out["p_home"], out["p_label"] = float(mod["p_elo"]), "Elo team ratings"
        if out["mu_m"] is None:
            out["mu_m"], out["m_label"] = float(mod["mu_m"]), "our model"
        if out["mu_t"] is None:
            out["mu_t"], out["t_label"] = float(mod["mu_t"]), "our model"
    return out


# --------------------------------------------------------------------------- sections

def _kpi_fp() -> tuple:
    files = [LAB_ROOT / "reports" / "homewin_deep" / "backtest.json", LAB_ROOT / "reports" / "forecast" / "results.json", GAMES_PATH,
             CACHE_DIR / "homewin_deep" / "kalshi_history.parquet", CACHE_DIR / "homewin_deep" / "walk_forward.parquet"]
    return tuple(f.stat().st_mtime_ns if f.exists() else 0 for f in files)


def kpi_row(week_games: pd.DataFrame) -> None:
    k = _kpis(_kpi_fp())
    c = st.columns(4)
    m = k.get("market_acc")
    if m:
        c[0].markdown(ui.card("Game winners picked correctly", f"{m[0]:.0%}", f"The betting market, 2025-26 ({m[1]} games). Elo ratings: {k.get('elo_acc_same', float('nan')):.0%} on the same games."), unsafe_allow_html=True)
    elif k.get("elo_acc_long"):
        a = k["elo_acc_long"]
        c[0].markdown(ui.card("Game winners picked correctly", f"{a[0]:.0%}", f"Elo team ratings over {a[1]:,} games ({a[2]})."), unsafe_allow_html=True)
    mm = k.get("margin_miss")
    if mm:
        c[1].markdown(ui.card("Typical miss on the final margin", f"{mm[0]:.1f} pts", f"Betting market. Our model misses by {mm[1]:.1f} pts (2026, {mm[2]} games). Lower is better.", "mut"), unsafe_allow_html=True)
    rh = k.get("range_hit")
    if rh:
        c[2].markdown(ui.card("Player ranges that held", f"{rh.get('liquid', rh.get('thin', 0)):.0%}", "We say a player's stat lands in our \"likely range\" 8 times in 10. In past tests it did."), unsafe_allow_html=True)
    n = len(week_games)
    first = week_games[week_games["kickoff_utc"] > pd.Timestamp.now(tz="UTC")]
    sub = f"Next kickoff: {kickoff_label(first['kickoff_et'].iloc[0])} ET" if len(first) else "All games for this week are finished."
    c[3].markdown(ui.card("Games this week", str(n), sub), unsafe_allow_html=True)


def reality_check() -> None:
    ui.show(ui.callout("<b>Reality check.</b> Over the last two seasons the betting market has been at least as accurate as our model, so every headline number on this page "
                       "follows the market and our model is shown next to it. Nothing here is betting advice. Open <b>How to read this</b> for plain-English definitions.", "info"))


def header(row: pd.Series, summ: dict) -> None:
    away, home = row["away_team"], row["home_team"]
    done = bool(row["completed"])
    mid = f"Final: {esc_team(away)} {int(row['away_score'])}, {esc_team(home)} {int(row['home_score'])}" if done else f"{row['kickoff_et'].strftime('%A, %b %d')} · {kickoff_label(row['kickoff_et'])} ET"
    stadium = row.get("stadium") or ""
    ui.show(f'<div class="gc-card"><div class="gc-row"><div class="gc-team">{ui.team_chip(away)}<div><div class="gc-teamname">{ui.esc(ui.TEAM_NAMES.get(away, away))}</div>'
            f'<div class="gc-meta">Record {summ[away]["record"]} · away team</div></div></div>'
            f'<div style="text-align:center"><div class="gc-h">{ui.esc(mid)}</div><div class="gc-meta">{ui.esc(stadium)}</div></div>'
            f'<div class="gc-team" style="flex-direction:row-reverse;text-align:right">{ui.team_chip(home)}<div><div class="gc-teamname">{ui.esc(ui.TEAM_NAMES.get(home, home))}</div>'
            f'<div class="gc-meta">Record {summ[home]["record"]} · home team</div></div></div></div></div>')


def esc_team(a: str) -> str:
    return ui.esc(a)


def margin_chart(mu: float, sd: float, home: str, away: str) -> alt.Chart:
    x = np.arange(-40, 41)
    p = norm.cdf((x + 0.5 - mu) / sd) - norm.cdf((x - 0.5 - mu) / sd)
    d = pd.DataFrame({"margin": x, "chance": p, "winner": np.where(x > 0, home, np.where(x < 0, away, "Tie"))})
    colors = alt.Scale(domain=[away, home, "Tie"], range=[ui.TEAM_COLORS.get(away, "#475569"), ui.TEAM_COLORS.get(home, "#475569"), "#64748b"])
    bars = alt.Chart(d).mark_bar().encode(x=alt.X("margin:Q", title=f"Final margin (positive = {home} wins by this many)"),
                                          y=alt.Y("chance:Q", title="Chance", axis=alt.Axis(format="%")), color=alt.Color("winner:N", scale=colors, legend=alt.Legend(title="Winner")),
                                          tooltip=[alt.Tooltip("margin:Q", title="Margin"), alt.Tooltip("chance:Q", title="Chance", format=".1%")])
    rule = alt.Chart(pd.DataFrame({"x": [mu]})).mark_rule(color="#fbbf24", strokeDash=[5, 4]).encode(x="x:Q")
    return (bars + rule).properties(height=250)


def total_chart(mu: float, sd: float) -> alt.Chart:
    x = np.arange(10, 91)
    d = pd.DataFrame({"points": x, "chance": norm.cdf((x + 0.5 - mu) / sd) - norm.cdf((x - 0.5 - mu) / sd)})
    bars = alt.Chart(d).mark_bar(color="#60a5fa").encode(x=alt.X("points:Q", title="Total points by both teams"), y=alt.Y("chance:Q", title="Chance", axis=alt.Axis(format="%")),
                                                         tooltip=[alt.Tooltip("points:Q", title="Total points"), alt.Tooltip("chance:Q", title="Chance", format=".1%")])
    rule = alt.Chart(pd.DataFrame({"x": [mu]})).mark_rule(color="#fbbf24", strokeDash=[5, 4]).encode(x="x:Q")
    return (bars + rule).properties(height=250)


def overview(row: pd.Series, fz: dict | None, summ: dict) -> None:
    away, home = row["away_team"], row["home_team"]
    header(row, summ)
    b = best_numbers(row, fz)
    if b["p_home"] is None:
        st.info("No forecast has been saved for this game yet. The weekly forecast is saved before each week's first kickoff (Run tab of the research page).")
        return
    p_home = b["p_home"]
    favored, p_fav = (home, p_home) if p_home >= 0.5 else (away, 1 - p_home)
    left, right = st.columns([1.15, 1])
    with left:
        ui.show('<div class="gc-card"><div class="gc-h">Who is likely to win?</div>' + ui.prob_bar(away, 1 - p_home, home, p_home) +
                f'<div class="gc-small">Based on {ui.esc(b["p_label"])}. The percentages are each team\'s chance to win.</div></div>')
        srcs = [("Betting market (Kalshi)", fz and fz.get("kalshi_winner_p_home")), ("Our model", fz and fz["model"]["p_win"]), ("Elo team ratings", fz and fz["model"]["p_elo"]),
                ("ESPN's forecast (FPI)", fz and fz.get("fpi_p_home"))]
        rows = "".join(f'<div class="gc-src"><span>{ui.esc(n)}</span><span><b>{ui.esc(home)} {pct(v)}</b> · {ui.esc(away)} {pct(1 - v if v is not None else None)}</span></div>' for n, v in srcs if v is not None)
        if rows:
            ui.show(f'<div class="gc-card" style="margin-top:10px"><div class="gc-h">What each source says</div>{rows}</div>')
            vals = [v for _, v in srcs if v is not None]
            spread_pts = (max(vals) - min(vals)) * 100
            ui.show(ui.callout(f"The sources {'<b>agree</b> closely' if spread_pts <= 6 else '<b>disagree</b> by ' + format(spread_pts, '.0f') + ' points'} on this game. "
                               f"{ui.esc(ui.TEAM_NAMES.get(favored, favored))} are favored at about {p_fav:.0%}.", "" if spread_pts <= 6 else "warn"))
    with right:
        c1, c2, c3 = st.columns(3)
        mu_m, mu_t = b["mu_m"], b["mu_t"]
        if mu_m is not None:
            fav_m = home if mu_m >= 0 else away
            c1.markdown(ui.card("Expected margin", f"{fav_m} by {abs(mu_m):.1f}", f"Based on {b['m_label']}. A margin of 3 = a field goal; 7 = a touchdown."), unsafe_allow_html=True)
        if mu_t is not None:
            c2.markdown(ui.card("Expected total points", f"{mu_t:.1f}", f"Both teams combined, based on {b['t_label']}."), unsafe_allow_html=True)
        if mu_m is not None and mu_t is not None:
            hp, ap = (mu_t + mu_m) / 2, (mu_t - mu_m) / 2
            c3.markdown(ui.card("Expected score", f"{ap:.0f} - {hp:.0f}", f"{away} {ap:.1f}, {home} {hp:.1f}. A typical outcome, not a guarantee."), unsafe_allow_html=True)
        if fz and fz.get("margin"):
            m = fz["margin"]
            diff = m["mu_model"] - m["mu_kalshi"]
            if m["abstain"]:
                msg = f"<b>No strong opinion.</b> Our model expects the margin within {abs(diff):.1f} points of the market, so we go with the market."
                kind = ""
            else:
                who = home if diff > 0 else away
                msg = (f"<b>Our model disagrees with the market.</b> It likes {ui.esc(who)} by about {abs(diff):.1f} more points than the market does. "
                       "In our tests this kind of disagreement has <i>not</i> beaten the market, so treat it as something to think about, not a tip.")
                kind = "warn"
            ui.show(ui.callout(msg, kind))
        if mu_m is not None:
            st.altair_chart(margin_chart(mu_m, b["sd_m"], home, away), use_container_width=True)
            st.caption(f"How the final margin could play out. Taller bars are more likely. The dashed line is the expected margin. About {p_fav:.0%} of the weight is on {favored} winning.")
    if b["mu_m"] is not None and b["mu_t"] is not None:
        st.markdown("##### How the game could play out")
        mu_m, mu_t, sm, stt = b["mu_m"], b["mu_t"], b["sd_m"], b["sd_t"]
        fav, sign = (home, 1) if mu_m >= 0 else (away, -1)
        line_t = round(mu_t * 2) / 2
        close = norm.cdf((3.5 - mu_m) / sm) - norm.cdf((-3.5 - mu_m) / sm)
        rows = [("Game is decided by 3 points or fewer", close),
                (f"{fav} wins by 7 or more", p_over(sign * mu_m, sm, 6.5)),
                (f"{fav} wins by 10 or more", p_over(sign * mu_m, sm, 9.5)),
                (f"Underdog wins outright", 1 - (p_home if fav == home else 1 - p_home)),
                (f"Both teams combine for more than {line_t:g} points", p_over(mu_t, stt, line_t)),
                (f"Both teams combine for fewer than {line_t:g} points", 1 - p_over(mu_t, stt, line_t))]
        t = pd.DataFrame({"What happens": [r[0] for r in rows], "Chance": [r[1] for r in rows]})
        t["Chance"] = t["Chance"].map(lambda v: f"{v:.0%}")
        a, bcol = st.columns([1, 1])
        a.dataframe(t, hide_index=True, use_container_width=True)
        bcol.altair_chart(total_chart(mu_t, stt), use_container_width=True)
        bcol.caption("How many total points could be scored. The dashed line is the expected total.")
    if bool(row["completed"]):
        won = home if row["home_score"] > row["away_score"] else away if row["away_score"] > row["home_score"] else "Tie"
        ui.show(ui.callout(f"<b>Result:</b> {ui.esc(won)} won. The market's favorite was {ui.esc(favored)}, so the favorite {'won' if won == favored else 'did not win'}.", "info"))


def matchup(row: pd.Series, g: pd.DataFrame, summ: dict) -> None:
    away, home = row["away_team"], row["home_team"]
    cols = st.columns(2)
    for col, team in zip(cols, (away, home)):
        s = summ[team]
        with col:
            last = "".join(f'<div class="gc-src"><span>{ui.esc(x)}</span></div>' for x in s["last"]) or '<div class="gc-small">No games played yet.</div>'
            ui.show(f'<div class="gc-card"><div class="gc-team">{ui.team_chip(team)}<div><div class="gc-teamname">{ui.esc(ui.TEAM_NAMES.get(team, team))}</div>'
                    f'<div class="gc-meta">{s["record"]} this season</div></div></div>'
                    f'<div class="gc-small" style="margin-top:8px">Scores <b>{(s["pf"] or 0):.1f}</b> points per game and allows <b>{(s["pa"] or 0):.1f}</b> (over {s["games"]} games).</div>'
                    f'<div class="gc-h" style="margin-top:10px">Last 5 games, newest first</div>{last}</div>')
    inj, stamp = injuries_now()
    st.markdown("##### Who is hurt?")
    if inj.empty:
        st.info("No injury information saved yet.")
        return
    st.caption(f"From ESPN's injury list (checked {stamp} UTC). Players listed Out or Doubtful are removed from our player projections; Questionable players are kept.")
    cols = st.columns(2)
    for col, team in zip(cols, (away, home)):
        d = inj[(inj["team"] == team) & inj["status"].isin(STATUS_PLAIN)].copy()
        d["o"] = d["status"].map(STATUS_ORDER)
        d["p"] = d["pos"].map(POS_ORDER).fillna(9)
        d = d.sort_values(["o", "p"]).head(14)
        with col:
            st.markdown(f"**{ui.TEAM_NAMES.get(team, team)}**")
            if d.empty:
                st.caption("No notable injuries listed.")
            for r in d.itertuples(index=False):
                lab, tone, expl = STATUS_PLAIN[r.status]
                note = (r.note[:150] + "…") if len(r.note) > 150 else r.note
                ui.show(f'<div class="gc-src"><span><b>{ui.esc(r.player)}</b> <span class="gc-meta">{ui.esc(r.pos or "")}</span><div class="gc-small">{ui.esc(note)}</div></span>'
                        f'<span>{ui.pill(lab, tone)}</span></div>')


def props(row: pd.Series, props_fz: dict | None, preview: pd.DataFrame) -> None:
    gid = row["game_id"]
    st.caption("Each row is one player and one kind of stat. \"Typical projection\" is our middle estimate; \"likely range\" is where we expect it to land 8 times in 10. "
               "Where a betting market exists we show its line and both chances of reaching it.")
    if preview.empty or gid not in set(preview["game_id"]):
        st.info("No player projections have been saved for this game yet.")
        return
    from lab.props import weekly as W
    sub = preview[preview["game_id"] == gid].drop(columns=[c for c in ("_src",) if c in preview])
    t = W.projection_table(sub, keep_pid=True)
    stats = ["All"] + sorted(t["Stat"].unique())
    pick = st.radio("Show", stats, horizontal=True, key=f"gc_stat_{gid}")
    team_pick = st.radio("Team", ["Both", row["away_team"], row["home_team"]], horizontal=True, key=f"gc_team_{gid}")
    if pick != "All":
        t = t[t["Stat"] == pick]
    if team_pick != "Both":
        t = t[t["Team"] == team_pick]
    ladders = {}
    if props_fz:
        for lad in props_fz["content"]["ladders"]:
            if lad["gid"] == gid:
                ladders[(lad["pid"], lad["stat"])] = lad
    out = []
    for _, r in t.sort_values("v2 median", ascending=False).head(40).iterrows():
        lad = ladders.get((r["Player ID"], STAT_CODE.get(r["Stat"], "")))
        line = mchance = ochance = None
        if lad:
            cand = [th for th in lad["thresholds"] if th.get("mid") is not None]
            if cand:
                th = min(cand, key=lambda x: abs(x["mid"] - 0.5))
                line, mchance, ochance = th["k"], th["mid"], th.get("p_corr", th.get("p_sim"))
        small = r["Stat"] in ("Receptions", "Catches")
        out.append({"Player": r["Player"], "Team": r["Team"], "Stat": r["Stat"], "Typical projection": f"{r['v2 median']:.1f}" if small else f"{r['v2 median']:.0f}",
                    "Likely range (8 in 10)": str(r["v2 10-90%"]).replace(" - ", " to "), "Market line": f"{line:g}+" if line is not None else "—",
                    "Market's chance": pct(mchance), "Our chance": pct(ochance)})
    if not out:
        st.info("No players match this filter.")
        return
    st.dataframe(pd.DataFrame(out), hide_index=True, use_container_width=True, height=min(740, 38 * len(out) + 40))
    st.caption("A dash means there is no active betting market for that player. Players reported Out or Doubtful are not included. Market chances come from Kalshi prices saved before the game.")


def spread_total(row: pd.Series, fz: dict | None) -> None:
    away, home = row["away_team"], row["home_team"]
    if not fz or not (fz.get("margin") or fz.get("total")):
        st.info("No market ladder was saved for this game, so there is nothing to compare yet.")
        return
    mod = fz["model"]
    ui.show(ui.callout("<b>How to read this.</b> Each row asks a yes/no question about the final score. The market column is what betting-market prices imply; "
                       "our model column is our own estimate. Big gaps are rare, and when they appear the market has usually been right.", "info"))
    a, b = st.columns(2)
    if fz.get("margin"):
        m = fz["margin"]
        th = sorted(m["thresholds"], key=lambda x: abs(x["c"] - m["mu_kalshi"]))[:9]
        th = sorted(th, key=lambda x: x["c"])
        d = pd.DataFrame({f"Question": [f"{home} wins by more than {t['c']:g}" if t["c"] >= 0 else f"{home} loses by fewer than {abs(t['c']):g}" for t in th],
                          "Market says": [pct(t["p_kalshi"]) for t in th],
                          "Our model says": [pct(p_over(mod["mu_m"], mod["sd_m"], t["c"])) for t in th]})
        with a:
            st.markdown("##### The spread: who wins and by how much")
            st.dataframe(d, hide_index=True, use_container_width=True)
    if fz.get("total"):
        m = fz["total"]
        th = sorted(sorted(m["thresholds"], key=lambda x: abs(x["c"] - m["mu_kalshi"]))[:9], key=lambda x: x["c"])
        d = pd.DataFrame({"Question": [f"Total points go over {t['c']:g}" for t in th], "Market says": [pct(t["p_kalshi"]) for t in th],
                          "Our model says": [pct(p_over(mod["mu_t"], mod["sd_t"], t["c"])) for t in th]})
        with b:
            st.markdown("##### The total: how many points in the game")
            st.dataframe(d, hide_index=True, use_container_width=True)


def guide() -> None:
    k = _kpis(_kpi_fp())
    st.markdown("#### What is this page?")
    st.write("Game Center shows, for every NFL game this week: who is likely to win, by how many points, how many points will be scored, and what individual players might do. "
             "Everything comes from data saved on this computer.")
    st.markdown("#### How much should I trust it?")
    bullets = []
    if k.get("market_acc"):
        bullets.append(f"The betting market picked the winner correctly {k['market_acc'][0]:.0%} of the time in 2025-26; simple Elo ratings got {k.get('elo_acc_same', 0):.0%} on the same games.")
    if k.get("margin_miss"):
        bullets.append(f"On the final margin, the market missed by {k['margin_miss'][0]:.1f} points on average and our model by {k['margin_miss'][1]:.1f}.")
    if k.get("range_hit"):
        bullets.append(f"Our \"likely range\" for players held the real result {k['range_hit'].get('liquid', 0):.0%} of the time for well-traded players.")
    bullets.append("So: the market is the benchmark. Our model is a sensible second opinion, and it is most useful for players that no betting market covers.")
    for x in bullets:
        st.write("• " + x)
    st.markdown("#### Words used on this page")
    for term, text in ui.GLOSSARY:
        with st.expander(term):
            st.write(text)
    st.markdown("#### What this page does not do")
    st.write("It does not give betting advice, place bets, or claim to beat the market. It never connects to a sportsbook or a trading account.")


# --------------------------------------------------------------------------- page

def render(archive_root: Path = ARCHIVE, games_path: Path = GAMES_PATH) -> None:
    G = games_table(games_path)
    st.markdown("<h1 style='margin-bottom:0'>NFL Game Center</h1>", unsafe_allow_html=True)
    st.caption("Who is likely to win, by how much, and what each player might do. Plain English, local data, no betting advice.")
    if G.empty:
        st.warning("The games table is missing. Open Data Manager and click Download / Update NFL Data.")
        return
    G = G[(G["season"] == SEASON) & (G["game_type"] == "REG")]
    fp = _fingerprint(archive_root)
    arch = _archives(str(archive_root), fp)
    fz_w, pr_w = latest_by_week(arch, "forecast_games"), latest_by_week(arch, "props_kalshi")
    now = pd.Timestamp.now(tz="UTC")
    upcoming = G[G["kickoff_utc"] > now]
    default_week = int(upcoming["week"].min()) if len(upcoming) else int(G["week"].max())
    weeks = sorted(G["week"].unique())
    top = st.columns([1.2, 3])
    week = top[0].selectbox("Week", weeks, index=weeks.index(default_week), format_func=lambda w: f"Week {int(w)}", key="gc_week")
    wk = G[G["week"] == week].reset_index(drop=True)
    kpi_row(wk)
    reality_check()
    fzr = fz_w.get((SEASON, int(week)))
    pfr = pr_w.get((SEASON, int(week)))
    games_fz = {g["gid"]: g for g in fzr["content"]["games"]} if fzr else {}
    labels = {r.game_id: f"{r.away_team} @ {r.home_team} · {kickoff_label(r.kickoff_et)}" for r in wk.itertuples(index=False)}
    nxt = wk[wk["kickoff_utc"] > now]
    default_game = (nxt["game_id"].iloc[0] if len(nxt) else wk["game_id"].iloc[0]) if len(wk) else None
    if not len(wk):
        st.info("No games found for this week.")
        return
    gids = list(labels)
    gid = st.radio("Pick a game", gids, index=gids.index(default_game), horizontal=True, format_func=labels.get, key=f"gc_game_{int(week)}")
    row = wk[wk["game_id"] == gid].iloc[0]
    fz = games_fz.get(gid)
    if fzr:
        saved = pd.Timestamp(fzr["frozen_at"]).tz_convert(ET).strftime("%a %b %d, %I:%M %p")
        st.caption(f"Forecast saved {saved} ET, before the week's first kickoff. It is never edited afterward.")
    summ = {t: team_summary(G, t) for t in (row["away_team"], row["home_team"])}
    tabs = st.tabs(["Overview", "Team matchup", "Player props", "Spread & total", "How to read this"])
    with tabs[0]:
        overview(row, fz, summ)
    with tabs[1]:
        matchup(row, G, summ)
    with tabs[2]:
        props(row, pfr, preview_table())
    with tabs[3]:
        spread_total(row, fz)
    with tabs[4]:
        guide()
