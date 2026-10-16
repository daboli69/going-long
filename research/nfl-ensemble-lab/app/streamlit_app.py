"""NFL Ensemble Lab dashboard. Start with launch_lab.bat (or `streamlit run app/streamlit_app.py`)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from lab import data_pipeline as dp  # noqa: E402
from lab import ensemble as ens  # noqa: E402
from lab import features as F  # noqa: E402
from lab import availability, models, sources, training, weekly  # noqa: E402
from lab.config import MODELS_DIR, REPORTS_DIR, SNAPSHOTS_DIR  # noqa: E402

st.set_page_config(page_title="NFL Ensemble Lab", page_icon="🏈", layout="wide")

PAGES = ["Home", "Data Manager", "Train Models", "Model Leaderboard", "Model Debate",
         "Weekly Predictions", "Upset Discovery Lab", "Reports"]
PCT = st.column_config.ProgressColumn


def name_of(key: str) -> str:
    return ens.MODEL_NAMES.get(key) or ens.ENSEMBLE_NAMES.get(key) or {
        "base_home_prior": "Baseline: home-field prior", "base_pointdiff": "Baseline: point-diff logistic",
        "market": "Sportsbook closing no-vig"}.get(key, key)


def logger(box):
    lines: list[str] = []

    def log(msg: str):
        lines.append(str(msg))
        box.code("\n".join(lines[-25:]))
    return log


@st.cache_data(show_spinner=False)
def cached_run(version):
    return training.load_run(version)


@st.cache_data(show_spinner=False)
def cached_fs(mtime):
    return dp.load_feature_store()


def feature_store():
    if not dp.FEATURE_STORE.exists():
        return None
    return cached_fs(dp.FEATURE_STORE.stat().st_mtime)


@st.cache_resource(show_spinner=False)
def cached_bundle(version):
    return training.load_bundle(version)


@st.cache_data(show_spinner="Running all six models ...")
def cached_week(version, season, week, fs_mtime):
    fs = dp.load_feature_store()
    games = fs[(fs["season"] == season) & (fs["week"] == week)]
    return weekly.predict_games(games, cached_bundle(version), cached_run(version))


def need(cond, msg):
    if not cond:
        st.info(msg)
        st.stop()


def freshness_panel():
    """Data and injury-report freshness, shown on Home, Weekly and Debate pages."""
    st_ = dp.load_status()
    inj = st_.get("injury") or {}
    c = st.columns(4)
    c[0].metric("Data refreshed (UTC)", (st_.get("refreshed_at") or "never")[:16].replace("T", " "))
    c[1].metric("Official injury file (UTC)", (inj.get("live_injury_file_downloaded_at") or "none")[:16].replace("T", " "))
    c[2].metric("ESPN injury feed (UTC)", (inj.get("espn_retrieved_at") or "none")[:16].replace("T", " "))
    c[3].metric("Archived injury snapshots", inj.get("archived_snapshots", 0))
    ts = st_.get("refreshed_at")
    if ts and (pd.Timestamp.now(tz="UTC") - pd.Timestamp(ts)).total_seconds() > 24 * 3600:
        st.warning("Data is more than 24 hours old. Refresh before relying on upcoming-game predictions.")


def fmt_metric(v, pct=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return f"{v:.1%}" if pct else f"{v:.4f}"


# ----------------------------------------------------------------------------- pages

def page_home():
    st.title("🏈 NFL Ensemble Lab")
    st.caption("Local research lab: six machine-learning models forecast NFL winners and margins. "
               "Research only. Not betting advice and not connected to GOING production.")
    status, version = dp.load_status(), training.current_version()
    c = st.columns(4)
    c[0].metric("Last data refresh (UTC)", status.get("refreshed_at", "never")[:16].replace("T", " "))
    c[1].metric("Completed games", status.get("completed_games", 0))
    c[2].metric("Seasons", f"{status['seasons'][0]}-{status['seasons'][-1]}" if status.get("seasons") else "none")
    c[3].metric("Model version", version or "not trained")
    if not status:
        st.warning("No data yet. Open **Data Manager** and click **Download / Update NFL Data**.")
    elif not version:
        st.warning("Data is ready. Open **Train Models** and click **Train All Six Models**.")
    if version:
        run = cached_run(version)
        s, lb = run["summary"], run["leaderboard"]
        st.subheader("Latest evaluation")
        ch = s["champion"]
        c = st.columns(4)
        c[0].metric("Research champion", name_of(ch))
        for i, split in enumerate(("validation", "test", "prospective"), 1):
            r = lb[(lb["split"] == split) & (lb["method"] == ch)]
            if len(r):
                c[i].metric(f"{split.title()} accuracy / log loss", f"{r['accuracy'].iloc[0]:.1%}", f"log loss {r['log_loss'].iloc[0]:.3f}", delta_color="off")
        st.caption("Champion chosen on 2023-2024 validation before 2025 test was scored. 2026 = prospective season to date.")
    snaps = weekly.list_snapshots()
    if snaps:
        st.subheader("Latest weekly snapshot")
        st.write(f"`{snaps[0].parent.name}` · {snaps[0].name}")
    st.subheader("Freshness")
    freshness_panel()
    warns = status.get("warnings", []) + dp.load_validation().get("errors", [])
    if warns:
        with st.expander(f"Warnings ({len(warns)})"):
            for w in warns:
                st.write("• " + w)


def page_data():
    st.title("Data Manager")
    st.write("Free sources, cached locally. Completed seasons are downloaded once; the current season and schedule refresh when older than "
             f"{sources.LIVE_MAX_AGE_HOURS} hours.")
    c = st.columns(3)
    log_box = st.empty()
    if c[0].button("⬇️ Download Historical Data", use_container_width=True, help="Downloads anything missing (first run: ~250 MB, a few minutes)"):
        with st.status("Downloading and building the feature store ...", expanded=True):
            dp.refresh_data(progress=logger(log_box))
        st.cache_data.clear()
        st.success("Data ready.")
    if c[1].button("🔄 Update NFL Data", use_container_width=True, help="Forces a fresh download of the schedule and the current season"):
        with st.status("Updating ...", expanded=True):
            sources.download_games(force=True, progress=logger(log_box))
            dp.refresh_data(progress=logger(log_box))
        st.cache_data.clear()
        st.success("Updated.")
    if c[2].button("✅ Validate Data", use_container_width=True):
        fs = feature_store()
        need(fs is not None, "Download data first.")
        rep = dp.validate(pd.read_parquet(dp.GAMES_TABLE), pd.read_parquet(dp.TEAM_GAMES), fs, cross_check=True, progress=lambda m: None)
        (st.success if rep["ok"] else st.error)(f"Validation {'passed' if rep['ok'] else 'failed'}: {len(rep['errors'])} errors, {len(rep['warnings'])} warnings")
    st.subheader("Sources")
    st.dataframe(pd.DataFrame([s.__dict__ for s in sources.SOURCES]), hide_index=True, use_container_width=True)
    rep = dp.load_validation()
    if rep:
        st.subheader("Coverage by season")
        st.dataframe(pd.DataFrame(rep["coverage"]), hide_index=True, use_container_width=True)
        st.subheader("Data quality")
        for e in rep["errors"]:
            st.error(e)
        for w in rep["warnings"]:
            st.warning(w)
        cc = rep.get("cross_check") or {}
        st.write(f"Cross-check vs api.nfldata.org: **{cc.get('status')}**, compared {cc.get('compared', 0)} games, "
                 f"{cc.get('mismatches', 0)} score mismatches. _{cc.get('note', '')}_")
        st.write("Most-missing model features (share of rows):")
        st.dataframe(pd.Series(rep["most_missing_features"], name="missing share"), use_container_width=True)
    man = sources.load_manifest()
    if man:
        with st.expander("Download manifest (provenance)"):
            st.dataframe(pd.DataFrame([v for k, v in man.items() if not k.startswith("_")]), hide_index=True, use_container_width=True)
    if dp.INJURY_COVERAGE.exists():
        st.subheader("Injury report coverage (rows usable only if available before kickoff)")
        st.dataframe(pd.read_csv(dp.INJURY_COVERAGE), hide_index=True, use_container_width=True)
        st.caption("2016-2024: nflverse rows with date_modified before kickoff. 2025: the published file has no row timestamps, "
                   "so it is excluded. 2026+: only snapshots this lab archived before kickoff. ESPN data is live monitoring only.")
    if dp.FEATURE_STORE.exists():
        with st.expander("Feature catalog (source, formula, pregame availability)"):
            st.dataframe(pd.read_csv(dp.CACHE_DIR / "feature_catalog.csv"), hide_index=True, use_container_width=True)


def page_train():
    st.title("Train Models")
    fs = feature_store()
    need(fs is not None, "Download data first (Data Manager).")
    groups = F.feature_groups(fs.columns)
    st.write("Protocol: tune on 2016-2022 → choose calibration and champion on 2023-2024 → score the untouched 2025 test once → "
             "track 2026 prospectively → refit production models on all completed games.")
    c1, c2 = st.columns(2)
    start = c1.selectbox("First training season", [2016, 2017, 2018], index=0)
    picked = c1.multiselect("Models", list(ens.MODEL_KEYS), default=list(ens.MODEL_KEYS), format_func=name_of)
    chosen = c2.multiselect("Feature groups", list(groups), default=list(F.DEFAULT_GROUPS))
    c2.caption(f"{len(F.select_features(fs.columns, chosen))} features selected")
    st.caption("Training settings (hyperparameter grids, calibration methods, walk-forward seasons) are fixed in lab/models.py and "
               "lab/config.py so runs stay comparable. Expect ~10-30 minutes on a Ryzen 7 3700X.")
    b = st.columns(3)
    if b[0].button("🚀 Train All Six Models", type="primary", use_container_width=True, disabled=not picked or not chosen):
        bar, box = st.progress(0.0), st.empty()
        with st.status("Training (tuning, walk-forward evaluation, calibration, ensembles, production refit) ...", expanded=True):
            res = training.run_training(groups=tuple(chosen), model_keys=tuple(picked), progress=logger(box),
                                        progress_frac=lambda f: bar.progress(min(f, 1.0)), training_from=start)
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success(f"Trained version {res['summary']['version']}. Champion: {name_of(res['summary']['champion'])}")
    if b[1].button("📊 Evaluate Models", use_container_width=True):
        st.info("Evaluation runs as part of training (walk-forward). See Model Leaderboard for the saved results.")
    if b[2].button("💾 Save Models", use_container_width=True):
        v = training.current_version()
        st.info(f"Models are saved automatically after every run: {MODELS_DIR / v}" if v else "No trained models yet.")
    v = training.current_version()
    if v:
        st.subheader("Saved model versions")
        vers = sorted([p.name for p in MODELS_DIR.glob("v*") if (p / "bundle.joblib").exists()], reverse=True)
        st.write(", ".join(f"**{x}** (current)" if x == v else x for x in vers))
        s = cached_run(v)["summary"]
        st.json({"hyperparameters": s["params"], "calibration": s["calibration"], "ensemble_weights": s["weights"]}, expanded=False)


def page_leaderboard():
    st.title("Model Leaderboard")
    v = training.current_version()
    need(v, "Train models first.")
    run = cached_run(v)
    lb, sel = run["leaderboard"].copy(), run["selection"]
    split = st.radio("Evaluation split", ["validation", "test", "prospective", "development"], horizontal=True,
                     help="validation = 2023-24 (used for selection) · test = 2025 (untouched) · prospective = 2026 to date · development = 2018-22 walk-forward")
    part = lb[lb["split"] == split].copy()
    part["name"] = part["method"].map(name_of)
    part["champion"] = part["method"] == sel.get("champion")
    st.dataframe(part[["name", "champion", "n", "accuracy", "accuracy_ci", "log_loss", "log_loss_ci", "brier", "ece"]].sort_values("log_loss"),
                 hide_index=True, use_container_width=True,
                 column_config={"accuracy": PCT("accuracy", format="%.1f%%" if False else "%.3f", min_value=0, max_value=1)})
    st.caption("Lower log loss / Brier is better. CI = 95% game-level bootstrap. Majority vote has accuracy only. "
               "Market = closing no-vig benchmark without timestamps; it is not a model input.")
    seasons = run["seasons"]
    if len(seasons):
        st.subheader("Season-by-season accuracy")
        keys = st.multiselect("Methods", sorted(seasons["method"].unique()), default=[sel.get("champion"), "market", "base_pointdiff", "logreg"], format_func=name_of)
        chart = alt.Chart(seasons[seasons["method"].isin(keys)].assign(name=lambda d: d["method"].map(name_of))).mark_line(point=True).encode(
            x=alt.X("season:O"), y=alt.Y("accuracy:Q", scale=alt.Scale(zero=False), axis=alt.Axis(format="%")), color="name:N",
            tooltip=["name", "season", alt.Tooltip("accuracy:Q", format=".1%"), alt.Tooltip("log_loss:Q", format=".3f"), "n"])
        st.altair_chart(chart, use_container_width=True)
    cal = run["calibration"]
    if len(cal):
        st.subheader("Calibration")
        m = st.selectbox("Method", sorted(cal["method"].unique()), format_func=name_of, index=sorted(cal["method"].unique()).index(sel.get("champion")) if sel.get("champion") in set(cal["method"]) else 0)
        c = cal[(cal["method"] == m)]
        base = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(strokeDash=[4, 4], color="gray").encode(x="x", y="y")
        pts = alt.Chart(c).mark_circle().encode(x=alt.X("mean_pred:Q", title="predicted home-win probability"),
                                                y=alt.Y("observed:Q", title="observed home-win rate"), size="n:Q", color="split:N",
                                                tooltip=["range", "n", alt.Tooltip("mean_pred", format=".2f"), alt.Tooltip("observed", format=".2f")])
        st.altair_chart(base + pts, use_container_width=True)
    st.subheader("Margin models (expected home margin, points)")
    mg = run["margins"]
    st.dataframe(mg[mg["split"] == split][["name", "n", "mae", "rmse", "winner_acc"]] if len(mg) else mg, hide_index=True, use_container_width=True)
    ag = run["agreement"]
    if len(ag):
        st.subheader("How often models vote the same way (validation + test)")
        ag = ag.assign(a=ag["model_a"].map(name_of), b=ag["model_b"].map(name_of))
        st.altair_chart(alt.Chart(ag).mark_rect().encode(x=alt.X("a:N", title=None), y=alt.Y("b:N", title=None),
                        color=alt.Color("vote_agreement:Q", scale=alt.Scale(scheme="blues")),
                        tooltip=["a", "b", alt.Tooltip("vote_agreement:Q", format=".1%"), alt.Tooltip("prob_correlation:Q", format=".2f")]),
                        use_container_width=True)
    imp = run["importance"]
    if len(imp):
        st.subheader("Global feature importance (permutation, out-of-sample)")
        m = st.selectbox("Model", list(ens.MODEL_KEYS), format_func=name_of, key="imp")
        st.dataframe(imp[imp["model"] == m].nlargest(15, "importance")[["feature", "importance", "std", "scope"]], hide_index=True, use_container_width=True)


def week_picker(fs, key):
    s0, w0 = weekly.default_week(fs)
    seasons = sorted(fs["season"].unique(), reverse=True)
    c = st.columns(2)
    season = c[0].selectbox("Season", seasons, index=seasons.index(s0) if s0 in seasons else 0, key=f"s{key}")
    weeks = sorted(fs[fs["season"] == season]["week"].unique())
    week = c[1].selectbox("Week", weeks, index=weeks.index(w0) if season == s0 and w0 in weeks else 0, key=f"w{key}")
    return int(season), int(week)


def page_debate():
    st.title("Model Debate")
    fs, v = feature_store(), training.current_version()
    need(fs is not None and v, "Download data and train models first.")
    season, week = week_picker(fs, "deb")
    freshness_panel()
    table, debates = cached_week(v, season, week, dp.FEATURE_STORE.stat().st_mtime)
    need(len(debates), "No games for this week.")
    labels = [d["matchup"] + ("  (played)" if table.iloc[i]["completed"] else "") for i, d in enumerate(debates)]
    i = st.selectbox("Matchup", range(len(debates)), format_func=lambda j: labels[j])
    d, row = debates[i], table.iloc[i]
    for w in d["warnings"]:
        st.warning(w)
    if row["completed"]:
        st.info(f"Final: {row['away_team']} {int(row['away_score'])} @ {row['home_team']} {int(row['home_score'])}. "
                "Models were trained on data that includes this game; check the leaderboard for genuine out-of-sample results.")
    t1, t2, t3, t4, t5 = st.tabs(["1 · Independent forecasts", "2 · Statistical arguments", "3 · Disagreements", "4 · Vote", "5 · Consensus"])
    with t1:
        r1 = pd.DataFrame(d["round1"])
        st.caption("Each model forecast on its own; no model sees another model's prediction for this game.")
        st.dataframe(r1[["name", "family", "winner", "p_home", "p_away", "vote", "val_accuracy", "val_log_loss"]], hide_index=True, use_container_width=True,
                     column_config={"p_home": PCT(f"P({row['home_team']} wins)", format="%.3f", min_value=0, max_value=1),
                                    "p_away": PCT(f"P({row['away_team']} wins)", format="%.3f", min_value=0, max_value=1),
                                    "val_accuracy": st.column_config.NumberColumn("2023-24 accuracy", format="%.3f"),
                                    "val_log_loss": st.column_config.NumberColumn("2023-24 log loss", format="%.3f")})
        bars = alt.Chart(r1).mark_bar().encode(x=alt.X("p_home:Q", scale=alt.Scale(domain=[0, 1]), title=f"P({row['home_team']} wins)"),
                                                y=alt.Y("name:N", sort=None, title=None), color=alt.Color("vote:N", scale=alt.Scale(domain=["home", "away"], range=["#2E7D32", "#C62828"])))
        rule = alt.Chart(pd.DataFrame({"x": [0.5]})).mark_rule(strokeDash=[4, 4]).encode(x="x")
        st.altair_chart(bars + rule, use_container_width=True)
    with t2:
        st.caption("Game-specific (local) attributions from each fitted model, shown in each method's own units. "
                   "Positive = pushes toward the home team. Global importance is on the Leaderboard page.")
        cols = st.columns(2)
        for j, k in enumerate(d["round2"]):
            e = d["round2"][k]
            with cols[j % 2].container(border=True):
                st.markdown(f"**{ens.MODEL_NAMES[k]}** · {e['method']} ({e['unit']})")
                if "rules" in e:
                    st.markdown("Decision path: " + " → ".join(f"`{r}`" for r in e["rules"]) +
                                f"  \nLeaf: {e['leaf_samples']} training games, home won {e['leaf_home_rate']:.1%}")
                st.dataframe(pd.DataFrame(e["top"]), hide_index=True, use_container_width=True,
                             column_config={"value": st.column_config.NumberColumn(format="%.3f"), "contribution": st.column_config.NumberColumn(format="%+.4f")})
    with t3:
        r3 = d["round3"]
        st.write(f"Probability range across models: **{r3['prob_range']:.1%}** (std {r3['prob_std']:.1%}).")
        st.write("Dissenting from the majority: " + (", ".join(r3["dissenters"]) or "none (unanimous)"))
        if r3["features_separating_blocs"]:
            st.write("Features weighted most differently by the two voting blocs (share of each model's total attribution):")
            st.dataframe(pd.DataFrame(r3["features_separating_blocs"]), hide_index=True, use_container_width=True)
        st.write("Votes by model family:")
        st.json(r3["family_votes"], expanded=True)
        st.caption(r3["note"])
        if r3["historical_pairwise_agreement"]:
            st.write("Historical vote agreement between models (validation + test seasons):")
            h = pd.DataFrame(r3["historical_pairwise_agreement"])
            h["model_a"], h["model_b"] = h["model_a"].map(name_of), h["model_b"].map(name_of)
            st.dataframe(h, hide_index=True, use_container_width=True)
        st.write("Validation calibration error (ECE, lower is better):")
        st.json({name_of(k): (round(v, 4) if v is not None else None) for k, v in r3["calibration_ece_validation"].items()})
    with t4:
        r4 = d["round4"]
        c = st.columns(3)
        c[0].metric(f"{row['home_team']} votes", r4["home_votes"])
        c[1].metric(f"{row['away_team']} votes", r4["away_votes"])
        c[2].metric("Majority", r4["winner_team"] + (" (tie broken by equal average)" if r4["tie"] else ""))
        if r4["unanimous"]:
            st.success("Unanimous vote.")
        if r4["tie"]:
            st.warning("3-3 tie: the models are split.")
        st.caption(r4["note"] + " Logistic Regression and the Single-Layer NN usually vote together because they are the same model family.")
    with t5:
        r5 = d["round5"]
        c = st.columns(4)
        c[0].metric("Champion method", name_of(r5["champion_method"]))
        c[1].metric(f"P({row['home_team']} wins)", f"{r5['champion_p_home']:.1%}")
        c[2].metric("Ensemble winner", r5["ensemble_winner"])
        c[3].metric("Predicted home margin", f"{r5['margin_ensemble']:+.1f}")
        if r5["vote_vs_ensemble_disagree"]:
            st.warning(f"Majority vote picks {r5['majority_winner']} but the probability ensemble picks {r5['ensemble_winner']}.")
        st.dataframe(pd.DataFrame({"method": ["Equal-weight average", "Validation-weighted average", "Out-of-fold stacking", "Sportsbook no-vig (current line)"],
                                   "p_home": [r5["equal_average"], r5["weighted_average"], r5["stacking"], r5["market_p_home_novig"]]}),
                     hide_index=True, column_config={"p_home": PCT("P(home wins)", format="%.3f", min_value=0, max_value=1)})
        st.write("Margin models (expected home margin):")
        st.dataframe(pd.Series(r5["margin_models"], name="points").round(1), use_container_width=True)
        if r5["spread_line"] is not None:
            st.caption(f"Current spread line (home perspective, from nfldata at refresh time): {r5['spread_line']:+.1f}. "
                       "A margin forecast is an expected value, not a final score.")


def page_weekly():
    st.title("Weekly Predictions")
    fs, v = feature_store(), training.current_version()
    need(fs is not None and v, "Download data and train models first.")
    season, week = week_picker(fs, "wk")
    freshness_panel()
    refresh = st.checkbox("Refresh data before predicting", value=True)
    if st.button("▶️ Generate Weekly Predictions", type="primary"):
        box = st.empty()
        with st.status(f"Predicting {season} week {week} ...", expanded=True):
            out = weekly.run_weekly(season, week, refresh=refresh, progress=logger(box))
        st.cache_data.clear()
        st.session_state["weekly_paths"] = out["paths"]
        st.success("Snapshot saved (immutable) and reports exported.")
    table, _ = cached_week(v, season, week, dp.FEATURE_STORE.stat().st_mtime)
    view = pd.DataFrame({
        "game": table["away_team"] + " @ " + table["home_team"],
        **{ens.MODEL_NAMES[k]: np.where(table[f"p_{k}"] > 0.5, table["home_team"], table["away_team"]) + " " +
           (np.maximum(table[f"p_{k}"], 1 - table[f"p_{k}"]) * 100).round(0).astype(int).astype(str) + "%" for k in ens.MODEL_KEYS if f"p_{k}" in table},
        "vote": table["vote_label"], "majority": table["majority_winner"], "ensemble winner": table["ensemble_winner"],
        "P(home)": table["p_champion"], "home margin": table["margin_ensemble"].round(1),
        "disagreement": table["prob_spread"], "warnings": table["data_warnings"]})
    st.dataframe(view, hide_index=True, use_container_width=True,
                 column_config={"P(home)": PCT(format="%.3f", min_value=0, max_value=1), "disagreement": st.column_config.NumberColumn(format="%.2f")})
    st.caption("Preview computed live. Click Generate to save a timestamped snapshot and Excel/CSV/JSON files.")
    games = fs[(fs["season"] == season) & (fs["week"] == week)]
    with st.expander("Injury & QB monitor (live context; ESPN and depth charts are NOT model inputs)", expanded=True):
        try:
            mon = availability.live_monitor(games, games, pd.read_parquet(dp.GAMES_TABLE))
        except Exception as exc:
            mon = []
            st.warning(f"Availability monitor unavailable: {exc}")
        if mon:
            view_m = pd.DataFrame([{"team": m["team"], "projected QB": m["projected_qb"], "QB uncertain": m["qb_uncertain"],
                                    "QB flags": "; ".join(m["qb_flags"]), "official final report": m["official_report_final"],
                                    "key listed players": "; ".join(f"{x['player']} {x['pos']} {x['status']}" for x in m["key_listed_players"]),
                                    "ESPN out/IR": "; ".join(f"{x['player']} {x['position']} {x['status']}" for x in m["espn_out_or_ir"][:8])}
                                   for m in mon])
            st.dataframe(view_m, hide_index=True, use_container_width=True)
            if not any(m["official_report_final"] for m in mon):
                st.warning("No final official injury designations are available for this week yet; injury features are missing "
                           "(the models fall back to their no-injury-information behaviour).")
    paths = st.session_state.get("weekly_paths")
    if paths:
        c = st.columns(3)
        for i, k in enumerate(("excel", "csv", "json")):
            p = Path(paths[k])
            c[i].download_button(f"Download {p.suffix}", p.read_bytes(), file_name=p.name)


def page_upset():
    st.title("Upset Discovery Lab")
    st.info("Phase 2 has not been built yet. No upset patterns have been searched for, validated or displayed. "
            "Phase 1 already saves what Phase 2 needs: the pregame feature store, walk-forward out-of-sample probabilities "
            "for every model and ensemble, closing no-vig market probabilities, and immutable weekly snapshots.")
    v = training.current_version()
    if v:
        st.write(f"Out-of-sample predictions for Phase 2: `{training.RUNS_DIR / v / 'oof_predictions.parquet'}`")


def page_reports():
    st.title("Reports")
    v = training.current_version()
    if st.button("📘 Build NFL_Ensemble_Training_Results.xlsx", disabled=not v):
        from lab.reports import training_workbook
        with st.spinner("Writing workbook ..."):
            st.success(f"Saved {training_workbook(v)}")
    files = sorted([p for p in REPORTS_DIR.glob("*") if p.suffix in (".xlsx", ".csv", ".json")], key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        st.info("No reports yet.")
    for p in files:
        c = st.columns([4, 1])
        c[0].write(f"`{p.name}` · {p.stat().st_size / 1024:.0f} KB")
        c[1].download_button("Download", p.read_bytes(), file_name=p.name, key=str(p))
    st.caption(f"Folder: {REPORTS_DIR} · Snapshots: {SNAPSHOTS_DIR}")


with st.sidebar:
    st.header("NFL Ensemble Lab")
    page = st.radio("Go to", PAGES, label_visibility="collapsed")
    st.caption("Phase 1 · research only")

try:
    {"Home": page_home, "Data Manager": page_data, "Train Models": page_train, "Model Leaderboard": page_leaderboard,
     "Model Debate": page_debate, "Weekly Predictions": page_weekly, "Upset Discovery Lab": page_upset, "Reports": page_reports}[page]()
except FileNotFoundError as exc:
    st.warning(str(exc))
except Exception as exc:  # show a readable error instead of a blank page
    st.error(f"Something went wrong: {exc}")
    st.exception(exc)
