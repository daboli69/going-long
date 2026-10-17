"""NFL Ensemble Lab dashboard. Start with launch_lab.bat (or `streamlit run app/streamlit_app.py`)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json  # noqa: E402
import os  # noqa: E402

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

PAGES = ["Home", "Live Readiness & Schedule", "Data Manager", "Train Models", "Model Leaderboard", "Model Debate",
         "Weekly Predictions", "Prospective Performance", "Prediction Archive", "Data Freshness", "Baseline Research",
         "Long-Run Research", "Advanced Football Intelligence", "Player Intelligence", "Data Coverage & Gaps",
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


@st.cache_data(show_spinner=False, ttl=300)
def scheduler_code_version() -> str:
    from lab import release
    return release.summary_line()


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
    _debate_context(fs, row)
    t1, t2, t3, t4, t5, t6 = st.tabs(["1 · Independent forecasts", "2 · Statistical arguments", "3 · Disagreements", "4 · Vote",
                                      "5 · Consensus", "6 · Players, matchups & uncertainty"])
    t7 = st.expander("7 · Timeline: how the forecast and football information changed across archived snapshots", expanded=False)
    with t7:
        from lab import live as _live
        from lab import prospective as _P
        led = _P.load_ledger()
        gl = led[led["game_id"] == d["game_id"]].sort_values("predicted_at") if len(led) else led
        if len(gl):
            rows_ = []
            for rr in gl.itertuples(index=False):
                sn = json.loads((SNAPSHOTS_DIR / rr.path).read_text(encoding="utf-8"))
                av = sn.get("availability", {})
                rows_.append({"stage": _P.STAGE_LABELS.get(rr.window, rr.window), "archived (ET)": pd.Timestamp(rr.predicted_at).tz_convert("America/New_York").strftime("%a %I:%M %p"),
                              "champion P(home)": sn["p_champion"], **{name_of(k): v for k, v in sn["p_home"].items()},
                              "margin": sn.get("margin_ensemble"),
                              "home QB out flag": av.get("home", {}).get("qb_projected_out"), "away QB out flag": av.get("away", {}).get("qb_projected_out"),
                              "home off. inj. load": av.get("home", {}).get("inj_out_off"), "away off. inj. load": av.get("away", {}).get("inj_out_off"),
                              "challengers": json.dumps({k: (v.get("p_champion") if isinstance(v, dict) else v) for k, v in sn.get("shadow_challengers", {}).items()})})
            st.dataframe(pd.DataFrame(rows_), hide_index=True, use_container_width=True)
        else:
            st.info("No archived snapshots for this game yet.")
        teams = d["matchup"].split(" @ ")
        since = gl["predicted_at"].min() if len(gl) else pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)
        ch = _live.changes(since=since)
        ch = ch[ch["team"].isin(teams)] if len(ch) else ch
        st.write("**Changes detected since the first snapshot** (official report, ESPN status, depth-chart QB1):")
        if len(ch):
            st.dataframe(ch, hide_index=True, use_container_width=True)
        else:
            st.caption("none detected")
        tx = _live.transactions(since=pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=10))
        tx = tx[tx["team"].isin(teams)] if len(tx) else tx
        st.write("**Recent transactions** (ESPN; monitoring only):")
        if len(tx):
            st.dataframe(tx, hide_index=True, use_container_width=True)
        else:
            st.caption("none")
    with t6:
        st.caption("Verified football data behind this matchup. Player values are statistical estimates from earlier plays only.")
        if d.get("player_context"):
            st.write("**Projected lineups, availability and replacements**")
            st.dataframe(pd.DataFrame(d["player_context"]), use_container_width=True)
        if d.get("matchups"):
            st.write("**Matchup indicators (home minus away; positive favours the home team)**")
            st.dataframe(pd.Series(d["matchups"], name="value"), use_container_width=True)
        if d.get("uncertainty"):
            u = d["uncertainty"]
            st.write(f"**Uncertainty:** the six models span {u['model_probability_range']:.1%} (std {u['model_probability_std']:.1%}). "
                     + u["note"])
            for w in u["missing_information"]:
                st.write("- " + w)
        sp = d.get("specialization") or {}
        st.write("**Model-specific historical evidence for this game's situation**")
        if sp.get("evidence"):
            st.dataframe(pd.DataFrame(sp["evidence"]), hide_index=True, use_container_width=True)
        st.caption(sp.get("note") or sp.get("status", ""))
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
    from lab import compare7
    df7 = compare7.collect()
    stage7 = st.selectbox("Stage", ["final", "t60", "t90", "t24h", "friday", "early_week", "early"], key="cmp7")
    c7 = compare7.compare(df7, stage7)
    st.subheader(f"Champion vs challengers on identical games ({c7['games']} games at stage '{stage7}')")
    if c7["games"]:
        st.dataframe(c7["by_version"].round(4), hide_index=True, use_container_width=True)
        st.dataframe(c7["paired"].round(4), hide_index=True, use_container_width=True)
        sc = compare7.stage_changes(df7)
        if len(sc):
            st.write("**Did fresher information help?** First vs last archived forecast for the same game:")
            st.dataframe(sc.round(4), hide_index=True, use_container_width=True)
    st.caption("A single weekend is far too small for conclusions; the registered rule needs 128+ games and Holm correction.")
    _market_research()
    if not n:
        st.info("No archived game has finished yet. Results appear automatically after the first tracked games end.")
        return
    w = st.radio("Cutoff", sorted(m["by_window"]), horizontal=True,
                 format_func=lambda x: __import__("lab.prospective", fromlist=["STAGE_LABELS"]).STAGE_LABELS.get(x, x))
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
    if m.get("paired"):
        st.subheader("Paired comparisons on identical games (negative = better than the champion / than final)")
        st.dataframe(pd.DataFrame(m["paired"]), hide_index=True, use_container_width=True)
    if m.get("challengers"):
        st.subheader("Challengers vs champion (Holm-corrected across all tracked challengers; 128+ games required)")
        st.dataframe(pd.DataFrame(m["challengers"]), hide_index=True, use_container_width=True)
    if m.get("hypotheses"):
        st.subheader("Frozen upset hypotheses (judged only on games archived after registration)")
        st.dataframe(pd.DataFrame(m["hypotheses"]), hide_index=True, use_container_width=True)


def _market_research():
    """Phase 8.1 research results (pre-registered; docs/PHASE8_1_PREREGISTRATION.md)."""
    from lab import market81_eval as ME
    from lab import scoring81
    r = ME.load()
    with st.expander("Market research (Phase 8.1): champion vs betting market, hypotheses, drive simulator", expanded=False):
        st.caption("Timestamp classes: T1 = quote time recorded before kickoff; T2 = opening line, time unrecorded; T3 = closing line, "
                   "untimestamped. Closing-line comparisons are unequal information (the market knows inactives and late news).")
        for k, title in (("compare_overall", "Champion vs market on identical games"), ("compare_by_season", "By season (closing line)"),
                         ("compare_by_band", "By favourite probability (closing line)"), ("compare_agreement", "Who was right (closing line)")):
            if k in r:
                st.write(f"**{title}**")
                st.dataframe(r[k].round(4), hide_index=True, use_container_width=True)
        s = r.get("summary")
        if s:
            st.write("**Pre-registered hypotheses** (Holm across H1-H5):")
            hy = s["hypotheses"]
            st.dataframe(pd.DataFrame([
                {"hypothesis": "H1 disagreement with the opening market predicts champion error", "p": s["primary_p"]["H1"], "p_holm": s["holm"]["H1"]},
                {"hypothesis": "H2 line movement adds beyond the closing line (expected null)", "p": s["primary_p"]["H2"], "p_holm": s["holm"]["H2"]},
                {"hypothesis": "H3 stale-input flags explain market-right disagreements", "p": s["primary_p"]["H3"], "p_holm": s["holm"]["H3"]},
                {"hypothesis": "H4 opening spread beats the champion margin (MAE)", "p": s["primary_p"]["H4"], "p_holm": s["holm"]["H4"]},
                {"hypothesis": "H5 champion + closing market beats market alone", "p": s["primary_p"]["H5"], "p_holm": s["holm"]["H5"]},
            ]).round(4), hide_index=True, use_container_width=True)
            st.caption(f"H5 log loss 2019-22: combination {hy['H5_close']['ll_C']:.4f}, market alone {hy['H5_close']['ll_M_raw']:.4f}, "
                       f"champion {hy['H5_close']['ll_champion']:.4f}. A combination that beats the champion only by copying the market "
                       "is not new football information.")
        if "drive_sim" in r:
            st.write("**Drive simulator (experimental scoring distributions)**")
            st.dataframe(r["drive_sim"], hide_index=True, use_container_width=True)
        ev = scoring81.evaluate()
        st.write(f"**Prospective drive-simulator archive:** {len(ev)} completed archived games so far.")
        if len(ev):
            st.write(f"Margin MAE {ev['margin_abs_err'].mean():.2f}, total MAE {ev['total_abs_err'].mean():.2f}, "
                     f"80% interval coverage margin {ev['margin_in_80'].mean():.0%}, total {ev['total_in_80'].mean():.0%}.")


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
    with st.expander("Phase 5 experiments (player-level features, specialized challengers, adaptive ensemble)"):
        st.write("Runs the nested Phase 5 study in the background (about 40-60 minutes). It never changes the champion.")
        if st.button("Run Phase 5 study", disabled=bool(active)):
            import subprocess
            flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000) if os.name == "nt" else 0
            log = open(LR.LR_DIR / "study5_process.log", "a")
            subprocess.Popen([sys.executable, "-W", "ignore", "-m", "lab.study5"], cwd=str(ROOT), stdout=log, stderr=log,
                             stdin=subprocess.DEVNULL, creationflags=flags)
            st.success("Phase 5 study started in the background; results appear on Player Intelligence when done.")
        st.caption("The long-run optimiser above also searches the Phase 5 feature groups automatically.")
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
    _job_analysis(jid)
    st.subheader("All jobs")
    st.dataframe(pd.DataFrame(jobs), hide_index=True, use_container_width=True)


def _job_analysis(jid):
    """Plain-language inspection of a completed research job (development-only analysis)."""
    from lab import analyze_longrun as AL
    from lab import longrun as LR
    st.subheader("What did this job learn?")
    an = AL.load(jid)
    if not an:
        if (LR.LR_DIR / jid / "final.json").exists() and st.button("Analyze this job (about 1 minute)"):
            with st.spinner("Analysing saved trials (no re-optimisation) ..."):
                AL.analyze(jid, progress=lambda m: None)
            st.rerun()
        st.caption("The analysis reads the saved trials and uses development seasons (2019-2022) only for every selection.")
        return
    sm = an["summary"]
    fin = LR.load_final(jid)
    chk = an.get("selection_noise_check", pd.DataFrame())
    if len(chk):
        held = int((chk["gain_2022_holdout"] > 0).sum())
        st.info(f"**Selection-noise check:** each model's best trial was picked using 2019-2021 only, then tested on 2022, "
                f"which the pick never saw. {held} of {len(chk)} models kept any improvement on 2022. "
                "Gains that vanish on the unseen fold are mostly noise from searching many configurations.")
        st.dataframe(chk[["family", "gain_2019_21", "gain_2022_holdout", "selected_mean_2019_21", "champion_mean_2019_21",
                          "selected_2022", "champion_2022"]].rename(columns={"gain_2019_21": "gain where picked (2019-21)",
                                                                           "gain_2022_holdout": "gain on unseen 2022"}),
                     hide_index=True, use_container_width=True)
    cands = an.get("candidates", pd.DataFrame())
    if len(cands):
        st.write("**Ensemble challengers considered** (rule fixed before results: improve 2019-21 and hold on 2022):")
        st.dataframe(cands, hide_index=True, use_container_width=True)
        if not cands["qualifies_for_prospective_tracking"].any():
            st.warning("No ensemble combination qualified, so no new shadow challenger was registered from this job.")
    tabs = st.tabs(["Best configurations", "Feature groups", "Dev vs validation", "Seasons & calibration", "Curves",
                    "Correlations", "Ensemble combinations"])
    with tabs[0]:
        tt = an.get("top_trials", pd.DataFrame())
        st.dataframe(tt[tt["rank"] == 1][["family", "trial", "dev_log_loss", "n_groups", "groups", "max_features", "calibration",
                                          "hyperparameters"]] if len(tt) else tt, hide_index=True, use_container_width=True)
        with st.expander("Top 10 trials per model"):
            st.dataframe(tt, hide_index=True, use_container_width=True)
    with tabs[1]:
        g = an.get("group_frequency", pd.DataFrame())
        if len(g):
            st.caption("Share of each model's 25 best trials that used a feature group. 'Enrichment' compares with all completed "
                       "trials. The search concentrates on what scored well, so high shares are not independent evidence.")
            piv = g.pivot(index="group", columns="family", values="share_in_top")
            piv["mean"] = piv.mean(axis=1)
            st.dataframe(piv.sort_values("mean", ascending=False).round(2), use_container_width=True)
            st.dataframe(g.groupby("group")["enrichment"].mean().sort_values(ascending=False).round(3), use_container_width=True)
    with tabs[2]:
        if fin:
            r = pd.DataFrame(fin["results"])
            st.caption(f"One-time validation look #{fin['validation_look']} (required level {fin['alpha_after_look_adjustment']:.4f}). "
                       "2023-2025 have been inspected before; these numbers check, they do not select.")
            st.dataframe(r[[c for c in ("family", "trials", "challenger_dev", "champion_dev", "challenger_val", "champion_val",
                                        "val_delta", "val_delta_ci", "p_holm", "challenger_diag_2025", "champion_diag_2025",
                                        "status") if c in r]], hide_index=True, use_container_width=True)
    with tabs[3]:
        vm = an.get("version_metrics", pd.DataFrame())
        st.caption("Development out-of-fold results (each season predicted by models trained on earlier seasons).")
        st.dataframe(vm.round(4), hide_index=True, use_container_width=True)
    with tabs[4]:
        cu = an.get("improvement_curves", pd.DataFrame())
        if len(cu):
            st.altair_chart(alt.Chart(cu).mark_line().encode(x="trial:Q", y=alt.Y("best_so_far:Q", scale=alt.Scale(zero=False),
                            title="best development log loss so far"), color="family:N"), use_container_width=True)
            st.caption("Flat curves mean extra trials stopped finding better development scores (diminishing returns).")
    with tabs[5]:
        pc = an.get("prediction_correlations", pd.DataFrame())
        if len(pc):
            m_ = pc.reset_index().melt(id_vars=pc.index.name or "index", var_name="b", value_name="r")
            m_.columns = ["a", "b", "r"]
            st.altair_chart(alt.Chart(m_).mark_rect().encode(x="a:N", y="b:N", color=alt.Color("r:Q", scale=alt.Scale(domain=[0.5, 1])),
                            tooltip=["a", "b", alt.Tooltip("r:Q", format=".3f")]), use_container_width=True)
            st.write(f"Effective number of independent models: champion versions {sm['effective_models_champion_versions']:.2f}, "
                     f"overnight versions {sm['effective_models_overnight_versions']:.2f} (of 6).")
    with tabs[6]:
        co = an.get("ensemble_combinations", pd.DataFrame())
        if len(co):
            st.caption("All 64 keep/replace combinations x 2 weightings, ranked on 2019-2021; the 2022 column is the check.")
            st.dataframe(co.round(4), hide_index=True, use_container_width=True)
            st.altair_chart(alt.Chart(co).mark_circle().encode(x=alt.X("gain_2019_21:Q", title="gain where selected (2019-21)"),
                            y=alt.Y("gain_2022_check:Q", title="gain on 2022 check"), color="n_replaced:O",
                            tooltip=["replaced", "weighting"]), use_container_width=True)


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
    _phase7_panel()


@st.cache_resource(show_spinner=False)
def _bundle_features(version):
    return training.load_bundle(version)["features"]


def _debate_context(fs, row):
    """Phase 7.1: (1) what the champion knew, (2) what each challenger knew, (3) what live monitoring knows now."""
    from lab import live
    from lab import prospective as P
    from lab import transparency as T
    g = fs[fs["game_id"] == row["game_id"]]
    if g.empty:
        return
    g = g.iloc[0]
    names = availability.player_names()
    nm = lambda i: names.get(i, i) if isinstance(i, str) else "unknown"
    lives = {}
    if not bool(g["completed"]):
        off = live.official_qb_status(int(g["season"]))
        for side in ("home", "away"):
            try:
                lives[side] = T.live_qb(g[f"{side}_team"], int(g["season"]), int(g["week"]), g, side, names, off)
                w = T.conflict_warning(g, side, lives[side], names)
                if w:
                    st.warning("QB conflict: " + w)
            except Exception as exc:
                lives[side] = {"live_qb": None, "status": f"unavailable ({exc.__class__.__name__})", "sources": {}}
    with st.expander("What each model version knew (and what live monitoring knows now)", expanded=True):
        st.caption("Rows 1-3 are model inputs computed from the current feature store for this game. The live row is "
                   "monitoring only and never changes a prediction. Archived pregame forecasts are listed below separately.")
        rows = []
        versions = [(training.current_version(), "1 · Champion")] + \
                   [(v, f"2 · Challenger {v.split('_', 2)[-1]}") for v in P.challenger_versions()]
        for v, label in versions:
            try:
                vi = T.version_inputs(g, _bundle_features(v))
            except Exception:
                continue
            rows.append({"version": label, "QB rule": vi["qb_rule"],
                         f"{g['away_team']} QB": nm(vi["away_qb_id"]), f"{g['home_team']} QB": nm(vi["home_qb_id"]),
                         "injury report": f"{g['away_team']}: {vi['away_injury_report']}; {g['home_team']}: {vi['home_injury_report']}",
                         "report retrieved": vi["home_injury_report_time"], "player model": vi["player_model"],
                         "missing features": f"{vi['features_missing']} of {vi['n_features']}" +
                                             (f" ({', '.join(vi['features_missing_names'][:4])})" if vi["features_missing"] else "")})
        if lives:
            rows.append({"version": "3 · Live monitoring (not a model input)", "QB rule": "official report + rosters + Sleeper + v2",
                         f"{g['away_team']} QB": f"{lives['away'].get('live_qb')} [{lives['away']['status']}]",
                         f"{g['home_team']} QB": f"{lives['home'].get('live_qb')} [{lives['home']['status']}]",
                         "injury report": f"official report week {lives['home'].get('official_report_week')}",
                         "report retrieved": None, "player model": "n/a", "missing features": "n/a"})
        if bool(g["completed"]):
            rows.append({"version": "Confirmed after the game (play-by-play)", "QB rule": "actual starters",
                         f"{g['away_team']} QB": T.confirmed_qb(g["game_id"], "away"), f"{g['home_team']} QB": T.confirmed_qb(g["game_id"], "home"),
                         "injury report": "", "report retrieved": None, "player model": "", "missing features": ""})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        if lives:
            if st.toggle("Show live QB sources", key=f"lqs_{g['game_id']}"):
                st.json({s_: {k: lives[s_].get(k) for k in ("sources", "official_out_or_doubtful", "roster_reserve_or_inactive", "status")}
                         for s_ in lives})
        hist = T.snapshot_history(g["game_id"])
        st.write("**Archived pregame forecasts** (immutable; what each version actually predicted at each stage):")
        if len(hist):
            st.dataframe(hist, hide_index=True, use_container_width=True)
        else:
            st.caption("None archived for this game. The forecasts on this page are newly calculated analysis, not archived predictions.")
        st.caption("Agreement is not extra confidence: all six models receive the same 85 features and one shared signal explains 91% "
                   "of their variation. Historically, unanimous 50-60% favourites won 51% of games versus 55% for split votes.")
    _lineup_section(g)
    _market_section(g)
    _specialist_section(g)


def _market_section(g):
    """Phase 8.1: market benchmark next to the official forecast. Market data is never a model input."""
    from lab import market81 as MK
    with st.expander("Market benchmark (betting market; not a model input, not an independent football prediction)", expanded=False):
        arc = MK.espn_archive()
        rows = []
        if len(arc):
            a = arc[(arc["home"] == g["home_team"]) & (arc["away"] == g["away_team"])]
            if len(a):
                a = a.sort_values("retrieved_at")
                last, first = a.iloc[-1], a.iloc[0]
                def nv(h, aw):
                    try:
                        return float(MK.novig(MK.american_to_prob([float(str(h).replace("+", ""))]), MK.american_to_prob([float(str(aw).replace("+", ""))]))[0])
                    except (TypeError, ValueError):
                        return None
                rows.append({"source": f"{last['provider']} via ESPN (opening price)", "retrieved": "opening, time not given by source",
                             f"P({g['home_team']}) no-vig": nv(last["home_ml_open"], last["away_ml_open"]), "spread (home)": last.get("home_spread_open"),
                             "total": last.get("over_open")})
                rows.append({"source": f"{last['provider']} via ESPN (current price)", "retrieved": last["retrieved_at"],
                             f"P({g['home_team']}) no-vig": nv(last["home_ml_close"], last["away_ml_close"]),
                             "spread (home)": last.get("spread_current"), "total": last.get("total_current")})
                st.caption(f"{len(a)} archived ESPN/DraftKings snapshots for this game since {first['retrieved_at']}.")
        sm = MK.snapshot_markets()
        sm = sm[sm["game_id"] == g["game_id"]] if len(sm) else sm
        for r in sm.itertuples(index=False):
            rows.append({"source": f"nfldata line inside the {r.stage} forecast archive", "retrieved": r.data_refreshed_at,
                         f"P({g['home_team']}) no-vig": r.p_home_novig, "spread (home)": r.spread_line, "total": None})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.caption("No timestamped market price archived for this game yet.")
        st.caption("History (2018-25): the closing market beat the champion (log loss 0.609 vs 0.630), but it knows late news, so "
                   "that is an unequal comparison. Against the opening line the champion was level (0.628 vs 0.630). Combining the "
                   "champion with the closing market did not beat the market alone. Details: Prospective Performance -> Market research.")


def _specialist_section(g):
    """Phase 8 (experimental): independent specialists. Never an official or tracked forecast."""
    from lab.specialists import core as SC
    from lab.specialists import evaluate as SE
    oof = SC.OUT / "specialist_oof.parquet"
    if not oof.exists():
        return
    sp = pd.read_parquet(oof)
    sp = sp[sp["game_id"] == g["game_id"]]
    if sp.empty:
        return
    res = SE.load_results()
    stand = res.get("standalone", pd.DataFrame())
    dev = stand[stand["window"].str.startswith("development")].set_index("model") if len(stand) else pd.DataFrame()
    with st.expander("Specialist debate (experimental research; not an official or tracked forecast)", expanded=False):
        st.caption("Six independent specialists, each limited to one kind of football information and fitted only on earlier "
                   "seasons. In the pre-registered development test none added reliable information beyond the champion, "
                   "so they are shown for discussion only. Signals are statistical associations, not reasons a team will win.")
        champ = float(g.get("p_champion", np.nan)) if "p_champion" in g else np.nan
        rows = []
        names = {s_.key: s_ for s_ in SC.SPECIALISTS}
        for r in sp.itertuples(index=False):
            spec = names[r.specialist]
            d = dev.loc[r.specialist] if r.specialist in dev.index else None
            rows.append({"specialist": f"{r.specialist} · {spec.name}",
                         f"P({g['home_team']} wins)": None if r.abstained else round(float(r.p_home), 3),
                         "status": "abstained (inputs missing)" if r.abstained else "available",
                         "main signals": getattr(r, "signals", "") if not r.abstained else "",
                         "historical corr. with champion": None if d is None else round(float(d.get("pred_corr_with_champion", np.nan)), 2),
                         "adds info beyond champion? (dev p)": None if d is None or pd.isna(d.get("incremental_p")) else round(float(d["incremental_p"]), 2)})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        e = sp[sp["specialist"] == "E"]
        if len(e) and pd.notna(e["margin"].iloc[0]):
            e = e.iloc[0]
            st.write(f"Drive simulation: expected margin {g['home_team']} {e['margin']:+.1f} (10-90%: {e.get('margin_p10', np.nan):+.0f} to "
                     f"{e.get('margin_p90', np.nan):+.0f}); expected total {e['total']:.1f} ({e.get('total_p10', np.nan):.0f}-{e.get('total_p90', np.nan):.0f}).")
        st.caption("'Historical corr.' near 1 means the specialist mostly repeats the champion; near 0 means different information, "
                   "which was not predictive here. Specialist F needs the champion's out-of-fold probability, which does not exist "
                   "for upcoming games, so it abstains.")


def _lineup_summary(t):
    st_ = t[t["starter"]]
    return {"starters expected out": round(float((1 - st_["availability"]).sum()), 1),
            "confirmed absences (starters)": ", ".join(f"{r.player} ({r.unit})" for r in st_[st_["status_type"] == "confirmed absence"].itertuples()) or "none",
            "uncertain starters": ", ".join(f"{r.player} ({r.unit}, {r.availability:.0%})" for r in st_[(st_["status_type"] != "confirmed absence") &
                                                                                                  (st_["availability"] < 0.95)].itertuples()) or "none",
            "offensive line": f"{int((st_[st_['unit'] == 'OL']['availability'] > 0.5).sum())} of {int((st_['unit'] == 'OL').sum())} regular OL starters expected"}


def _lineup_section(g):
    from lab import lineup72
    with st.expander("Expected lineups and injuries (analysis: not an input of the champion or the registered challengers)",
                     expanded=not bool(g["completed"])):
        st.caption("Usual snap share = last 4 games (verified PFR snap counts). Availability: Out and reserve/IR (last week's roster) are "
                   "confirmed absences; Questionable and listed players get a probability estimated from past seasons by status, practice "
                   "and starter role. Without a verified report a team is 'unknown', never 'healthy'. Player values are the Phase 7 "
                   "snap-model ratings (EPA/play, heavily shrunk); they are approximate and not a point value per player.")
        cols = st.columns(2)
        for col, side in zip(cols, ("away", "home")):
            team = g[f"{side}_team"]
            with col:
                st.write(f"**{team}**")
                try:
                    t = lineup72.player_table(g, team)
                except Exception as exc:
                    st.caption(f"unavailable ({exc.__class__.__name__})")
                    continue
                if t.empty:
                    st.caption("No snap history.")
                    continue
                for k, v in _lineup_summary(t).items():
                    st.write(f"- {k}: {v}")
                if st.toggle("Show players", key=f"lu_{g['game_id']}_{team}"):
                    st.dataframe(t, hide_index=True, use_container_width=True)
        p72 = {c: g.get(c) for c in ("diff_p72_OL_missing_share", "diff_p72_SKILL_starters_out", "diff_p72_QB_missing_share",
                                     "diff_p72_ol_expected_continuity", "p72mx_net_total")}
        if any(pd.notna(v) for v in p72.values()):
            st.caption("Phase 7.2 lineup-change features for this game (home minus away; tested in development, not adopted by any model): " +
                       ", ".join(f"{k} {v:+.3f}" for k, v in p72.items() if pd.notna(v)))


def _phase7_panel():
    from lab import audit7, errors, extra_sources as X, study7
    st.header("Phase 7: 2026 data, QB intelligence and error analysis")
    st.caption("Monitoring sources never enter models. Historical results below are descriptive unless marked as the pre-declared test.")
    t = st.tabs(["QB sources", "QB projection v2", "Snap model & challenger test", "Error analysis", "Weekend audit",
                 "Why the models agree", "Injury-adjusted lineups (7.2)"])
    with t[6]:
        from lab import study72
        r = study72.load()
        st.write("Expected lineups from verified snap shares, official reports (probabilities estimated from past seasons) and "
                 "reserve/IR status. Features are changes versus the recent lineup, so absences already reflected in team ratings "
                 "are not counted twice.")
        if "independence" in r:
            ind = r["independence"]
            st.write("**Overlap with the champion's features and incremental information** (development 2018-22): R² from the "
                     "champion's 85 features, and correlation of the unexplained part with the champion's margin error.")
            st.dataframe(ind.groupby("group")[["r2_explained_by_champion_features", "residual_corr_with_champion_margin_error"]].agg(
                ["mean", "max"]).round(3), use_container_width=True)
            st.dataframe(ind.reindex(ind["residual_corr_with_champion_margin_error"].abs().sort_values(ascending=False).index).head(15).round(3),
                         hide_index=True, use_container_width=True)
            st.caption("About 60 features were examined, so a few nominal 95% intervals excluding zero are expected by chance.")
        if "dev_experiment" in r:
            st.write("**Pre-declared development-only experiment** (rule: improve 2019-21, hold on 2022, Holm-adjusted p < 0.05):")
            st.dataframe(r["dev_experiment"].round(4), hide_index=True, use_container_width=True)
            st.dataframe(r["dev_experiment_by_family"].round(4), hide_index=True, use_container_width=True)
            if not r["dev_experiment"]["qualifies"].any():
                st.warning("No candidate met the pre-declared standard; no new challenger was registered.")
    with t[5]:
        from lab import shared_errors as SE
        r = SE.load()
        if not r:
            st.caption("Run `python -m lab.cli shared-errors`.")
        else:
            st.write(r["inputs"])
            st.write(f"One shared component explains **{r['first_component_share_of_prediction_variance']:.0%}** of the six models' "
                     "prediction variance.")
            st.dataframe(r["shared_signal"].round(3), hide_index=True, use_container_width=True)
            st.write("**Is agreement confidence?** Observed favourite win rate by vote split, and unanimity within the same probability band:")
            st.dataframe(r["vote_split"].round(3), hide_index=True, use_container_width=True)
            st.dataframe(r["unanimity_within_band"].round(3), hide_index=True, use_container_width=True)
            a6 = r["all_six_wrong"]
            st.write(f"**Games all six got wrong:** {a6['games']} ({a6['share']:.0%}). The closing market was also wrong in "
                     f"{a6['market_also_wrong']:.0%} of them, which suggests most shared misses were not predictable before kickoff. "
                     f"In {a6['market_right_models_wrong']:.0%} the market was right: candidates for missing pregame information.")
            st.dataframe(r["by_qb"].round(3), hide_index=True, use_container_width=True)
            st.caption("Descriptive, all walk-forward seasons including the inspected 2023-24; nothing here selects a model.")
    with t[0]:
        from lab.data_pipeline import current_season
        fs = feature_store()
        wk = int(fs[(fs["season"] == current_season()) & (~fs["completed"])]["week"].min()) if fs is not None else 1
        q = X.qb_sources(current_season(), wk)
        st.caption(f"Week {wk}: every QB signal with its retrieval time. 'Agreement' between sources is descriptive, not confirmation.")
        st.dataframe(q, hide_index=True, use_container_width=True)
    with t[1]:
        st.write("v2 adds a **returning starter** rule: the team's primary starter (most dropbacks over its last 8 games) is projected back "
                 "when he missed the previous game but this game's verified report lists him with a status other than Out/Doubtful. "
                 "Requiring him to be on the report matters: 'not on the report' was right only ~28% of the time (benched, IR, traded).")
        e = errors.load()
        if "qb_agreement" in e:
            st.dataframe(e["qb_agreement"].round(3), hide_index=True, use_container_width=True)
            st.caption("Share of games where both projected starters actually started (post-hoc diagnostic, never a model input).")
    with t[2]:
        st.write("The snap model rates players from verified PFR snap shares and team-game EPA per play: a labelled substitute for "
                 "the play participation file nflverse has not published for 2026. It sees who played how much in each game, not who "
                 "was on the field for each play.")
        r = study7.load()
        if r:
            st.write("**Pre-declared development test** (champion hyperparameters, no tuning, equal-weight six-model ensemble; "
                     "rule: improve 2019-21 and hold on 2022):")
            st.dataframe(r["results"].round(4), hide_index=True, use_container_width=True)
            if "by_family" in r:
                st.dataframe(r["by_family"].round(4), hide_index=True, use_container_width=True)
            st.info("The combined candidate was registered as a frozen shadow challenger (v20261017_142546_p7_qb_snap). Gains of "
                    "0.0014-0.0039 are small; only 128+ prospective games can show whether they are real. Nothing is promoted.")
    with t[3]:
        e = errors.load()
        if not e:
            st.caption("Run `python -m lab.cli errors` to build the error analysis.")
        else:
            st.write(f"Effective independent models: **{e['effective_models']:.2f} of 6**. All six models were wrong together in "
                     f"{e['all_six_wrong_share']:.0%} of games (ensemble wrong {e['ensemble_wrong_share']:.0%}).")
            st.dataframe(e["residual_correlation"], use_container_width=True)
            b = e["buckets"]
            f_ = st.selectbox("Factor", b["factor"].unique().tolist(), key="p7err")
            st.dataframe(b[b["factor"] == f_].drop(columns=["factor"]).round(4), hide_index=True, use_container_width=True)
            st.caption("Descriptive only. Validation seasons 2023-24 were inspected before, so nothing here was used to choose anything.")
            st.subheader("Over/under-confidence")
            st.dataframe(e["calibration"].round(3), hide_index=True, use_container_width=True)
            with st.expander("Worst misses (all six models wrong)"):
                st.dataframe(e["worst_misses"].round(3), hide_index=True, use_container_width=True)
    with t[4]:
        a = audit7.load()
        if st.button("Re-run weekend audit"):
            a = audit7.run()
        if a:
            st.caption(f"Audited {a['audited_at']} (completed scheduler work only; unplayed games are never evaluated).")
            st.dataframe(pd.DataFrame(a["checks"]), hide_index=True, use_container_width=True)


def page_coverage():
    from lab import extra_sources as X, inventory, live
    st.title("Data Coverage & Gaps")
    st.caption("What the lab has, what it uses each source for, and what is missing. Monitoring sources never enter models.")
    st.subheader("Sources")
    inv = inventory.build()
    st.dataframe(inv, hide_index=True, use_container_width=True,
                 column_config={"role": st.column_config.TextColumn(help="model = historically valid pregame input; model* = incomplete for "
                                                                         "2026; monitoring = shown only")})
    st.subheader("Not available for free (checked)")
    st.dataframe(inventory.unavailable(), hide_index=True, use_container_width=True)
    st.subheader("Source health (Phase 7 sources)")
    h = X.source_health()
    if len(h):
        st.dataframe(h, hide_index=True, use_container_width=True)
    else:
        st.caption("No checks logged yet (they run with every light refresh).")
    st.dataframe(live.source_freshness(), hide_index=True, use_container_width=True)
    st.subheader("Per-game gaps (upcoming games)")
    fs = feature_store()
    need(fs is not None, "Download data first.")
    from lab.data_pipeline import current_season
    up = fs[(fs["season"] == current_season()) & (~fs["completed"])]
    wk = st.selectbox("Week", sorted(up["week"].unique().tolist()), key="covwk") if len(up) else None
    if wk is not None:
        r = live.game_readiness(up[up["week"] == wk])
        st.dataframe(r, hide_index=True, use_container_width=True)
        st.caption("QB labels: consistent = projection agrees with the official report and listings (never a confirmation); "
                   "uncertain = a source disagrees; changed = official report lists the usual starter Out/Doubtful.")


def page_players():
    st.title("Player Intelligence")
    from lab import players as PL
    from lab.features import P5_GROUPS, feature_groups
    fs = feature_store()
    need(fs is not None, "Download data first.")
    st.caption("Player effects come from a regularised adjusted plus-minus model on per-play EPA, refit every week using only "
               "earlier plays and shrunk toward each position group. They are statistical associations given teammates, "
               "opponents and situation, not causal player values. Teammates who always play together cannot be separated.")
    meta = json.loads(PL.META_CACHE.read_text()) if PL.META_CACHE.exists() else {}
    c = st.columns(4)
    c[0].metric("Plays with full on-field lists", f"{meta.get('plays', 0):,}")
    c[1].metric("Players rated", f"{meta.get('players', 0):,}")
    c[2].metric("Weekly refits", meta.get("fits", 0))
    c[3].metric("Newest play in model", str(meta.get("last_play_kickoff", "n/a"))[:10])
    st.caption(f"Shrinkage chosen on 2016-17 -> 2018 plays only: lambda = {meta.get('lambda')}. "
               "No 2026 participation file exists yet, so 2026 games use ratings through 2025 (staleness is shown per game).")
    groups = feature_groups(fs.columns)
    cov = []
    for gname in P5_GROUPS:
        cols = groups.get(gname, [])
        r = fs[fs["season"] >= 2016].groupby("season")[cols].apply(lambda d: d.notna().mean().mean()) if cols else pd.Series(dtype=float)
        cov.append({"group": gname, "features": len(cols), **{str(k): round(float(v), 2) for k, v in r.items()}})
    st.subheader("Coverage by season")
    st.dataframe(pd.DataFrame(cov), hide_index=True, use_container_width=True)
    season, week = week_picker(fs, "pi")
    games = fs[(fs["season"] == season) & (fs["week"] == week)]
    labels = [f"{r.away_team} @ {r.home_team}" for r in games.itertuples()]
    i = st.selectbox("Game", range(len(games)), format_func=lambda j: labels[j], key="pi_game")
    g = games.iloc[i]
    from lab.weekly import P5_SIDE
    st.subheader("Lineups, availability and replacements (pregame)")
    tbl = {g[f"{sd}_team"]: {lbl: g.get(f"{sd}_{k}") for k, lbl in P5_SIDE.items()} for sd in ("home", "away")}
    st.dataframe(pd.DataFrame(tbl), use_container_width=True)
    st.caption("Lineup = snap shares over each team's last 4 completed games. Players listed Out/Doubtful in a verified pregame "
               "report are replaced by the team's bench at that position (or a data-driven replacement level). Low-information "
               "players (< 300 prior plays) have estimates shrunk strongly toward their position group.")
    st.subheader("Unit matchups (expected EPA per play; positive favours the home team)")
    st.dataframe(pd.Series({k: g.get(k) for k in ("p5mx_net_expected_epa", "p5mx_net_trenches", "p5mx_net_pass_game",
                                                  "p5mx_home_expected_epa", "p5mx_away_expected_epa")}, name="value"), use_container_width=True)
    from lab import study5
    sd = study5.load_study()
    st.subheader("Did player-level information improve forecasts?")
    if not sd:
        st.info("Phase 5 study not run yet (Long-Run Research page, or python -m lab.study5).")
        return
    sm = sd["summary"]
    st.write(f"{sm['n_candidates']} candidates vs the champion; **{sm['n_passed']} passed** the pre-declared gate. "
             f"Specialized family challengers that beat their own family: {', '.join(sm['families_improved']) or 'none'}.")
    st.dataframe(sd["gate_results"], hide_index=True, use_container_width=True)
    if len(sd["margins"]):
        st.subheader("Margin models: original vs enhanced (MAE, points)")
        mg = sd["margins"]
        st.dataframe(mg[mg["model"].isin(["ensemble", "closing spread"])].pivot_table(index=["config", "model"], columns="period", values="mae"),
                     use_container_width=True)


def page_live():
    st.title("Live Readiness & Schedule")
    from lab import live, scheduler as S
    st.caption("All times are America/New_York. The Windows task runs a scheduler tick every 5 minutes (no dashboard needed). "
               "Labels describe freshness and completeness only; they are not confidence scores.")
    if st.button("Run a scheduler tick now"):
        with st.spinner("Running due refreshes and snapshots ..."):
            r = S.tick(progress=lambda m: None)
        st.write(r)
    _operations_panel()
    fs = feature_store()
    need(fs is not None, "Download data first.")
    sched = S.current_schedule()
    now = pd.Timestamp.now(tz="UTC")
    upc = sched[(pd.to_datetime(sched["kickoff_utc"], utc=True) > now) & (pd.to_datetime(sched["kickoff_utc"], utc=True) < now + pd.Timedelta(days=9))]
    rows = fs[fs["game_id"].isin(upc["game_id"])].drop(columns=["kickoff_utc"]).merge(upc[["game_id", "kickoff_utc", "kickoff_moved"]], on="game_id")
    st.subheader("Prediction readiness for upcoming games")
    if len(rows):
        rd = live.game_readiness(rows.sort_values("kickoff_utc"))
        st.dataframe(rd, hide_index=True, use_container_width=True)
        moved = rows[rows["kickoff_moved"]]
        if len(moved):
            st.warning("Kickoff times changed per ESPN: " + ", ".join(moved["game_id"]))
    else:
        st.info("No upcoming games in the next 9 days.")
    st.subheader("Source freshness (last successful retrieval; last valid data is kept on failures)")
    st.dataframe(live.source_freshness(), hide_index=True, use_container_width=True)
    st.info("Scheduler code version: " + scheduler_code_version() + "  (see docs/RELEASES.md)")
    st.subheader("Scheduled events (next 48 hours and last 48 hours)")
    ev = S.upcoming_events(48)
    if len(ev):
        st.dataframe(ev[["time_et", "kind", "stage", "game_id", "action", "status"]], hide_index=True, use_container_width=True)
    else:
        st.info("The scheduler has not built a plan yet (it does on its first tick).")
    hist = S.event_history()
    if len(hist):
        missed = hist[hist["outcome"] == "missed"]
        st.subheader(f"Missed events ({len(missed)})")
        st.caption("A missed pregame snapshot is never back-filled after kickoff.")
        st.dataframe(missed[["time_et", "kind", "stage", "game_id", "reason"]].tail(50), hide_index=True, use_container_width=True)
    th = S.tick_history()
    if len(th):
        st.subheader("Scheduler runs")
        th = th.assign(errors=th["errors"].map(lambda e: "; ".join(e) if isinstance(e, list) else e))
        st.dataframe(th.iloc[::-1].head(60), hide_index=True, use_container_width=True)
    from lab import audit7, compare7
    stt = audit7.stage_table()
    if len(stt):
        st.subheader("Kickoff-relative forecasts: completed, missed and pending")
        st.caption("One immutable archive per game and stage. Pending stages are never evaluated; missed stages are never back-filled.")
        o = stt["outcome"].value_counts()
        c1, c2, c3 = st.columns(3)
        c1.metric("Archived", int(o.get("done", 0)))
        c2.metric("Missed", int(o.get("missed", 0)))
        c3.metric("Pending", int(o.get("pending", 0)))
        show = stt[stt["outcome"] != "pending"].copy()
        for c in ("scheduled_utc", "kickoff_utc", "archived_at"):
            if c in show:
                show[c] = show[c].map(lambda t: S.et(t) if pd.notna(t) else None)
        st.dataframe(show, hide_index=True, use_container_width=True)
    cmp_ = compare7.compare(compare7.collect())
    st.subheader("Prospective comparison (identical archived games)")
    if cmp_["games"]:
        st.dataframe(cmp_["by_version"].round(4), hide_index=True, use_container_width=True)
        st.dataframe(cmp_["paired"].round(4), hide_index=True, use_container_width=True)
    else:
        st.caption("No archived game has finished yet; results appear automatically after games end (128+ games needed for any conclusion).")
    from lab import extra_sources as X
    h = X.source_health()
    if len(h):
        st.subheader("Phase 7 source health (NFL.com report, weekly rosters, Sleeper)")
        st.dataframe(h, hide_index=True, use_container_width=True)
    ch = live.changes()
    if len(ch):
        st.subheader("Detected changes (official report, ESPN statuses, depth-chart QB1)")
        st.dataframe(ch.head(100).astype(str), hide_index=True, use_container_width=True)


def _operations_panel():
    """Phase 7.3: is the live pipeline healthy and on time right now?"""
    import json as _json
    from lab import audit7, cache73, freshness73, live, scheduler as S
    from lab import extra_sources as X
    from lab.data_pipeline import BUILD_LEDGER, load_status
    st.subheader("Operations")
    now = pd.Timestamp.now(tz="UTC")
    ticks = S.tick_history()
    lock = S.LOCK.exists()
    stt = audit7.stage_table()
    arc = stt[stt["archived_at"].notna()] if "archived_at" in stt else stt.iloc[:0]
    c = st.columns(5)
    last_tick = pd.Timestamp(ticks["started_at"].iloc[-1]) if len(ticks) else None
    c[0].metric("Last scheduler run", S.et(last_tick) if last_tick is not None else "never",
                help="The Windows task runs every 5 minutes.")
    c[1].metric("Processing now", "yes (lock held)" if lock else "idle")
    status = load_status()
    c[2].metric("Last feature build", S.et(pd.Timestamp(status.get("features_rebuilt_at"))) if status.get("features_rebuilt_at") else "-")
    tl = arc["timeliness"].value_counts() if len(arc) and "timeliness" in arc else pd.Series(dtype=int)
    c[3].metric("Stage forecasts on time", f"{int(tl.get('on_time', 0))} of {len(arc)}",
                help="on time = archived within 5 minutes of the scheduled stage time; late but valid = later, still before kickoff")
    c[4].metric("Missed stages", int((stt["outcome"] == "missed").sum()) if len(stt) else 0,
                help="Missed stages are never back-filled after kickoff.")
    if len(tl):
        st.caption("Timeliness of archived stage forecasts: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in tl.items()) +
                   ". Policy: on time = within one scheduler interval (5 min) of the scheduled time; late but valid = later "
                   "but before kickoff; missed = no forecast before the stage deadline; unavailable = the game, model or data "
                   "could not produce a forecast. A forecast is never archived after kickoff.")
    tabs = st.tabs(["Processing times", "Injury propagation", "Source failures", "Cache health", "Archive integrity"])
    with tabs[0]:
        if BUILD_LEDGER.exists():
            b = pd.DataFrame([_json.loads(x) for x in BUILD_LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()])
            if len(b):
                st.dataframe(b[["finished_at", "kind", "seconds", "rebuilt", "latest_nflverse_archive"]].iloc[::-1].head(20),
                             hide_index=True, use_container_width=True)
        if len(arc) and "compute_seconds" in arc:
            st.write("Stage forecasts: scheduled vs actual archive time")
            show = arc[["game_id", "stage", "scheduled_utc", "archived_at", "lag_min", "compute_seconds", "timeliness"]].copy()
            for col in ("scheduled_utc", "archived_at"):
                show[col] = show[col].map(S.et)
            st.dataframe(show.iloc[::-1].head(40), hide_index=True, use_container_width=True)
        pb = Path(__file__).resolve().parents[1] / "artifacts" / "phase73" / "benchmark.csv"
        if pb.exists():
            st.write("Benchmark (cold vs warm caches)")
            st.dataframe(pd.read_csv(pb), hide_index=True, use_container_width=True)
    with tabs[1]:
        st.caption(freshness73.cadence_note())
        pr = freshness73.propagation()
        if len(pr):
            st.dataframe(pr, hide_index=True, use_container_width=True)
        sl = freshness73.source_lead()
        if len(sl):
            st.write("First retrieval carrying the week's game statuses, per source")
            st.dataframe(sl, hide_index=True, use_container_width=True)
        off = live.official_qb_status(int(status.get("live_season") or now.year))
        st.caption(f"Live monitoring currently uses: {off.get('_source')} (retrieved {off.get('_retrieved')}, week {off.get('_week')}). "
                   "Model inputs keep using the nflverse copy, which is what the frozen models were built on.")
    with tabs[2]:
        h = X.source_health()
        if len(h):
            st.dataframe(h, hide_index=True, use_container_width=True)
        if len(ticks):
            err = ticks[ticks["errors"].map(lambda e: bool(e) if isinstance(e, list) else bool(e))]
            st.write(f"Scheduler runs with errors: {len(err)} of {len(ticks)}")
            if len(err):
                st.dataframe(err.tail(20), hide_index=True, use_container_width=True)
        st.dataframe(live.source_freshness(), hide_index=True, use_container_width=True)
    with tabs[3]:
        st.caption("Each cache is keyed on every input up to and including its season plus the feature code; any change "
                   "recomputes the affected seasons. The leakage gate always runs without caches.")
        hc = cache73.health()
        if len(hc):
            st.dataframe(hc, hide_index=True, use_container_width=True)
        else:
            st.caption("No caches yet (first build will create them).")
    with tabs[4]:
        a = audit7.load()
        if st.button("Re-run integrity audit", key="ops_audit"):
            a = audit7.run()
        if a:
            st.dataframe(pd.DataFrame(a["checks"]), hide_index=True, use_container_width=True)
    up = S.upcoming_events(hours=24)
    if len(up):
        nxt = up[(up["status"] == "pending") & (up["time_utc"] >= now)].sort_values("time_utc").head(8)
        if len(nxt):
            st.write("Next scheduled forecasts and refreshes")
            st.dataframe(nxt[["time_et", "kind", "stage", "game_id", "action"]], hide_index=True, use_container_width=True)


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
    {"Home": page_home, "Live Readiness & Schedule": page_live, "Data Manager": page_data, "Train Models": page_train, "Model Leaderboard": page_leaderboard,
     "Model Debate": page_debate, "Weekly Predictions": page_weekly, "Prospective Performance": page_prospective,
     "Prediction Archive": page_archive, "Data Freshness": page_freshness, "Baseline Research": page_baseline_research,
     "Long-Run Research": page_longrun, "Advanced Football Intelligence": page_afi, "Player Intelligence": page_players,
     "Data Coverage & Gaps": page_coverage, "Upset Discovery": page_discovery,
     "Upset Explorer": page_explorer, "Research Validation": page_validation, "Research Runs": page_runs,
     "Reports": page_reports}[page]()
except FileNotFoundError as exc:
    st.warning(str(exc))
except Exception as exc:  # show a readable error instead of a blank page
    st.error(f"Something went wrong: {exc}")
    st.exception(exc)
