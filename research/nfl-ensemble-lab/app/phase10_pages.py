"""Local, read-only Phase 10 views. Rendering never fetches, fits or promotes."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import numpy as np
import pandas as pd
import streamlit as st
from lab.props.amendment2.sheets import skew_flags

PATTERN = re.compile(r"^(?:projections|leans)_(\d{4})_w(\d+)(?:_r(\d+))?(?:_(\d{8}T\d+Z))?$", re.I)


def sheet_key(path):
    m = PATTERN.fullmatch(Path(path).stem)
    if not m:
        return None
    season, week, revision, stamp = m.groups()
    created = datetime.min
    if stamp:
        created = datetime.strptime(stamp[:15], "%Y%m%dT%H%M%S").replace(microsecond=int((stamp[15:-1]+"000000")[:6]))
    return int(season), int(week), int(revision or 0), created


def latest_sheet(directory, kind):
    paths = [p for p in Path(directory).glob(kind+"_*.csv") if sheet_key(p) is not None]
    return max(paths, key=sheet_key) if paths else None


def matching_sheet(directory, kind, reference):
    key = sheet_key(reference)
    paths = [p for p in Path(directory).glob(kind+"_*.csv") if sheet_key(p) is not None and sheet_key(p)[:3] == key[:3]]
    return max(paths, key=sheet_key) if paths else None


@st.cache_data(show_spinner=False)
def read_table(path: str, mtime_ns: int):
    """mtime invalidates contents, but never determines which revision is latest."""
    p = Path(path)
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p, low_memory=False)


def load(path):
    return read_table(str(path), path.stat().st_mtime_ns)


def truth(series):
    return series.astype(str).str.lower().isin(("true", "1", "1.0"))


def prepare(frame):
    d = skew_flags(frame)
    for col in ("our_mean", "our_median"):
        fallback = "projection" if col == "our_mean" else "q50"
        if col not in d:
            d[col] = d.get(fallback, np.nan)
    if "quote_time" in d:
        dates = pd.to_datetime(d.quote_time, utc=True, errors="coerce", format="mixed")
        d["line_age_hours"] = (pd.Timestamp.now(tz="UTC")-dates).dt.total_seconds()/3600
        d.loc[d.line_age_hours.gt(24), "line_status"] = "stale"
        d.loc[dates.isna() | d.line_age_hours.lt(0), "line_status"] = "unavailable"
    return d


def filter_players(frame, *, include_types=(), include_stale=False, include_skew=True):
    d = frame.copy()
    if "line_type" in d:
        d = d[d.line_type.isin(["consensus", *include_types])]
        if "is_consensus_representative" in d:
            d = d[~d.line_type.eq("consensus") | truth(d.is_consensus_representative)]
    if not include_stale and "line_status" in d:
        d = d[d.line_status.eq("current")]
    if not include_skew and "skew_artifact_flag" in d:
        d = d[~truth(d.skew_artifact_flag)]
    keys = [c for c in ("game_id", "pid", "stat") if c in d]
    if len(keys) == 3 and not include_types:
        d = d.drop_duplicates(keys)
    return d


PLAYER_COLUMNS = ["name", "team", "stat", "consensus_line", "our_mean", "our_median", "q10", "q50", "q90",
    "p_over", "p_under", "p_push", "gap", "no_vig_market_probability", "member_min", "member_max",
    "skew_artifact_flag", "stability_flag", "coherence_flag", "scenario_sensitivity", "confidence_tier",
    "line_type", "line_status", "line_age_hours", "reconciled_projection", "other_players_projection"]


def show_table(d, key, columns=None):
    selected = [c for c in (columns or list(d.columns)) if c in d]
    view = d[selected].copy()
    st.dataframe(view, hide_index=True, use_container_width=True)
    st.download_button("Download filtered CSV", view.to_csv(index=False).encode("utf-8"), key+".csv", "text/csv", key=key)


def spread(gid, margin):
    if pd.isna(margin):
        return "unavailable"
    away, home = str(gid).split("_")[-2:]
    return f"{home if margin >= 0 else away} {-abs(margin):+.1f}"


def game_table(frame):
    if "row_type" not in frame:
        return pd.DataFrame()
    rows = []
    for gid, z in frame[frame.row_type.eq("game")].groupby("game_id"):
        r = {"game": " @ ".join(str(gid).split("_")[-2:]), "game_id": gid}
        for stat in ("margin", "total"):
            a = z[z.stat.eq(stat)].copy()
            if a.empty:
                continue
            a["_rep"] = truth(a.get("is_consensus_representative", pd.Series(False, index=a.index)))
            v = a.sort_values("_rep", ascending=False, kind="stable").iloc[0]
            fmt = lambda x: spread(gid, x) if stat == "margin" else x
            r.update({"market_"+stat: fmt(v.get("consensus_line", np.nan)),
                "independent_"+stat: fmt(v.get("projection", np.nan)),
                "market_anchored_"+stat: fmt(v.get("market_anchored_projection", np.nan)),
                stat+"_gap": v.get("gap"), stat+"_P_cover" if stat == "margin" else "total_P_over":v.get("p_over"),
                stat+"_line_status":v.get("line_status")})
            for q in ("q10", "q50", "q90"):
                r[stat+"_"+q] = v.get(q)
        rows.append(r)
    return pd.DataFrame(rows)


GLOSSARY = {
    "name":"Player name; unresolved identities are not guessed.", "team":"Player's frozen as-of team.",
    "stat":"Passing/rushing/receiving yards, receptions, passing TDs, rushing/receiving anytime TD, or first offensive TD.",
    "consensus_line":"Most common latest traditional-book line; DFS and exchanges excluded. Lowest line breaks a tie.",
    "our_mean":"Average of the predictive distribution; can differ substantially from its median.",
    "our_median":"Predictive 50th percentile. Binary probability rows have no continuous median.",
    "q10 / q50 / q90":"10th / 50th / 90th predictive outcome percentiles, not confidence limits on model accuracy.",
    "p_over / p_under":"Probability strictly above / below this row's line. Neither includes a push.",
    "p_push":"Probability equal to the line. p_over_no_push conditions on avoiding a push.",
    "gap":"Our mean minus a consensus line; ATD uses probability minus a real quoted probability. Units differ. No alternate-line gaps.",
    "no_vig_market_probability":"Two-sided market probability with the quoted margin removed; unavailable with only one side.",
    "member_min / member_max":"Smallest / largest member point projection; agreement is descriptive, not a probability.",
    "skew_artifact_flag":"Mean and median are on opposite sides of the line; an apparent lean may be caused by skew.",
    "stability_flag":"Whether structural outputs moved beyond fixed tolerances across simulation seeds; not accuracy.",
    "coherence_flag":"Eligible-player sums differ from team totals. ATD sums are expected distinct scorers, not TD counts.",
    "scenario_sensitivity":"Changes under role/script interventions. Missing scenarios remain unknown.",
    "confidence_tier":"Investigation readiness, never win probability. A needs current consensus, stable/coherent/agreeing/robust evidence; B has uncertainty; C lacks usable comparison evidence.",
    "line_type":"Consensus: modal traditional line. Alternate: other traditional line. DFS-pickem: pick'em platform. Exchange: trading venue.",
    "line_status / line_age_hours":"Current only with a known nonfuture quote timestamp <=24 hours old. Stale/unavailable stays explicit.",
    "independent":"Football-only game anchor, with no market feature. Default learned props are independent.",
    "market-anchored":"Structural simulator scores adjusted to market points; this is not an independent forecast.",
    "market-informed":"Labelled retrospective ablation adding closing-implied team points; never the independent default.",
    "game ranges":"Margin quantiles use home-minus-away points; displayed spreads use favored team plus signed handicap. Total quantiles are combined points. Game P(cover) refers to the home side; market is shown first.",
    "reconciled_projection / other_players_projection":"Separate shadow accounting values and explicit unlisted-player remainder; originals remain visible.",
}


def diagnostics(frame):
    st.subheader("Slate diagnostics")
    if "row_type" not in frame:
        return
    players = filter_players(frame[frame.row_type.eq("player")])
    if not players.empty:
        z = players.copy()
        z["mean_under_line"] = z.our_mean < z.get("market_line", z.get("consensus_line", np.nan))
        z["median_under_line"] = z.our_median < z.get("market_line", z.get("consensus_line", np.nan))
        st.dataframe(z.groupby("stat").agg(under_side_share=("mean_under_line","mean"), median_under_side_share=("median_under_line","mean"), average_P_over=("p_over","mean"), skew_share=("skew_artifact_flag","mean"), rows=("stat","size")), use_container_width=True)
        atd = z[z.stat.eq("anytime_td")]
        if not atd.empty:
            delta = (atd.our_mean-atd.get("no_vig_market_probability", np.nan)).mean()
            st.write("Average anytime-TD probability minus two-sided no-vig market:", "unavailable" if pd.isna(delta) else f"{delta:+.3f}")
            if pd.isna(delta) and "market_probability" in atd:
                raw_delta = (atd.our_mean-atd.market_probability).mean()
                st.write("Versus available raw implied probability (one-sided vig may remain):", "unavailable" if pd.isna(raw_delta) else f"{raw_delta:+.3f}")
    atd = frame[frame.row_type.eq("player") & frame.stat.eq("anytime_td")].drop_duplicates(["game_id","pid","stat"])
    if not atd.empty:
        st.caption("Sum of anytime probabilities = expected distinct eligible scorers, not expected TD count; missing players excluded.")
        st.dataframe(atd.groupby(["game_id","team"]).our_mean.sum().rename("expected_distinct_eligible_scorers"), use_container_width=True)
    st.write("Raw source line-status counts:", frame.get("line_status", pd.Series(dtype=str)).fillna("unavailable").value_counts().to_dict())
    dates = pd.to_datetime(frame.get("quote_time", pd.Series(dtype=str)), utc=True, errors="coerce", format="mixed")
    if dates.notna().any():
        latest = dates.max()
        st.caption(f"Latest quote: {latest.isoformat()}; age {(pd.Timestamp.now(tz='UTC')-latest).total_seconds()/3600:.1f} hours.")


def render(kind="projections", reports=None):
    from lab.config import REPORTS_DIR
    reports = Path(reports) if reports is not None else REPORTS_DIR
    title = "Leans" if kind == "leans" else "Projections"
    st.title(title)
    st.warning("Phase 10 shadow research, unvalidated (review 2026-10-20): no preregistered gate passed. Game spread/total gaps are not signals: total blend weight was 0, margin blend failed, and closing lines beat independent projections. Anytime-TD probabilities ran below market on average; every reviewed team failed coherence. Many under-side rows reflect mean/median skew. Not betting advice.")
    path = latest_sheet(reports, kind)
    if path is None:
        st.info(f"No {kind} sheets available. Run run_week_projections.bat after reviewing its options.")
        return
    d = prepare(load(path))
    if d.empty:
        st.info("The latest sheet is empty; no projections are available.")
        return
    if not {"row_type","game_id","stat"} <= set(d):
        st.info("Sheet is missing row classification/game/stat fields; no table can be displayed.")
        return
    evidence = matching_sheet(reports, "leans", path)
    source = prepare(load(evidence)) if evidence else d
    if {"pid","projection","gap","line_type","line_status","coherence_flag","q10","q90"} <= set(d):
        from lab.props.amendment2.sheets import leans
        maps = []
        for column in ("stability_flag", "scenario_sensitivity"):
            maps.append({(r.game_id, str(r.pid) if pd.notna(r.pid) else "", r.stat):getattr(r,column)
                for r in source.itertuples()} if column in source else {})
        d["pid"] = d.pid.fillna("")
        d = skew_flags(leans(d, *maps))
    st.caption(f"Source: {path.name}; training cutoff: {', '.join(d.get('training_cutoff_date',pd.Series(['unknown'])).dropna().astype(str).unique())}. View only; no fetch, fit or promotion on rerun.")
    with st.expander("Glossary: columns and model variants"):
        for label, explanation in GLOSSARY.items():
            st.markdown(f"**{label}:** {explanation}")
    with st.expander("Slate diagnostics"):
        diagnostics(d)
    players, games, first, scenarios, coherence = st.tabs(["Players", "Games", "First TD", "Scenarios", "Coherence"])
    with players:
        include_types = [name for name in ("alternate","DFS-pickem","exchange") if st.checkbox("Include "+name, key=kind+name)]
        stale = st.checkbox("Include stale / unavailable rows", key=kind+"stale")
        skew = st.checkbox("Include skew-flagged rows", value=kind!="leans", key=kind+"skew")
        full = st.checkbox("Show all columns", key=kind+"raw")
        z = filter_players(d[d.row_type.eq("player")],include_types=include_types,include_stale=stale,include_skew=skew)
        for col, label in (("team","Team"),("stat","Stat")):
            if col in z:
                selection = st.multiselect(label, sorted(z[col].dropna().astype(str).unique()), key=kind+col)
                if selection:
                    z = z[z[col].astype(str).isin(selection)]
        st.caption(f"{len(z)} rows. Default: current representative consensus, one row per player/stat/game. Optional venue rows remain separate.")
        show_table(z,kind+"_players",None if full else PLAYER_COLUMNS)
    with games:
        st.caption("Market first, independent model second. Gaps are diagnostics, not validated signals. Home-side P(cover); margin ranges are home minus away.")
        show_table(game_table(d),kind+"_games")
    with first:
        st.info("First offensive rushing/receiving TD in regulation only; passing/defensive/special-teams TDs excluded. Unknown quote settlement prevents price comparisons.")
        z = d[d.stat.eq("first_td")].drop_duplicates([c for c in ("game_id","pid","stat") if c in d])
        show_table(z,kind+"_first",["game_id"]+PLAYER_COLUMNS)
    with scenarios:
        st.warning("Scenario, not forecast. Structural role/script interventions hold unmodelled efficiencies fixed. Unknown replacements remain unknown; assumption-based rows are not verified lineups.")
        companion = path.with_name(path.stem+"_scenarios.csv")
        candidates = sorted((reports.parent/"artifacts/props/phase10/amendment2/part2").glob("*/simulations/scenario_changes.parquet"))
        source = companion if companion.exists() else (candidates[-1] if candidates else None)
        if source:
            s = load(source)
            st.caption(f"Scenario source: {source.name}. Only matching slate games are shown; these are separate role assumptions, not updated forecasts.")
            if "game_id" in s:
                s = s[s.game_id.isin(d.game_id)]
                if not s.empty:
                    selected = st.selectbox("Scenario game", sorted(s.game_id.dropna().unique()), key=kind+"scenario_game")
                    s = s[s.game_id.eq(selected)]
                else:
                    st.info("No scenario game matches this slate; unrelated runs are excluded.")
            if {"pid","game_id","name"} <= set(d) and {"pid","game_id"} <= set(s) and "name" not in s:
                names=d[["game_id","pid","name"]].drop_duplicates(["game_id","pid"])
                s=s.merge(names,on=["game_id","pid"],how="left",validate="many_to_one")
                anonymous=s.pid.astype(str).str.startswith("assumption:")
                s.loc[anonymous,"name"]="Assumed replacement; real identity unknown"
            show_table(s,kind+"_scenarios")
        else:
            st.info("No scenario output is available for this sheet.")
    with coherence:
        projection = path if kind=="projections" else matching_sheet(reports,"projections",path)
        source = projection.with_name(projection.stem+"_coherence.csv") if projection else None
        if source and source.exists():
            st.caption("Team projection versus eligible-player sum, by game/team. Missing players and expected-distinct-scorer accounting matter. Originals are not replaced.")
            show_table(load(source),kind+"_coherence")
            remainder=projection.with_name(projection.stem+"_reconciliation.csv")
            if remainder.exists():
                st.caption("Separate shadow reconciliation: original eligible sum, reconciled sum and explicit other-player remainder. This accounting does not establish accuracy or replace the original forecast.")
                show_table(load(remainder),kind+"_remainder")
        else:
            st.info("No matching per-team coherence file is available.")
