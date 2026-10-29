"""Home-win research page: frozen forecasts, prospective record, preregistered backtests, run controls.

Reads only local archives and report files (no downloads on page load). Research only; nothing here is promoted.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from lab.archive10 import ARCHIVE, canonical
from lab.config import CACHE_DIR, LAB_ROOT

KINDS = {"homewin_deep": "Weekly freeze (v1 deep)", "homewin_sim": "Simulator freeze", "homewin_v2_game": "Per-game T-90 freeze (v2)"}
REPORTS = {"v1": LAB_ROOT / "reports" / "homewin_deep" / "backtest.json",
           "v2": LAB_ROOT / "reports" / "homewin_v2" / "results.json",
           "v2_power": LAB_ROOT / "reports" / "homewin_v2" / "power.json",
           "sim": LAB_ROOT / "reports" / "homewin_sim" / "results.json",
           "sim_power": LAB_ROOT / "reports" / "homewin_sim" / "power.json"}
LOG_DIR = LAB_ROOT / "reports" / "homewin_logs"
COMMANDS = {
    "Weekly freeze (v1 deep, all 8 models)": ["scripts/home_win_deep.py", "freeze"],
    "Simulator freeze (full distributions)": ["scripts/home_win_sim.py", "freeze"],
    "Per-game T-90 freeze (only inside 90-105 min of a kickoff)": ["scripts/home_win_v2.py", "freeze-game"],
    "Score v1 freezes in the terminal log": ["scripts/home_win_deep.py", "score"],
}
LONG = {
    "v1 backtest (about 45 min)": ["scripts/home_win_deep.py", "backtest"],
    "v2 backtest (about 1.5 h)": ["scripts/home_win_v2.py", "backtest"],
    "Simulator backtest (about 45 min)": ["scripts/home_win_sim.py", "backtest"],
}
SIM_LABEL = "simulator"


# --------------------------------------------------------------------------- loading

@st.cache_data(show_spinner=False)
def _read_json(path: str, mtime_ns: int):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_json(path: Path):
    return _read_json(str(path), path.stat().st_mtime_ns) if path.exists() else None


def _verify(d: dict) -> bool:
    """Recompute the content hash. Simulator freezes made before 2026-10-29 06:40 UTC hashed their pmfs with
    integer keys, which JSON stores as strings; restoring the integer keys reproduces those hashes exactly."""
    if hashlib.sha256(canonical(d["content"])).hexdigest() == d.get("content_sha256"):
        return True
    games = d["content"].get("games")
    if not isinstance(games, list) or not any("margin_pmf" in g for g in games):
        return False
    restored = {**d["content"], "games": [{**g, **{k: {int(x): v for x, v in g[k].items()} for k in ("margin_pmf", "total_pmf") if k in g}}
                                          for g in games]}
    return hashlib.sha256(canonical(restored)).hexdigest() == d.get("content_sha256")


def load_archives(root: Path = ARCHIVE) -> dict[str, list[dict]]:
    """Every freeze archive by kind, each with a recomputed-hash integrity flag."""
    out = {}
    for kind in KINDS:
        rows = []
        for p in sorted((root / kind).glob("*.json")):
            d = read_json(p)
            if not d:
                continue
            ok = _verify(d)
            rows.append(d | {"_file": p.name, "_hash_ok": ok})
        out[kind] = rows
    return out


def frozen_table(arch: dict) -> pd.DataFrame:
    """One row per game: the earliest freeze of each kind (later freezes never replace earlier ones)."""
    rows = {}
    for d in sorted(arch.get("homewin_deep", []), key=lambda x: x["frozen_at"]):
        for g in d["content"]["games"]:
            r = rows.setdefault(g["gid"], {"gid": g["gid"], "season": d["content"]["season"], "week": d["content"]["week"],
                                           "kickoff_utc": g["kickoff_utc"], "home": g["home"], "away": g["away"]})
            if "p_elo" in r:
                continue
            r |= {k: g.get(k) for k in ("p_elo", "p_xgb_v1", "p_margin_platt", "p_xgb_deep_platt", "pred_margin",
                                        "market_p_home_at_freeze", "fpi_p_home", "qb_change_home", "qb_change_away")}
            r["v1_frozen_at"] = d["frozen_at"]
    for d in sorted(arch.get("homewin_sim", []), key=lambda x: x["frozen_at"]):
        for g in d["content"]["games"]:
            r = rows.setdefault(g["gid"], {"gid": g["gid"], "season": d["content"]["season"], "week": d["content"]["week"],
                                           "kickoff_utc": g["kickoff_utc"]})
            if "p_sim" in r:
                continue
            r |= {"p_sim": g["p_home"], "sim_p_tie": g["p_tie"], "sim_median_margin": g["median_margin"],
                  "sim_median_total": g["median_total"], "sim_frozen_at": d["frozen_at"]}
    for d in sorted(arch.get("homewin_v2_game", []), key=lambda x: x["frozen_at"]):
        g = d["content"]
        r = rows.setdefault(g["gid"], {"gid": g["gid"], "kickoff_utc": g["kickoff_utc"]})
        if "p_t90_xgb_deep" in r:
            continue
        r |= {"p_t90_xgb_deep": g.get("p_xgb_deep"), "p_t90_margin": g.get("p_margin"), "t90_frozen_at": d["frozen_at"],
              "market_p_home_t90": g.get("market_p_home_at_freeze")}
    df = pd.DataFrame(rows.values())
    if len(df):
        parts = df["gid"].str.split("_", expand=True)
        df["season"] = df.get("season", pd.Series(dtype=float)).fillna(parts[0].astype(int))
        df["week"] = df.get("week", pd.Series(dtype=float)).fillna(parts[1].astype(int))
        df["away"] = df.get("away", pd.Series(dtype=object)).fillna(parts[2])
        df["home"] = df.get("home", pd.Series(dtype=object)).fillna(parts[3])
    return df


def load_results(cache_dir: Path = CACHE_DIR) -> pd.DataFrame:
    """Final scores from the nfldata API cache that every runner refreshes (no network here)."""
    from lab.ingest import canonical_game_id
    rows = []
    for p in sorted((cache_dir / "xgb_api_games").glob("*.json")):
        for g in read_json(p) or []:
            if g.get("game_type") != "REG" or g.get("home_score") is None or g.get("away_score") is None:
                continue
            try:
                gid = canonical_game_id(g["season"], g["week"], g["away_team"], g["home_team"])
            except ValueError:
                continue
            rows.append({"gid": gid, "home_score": g["home_score"], "away_score": g["away_score"]})
    return pd.DataFrame(rows, columns=["gid", "home_score", "away_score"]).drop_duplicates("gid")


def model_columns(df: pd.DataFrame) -> dict[str, str]:
    cols = {"p_elo": "Elo", "p_xgb_v1": "XGBoost v1", "p_margin_platt": "Margin (Platt)", "p_xgb_deep_platt": "XGB deep (Platt)",
            "p_sim": "Simulator", "p_t90_xgb_deep": "XGB deep @T-90", "market_p_home_at_freeze": "Market at freeze",
            "fpi_p_home": "ESPN FPI at freeze"}
    return {k: v for k, v in cols.items() if k in df and df[k].notna().any()}


def score(df: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    m = df.merge(results, on="gid")
    m = m[m["home_score"] != m["away_score"]]
    if m.empty:
        return pd.DataFrame()
    y = (m["home_score"] > m["away_score"]).astype(float).to_numpy()
    out = []
    for col, name in model_columns(m).items():
        mask = m[col].notna().to_numpy()
        if not mask.any():
            continue
        p = np.clip(m.loc[mask, col].astype(float).to_numpy(), 1e-12, 1 - 1e-12)
        yy = y[mask]
        out.append({"Model": name, "Games": int(mask.sum()), "Log loss": float(-(yy * np.log(p) + (1 - yy) * np.log(1 - p)).mean()),
                    "Brier": float(((p - yy) ** 2).mean()), "Accuracy": float(((p >= 0.5) == (yy == 1)).mean())})
    return pd.DataFrame(out).sort_values("Log loss")


# --------------------------------------------------------------------------- tabs

def _pct(x):
    return "" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.1%}"


def tab_this_week(arch: dict, results: pd.DataFrame):
    df = frozen_table(arch)
    if df.empty:
        st.info("No frozen forecasts yet. Use the Run tab: start with the weekly freeze before the first kickoff.")
        return
    weeks = sorted({(int(s), int(w)) for s, w in zip(df["season"], df["week"])})
    s, w = st.selectbox("Week", weeks, index=len(weeks) - 1, format_func=lambda x: f"{x[0]} week {x[1]}", key="hw_week")
    wk = df[(df["season"] == s) & (df["week"] == w)].sort_values("kickoff_utc").merge(results, on="gid", how="left")
    cols = model_columns(wk)
    show = pd.DataFrame({"Kickoff (UTC)": pd.to_datetime(wk["kickoff_utc"]).dt.strftime("%a %m-%d %H:%M"),
                         "Game": wk["away"] + " @ " + wk["home"]})
    for c, name in cols.items():
        show[f"{name} P(home)"] = wk[c].map(_pct)
    if "sim_median_margin" in wk:
        show["Sim margin / total"] = [f"{m:+.0f} / {t:.0f}" if pd.notna(m) else "" for m, t in zip(wk["sim_median_margin"], wk["sim_median_total"])]
    show["Final"] = [f"{int(a)}-{int(h)}" if pd.notna(h) else "" for a, h in zip(wk["away_score"], wk["home_score"])]
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.caption("All values are as frozen before kickoff and never edited. Elo is the champion; every other model failed "
               "its preregistered gate against Elo and is shown for prospective tracking only. Market and FPI were "
               "captured at the same instant as the freeze.")

    sims = {g["gid"]: g for d in arch.get("homewin_sim", []) for g in d["content"]["games"]}
    have = [g for g in wk["gid"] if g in sims]
    if have:
        gid = st.selectbox("Simulator distribution", have, format_func=lambda g: g.split("_")[2] + " @ " + g.split("_")[3], key="hw_sim_game")
        g = sims[gid]
        mp = pd.DataFrame({"Home margin": list(map(int, g["margin_pmf"])), "Probability": list(g["margin_pmf"].values())})
        mp = mp[mp["Home margin"].between(-35, 35)]
        mp["Key number"] = mp["Home margin"].abs().isin([3, 7])
        tp = pd.DataFrame({"Total": list(map(int, g["total_pmf"])), "Probability": list(g["total_pmf"].values())})
        c1, c2 = st.columns(2)
        c1.altair_chart(alt.Chart(mp).mark_bar().encode(x="Home margin:O", y="Probability:Q",
                        color=alt.Color("Key number:N", legend=None), tooltip=["Home margin", alt.Tooltip("Probability", format=".1%")])
                        .properties(title=f"Margin: P(home) {g['p_home']:.1%}, tie {g['p_tie']:.2%}"), use_container_width=True)
        c2.altair_chart(alt.Chart(tp[tp["Total"].between(10, 80)]).mark_bar().encode(x="Total:O", y="Probability:Q",
                        tooltip=["Total", alt.Tooltip("Probability", format=".1%")]).properties(title=f"Total: median {g['median_total']:.0f}"),
                        use_container_width=True)
        st.caption("The simulator under-predicts margins of exactly 3 and 7 (16.9% vs 23.1% in the backtest) and its margins run too narrow.")


def tab_prospective(arch: dict, results: pd.DataFrame):
    bad = [d["_file"] for rows in arch.values() for d in rows if not d["_hash_ok"]]
    if bad:
        st.error(f"Archive hash mismatch (do not trust these): {bad}")
    n = {k: len(v) for k, v in arch.items()}
    st.write(" · ".join(f"{KINDS[k]}: {n[k]} archives" for k in KINDS))
    df = frozen_table(arch)
    sc = score(df, results) if len(df) else pd.DataFrame()
    if sc.empty:
        st.info("No frozen game has a final result yet.")
    else:
        st.dataframe(sc.style.format({"Log loss": "{:.4f}", "Brier": "{:.4f}", "Accuracy": "{:.1%}"}), hide_index=True, use_container_width=True)
        frozen_weeks = df.merge(results, on="gid")[["season", "week"]].drop_duplicates().shape[0]
        st.caption(f"{frozen_weeks} scored week(s). Models are scored only on the games each one froze, so game counts can differ.")
    p2, ps = read_json(REPORTS["v2_power"]) or {}, read_json(REPORTS["sim_power"]) or {}
    need = []
    if p2:
        need += [("v2 CLV at Friday", p2.get("clv", {}).get("N_CLV_weeks")), ("v2 log loss vs Elo", p2.get("log_loss", {}).get("N_LL_weeks"))]
    if ps:
        need += [(f"Simulator {k.split('_', 1)[1].replace('_', ' ')}", v.get("N_weeks")) for k, v in ps.items() if isinstance(v, dict) and "N_weeks" in v]
    if need:
        st.subheader("Weeks required before any verdict (committed in advance)")
        st.dataframe(pd.DataFrame(need, columns=["Test", "Frozen weeks needed"]), hide_index=True)


def _gate_rows(results: dict) -> pd.DataFrame:
    rows = []
    for m, c in results.items():
        if not isinstance(c, dict) or "ll_delta" not in c:
            continue
        rows.append({"Candidate": m, "Log-loss delta vs Elo": c["ll_delta"], "CI": f"[{c['ll_ci'][0]:+.5f}, {c['ll_ci'][1]:+.5f}]",
                     "DM p": c["dm"]["p"], "Brier delta": c["brier_delta"], "Seasons better": f"{c['seasons_better']}/{c['seasons']}",
                     "Gate": "PASS" if c.get("pass") else "fail"})
    return pd.DataFrame(rows)


def tab_backtests():
    st.caption("One look per preregistered hypothesis on reused 2012-2026 history. Positive deltas mean worse than Elo. "
               "Readings are provisional until an independent rebuild matches.")
    v1, v2, sim = read_json(REPORTS["v1"]), read_json(REPORTS["v2"]), read_json(REPORTS["sim"])
    with st.expander("v1 deep model: PBP ratings + QB (docs/HOMEWIN_DEEP_RESULTS.md)", expanded=v1 is not None):
        if v1:
            st.dataframe(pd.DataFrame([{"Model": m, "Log loss": r["log_loss"], "Brier": r["brier"], "Accuracy": r["accuracy"],
                                        "ROC AUC": r["roc_auc"], "ECE": r["ece"]} for m, r in v1["models"].items()]).sort_values("Log loss"),
                         hide_index=True, use_container_width=True)
            st.dataframe(_gate_rows(v1["gate"]["results"]), hide_index=True, use_container_width=True)
        else:
            st.info("No v1 backtest report yet.")
    with st.expander("v2: walk-forward EPA, per-game decision points, stacking, CLV (docs/HOMEWIN_V2_RESULTS.md)"):
        if v2:
            st.markdown("**H1 weekly (walk-forward EPA)**")
            st.dataframe(_gate_rows(v2["H1"]["gate"]["results"]), hide_index=True, use_container_width=True)
            st.markdown("**H2 per-game T-90**")
            st.dataframe(_gate_rows(v2["H2"]["gate_t90"]["results"]), hide_index=True, use_container_width=True)
            voi = pd.DataFrame(v2["H2"]["value_of_information"]).T[["qb_change_flags", "elo", "margin", "xgb_deep"]]
            st.markdown("**Value of information** (log loss on the same games)")
            st.dataframe(voi, use_container_width=True)
            st.markdown("**H3 stacks with Elo** (97.5% intervals)")
            st.dataframe(pd.DataFrame([{"Stack": f"elo + {m}", **{k: f"{v['w']:+.3f} [{v['ci'][0]:+.3f}, {v['ci'][1]:+.3f}]" for k, v in v2["H3"][m]["weights"].items()},
                                        "Adds value": v2["H3"][m]["adds_value"], "Walk-forward LL": v2["H3"][m]["walk_forward_stack_ll"]}
                                       for m in ("margin", "xgb_deep")]), hide_index=True, use_container_width=True)
            st.markdown(f"**H4 CLV** (primary {v2['H4']['primary']}; others descriptive)")
            st.dataframe(pd.DataFrame([{"Point/model": k, "Games": v["games"], "Mean CLV": v["mean_clv"],
                                        "95% CI": f"[{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}]" if v["ci95"] else "",
                                        "Toward/away": f"{v['positive']}/{v['negative']}", "Sign p": v["sign_test_p_one_sided"]}
                                       for k, v in v2["H4"]["results"].items()]), hide_index=True, use_container_width=True)
        else:
            st.info("No v2 report yet.")
    with st.expander("Drive-level simulator (docs/HOMEWIN_SIM_RESULTS.md)"):
        if sim:
            rows = [{"Family": "D drives", "Candidate": sim["D"]["mean_a"], "Baseline": sim["D"]["mean_b"], "Delta": sim["D"]["delta"],
                     "CI": f"[{sim['D']['ci'][0]:+.4f}, {sim['D']['ci'][1]:+.4f}]", "Result": "PASS" if sim["D"]["pass"] else "fail"}]
            rows += [{"Family": f"G {k}", "Candidate": x["mean_a"], "Baseline": x["mean_b"], "Delta": x["delta"],
                      "CI": f"[{x['ci'][0]:+.4f}, {x['ci'][1]:+.4f}]", "Result": "PASS" if x["pass"] else "fail"} for k, x in sim["G"].items()]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.dataframe(_gate_rows({k: v for k, v in sim["W"].items() if k != "elo_metrics"}), hide_index=True, use_container_width=True)
            abl = read_json(LAB_ROOT / "reports" / "homewin_sim" / "ablation_team_effects.json")
            if abl:
                st.warning(f"Post-look ablation: team effects make drive predictions worse by {abl['delta']:+.4f} nats "
                           f"[{abl['ci'][0]:+.4f}, {abl['ci'][1]:+.4f}]. The drive-family pass comes from clock and score state.")
            d = sim["descriptive"]
            st.write(f"Margins of exactly 3 or 7: actual {d['key_3_7_actual']:.1%}, simulated {d['key_3_7_predicted']:.1%}. "
                     f"Ties: {d['tie_actual']:.2%} vs {d['tie_predicted']:.2%}. PIT uniformity p (margin/total): "
                     f"{d['pit_margin']['chi2_p']:.3g} / {d['pit_total']['chi2_p']:.3g}.")
        else:
            st.info("No simulator report yet.")


def _launch(label: str, args: list[str]):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / (label.split(" (")[0].replace(" ", "_").replace("/", "-") + ".log")
    py = LAB_ROOT / ".venv" / "Scripts" / "python.exe"
    fh = log.open("w", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen([str(py if py.exists() else sys.executable), "-W", "ignore", *args], cwd=LAB_ROOT, stdout=fh,
                     stderr=subprocess.STDOUT, creationflags=flags)
    st.success(f"Started. Log: {log}")


def tab_run():
    st.caption("Each button starts a separate background process; the page stays usable. Freezes fetch fresh data, "
               "write a write-once archive and append the ledger. They never change the champion or the scheduler.")
    for label, args in COMMANDS.items():
        if st.button(label, key=f"hw_run_{label}"):
            _launch(label, args)
    with st.expander("Backtests (long, one look each; rerunning only reproduces committed results)"):
        ok = st.checkbox("I understand these take 45-90 minutes and reuse already-scored history", key="hw_long_ok")
        for label, args in LONG.items():
            if st.button(label, key=f"hw_long_{label}", disabled=not ok):
                _launch(label, args)
    logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True) if LOG_DIR.exists() else []
    if logs:
        pick = st.selectbox("Log", logs, format_func=lambda p: p.name, key="hw_log")
        if st.button("Refresh log", key="hw_log_refresh"):
            st.rerun()
        lines = pick.read_text(encoding="utf-8", errors="replace").splitlines()
        st.code("\n".join(lines[-40:]) or "(empty)")


def render(archive_root: Path = ARCHIVE, cache_dir: Path = CACHE_DIR):
    st.title("Home-Win Research")
    st.caption("Elo remains the champion. The deep model, v2 and the drive simulator are research challengers that "
               "failed their preregistered gates; they are frozen weekly so the prospective record can accumulate.")
    arch, results = load_archives(archive_root), load_results(cache_dir)
    t1, t2, t3, t4 = st.tabs(["This week", "Prospective record", "Backtests", "Run"])
    with t1:
        tab_this_week(arch, results)
    with t2:
        tab_prospective(arch, results)
    with t3:
        tab_backtests()
    with t4:
        tab_run()
