"""Game Center page for the Streamlit dashboard: same saved numbers as the web app (nba_lab.gamecenter_data), drawn with nba_lab.ui."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from nba_lab import gamecenter_data as D
from nba_lab import ui


def _pct(x) -> str:
    return "—" if x is None else f"{x:.0%}"


def render() -> None:
    meta = D.meta()
    if not meta["ok"]:
        ui.show(ui.callout(ui.esc(meta["reason"]), "warn"))
        return
    dates = sorted(set(meta["dates"]) | {meta["today"]})
    day = st.selectbox("Game date (Eastern)", dates, index=dates.index(meta["default_date"]),
                       format_func=lambda d: pd.Timestamp(d).strftime("%a, %b %d") + (" (today)" if d == meta["today"] else ""))
    games = D.day_games(day)
    if not games:
        ui.show(ui.callout("No games on this date.", "info"))
        return
    labels = {g["gid"]: f'{g["away"]} at {g["home"]}' for g in games}
    gid = st.radio("Game", list(labels), format_func=labels.get, horizontal=True, label_visibility="collapsed")
    d = D.game_detail(gid)
    away, home = d["away"], d["home"]

    when = f'Final: {away} {d["away_score"]:.0f}, {home} {d["home_score"]:.0f}' if d["completed"] else f'{d["date_label"]} · {d["time_label"]} ET'
    ui.show(f'<div class="gc-card"><div class="gc-row">'
            f'<div class="gc-team">{ui.team_chip(away)}<div><div class="gc-teamname">{ui.esc(d["away_name"])}</div><div class="gc-meta">{d["records"][away]} · away</div></div></div>'
            f'<div class="gc-h">{ui.esc(when)}</div>'
            f'<div class="gc-team" style="flex-direction:row-reverse;text-align:right">{ui.team_chip(home)}<div><div class="gc-teamname">{ui.esc(d["home_name"])}</div><div class="gc-meta">{d["records"][home]} · home</div></div></div>'
            f'</div></div>')

    if not d["has_forecast"]:
        ui.show(ui.callout("No forecast is saved for this game yet. Forecasts are saved by the daily refresh before tipoff.", "info"))
        return
    h = d["headline"]
    if d.get("result"):
        r = d["result"]
        ui.show(ui.callout(f'{r["winner"]} won. The favorite ({h["favored"]}) {"won" if r["favorite_won"] else "lost"}.', "" if r["favorite_won"] else "warn"))

    left, right = st.columns(2)
    with left:
        v = d["vote"]
        vote = f'{v["home"]}-{v["away"]} tie' if v["tie"] else f'{home if v["home"] > v["away"] else away} {max(v["home"], v["away"])} of 6'
        rows = "".join(f'<div class="gc-src"><span>{ui.esc(s["name"])}</span><b>{_pct(s["p_home"])}</b></div>' for s in d["sources"])
        ui.show(f'<div class="gc-card"><div class="lbl gc-mut">Win chance</div>{ui.prob_bar(away, 1 - h["p_home"], home, h["p_home"])}'
                f'<div class="gc-small">Source: {ui.esc(h["p_label"])}.</div>'
                f'<div class="gc-src" style="margin-top:8px"><span>Model vote</span><b>{vote}</b></div>'
                + (f'<div class="gc-small" style="margin-top:8px">Research forecasts, {home} win chance (not used above)</div>{rows}' if rows else "")
                + '</div>')
    with right:
        e = d.get("expected")
        if e:
            fav = home if e["margin"] >= 0 else away
            ui.show(ui.card("Expected score", f'{away} {e["away_pts"]:.0f}, {home} {e["home_pts"]:.0f}',
                            f'Spread: {fav} by {abs(e["margin"]):.1f} · Total: {e["total"]:.1f}. 8 in 10 games like this land between '
                            f'{e["total_range"][0]:.0f} and {e["total_range"][1]:.0f} total points. Separate score model, not a sportsbook line.'))
        else:
            ui.show(ui.callout("No score projection is saved for this game.", "info"))

    st.markdown("")
    st.markdown("**Six models**")
    models = pd.DataFrame(d["models"]).sort_values("p_home", ascending=False).rename(columns={"name": "Model", "p_home": f"{home} win chance"})
    st.dataframe(models, hide_index=True, use_container_width=True,
                 column_config={f"{home} win chance": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1)})
    st.caption(f'Highest and lowest differ by {d["disagreement_points"]:.0f} points. All six learn from the same games, so 6 of 6 agreeing is not a sure thing.')

    cols = st.columns(2)
    for col, abbr in zip(cols, (away, home)):
        with col:
            s = d["matchup"][abbr]
            inj = d["injuries"]["teams"].get(abbr, [])
            body = "".join(f'<div class="gc-src"><span>{ui.esc(r["player"])}</span>{ui.pill(r["status"], r["tone"])}</div>' for r in inj) \
                or '<div class="gc-small">No one listed on the latest saved check. That is not a confirmed lineup.</div>'
            ui.show(f'<div class="gc-card"><div class="gc-team">{ui.team_chip(abbr, small=True)}<div class="gc-h">{ui.esc(D.team(abbr)[0])}</div></div>'
                    f'<div class="gc-small">Record {s["record"]} · last {len(s["last"])}: {" ".join(s["last"]) or "none"}</div>'
                    f'<div class="gc-h" style="margin-top:8px">Injury list</div>{body}</div>')
    st.caption("Injury list from ESPN. The original forecast does not use injuries. " + meta["reality_check"].split(". ")[0] + ".")
