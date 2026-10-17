"""Phase 8 specialist framework (implements docs/PHASE8_PREREGISTRATION.md; research only).

Every specialist: own hypothesis, explicit input boundary (no rating-margin difference), walk-forward fit on seasons
< s with preprocessing inside the training window, Platt calibration on its own earlier OOF predictions, abstention
when inputs are missing. Output: one row per (game, specialist) with p_home (+ margin/total for E) or NaN (abstained).
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..config import ARTIFACTS_DIR

OUT = ARTIFACTS_DIR / "phase8"
TARGETS = list(range(2018, 2027))
FORBIDDEN = ("rating_margin", "rating_epa")          # the shared team-strength signal no specialist may use
SEED = 20261017


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _sig(x):
    return 1 / (1 + np.exp(-x))


# --------------------------------------------------------------------------- research data snapshot

def research_frame() -> tuple[pd.DataFrame, str]:
    from ..data_pipeline import GAMES_TABLE, load_feature_store
    from . import drives
    fs = load_feature_store()
    g = pd.read_parquet(GAMES_TABLE)
    dr = drives.build(g, sorted(g["season"].unique()))
    for side in ("home", "away"):
        fs = fs.merge(dr.rename(columns={c: f"{side}_{c}" for c in dr.columns if c not in ("game_id", "team")})
                      .rename(columns={"team": f"{side}_team"}), on=["game_id", f"{side}_team"], how="left")
    fs = fs[fs["season"] >= 2016].sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    sig = hashlib.sha256(pd.util.hash_pandas_object(fs[["game_id", "home_win"]].fillna(-1), index=False).values.tobytes()).hexdigest()[:12]
    return fs, sig


# --------------------------------------------------------------------------- specialist definitions

def _cols(df, pred):
    return [c for c in df.columns if pred(c) and not any(f in c for f in FORBIDDEN)]


class Specialist:
    key, name, hypothesis, mechanism = "", "", "", ""

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        f = cls.__dict__.get("features")
        if f is not None:                                  # every specialist's feature list passes the rating guard
            cls.features = lambda self, df, _f=f: allowed(_f(self, df))

    def features(self, df: pd.DataFrame) -> list[str]:
        raise NotImplementedError

    def prepare(self, df, train):            # optional feature construction with training-window statistics
        return df

    def abstain(self, df) -> np.ndarray:
        cols = self.features(df)
        return (df[cols].isna().mean(axis=1) > 0.5).to_numpy()

    def model(self):
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))


class Availability(Specialist):
    key, name = "A", "Player availability & lineup"
    hypothesis = "Who is expected to play (missing snaps, starters out, QB uncertainty, OL continuity) adds information beyond team form."
    mechanism = "L2 logistic regression on availability counts; abstains without a verified report for both teams."

    def features(self, df):
        keep = ("_missing_share", "_starters_out", "_starters_confirmed_out", "_uncertainty", "ol_expected_continuity", "ol_same_as_last_game")
        f = _cols(df, lambda c: c.startswith("diff_p72_") and c.endswith(keep))
        f += _cols(df, lambda c: c.startswith(("home_qb_", "away_qb_", "home_qb7_", "away_qb7_")) and c.split("_", 1)[1].split("_", 1)[1] in
                   ("change", "projected_out", "questionable", "returning"))
        f += _cols(df, lambda c: c.startswith("diff_inj_"))
        return sorted(set(f))

    def abstain(self, df):
        return ~((df["home_p72_report_known"] == 1) & (df["away_p72_report_known"] == 1)).to_numpy()


PAIRS = [("blend_pass_epa", "blend_d_pass_epa"), ("blend_rush_epa", "blend_d_rush_epa"), ("blend_explosive_rate", "blend_d_explosive_rate"),
         ("blend_sack_rate", "blend_d_sack_rate"), ("blend_third_conv", "blend_d_third_conv"), ("blend_rz_td_rate", "blend_d_rz_td_rate"),
         ("blend_pass_sr", "blend_d_pass_sr"), ("blend_rush_sr", "blend_d_rush_sr"),
         ("p4pfr_blend_pfr_pressured_rate", "p4pfr_blend_pfr_def_pressure_rate"),
         ("p4pfr_blend_pfr_ybc_per_carry", "p4pfr_blend_def_pfr_ybc_allowed"),
         ("p4ngs_blend_ngs_separation", "p4ngs_blend_def_ngs_separation_allowed"),
         ("p4ngs_blend_ngs_cpoe", "p4ngs_blend_def_ngs_cpoe_allowed")]


class Matchup(Specialist):
    key, name = "B", "Tactical matchup"
    hypothesis = "Specific unit-vs-unit interactions (protection vs rush, passing vs coverage, run vs run defense) matter beyond totals."
    mechanism = "Gradient-boosted trees (depth 3) on standardised unit pairings: per side the offence-defence sum and product, net of both sides."

    def prepare(self, df, train):
        df = df.copy()
        for o, d in PAIRS:
            cols = [f"{s}_{x}" for s in ("home", "away") for x in (o, d)]
            if not all(c in df for c in cols):
                continue
            mo = pd.concat([train[f"home_{o}"], train[f"away_{o}"]]).agg(["mean", "std"])
            md = pd.concat([train[f"home_{d}"], train[f"away_{d}"]]).agg(["mean", "std"])
            z = lambda s, m: (s - m["mean"]) / (m["std"] or 1)
            for side, opp in (("home", "away"), ("away", "home")):
                zo, zd = z(df[f"{side}_{o}"], mo), z(df[f"{opp}_{d}"], md)
                df[f"p8mx_{side}_{o}_sum"], df[f"p8mx_{side}_{o}_prod"] = zo + zd, zo * zd
            df[f"p8mx_net_{o}_sum"] = df[f"p8mx_home_{o}_sum"] - df[f"p8mx_away_{o}_sum"]
            df[f"p8mx_net_{o}_prod"] = df[f"p8mx_home_{o}_prod"] - df[f"p8mx_away_{o}_prod"]
        return df

    def features(self, df):
        return [c for c in df.columns if c.startswith("p8mx_net_")]

    def model(self):
        return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.04, max_iter=250, l2_regularization=2.0,
                                              min_samples_leaf=60, random_state=SEED)


FORM_STATS = ["epa_pp", "pass_epa", "rush_epa", "sr", "early_epa", "d_epa_pp", "d_pass_epa", "d_rush_epa", "d_sr"]


class FormChange(Specialist):
    key, name = "C", "Recent form & change-point"
    hypothesis = "Genuine change appears as shrunk recent-vs-baseline shifts and personnel/coaching changes not yet in season ratings."
    mechanism = "L2 logistic regression on (last 3 - season blend) shifts, QB/coach/OL/snap-distribution change indicators."

    def prepare(self, df, train):
        df = df.copy()
        for st in FORM_STATS:
            for side in ("home", "away"):
                df[f"p8chg_{side}_{st}"] = df[f"{side}_l3_{st}"] - df[f"{side}_blend_{st}"]
            df[f"p8chg_net_{st}"] = df[f"p8chg_home_{st}"] - df[f"p8chg_away_{st}"]
        for side in ("home", "away"):
            df[f"p8chg_{side}_snapdist"] = df.get(f"{side}_p4roster_l5_returning_snap_share") - df.get(f"{side}_p4roster_blend_returning_snap_share")
        df["p8chg_net_snapdist"] = df["p8chg_home_snapdist"] - df["p8chg_away_snapdist"]
        return df

    def features(self, df):
        f = [c for c in df.columns if c.startswith("p8chg_net_")]
        f += [c for c in df.columns if c in ("home_qb_change", "away_qb_change", "home_qb_offseason", "away_qb_offseason",
                                             "home_coach_new_this_season", "away_coach_new_this_season",
                                             "home_coach_changed_midseason", "away_coach_changed_midseason", "p3_diff_ol_churn_l4")]
        return f


class Environment(Specialist):
    key, name = "D", "Game environment"
    hypothesis = "Rest, travel, time zones, roof, division and home field add little beyond ratings (expected weak; no weather)."
    mechanism = "L2 logistic regression; no weather because historical forecasts are not recoverable (actual weather is post hoc)."

    def features(self, df):
        f = [c for c in df.columns if c.startswith("ctx_")]
        f += [c for c in df.columns if c in ("p3_diff_travel_km", "p3_diff_tz_shift", "p3_diff_body_clock_hour", "home_rest_days", "away_rest_days")]
        return f

    def abstain(self, df):
        return np.zeros(len(df), bool)


class DriveSim(Specialist):
    key, name = "E", "Drive & scoring simulation"
    hypothesis = "Scores built from possessions x drive outcomes give differently shaped errors than rating-difference models."
    mechanism = ("Opponent-adjusted (log5) TD and FG probabilities per drive with a home edge, expected drives from both teams' pace, "
                 "Monte Carlo of 4,000 games -> P(win), margin, total; parameters from training seasons only; Platt-calibrated.")
    N_SIM = 4000

    def features(self, df):
        return [c for c in df.columns if c.startswith(("home_p8dr_blend", "away_p8dr_blend"))]

    def fit_predict(self, train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
        lg = {}
        for k in ("td_rate", "fg_rate", "drives"):
            lg[k] = float(pd.concat([train[f"home_p8dr_blend_{k}"], train[f"away_p8dr_blend_{k}"]]).mean())
        # home edge on TD odds from training games: mean log-odds ratio of realised home vs away scoring proxies
        tr = train.dropna(subset=["home_score", "away_score"])
        hpts, apts = tr["home_score"].mean(), tr["away_score"].mean()
        edge = float(np.log(max(hpts, 1) / max(apts, 1)))
        odds = lambda p: p / (1 - p)
        out = []
        for r in test.itertuples(index=False):
            row = r._asdict()
            vals = {k: row.get(k) for k in ("home_p8dr_blend_td_rate", "away_p8dr_blend_td_rate", "home_p8dr_blend_def_td_rate",
                                             "away_p8dr_blend_def_td_rate", "home_p8dr_blend_fg_rate", "away_p8dr_blend_fg_rate",
                                             "home_p8dr_blend_def_fg_rate", "away_p8dr_blend_def_fg_rate", "home_p8dr_blend_drives",
                                             "away_p8dr_blend_drives")}
            if any(v is None or pd.isna(v) for v in vals.values()):
                out.append({"game_id": r.game_id, "raw": np.nan, "margin": np.nan, "total": np.nan})
                continue

            def log5(a, b, l, e=0.0):
                o = odds(min(max(a, 1e-3), 0.95)) * odds(min(max(b, 1e-3), 0.95)) / odds(l) * np.exp(e)
                return o / (1 + o)
            h_td = log5(vals["home_p8dr_blend_td_rate"], vals["away_p8dr_blend_def_td_rate"], lg["td_rate"], edge / 2)
            a_td = log5(vals["away_p8dr_blend_td_rate"], vals["home_p8dr_blend_def_td_rate"], lg["td_rate"], -edge / 2)
            h_fg = log5(vals["home_p8dr_blend_fg_rate"], vals["away_p8dr_blend_def_fg_rate"], lg["fg_rate"])
            a_fg = log5(vals["away_p8dr_blend_fg_rate"], vals["home_p8dr_blend_def_fg_rate"], lg["fg_rate"])
            h_fg, a_fg = min(h_fg, 0.95 - h_td), min(a_fg, 0.95 - a_td)
            n = np.mean([vals["home_p8dr_blend_drives"], vals["away_p8dr_blend_drives"]])
            rng = np.random.default_rng(int(hashlib.sha256(r.game_id.encode()).hexdigest()[:8], 16) ^ SEED)
            N = rng.poisson(n, self.N_SIM)
            # vectorised by grouping identical drive counts
            pts_h, pts_a = np.empty(self.N_SIM), np.empty(self.N_SIM)
            for k in np.unique(N):
                idx = np.flatnonzero(N == k)
                h = rng.multinomial(k, [h_td, h_fg, 1 - h_td - h_fg], size=len(idx))
                a = rng.multinomial(k, [a_td, a_fg, 1 - a_td - a_fg], size=len(idx))
                pts_h[idx] = 6.95 * h[:, 0] + 3 * h[:, 1]
                pts_a[idx] = 6.95 * a[:, 0] + 3 * a[:, 1]
            p = float(np.mean(pts_h > pts_a) + 0.5 * np.mean(pts_h == pts_a))
            m = pts_h - pts_a
            out.append({"game_id": r.game_id, "raw": p, "margin": float(m.mean()), "total": float((pts_h + pts_a).mean()),
                        "margin_p10": float(np.percentile(m, 10)), "margin_p90": float(np.percentile(m, 90)),
                        "total_p10": float(np.percentile(pts_h + pts_a, 10)), "total_p90": float(np.percentile(pts_h + pts_a, 90))})
        return pd.DataFrame(out)


class Situational(Specialist):
    key, name = "F", "Situational residual correction"
    hypothesis = "The champion is miscalibrated in identifiable pregame situations (favourite size, early season, QB uncertainty, disruption)."
    mechanism = "L2 logistic correction on the champion's out-of-fold logit and its interactions with pregame situations; earlier seasons' OOF only."

    def prepare(self, df, train):
        df = df.copy()
        lc = df["champ_logit"]
        fav = _sig(lc.abs())
        df["p8sit_lc"] = lc
        for lo, hi, nm in ((0.6, 0.7, "b60"), (0.7, 0.8, "b70"), (0.8, 1.01, "b80")):
            df[f"p8sit_lc_{nm}"] = lc * ((fav >= lo) & (fav < hi))
        df["p8sit_lc_early"] = lc * (df["week"] <= 4)
        qbu = df[[c for c in ("home_qb_change", "away_qb_change", "home_qb_questionable", "away_qb_questionable",
                              "home_qb7_returning", "away_qb7_returning") if c in df]].fillna(0).sum(axis=1).clip(0, 1)
        df["p8sit_lc_qbunc"] = lc * qbu
        df["p8sit_qb_net"] = df.get("away_qb_change", 0).fillna(0) - df.get("home_qb_change", 0).fillna(0)
        dis = df.get("diff_p72_OL_starters_out", 0)
        df["p8sit_disruption"] = pd.Series(dis, index=df.index).fillna(0)
        mx = df.get("mx_net_epa_pp")
        df["p8sit_lc_extreme"] = lc * (pd.Series(mx, index=df.index).abs() > pd.concat([train.get("mx_net_epa_pp").abs()]).quantile(0.9))
        return df

    def features(self, df):
        return [c for c in df.columns if c.startswith("p8sit_")]

    def abstain(self, df):
        return df["champ_logit"].isna().to_numpy()

    def model(self):
        return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=0.3, max_iter=2000))


SPECIALISTS = [Availability(), Matchup(), FormChange(), Environment(), DriveSim(), Situational()]


# --------------------------------------------------------------------------- walk-forward

def _signals(model, cols, X, k: int = 3) -> list[str]:
    """Top-k inputs behind each prediction. Linear specialists: coefficient x standardised value (log-odds toward the
    home team). Tree specialists: the inputs furthest from their training mean (association, not causation)."""
    try:
        if hasattr(model, "named_steps") and "logisticregression" in model.named_steps:
            imp, sc, lr = model.named_steps["simpleimputer"], model.named_steps["standardscaler"], model.named_steps["logisticregression"]
            contrib = sc.transform(imp.transform(X)) * lr.coef_[0]
            fmt = lambda c, v: f"{c} ({v:+.2f} log-odds to home)"
        else:
            mu, sd = np.nanmean(X, axis=0), np.nanstd(X, axis=0)
            contrib = np.nan_to_num((X - mu) / np.where(sd > 0, sd, 1))
            fmt = lambda c, v: f"{c} ({v:+.1f} sd)"
        out = []
        for row in contrib:
            idx = np.argsort(-np.abs(row))[:k]
            out.append("; ".join(fmt(cols[i], row[i]) for i in idx if abs(row[i]) > 1e-9))
        return out
    except Exception:
        return [""] * len(X)


def _platt(raw_hist, y_hist, raw):
    if len(raw_hist) < 100 or np.unique(y_hist).size < 2:
        return raw
    m = LogisticRegression(C=1e3, max_iter=1000).fit(_logit(raw_hist).reshape(-1, 1), y_hist)
    return m.predict_proba(_logit(raw).reshape(-1, 1))[:, 1]


def allowed(cols) -> list[str]:
    """Structural guard: no specialist may use the shared team-strength (rating) columns."""
    return [c for c in cols if not any(f in c for f in FORBIDDEN)]


def run_specialist(spec: Specialist, df: pd.DataFrame, targets=TARGETS) -> pd.DataFrame:
    rows, hist = [], []
    done = df["home_win"].notna()
    for s in targets:
        train = df[(df["season"] < s) & done]
        if spec.key == "F":
            train = train[train["champ_logit"].notna()]
        test = df[df["season"] == s]
        if spec.key == "F" and len(train) < 200:
            continue
        if isinstance(spec, DriveSim):
            pr = spec.fit_predict(train, test)
            raw = pr["raw"].to_numpy()
            extra = pr.drop(columns=["raw"]).set_index("game_id")
        else:
            trp, tep = spec.prepare(train, train), spec.prepare(test, train)
            cols = allowed(spec.features(trp))
            keep = ~spec.abstain(trp)
            m = spec.model().fit(trp.loc[keep, cols].astype(float).to_numpy(), trp.loc[keep, "home_win"].to_numpy())
            Xte = tep[cols].astype(float).to_numpy()
            raw = m.predict_proba(Xte)[:, 1]
            raw[spec.abstain(tep)] = np.nan
            extra = pd.DataFrame({"game_id": tep["game_id"].to_numpy(), "signals": _signals(m, cols, Xte)}).set_index("game_id")
        ok = ~np.isnan(raw)
        h = pd.concat(hist) if hist else pd.DataFrame(columns=["raw", "y"])
        hh = h.dropna()
        cal = np.full(len(raw), np.nan)
        if ok.any():
            cal[ok] = _platt(hh["raw"].to_numpy(), hh["y"].to_numpy(), raw[ok]) if len(hh) else raw[ok]
        part = pd.DataFrame({"game_id": test["game_id"].to_numpy(), "season": s, "specialist": spec.key, "raw": raw, "p_home": cal,
                             "abstained": ~ok, "home_win": test["home_win"].to_numpy()})
        if extra is not None:
            part = part.join(extra[~extra.index.duplicated()], on="game_id")
        rows.append(part)
        hist.append(pd.DataFrame({"raw": raw[test["home_win"].notna().to_numpy()], "y": test["home_win"].dropna().to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def run_all(progress=print) -> pd.DataFrame:
    from .baseline import load_oof
    df, sig = research_frame()
    oof = load_oof()[["game_id", "p_weighted_average", "margin_ensemble"]]
    df = df.merge(oof, on="game_id", how="left")
    df["champ_logit"] = np.where(df["p_weighted_average"].notna(), _logit(df["p_weighted_average"].fillna(0.5)), np.nan)
    out = []
    for spec in SPECIALISTS:
        progress(f"  specialist {spec.key}: {spec.name}")
        out.append(run_specialist(spec, df))
    res = pd.concat(out, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_parquet(OUT / "specialist_oof.parquet", index=False)
    df[["game_id", "season", "week", "home_team", "away_team", "home_win", "home_score", "away_score", "p_weighted_average",
        "margin_ensemble", "completed"]].to_parquet(OUT / "research_games.parquet", index=False)
    (OUT / "research_snapshot.json").write_text(json.dumps({"feature_store_signature": sig, "rows": int(len(df)),
                                                             "specialists": [{"key": s.key, "name": s.name, "hypothesis": s.hypothesis,
                                                                              "mechanism": s.mechanism} for s in SPECIALISTS]}, indent=2))
    return res


def feature_inventory() -> pd.DataFrame:
    df, _ = research_frame()
    rows = []
    for spec in SPECIALISTS:
        if isinstance(spec, DriveSim):
            cols = spec.features(df)
        else:
            d2 = df.assign(champ_logit=0.0) if spec.key == "F" else df
            cols = spec.features(spec.prepare(d2, d2))
        rows += [{"specialist": spec.key, "feature": c, "uses_forbidden_rating": any(f in c for f in FORBIDDEN)} for c in cols]
    return pd.DataFrame(rows)
