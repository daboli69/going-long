"""NFL Ensemble Lab dashboard. Start with launch_lab.bat (or `streamlit run app/streamlit_app.py`)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json  # noqa: E402

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
         "Weekly Predictions", "Prospective Performance", "Prediction Archive", "Data Freshness", "Baseline Research",
         "Long-Run Research", "Advanced Football Intelligence",
         "Upset Discovery", "Upset Explorer", "Research Validation", "Research Runs", "Reports"]
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
        if r3.get("agreement_note"):
            st.success(r3["agreement_note"])
        st.write(f"Probability range across models: **{r3['prob_range']:.1%}** (std {r3['prob_std']:.1%}).")
        if r3.get("factor_net_by_model"):
            st.write("**Football factors behind each model's forecast** (net share of the model's own attributions; "
                     "positive = toward the home team):")
            st.dataframe(pd.DataFrame(r3["factor_net_by_model"]), hide_index=True, use_container_width=True)
        if r3.get("factors_separating_blocs_by_factor"):
            top = r3["factors_separating_blocs_by_factor"][0]
            st.write(f"The factor that most separates the two voting blocs is **{top['factor']}** "
                     f"(home-voting models {top['home_bloc_net']:+.3f} vs away-voting models {top['away_bloc_net']:+.3f}).")
            st.dataframe(pd.DataFrame(r3["factors_separating_blocs_by_factor"]), hide_index=True, use_container_width=True)
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
        if r5.get("challengers"):
            st.write("Shadow challengers (experimental, not the primary forecast):")
            st.dataframe(pd.DataFrame([{"challenger": k, "p_home": v} for k, v in r5["challengers"].items()]), hide_index=True)
        else:
            st.caption("No shadow challenger is registered; the champion is the only ensemble.")
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


def _exp_or_stop():
    from lab import discovery as D
    exps = [r["experiment"] for r in D.list_experiments() if r.get("created_at")]
    need(exps, "No discovery experiment yet. Open Research Runs and click Run discovery experiment.")
    exps = sorted(set(exps), reverse=True)
    cur = D.current_experiment()
    exp = st.selectbox("Experiment", exps, index=exps.index(cur) if cur in exps else 0)
    return D, D.load_experiment(exp)


def page_discovery():
    st.title("Upset Discovery")
    st.caption("Automated search for situations where underdogs win more or less often than a baseline probability says. "
               "Only candidates that pass independent validation are trusted. Zero validated patterns is a legitimate result.")
    D, e = _exp_or_stop()
    s = e["summary"]
    for bl, info in s["baselines"].items():
        cols = st.columns(len(info["origins"]) + 1)
        cols[0].markdown(f"**Baseline: {bl}**  \n{info['rows']} games  \nmodel {info['model_version']}")
        for i, (o, v) in enumerate(info["origins"].items(), 1):
            cols[i].metric(f"{o}: validated / carried / tested", f"{v['n_validated']} / {v['n_carried']} / {v['n_tested']}")
    st.info("Verdicts: " + "; ".join(f"{bl}: patterns {i['verdict']['validated_patterns']}, GBM {i['verdict']['gbm_residual']}"
                                      for bl, i in s["baselines"].items()))
    keys = sorted(e["catalogs"])
    c1, c2, c3 = st.columns([2, 2, 3])
    key = c1.selectbox("Catalog (baseline_origin)", keys)
    status = c2.multiselect("Status", ["validated", "rejected", "exploratory (not carried)"], default=["validated", "rejected"])
    q = c3.text_input("Search descriptions / features", "")
    cat = e["catalogs"][key]
    view = cat[cat["status"].isin(status)]
    if q:
        view = view[view["description"].str.contains(q, case=False, na=False) | view["features"].str.contains(q, case=False, na=False)]
    show = [c for c in ["status", "method", "description", "disc_n", "disc_underdog_win_rate", "disc_baseline_underdog_prob", "disc_z",
                        "disc_q_bh_nominal", "val_n", "val_underdog_win_rate", "val_baseline_underdog_prob", "val_logodds_effect",
                        "val_effect_ci_low", "val_effect_ci_high", "val_effect_shrunk", "val_p_holm", "val_season_sign_share",
                        "season_effects", "rejection_reasons", "provenance"] if c in view]
    st.dataframe(view[show], hide_index=True, use_container_width=True)
    st.caption(f"{len(view)} rows. Click a column header to sort. Discovery p/q values are nominal (adaptive search); "
               "val_p_holm is the multiple-testing-adjusted validation test. Effects are log-odds relative to the baseline.")
    inter = e["interactions"].get(key)
    if inter is not None and len(inter):
        st.subheader("Strongest feature interactions (discovery-period residual model)")
        st.dataframe(inter, hide_index=True, use_container_width=True)


def page_explorer():
    st.title("Upset Explorer")
    fs, v = feature_store(), training.current_version()
    need(fs is not None and v, "Download data and train models first.")
    from lab import discovery as D
    need(D.current_experiment(), "No discovery experiment yet. Run one from Research Runs.")
    season, week = week_picker(fs, "ux")
    table, _ = cached_week(v, season, week, dp.FEATURE_STORE.stat().st_mtime)
    games = fs[(fs["season"] == season) & (fs["week"] == week)]
    adj, signals = D.upcoming_adjustments(table, games)
    labels = [f"{r.away_team} @ {r.home_team}" for r in adj.itertuples()]
    i = st.selectbox("Game", range(len(adj)), format_func=lambda j: labels[j])
    r = adj.iloc[i]
    c = st.columns(4)
    c[0].metric(f"Original P({r.home_team} wins)", f"{r.p_home_original:.1%}")
    c[1].metric("Validated-pattern adjusted", f"{r.p_home_adj_patterns:.1%}", f"{r.adj_patterns:+.1%}", delta_color="off")
    c[2].metric("GBM-residual adjusted", f"{r.p_home_adj_gbm:.1%}", f"{r.adj_gbm:+.1%}", delta_color="off")
    c[3].metric("Underdog (baseline)", r.underdog)
    st.info(f"Primary forecast: **{r.primary_forecast}**. Pattern layer: {r.patterns_verdict}. GBM layer: {r.gbm_verdict}.")
    st.subheader("Why the probability changed (or did not)")
    sig = signals[i]
    if not any(x["status"] == "applies" for x in sig):
        st.write("No validated discovery applies to this game, so the validated-pattern layer makes **no adjustment**.")
    if abs(r.adj_gbm) < 1e-9:
        st.write("The GBM residual layer's shrinkage factor chosen on validation is 0, so it makes **no adjustment**.")
    if sig:
        st.dataframe(pd.DataFrame(sig), hide_index=True, use_container_width=True)
    if r.missing_gbm_inputs:
        st.warning(f"{r.missing_gbm_inputs} residual-model inputs are missing for this game (e.g. {r.missing_examples}).")
    st.subheader("Availability context (injury and QB)")
    g = games.iloc[i]
    ctx = {k: g.get(k) for k in ("home_qb_projected_out", "away_qb_projected_out", "home_qb_questionable", "away_qb_questionable",
                                 "home_qb_offseason", "away_qb_offseason", "home_inj_report_available", "away_inj_report_available",
                                 "home_inj_out_off", "away_inj_out_off", "home_inj_out_def", "away_inj_out_def",
                                 "inj_mx_home_ol_out_x_opp_pass_rush", "inj_mx_away_ol_out_x_opp_pass_rush") if k in g}
    st.dataframe(pd.Series(ctx, name="value").astype(str), use_container_width=True)
    st.caption("Injury loads are missing (not zero) until a final official report exists before kickoff. "
               "Injury-feature patterns are tested by the engine when historically valid (2016-2024 reports).")


def page_validation():
    st.title("Research Validation")
    D, e = _exp_or_stop()
    s = e["summary"]
    rows = []
    for bl, info in s["baselines"].items():
        for o, v in info["origins"].items():
            for period, ev in v["evals"].items():
                for layer in ("baseline", "validated_patterns", "gbm_residual"):
                    x = ev.get(layer, {})
                    rows.append({"baseline": bl, "origin": o, "period": period, "seasons": str(ev.get("seasons")), "layer": layer,
                                 "n": x.get("n"), "log_loss": x.get("log_loss"), "brier": x.get("brier"), "ece": x.get("ece"),
                                 "delta_log_loss": x.get("delta_log_loss"), "delta_95ci": str(x.get("delta_ci", "")),
                                 "mean_abs_adjustment": x.get("mean_abs_adjustment")})
    st.subheader("Baseline vs adjusted (held-out seasons)")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("evaluation = seasons untouched by discovery, validation and shrinkage choice. diagnostic_2025 was already inspected "
               "in Phase 1, so it is supporting evidence only. Negative delta = better than baseline.")
    for bl, info in s["baselines"].items():
        for o, v in info["origins"].items():
            lam = v["layers"]["gbm_residual"]
            st.write(f"{bl}/{o}: GBM shrinkage chosen on validation = **{lam['lambda']}** "
                     f"(validation log loss by factor: {', '.join(f'{k}: {x:.4f}' for k, x in lam['validation_log_loss_by_lambda'].items())})")
    st.subheader("Overfitting check: discovery strength vs validation effect")
    key = st.selectbox("Catalog", sorted(e["catalogs"]), key="valcat")
    cat = e["catalogs"][key]
    car = cat[cat["carried_to_validation"].astype(bool)].copy()
    if len(car):
        car["disc_effect"] = car["disc_logodds_effect"]
        chart = alt.Chart(car).mark_circle(size=70).encode(
            x=alt.X("disc_effect:Q", title="effect in discovery seasons (log-odds)"),
            y=alt.Y("val_logodds_effect:Q", title="effect in validation seasons (log-odds)"),
            color="status:N", tooltip=["description", "method", "disc_n", "val_n", "val_p_holm"])
        zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4, 4]).encode(y="y")
        st.altair_chart(chart + zero, use_container_width=True)
        st.caption("If discovered patterns were real, points would lie near the diagonal. Points collapsing toward 0 or flipping "
                   "sign show the search found noise, which validation then rejects.")
    cal = [pd.read_csv(f).assign(baseline=f.stem[12:]) for f in e["dir"].glob("calibration_*.csv")]
    if cal:
        st.subheader("Calibration of the baselines for underdogs, by season")
        c = pd.concat(cal)
        bl = st.selectbox("Baseline", sorted(c["baseline"].unique()), key="calbl")
        c = c[c["baseline"] == bl]
        st.altair_chart(alt.Chart(c).mark_line(point=True).encode(
            x="season:O", y=alt.Y("observed:Q", title="observed underdog win rate"), color="bucket:N",
            tooltip=["season", "bucket", "n", alt.Tooltip("expected:Q", format=".3f"), alt.Tooltip("observed:Q", format=".3f")]),
            use_container_width=True)
        agg = c.groupby("season").apply(lambda d: pd.Series({"underdog wins - expected": float((d["observed"] * d["n"]).sum() - (d["expected"] * d["n"]).sum()),
                                                             "games": int(d["n"].sum())}), include_groups=False).reset_index()
        st.dataframe(agg, hide_index=True)
    st.subheader("Prospective evidence (predictions archived before kickoff)")
    pc = D.prospective_check()
    st.write(f"Completed games with a pre-kickoff archived prediction: **{pc['n_games']}**. {pc['note']}")
    if pc["summary"]:
        st.json(pc["summary"])


def page_runs():
    st.title("Research Runs")
    st.caption("Discovery experiments run only when you start them here or with run_research.bat. The twice-daily data refresh "
               "never runs discovery, and nothing here retrains or replaces the Phase 1 models.")
    from lab import discovery as D, readiness, research
    c = st.columns(3)
    box = st.empty()
    if c[0].button("Run readiness gate", use_container_width=True):
        with st.status("Checking data integrity ...", expanded=True):
            r = readiness.run(progress=logger(box))
        (st.success if r["ok"] else st.error)(f"Readiness {'passed' if r['ok'] else 'FAILED'}")
    if c[1].button("Run discovery experiment", type="primary", use_container_width=True):
        with st.status("Running discovery (both baselines, two research origins) ...", expanded=True):
            gate = readiness.run(progress=logger(box))
            if not gate["ok"]:
                st.error("Readiness gate failed; discovery not run. See artifacts/readiness_report.json.")
                st.stop()
            r = D.run_experiment(progress=logger(box))
        st.cache_data.clear()
        st.success(f"Experiment {r['summary']['experiment']} saved.")
    if c[2].button("Full research workflow (refresh + discovery + reports)", use_container_width=True):
        with st.status("Running the full research workflow ...", expanded=True):
            research.run_research(progress=logger(box))
        st.cache_data.clear()
        st.success("Research workflow finished; reports are in the reports folder.")
    st.subheader("Experiments")
    st.dataframe(pd.DataFrame(D.list_experiments()), hide_index=True, use_container_width=True)
    cur = D.current_experiment()
    st.write(f"Current experiment used for upcoming-game adjustments: **{cur or 'none'}**")
    hist = research.run_history()
    if hist:
        st.subheader("Workflow history")
        st.dataframe(pd.DataFrame(hist), hide_index=True, use_container_width=True)
    rep = readiness.REPORT
    if rep.exists():
        with st.expander("Latest readiness report"):
            st.json(json.loads(rep.read_text(encoding="utf-8")))
    if cur:
        with st.expander("Current experiment configuration and seeds"):
            st.json(D.load_experiment(cur)["summary"]["config"])


def page_prospective():
    st.title("Prospective Performance")
    st.caption("Genuinely unseen games only: predictions frozen BEFORE kickoff by the scheduled task, scored after the game. "
               "Historical backtests are on Model Leaderboard and are not mixed in here.")
    from lab import prospective as P
    m = P.load_metrics()
    if st.button("Re-score now"):
        m = P.score()
    n = (m.get("overall") or {}).get("games_scored", 0)
    st.metric("Completed games with a pre-kickoff archived prediction", n)
    if not n:
        st.info("No archived game has finished yet. Results appear automatically after the first tracked games end.")
        return
    w = st.radio("Cutoff", sorted(m["by_window"]), horizontal=True,
                 format_func=lambda x: {"final": "Final pregame (<= 30 h before kickoff)", "early": "Early week (30 h - 8 days)"}.get(x, x))
    r = m["by_window"][w]
    c = st.columns(4)
    ch = r["champion"]
    c[0].metric("Games", ch["n"])
    c[1].metric("Accuracy", f"{ch['accuracy']:.1%}")
    c[2].metric("Log loss", f"{ch['log_loss']:.3f}")
    c[3].metric("Brier", f"{ch['brier']:.3f}")
    comp = [{"forecast": k, **{x: v.get(x) for x in ("n", "accuracy", "log_loss", "brier", "ece")}} for k, v in r.items()
            if isinstance(v, dict) and "log_loss" in v]
    st.subheader("Champion vs individual models, market at snapshot time, experimental adjustments, shadow challengers")
    st.dataframe(pd.DataFrame(comp), hide_index=True, use_container_width=True)
    st.caption("market_at_snapshot uses the line nfldata showed when the snapshot was taken, a timestamp-valid benchmark.")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Calibration")
        cal = pd.DataFrame(r["calibration"])
        st.altair_chart(alt.Chart(cal).mark_circle().encode(x=alt.X("mean_pred:Q", scale=alt.Scale(domain=[0, 1])),
                        y=alt.Y("observed:Q", scale=alt.Scale(domain=[0, 1])), size="n:Q", tooltip=["range", "n", "mean_pred", "observed"])
                        + alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(strokeDash=[4, 4]).encode(x="x", y="y"),
                        use_container_width=True)
    with c2:
        st.subheader("Over time")
        wk = pd.DataFrame(r["by_week"])
        wk["label"] = wk["season"].astype(str) + "-W" + wk["week"].astype(str)
        st.altair_chart(alt.Chart(wk).mark_bar().encode(x=alt.X("label:N", sort=None, title="week"), y="log_loss:Q",
                        tooltip=["label", "n", "log_loss", "accuracy"]), use_container_width=True)
    st.subheader("Favorites vs underdogs")
    st.json(r["favorite_vs_underdog"])
    st.subheader("By injury-report completeness (both teams' final reports available before the snapshot)")
    st.dataframe(pd.DataFrame(r["by_injury_completeness"]).T, use_container_width=True)
    st.subheader("Margins")
    st.dataframe(pd.DataFrame({"ensemble margin": r["margin"], "spread at snapshot": r["spread_at_snapshot"]}).T, use_container_width=True)
    st.caption("Small samples are noisy: with fewer than ~100 games, differences of a few points of accuracy mean little.")


def page_archive():
    st.title("Prediction Archive")
    from lab import prospective as P
    led = P.load_ledger()
    need(len(led), "No prospective snapshots yet. They are created by the scheduled task (refresh_data.bat).")
    st.caption("Every row is a write-once, read-only snapshot taken before kickoff. Nothing here is ever edited after the game.")
    c = st.columns(3)
    seasons = sorted(led["season"].unique(), reverse=True)
    season = c[0].selectbox("Season", seasons)
    weeks = sorted(led[led["season"] == season]["week"].unique(), reverse=True)
    week = c[1].selectbox("Week", weeks)
    win = c[2].multiselect("Window", ["early", "final"], default=["early", "final"])
    v = led[(led["season"] == season) & (led["week"] == week) & led["window"].isin(win)].sort_values(["game_id", "predicted_at"])
    v = v.assign(lead_hours=((v["kickoff_utc"] - v["predicted_at"]).dt.total_seconds() / 3600).round(1))
    st.dataframe(v[["game_id", "window", "predicted_at", "kickoff_utc", "lead_hours", "p_champion", "model_version", "stale_data", "path"]],
                 hide_index=True, use_container_width=True, column_config={"p_champion": PCT("P(home)", format="%.3f", min_value=0, max_value=1)})
    pick = st.selectbox("Open snapshot", v["path"].tolist())
    if pick:
        snap = json.loads((SNAPSHOTS_DIR / pick).read_text(encoding="utf-8"))
        st.json({k: snap[k] for k in ("matchup", "window", "predicted_at", "kickoff_utc", "hours_to_kickoff", "model_version", "p_champion",
                                      "p_home", "margin_ensemble", "market_at_snapshot", "experimental", "availability", "missing",
                                      "data_cutoff", "weather_forecast_live_only", "stale_data", "shadow_challengers")}, expanded=False)
        st.download_button("Download snapshot JSON", (SNAPSHOTS_DIR / pick).read_bytes(), file_name=Path(pick).name)


def page_freshness():
    st.title("Data Freshness & Missing Predictions")
    from lab import prospective as P
    freshness_panel()
    runs = P.run_history()
    st.subheader("Scheduled runs (append-only log)")
    if runs.empty:
        st.warning("The scheduled task has not run the prospective routine yet.")
    else:
        r = runs.copy()
        r["errors"] = r["errors"].map(lambda e: "; ".join(e) if isinstance(e, list) else e)
        st.dataframe(r[[c for c in ("started_at", "finished_at", "refresh_ok", "eligible_games", "written", "skipped", "refused",
                                     "stale_data", "errors") if c in r]].iloc[::-1], hide_index=True, use_container_width=True)
        last = pd.Timestamp(r["started_at"].iloc[-1])
        age_h = (pd.Timestamp.now(tz="UTC") - last).total_seconds() / 3600
        (st.success if age_h < 14 else st.error)(f"Last scheduled run {age_h:.1f} hours ago.")
    st.subheader("Prediction coverage per game and cutoff")
    mr = P.missing_report()
    if len(mr):
        missed = mr[mr["status"].str.startswith("MISSED")]
        (st.error if len(missed) else st.success)(f"{len(missed)} missed cutoffs; {int((mr['status'] == 'archived').sum())} archived.")
        st.dataframe(mr.sort_values("kickoff_utc"), hide_index=True, use_container_width=True)
    st.caption("If the PC is off or asleep for a whole cutoff window, that prediction is reported as MISSED and is never "
               "back-filled after kickoff. Windows Task Scheduler runs a missed run as soon as the PC is available.")


def page_baseline_research():
    st.title("Baseline Research")
    from lab import study3
    st.caption("Nested chronological comparison of feature sets, simpler ensembles and individual models against the "
               "current champion. 2019-2022 development, 2023-2024 previously inspected validation, 2025 diagnostic only. "
               "No fresh historical holdout exists; promotion requires prospective evidence.")
    st.markdown("**Pre-declared gate**  \n" + study3.__doc__.split("Pre-declared gate (written before results were seen):")[1]
                .split("The production champion")[0].replace("\n  ", "\n"))
    s = study3.load_study()
    need(s, "The study has not been run yet (python -m lab.study3).")
    sm = s["summary"]
    c = st.columns(3)
    c[0].metric("Candidates evaluated", sm["n_candidates"])
    c[1].metric("Passed the gate", sm["n_passed"])
    c[2].metric("Champion method (unchanged)", name_of(sm["champion_method"]))
    g = s["gate"].copy()
    st.dataframe(g, hide_index=True, use_container_width=True)
    st.caption("Deltas are log loss vs the champion (negative = better). dev/val deltas use the mean per-season log loss.")
    st.subheader("Do the six models carry independent information?")
    red = sm["redundancy"]
    st.write(f"Effective number of independent models: **{red['effective_independent_models']:.2f}** of 6 "
             f"(mean logit correlation {red['mean_offdiag_logit_corr']:.2f}; mean error correlation {red['mean_offdiag_error_corr']:.2f}).")
    st.dataframe(pd.DataFrame(red["error_correlation"]), use_container_width=True)
    st.subheader("Feature stability (L1 logistic, refit on each expanding window 2019-2024)")
    st.dataframe(s["l1"], hide_index=True, use_container_width=True)
    from lab.prospective import challenger_versions
    st.write(f"Shadow challengers being tracked prospectively: **{', '.join(challenger_versions()) or 'none'}**")


def page_longrun():
    st.title("Long-Run Research")
    from lab import longrun as LR
    from lab.prospective import challenger_versions
    st.caption("Extended, resumable optimisation of all six model families on your CPU. Runs as its own background process, "
               "so you can close the dashboard. Search uses development seasons 2019-2022 only; validation 2023-24 is looked at "
               "once per finished job and every look is counted. Longer searches are not assumed to be better.")
    hw = LR.hardware()
    c = st.columns(4)
    c[0].metric("CPU cores (physical / logical)", f"{hw['physical_cpus']} / {hw['logical_cpus']}")
    c[1].metric("Memory", f"{hw['memory_gb']} GB")
    c[2].metric("Default research threads", hw["default_threads"])
    active = LR.active_job()
    c[3].metric("Active job", active or "none")
    st.subheader("Start a research session")
    dur = st.radio("Duration", ["1 hour", "4 hours", "8 hours (overnight)", "12 hours", "Custom"], horizontal=True, index=2)
    hours = {"1 hour": 1, "4 hours": 4, "8 hours (overnight)": 8, "12 hours": 12}.get(dur)
    if dur == "Custom":
        hours = st.number_input("Hours", min_value=0.1, max_value=72.0, value=2.0, step=0.5)
    threads = st.slider("CPU threads for research (fewer = more responsive PC)", 1, hw["logical_cpus"], hw["default_threads"])
    if st.button("Start research", type="primary", disabled=bool(active)):
        jid = LR.create_job(hours=hours, threads=threads)
        pid = LR.launch_detached(jid)
        st.success(f"Started job {jid} (process {pid}). It keeps running if you close this page.")
    jobs = LR.list_jobs()
    need(jobs, "No research jobs yet.")
    names = [j["job"] for j in jobs]
    jid = st.selectbox("Job", names, index=names.index(active) if active in names else 0)
    job = LR.Job(jid)
    stt, meta = job.status(), job.meta
    b = st.columns(5)
    if b[0].button("Pause", disabled=jid != active):
        job.set_control("pause")
    if b[1].button("Continue", disabled=jid != active):
        job.set_control("run")
    if b[2].button("Stop", disabled=jid != active):
        job.set_control("stop")
        st.info("Stop requested; the job ends after the current trial and then runs its validation check.")
    if b[3].button("Resume (new process)", disabled=bool(active) or stt.get("state") in ("completed",)):
        LR.launch_detached(jid, resume=True)
        st.success("Resumed. Completed trials are kept; the remaining time budget continues.")
    if b[4].button("Refresh status"):
        st.rerun()
    if stt:
        m = st.columns(5)
        m[0].metric("State", stt.get("state"))
        m[1].metric("Trials", stt.get("trials_total"))
        m[2].metric("Elapsed / budget", f"{stt.get('elapsed_seconds', 0) / 3600:.2f} / {stt.get('budget_seconds', 0) / 3600:.1f} h"
                    if stt.get("budget_seconds", 0) < 10 ** 8 else f"{stt.get('elapsed_seconds', 0) / 3600:.2f} h")
        m[3].metric("CPU (system / job)", f"{stt.get('cpu_percent_system', 0):.0f}% / {stt.get('cpu_percent_process', 0):.0f}%")
        m[4].metric("Memory (job / free)", f"{stt.get('memory_process_gb', 0)} / {stt.get('memory_available_gb', 0)} GB")
        if stt.get("est_remaining_trials") is not None:
            st.caption(f"About {stt['est_remaining_trials']} more trials expected (avg {stt.get('avg_trial_seconds')} s per trial). "
                       f"Errors so far: {stt.get('errors', 0)}.")
        fam = pd.DataFrame(stt.get("per_family", {})).T
        best = {f: v.get("dev_log_loss") for f, v in stt.get("best", {}).items()}
        fam["best_dev_log_loss"] = pd.Series(best)
        fam.index = [name_of(i) for i in fam.index]
        st.subheader("Best candidate per model family (development folds)")
        st.dataframe(fam, use_container_width=True)
    tf = job.dir / "trials.csv"
    if tf.exists():
        t = pd.read_csv(tf)
        t = t[t["dev_log_loss"].notna()].sort_values(["family", "trial"])
        if len(t):
            t["best_so_far"] = t.groupby("family")["dev_log_loss"].cummin()
            st.altair_chart(alt.Chart(t).mark_line().encode(x="trial:Q", y=alt.Y("best_so_far:Q", scale=alt.Scale(zero=False)),
                            color="family:N"), use_container_width=True)
    fin = LR.load_final(jid)
    st.subheader("Validation check and promotion status")
    if fin:
        st.write(f"Validation look #{fin['validation_look']} on 2023-24 (required level after look adjustment: {fin['alpha_after_look_adjustment']:.4f}).")
        r = pd.DataFrame(fin["results"])
        st.dataframe(r, hide_index=True, use_container_width=True)
        passing = r[r.get("passes", False) == True]["family"].tolist() if "passes" in r else []  # noqa: E712
        if passing:
            st.success(f"Families that beat the champion's version on validation: {', '.join(passing)}. They can be tracked as a "
                       "shadow challenger; promotion still needs 128+ prospective games.")
            if st.button("Register shadow challenger (champion unchanged)"):
                from lab import training as _tr
                from lab.prospective import CHALLENGERS
                ov = {f: fin["best_configs"][f] for f in passing}
                res = _tr.run_training(production=True, set_current=False, tag="lr_shadow", model_overrides=ov, progress=lambda m: None)
                CHALLENGERS.write_text(json.dumps({"versions": challenger_versions() + [res["summary"]["version"]]}, indent=2))
                st.success(f"Registered {res['summary']['version']} for prospective shadow tracking.")
        else:
            st.info("No family's best configuration beat the champion's version of that family on validation. Champion unchanged.")
    else:
        st.write("Not finalized yet (happens automatically when the job completes or is stopped).")
    st.write(f"Current champion: **{training.current_version()}** ({name_of(training.load_run()['selection'].get('champion', ''))}). "
             f"Shadow challengers: {', '.join(challenger_versions()) or 'none'}.")
    if LR.VAL_LEDGER.exists():
        with st.expander("Validation look ledger"):
            st.code(LR.VAL_LEDGER.read_text(encoding="utf-8"))
    lf = job.dir / "log.txt"
    if lf.exists():
        with st.expander("Job log"):
            st.code("\n".join(lf.read_text(encoding="utf-8").splitlines()[-60:]))
    st.subheader("All jobs")
    st.dataframe(pd.DataFrame(jobs), hide_index=True, use_container_width=True)


def page_afi():
    st.title("Advanced Football Intelligence")
    from lab import advanced, study4
    from lab.features import P4_GROUPS, feature_groups
    fs = feature_store()
    need(fs is not None, "Download data first.")
    st.subheader("Historical data sources")
    st.dataframe(pd.DataFrame(advanced.SOURCE_INFO), hide_index=True, use_container_width=True)
    with st.expander("Investigated but not used"):
        st.dataframe(pd.DataFrame(advanced.INVESTIGATED_NOT_USED, columns=["source", "reason"]), hide_index=True, use_container_width=True)
    groups = feature_groups(fs.columns)
    st.subheader("New feature groups and coverage (share of games with a value)")
    rows = []
    for g in P4_GROUPS:
        cols = groups.get(g, [])
        cov = fs[fs["season"] >= 2016].groupby("season")[cols].apply(lambda d: d.notna().mean().mean()) if cols else pd.Series(dtype=float)
        rows.append({"group": g, "features": len(cols), **{str(k): round(float(v), 2) for k, v in cov.items()}})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("Every value comes from games played before kickoff; seasons a source does not cover stay missing.")
    season, week = week_picker(fs, "afi")
    games = fs[(fs["season"] == season) & (fs["week"] == week)]
    labels = [f"{r.away_team} @ {r.home_team}" for r in games.itertuples()]
    i = st.selectbox("Game", range(len(games)), format_func=lambda j: labels[j], key="afi_game")
    g = games.iloc[i]
    st.subheader("Player and position-group availability")
    avail = {}
    for side in ("home", "away"):
        avail[g[f"{side}_team"]] = {k: g.get(f"{side}_{k}") for k in (
            "qb_projected_out", "qb_questionable", "inj_report_available", "inj_out_off", "inj_out_def",
            "p4roster_blend_ol_exp", "p4roster_blend_def_exp", "p4roster_blend_returning_snap_share",
            "p4roster_l5_depth_OL", "p4roster_l5_depth_DB", "ol_churn_l4")}
    st.dataframe(pd.DataFrame(avail), use_container_width=True)
    st.subheader("Offense vs defense matchups (from earlier games only)")
    mx = {}
    for name, (o, d) in {"pressure rate (OL allowed + opp. pass rush)": ("p4pfr_blend_pfr_pressured_rate", "p4pfr_blend_def_pfr_def_pressure_rate"),
                         "yards before contact (run blocking vs run defense)": ("p4pfr_blend_pfr_ybc_per_carry", "p4pfr_blend_def_pfr_ybc_allowed"),
                         "receiver separation vs coverage": ("p4ngs_blend_ngs_separation", "p4ngs_blend_def_ngs_separation_allowed"),
                         "CPOE vs CPOE allowed": ("p4ngs_blend_ngs_cpoe", "p4ngs_blend_def_ngs_cpoe_allowed")}.items():
        mx[name] = {f"{g['home_team']} offense": g.get(f"home_{o}"), f"{g['away_team']} defense allows": g.get(f"away_{d}"),
                    f"{g['away_team']} offense": g.get(f"away_{o}"), f"{g['home_team']} defense allows": g.get(f"home_{d}")}
    st.dataframe(pd.DataFrame(mx).T, use_container_width=True)
    st.subheader("Do the new groups improve predictions? (nested chronological study)")
    sd = study4.load_study()
    if not sd:
        st.info("The Phase 4 feature-group study has not been run yet (python -m lab.study4).")
        return
    sm = sd["summary"]
    st.write(f"{sm['n_candidates']} candidates vs the champion; **{sm['n_passed']} passed** the pre-declared gate.")
    st.dataframe(sd["gate"], hide_index=True, use_container_width=True)
    ps = sd["per_season"]
    if len(ps):
        ps = ps.assign(delta=ps["config_ll"] - ps["champion_ll"])
        st.altair_chart(alt.Chart(ps).mark_line(point=True).encode(x="season:O", y=alt.Y("delta:Q", title="log loss vs champion (lower = better)"),
                        color="config:N", tooltip=["config", "season", alt.Tooltip("delta:Q", format="+.4f")]), use_container_width=True)
    fi = sd["feature_importance"]
    if len(fi):
        st.subheader("Out-of-sample permutation importance of new features (2023, models trained on earlier seasons)")
        st.dataframe(fi[fi["feature"].str.contains("p4|p3_")].sort_values("importance", ascending=False).head(25),
                     hide_index=True, use_container_width=True)


def page_reports():
    st.title("Reports")
    v = training.current_version()
    from lab import discovery as D
    if st.button("Build NFL_Upset_Discovery.xlsx", disabled=not D.current_experiment()):
        from lab.reports import discovery_workbook
        with st.spinner("Writing workbook ..."):
            st.success(f"Saved {discovery_workbook()}")
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
    st.caption("Phase 1 + Phase 2 research · not betting advice")

try:
    {"Home": page_home, "Data Manager": page_data, "Train Models": page_train, "Model Leaderboard": page_leaderboard,
     "Model Debate": page_debate, "Weekly Predictions": page_weekly, "Prospective Performance": page_prospective,
     "Prediction Archive": page_archive, "Data Freshness": page_freshness, "Baseline Research": page_baseline_research,
     "Long-Run Research": page_longrun, "Advanced Football Intelligence": page_afi,
     "Upset Discovery": page_discovery,
     "Upset Explorer": page_explorer, "Research Validation": page_validation, "Research Runs": page_runs,
     "Reports": page_reports}[page]()
except FileNotFoundError as exc:
    st.warning(str(exc))
except Exception as exc:  # show a readable error instead of a blank page
    st.error(f"Something went wrong: {exc}")
    st.exception(exc)
