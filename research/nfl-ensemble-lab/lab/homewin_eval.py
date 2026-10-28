"""Walk-forward evaluation, preregistered gate, freeze and scoring for the deep home-win model.

Protocol: docs/HOMEWIN_DEEP_PREREGISTRATION.md (commit 741a13e7).
"""
from __future__ import annotations

import hashlib
import json
import subprocess

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score

from . import homewin_deep as h
from .archive10 import ARCHIVE, canonical, save
from .config import LAB_ROOT

PREREG_COMMIT = "741a13e7"
BASE_MODELS = ["elo", "xgb_v1", "margin", "xgb_deep"]
MODELS = BASE_MODELS + [f"{m}_platt" for m in BASE_MODELS]
GATE_CANDIDATES = ["margin", "margin_platt", "xgb_deep", "xgb_deep_platt"]
PRIMARY = "margin_platt"
N_BOOT, SEED, DM_LAG = 2000, 0, 4
REPORT_DIR = LAB_ROOT / "reports" / "homewin_deep"
FREEZE_KIND = "homewin_deep"


# --------------------------------------------------------------------------- walk-forward

def walk_forward(data: h.Data, feats: pd.DataFrame, progress=print, prior_preds: pd.DataFrame | None = None,
                 prior_params: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """For each week from 2012 with played games: train on rows before T_w, predict only that week.

    With prior_preds/prior_params, resumes after the last week already predicted (same results as a full run).
    """
    from xgboost import XGBClassifier
    import xgb_home_win as v1

    v1X, _ = h.v1_frame(data)
    v1X = v1X.merge(data.games[["gid", "kickoff_utc", "y_home_win"]], on="gid")
    usable = feats[feats["played"]].copy()
    cls = usable[~usable["tie"]].copy()
    cls["y_home_win"] = cls["y_home_win"].astype(int)
    weeks = cls[cls["season"] >= h.EVAL_START][["season", "week"]].drop_duplicates().sort_values(["season", "week"])
    out = prior_preds.to_dict("records") if prior_preds is not None and len(prior_preds) else []
    params = dict(prior_params or {})
    if out:
        done = max((r["season"], r["week"]) for r in out)
        weeks = weeks[[(a, b) > done for a, b in zip(weeks["season"], weeks["week"])]]
    for s, w in weeks.itertuples(index=False):
        T = h.week_cutoff(data, s, w)
        test = cls[(cls["season"] == s) & (cls["week"] == w)]
        tr_m = usable[(usable["season"] >= h.MARGIN_TRAIN_START) & (usable["kickoff_utc"] < T)]
        tr_c = cls[(cls["season"] >= h.MARGIN_TRAIN_START) & (cls["kickoff_utc"] < T)]
        hist = pd.DataFrame(out)
        hist = hist[hist["kickoff_utc"] < T] if len(hist) else hist
        resid = (hist["margin"] - hist["pred_margin"]).to_numpy() if len(hist) else np.array([])

        pred, p_margin, sigma = h.margin_predict(tr_m, test, resid)
        if s not in params:
            params[s] = h.tune_deep(tr_c, s)
            progress(f"  {s}: tuned xgb_deep {params[s]}")
        p_deep = h.deep_predict(tr_c, test, params[s])
        v_tr = v1X[v1X["kickoff_utc"] < T]
        v_te = v1X.set_index("gid").loc[test["gid"]]
        m1 = XGBClassifier(**v1.XGB_PARAMS).fit(v_tr[v1.FEATURES], v_tr["y_home_win"].astype(int))
        p_v1 = m1.predict_proba(v_te[v1.FEATURES])[:, 1]

        block = test[["gid", "season", "week", "kickoff_utc", "decision_utc", "margin", "y_home_win"]].copy()
        block["pred_margin"], block["sigma"] = pred, sigma
        block["p_elo"], block["p_xgb_v1"] = test["elo_prob_home"].to_numpy(), p_v1
        block["p_margin"], block["p_xgb_deep"] = p_margin, p_deep
        for m in BASE_MODELS:
            ph = hist[f"p_{m}"].to_numpy() if len(hist) else np.array([])
            yh = hist["y_home_win"].to_numpy() if len(hist) else np.array([])
            block[f"p_{m}_platt"] = h.platt(ph, yh, block[f"p_{m}"].to_numpy())
        out.extend(block.to_dict("records"))
    return pd.DataFrame(out), params


# --------------------------------------------------------------------------- metrics and tests

def _ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def reliability(y, p, bins: int = 10) -> tuple[list[dict], float]:
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    rows, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        if not m.any():
            continue
        mp, my = float(p[m].mean()), float(y[m].mean())
        rows.append({"bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}", "n": int(m.sum()), "mean_p": round(mp, 4), "win_rate": round(my, 4)})
        ece += m.mean() * abs(mp - my)
    return rows, float(ece)


def metrics(y, p) -> dict:
    rel, ece = reliability(y, p)
    return {"n": int(len(y)), "log_loss": float(_ll(y, p).mean()), "brier": float(((p - y) ** 2).mean()),
            "accuracy": float(((p >= 0.5) == (y == 1)).mean()), "roc_auc": float(roc_auc_score(y, p)) if len(set(y)) > 1 else None,
            "ece": ece, "reliability": rel}


def cluster_boot(d: np.ndarray, clusters: np.ndarray, alpha: float, n_boot: int = N_BOOT, seed: int = SEED) -> tuple:
    """Percentile CI of the mean paired difference, resampling whole weeks."""
    codes, inv = np.unique(clusters, return_inverse=True)
    sums, counts = np.bincount(inv, weights=d), np.bincount(inv)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(codes), (n_boot, len(codes)))
    means = sums[draws].sum(1) / counts[draws].sum(1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def dm_test(d: np.ndarray, clusters: np.ndarray, order: np.ndarray, lag: int = DM_LAG) -> dict:
    """Diebold-Mariano on weekly mean loss differences, Newey-West variance."""
    s = pd.DataFrame({"d": d, "c": clusters, "o": order}).groupby("c").agg(d=("d", "mean"), o=("o", "min")).sort_values("o")["d"].to_numpy()
    n, mu = len(s), s.mean()
    x = s - mu
    var = x @ x / n + 2 * sum((1 - k / (lag + 1)) * (x[k:] @ x[:-k] / n) for k in range(1, lag + 1))
    stat = mu / np.sqrt(var / n)
    return {"weeks": n, "stat": float(stat), "p": float(2 * norm.sf(abs(stat)))}


def compare(df: pd.DataFrame, a: str, b: str, alpha: float) -> dict:
    y = df["y_home_win"].to_numpy(float)
    la, lb = _ll(y, df[a].to_numpy()), _ll(y, df[b].to_numpy())
    ba, bb = (df[a] - y) ** 2, (df[b] - y) ** 2
    cl = (df["season"].astype(str) + "_" + df["week"].astype(str)).to_numpy()
    order = df["kickoff_utc"].astype("int64").to_numpy()
    d = la - lb
    by_season = pd.DataFrame({"s": df["season"], "d": d}).groupby("s")["d"].mean()
    return {"a": a, "b": b, "n": int(len(df)), "ll_delta": float(d.mean()), "ll_ci": cluster_boot(d, cl, alpha),
            "ci_level": 1 - alpha, "brier_delta": float((ba - bb).mean()), "dm": dm_test(d, cl, order),
            "seasons_better": int((by_season < 0).sum()), "seasons": int(len(by_season))}


def evaluate(preds: pd.DataFrame, data: h.Data) -> dict:
    y = preds["y_home_win"].to_numpy(float)
    res = {"prereg_commit": PREREG_COMMIT, "window": f"{int(preds.season.min())}-{int(preds.season.max())}",
           "models": {m: metrics(y, preds[f"p_{m}"].to_numpy()) for m in MODELS},
           "per_season_log_loss": preds.groupby("season").apply(
               lambda d: {m: float(_ll(d["y_home_win"].to_numpy(float), d[f"p_{m}"].to_numpy()).mean()) for m in MODELS}).to_dict()}
    alpha = 0.05 / len(GATE_CANDIDATES)
    gate = {}
    for m in GATE_CANDIDATES:
        c = compare(preds, f"p_{m}", "p_elo", alpha)
        c["pass"] = bool(c["ll_ci"][1] < 0 and c["dm"]["p"] < alpha and c["brier_delta"] <= 0 and c["seasons_better"] >= 9)
        gate[m] = c
    res["gate"] = {"family_alpha": alpha, "primary": PRIMARY, "results": gate}
    res["vs_xgb_v1"] = {m: compare(preds, f"p_{m}", "p_xgb_v1", 0.05) for m in GATE_CANDIDATES}

    mk = market_frame(preds, data)
    res["market_coverage"] = {"games_scored": int(len(preds)), "seasons_with_any_t1_quote": sorted(int(s) for s in mk.loc[mk["p_market_close"].notna(), "season"].unique()),
                              "close_available": int(mk["p_market_close"].notna().sum()),
                              "decision_available": int(mk["p_market_decision"].notna().sum())}
    res["vs_market"] = {}
    for col in ("p_market_close", "p_market_decision"):
        sub = mk[mk[col].notna()]
        if len(sub) >= 10:
            res["vs_market"][col] = {"market": metrics(sub["y_home_win"].to_numpy(float), sub[col].to_numpy()),
                                     **{m: compare(sub, f"p_{m}", col, 0.05) for m in MODELS}}
    return res


def market_frame(preds: pd.DataFrame, data: h.Data) -> pd.DataFrame:
    g = data.games.set_index("gid")
    rows = []
    for r in preds.itertuples(index=False):
        gg = g.loc[r.gid]
        close = h.market_probability(data.quotes, gg["home"], gg["away"], gg["kickoff_utc"], gg["kickoff_utc"])
        dec = h.market_probability(data.quotes, gg["home"], gg["away"], gg["kickoff_utc"], gg["decision_utc"])
        rows.append({"gid": r.gid, "p_market_close": close["p_home"], "p_market_decision": dec["p_home"]})
    return preds.merge(pd.DataFrame(rows), on="gid")


# --------------------------------------------------------------------------- leakage check (preregistered; stops the run)

LEAKAGE_WEEKS = [(2016, 3), (2020, 12), (2024, 9), (2026, 6)]


def leakage_check(data: h.Data, weeks=LEAKAGE_WEEKS) -> dict:
    """Corrupt every result, play, injury row and quote at or after T_w; week w's inputs must not move."""
    pm = h.qb_prior_mean(data.qb_games[data.qb_games["season"] <= 2011])
    out = {}
    for season, week in weeks:
        T = h.week_cutoff(data, season, week)
        base = h.week_features(data, season, week, prior_mean=pm)
        bad = h.perturb_after(data, T, season, week)
        if not (bad.team_games["pass_epa"] != data.team_games["pass_epa"]).any():
            raise h.DataCheckError(f"perturbation did not change future plays for {season} w{week}")
        again = h.week_features(bad, season, week, prior_mean=pm)
        num = base.select_dtypes("number").columns
        same = np.allclose(base[num].to_numpy(float), again[num].to_numpy(float), equal_nan=True) and             base.filter(like="qb_expected").equals(again.filter(like="qb_expected"))
        g = data.games[(data.games["season"] == season) & (data.games["week"] == week)]
        mk = 0
        for r in g.itertuples(index=False):
            a = h.market_probability(data.quotes, r.home, r.away, r.kickoff_utc, T)["p_home"]
            b = h.market_probability(bad.quotes, r.home, r.away, r.kickoff_utc, T)["p_home"]
            same &= (np.isnan(a) and np.isnan(b)) or a == b
            mk += not np.isnan(a)
        inj = data.injuries
        used = inj[(inj["season"] == season) & (inj["week"] == week) & inj["available_at"].notna() & (inj["available_at"] < T)]
        if not same:
            raise h.DataCheckError(f"LEAKAGE: features or market for {season} w{week} changed when post-cutoff data was corrupted")
        out[f"{season}_w{week}"] = {"games": len(g), "pre_cutoff_injury_rows": len(used), "market_games": mk, "unchanged": True}
    # Negative control: a cutoff 8 days late must let the corruption through, proving the check can fail.
    season, week = weeks[-1]
    late = h.week_cutoff(data, season, week) + pd.Timedelta(days=8)
    bad = h.perturb_after(data, h.week_cutoff(data, season, week), season, week)
    a = h.week_features(data, season, week, cutoff=late, prior_mean=pm)
    b = h.week_features(bad, season, week, cutoff=late, prior_mean=pm)
    if np.allclose(a.select_dtypes("number").to_numpy(float), b.select_dtypes("number").to_numpy(float), equal_nan=True):
        raise h.DataCheckError("leakage check negative control did not detect a late cutoff")
    out["negative_control_detected"] = True
    return out


# --------------------------------------------------------------------------- freeze and score

def _git_sha() -> str:
    return subprocess.run(["git", "-C", str(LAB_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def fpi_projection(event_id: str | None, espn_home: str | None, home: str) -> dict:
    if not event_id:
        return {"fpi_p_home": None, "fpi_last_modified": None}
    try:
        p = h._get_json(f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/{event_id}/competitions/{event_id}/predictor")
        gp = next(s["value"] for s in p["homeTeam"]["statistics"] if s["name"] == "gameProjection") / 100
        return {"fpi_p_home": gp if espn_home == home else 1 - gp, "fpi_last_modified": p.get("lastModified")}
    except Exception as exc:  # optional external comparison
        return {"fpi_p_home": None, "fpi_last_modified": None, "fpi_error": str(exc)[:200]}


def freeze(data: h.Data, feats: pd.DataFrame, preds: pd.DataFrame, params: dict, now: pd.Timestamp | None = None) -> dict:
    """Archive every model's probability for the next week's games that have not kicked off."""
    from xgboost import XGBClassifier
    import xgb_home_win as v1

    now = pd.Timestamp.now(tz="UTC") if now is None else now
    g = data.games
    up = g[~g["played"] & (g["kickoff_utc"] > now)]
    if up.empty:
        return {"frozen": 0, "reason": "no upcoming games"}
    s, w = up.sort_values("kickoff_utc").iloc[0][["season", "week"]]
    T = h.week_cutoff(data, s, w)
    cutoff = min(now, T)
    end = h.season_end_ratings(data.team_games[data.team_games["season"] < s])
    pm = h.qb_prior_mean(data.qb_games[data.qb_games["season"] <= 2011])
    f = h.week_features(data, s, w, cutoff=cutoff, end_ratings=end, prior_mean=pm)
    f = f.merge(g[["gid", "kickoff_utc", "home", "away", "espn_event_id", "espn_home"]], on="gid")
    f = f[f["kickoff_utc"] > now]

    usable = feats[feats["played"] & (feats["kickoff_utc"] < cutoff)]
    cls = usable[~usable["tie"]].assign(y_home_win=lambda d: d["y_home_win"].astype(int))
    hist = preds[preds["kickoff_utc"] < cutoff]
    pred, p_margin, sigma = h.margin_predict(usable[usable["season"] >= h.MARGIN_TRAIN_START], f,
                                             (hist["margin"] - hist["pred_margin"]).to_numpy())
    p_deep = h.deep_predict(cls[cls["season"] >= h.MARGIN_TRAIN_START], f, params.get(s) or h.tune_deep(cls, s))
    v1X, vhist = h.v1_frame(data)
    v1X = v1X.merge(g[["gid", "kickoff_utc", "y_home_win"]], on="gid")
    v_tr = v1X[v1X["kickoff_utc"] < cutoff]
    m1 = XGBClassifier(**v1.XGB_PARAMS).fit(v_tr[v1.FEATURES], v_tr["y_home_win"].astype(int))
    tg = g.set_index("gid").loc[f["gid"]].reset_index().rename(columns={"home": "home_id", "away": "away_id"})
    p_v1 = v1.predict_upcoming(m1, None, vhist, tg)["p_home"].to_numpy()

    probs = {"elo": f["elo_prob_home"].to_numpy(), "xgb_v1": p_v1, "margin": p_margin, "xgb_deep": p_deep}
    for m in BASE_MODELS:
        probs[f"{m}_platt"] = h.platt(hist[f"p_{m}"].to_numpy(), hist["y_home_win"].to_numpy(), probs[m])
    games = []
    for i, r in enumerate(f.itertuples(index=False)):
        mk = h.market_probability(data.quotes, r.home, r.away, r.kickoff_utc, now)
        games.append({"gid": r.gid, "kickoff_utc": r.kickoff_utc.isoformat(), "home": r.home, "away": r.away,
                      "pred_margin": float(pred[i]), "sigma": sigma, "qb_expected_home": r.qb_expected_home,
                      "qb_expected_away": r.qb_expected_away, "qb_change_home": int(r.qb_change_home),
                      "qb_change_away": int(r.qb_change_away),
                      **{f"p_{m}": float(probs[m][i]) for m in MODELS},
                      "market_p_home_at_freeze": mk["p_home"], "market_books": mk["books"], "market_quote_time": mk["quote_time"],
                      **fpi_projection(r.espn_event_id, r.espn_home, r.home)})
    content = {"season": int(s), "week": int(w), "decision_utc": T.isoformat(), "feature_cutoff_utc": cutoff.isoformat(),
               "games": games}
    meta = {"prereg_commit": PREREG_COMMIT, "code_commit": _git_sha(), "frozen_at": now.isoformat(),
            "first_kickoff_utc": up["kickoff_utc"].min().isoformat()}
    saved = save(FREEZE_KIND, f"{int(s)}_w{int(w):02d}", content, meta)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if saved["new"]:
        with (REPORT_DIR / "freeze_ledger.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"season": int(s), "week": int(w), "games": len(games), "frozen_at": now.isoformat(),
                                 "sha256": saved["sha256"], "file": saved["file"].split("archive")[-1].lstrip("\\/")}) + "\n")
    return saved | {"season": int(s), "week": int(w), "games": games}


def score_freezes(data: h.Data) -> pd.DataFrame:
    """Score every archived freeze against final results; verify each archive's hash first."""
    rows = []
    res = data.games.set_index("gid")
    for p in sorted((ARCHIVE / FREEZE_KIND).glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if hashlib.sha256(canonical(d["content"])).hexdigest() != d["content_sha256"]:
            raise h.DataCheckError(f"Freeze archive hash mismatch: {p.name}")
        for gm in d["content"]["games"]:
            r = res.loc[gm["gid"]] if gm["gid"] in res.index else None
            if r is None or not r["played"] or r["tie"]:
                continue
            rows.append({"file": p.name, "frozen_at": d["frozen_at"], "gid": gm["gid"], "y_home_win": int(r["y_home_win"]),
                         **{k: v for k, v in gm.items() if k.startswith("p_") or k in ("market_p_home_at_freeze", "fpi_p_home")}})
    return pd.DataFrame(rows)
