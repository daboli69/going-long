"""Phase 11: market-blend SHADOW challenger, exactly as pre-registered in docs/PHASE11_MARKET_BLEND_PREREGISTRATION.md.

p = sigmoid(a + b_c * logit(p_champion) + b_o * logit(p_open)), with the weights frozen in the pre-registration (fitted on
2018-21 AusSportsBetting opening moneylines). Scored only from the immutable stage snapshots and the ESPN odds archive,
both read-only; writes only to artifacts/phase11/. Never touches the scheduler, the champion or the snapshots."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import ARTIFACTS_DIR
from .market81 import american_to_prob, novig

OUT = ARTIFACTS_DIR / "phase11"
DOC = "docs/PHASE11_MARKET_BLEND_PREREGISTRATION.md"
# commit 9eea727 (pre-registration, before any code); only final snapshots made after this count toward the primary test
REGISTERED_AT = pd.Timestamp("2026-10-26T20:12:16Z")
WEIGHTS = {"intercept": -0.13190614801204809, "champion": 0.2569285247107809, "open": 0.8164881145183679}
FIT_SEASONS = (2018, 2021)
RETRO_SEASONS = (2022, 2025)
MIN_GAMES = 128
KICKOFF_TOL = pd.Timedelta(hours=24)


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def blend(p_champion, p_open, w: dict = WEIGHTS):
    z = w["intercept"] + w["champion"] * _logit(p_champion) + w["open"] * _logit(p_open)
    return 1 / (1 + np.exp(-z))


def _american(o) -> float:
    s = str(o).strip().upper().replace("+", "")
    if s in ("EVEN", "EV", "PK"):
        return 100.0
    try:
        v = float(s)
    except ValueError:
        return np.nan
    return v if abs(v) >= 100 else np.nan


def ml_novig(home_ml, away_ml) -> float:
    """American moneylines -> multiplicative no-vig home probability (NaN if either side is unusable)."""
    h, a = _american(home_ml), _american(away_ml)
    if np.isnan(h) or np.isnan(a):
        return np.nan
    return float(novig(american_to_prob([h]), american_to_prob([a]))[0])


# --------------------------------------------------------------------------- frozen weights (historical fit)

def fit_frame() -> pd.DataFrame:
    """Champion out-of-fold probability joined to ASB opening moneylines (decimal), all seasons with both."""
    from . import upsets85 as U
    from .data_pipeline import GAMES_TABLE
    from .specialists.baseline import load_oof
    m = U.match_asb(U.load_asb(), pd.read_parquet(GAMES_TABLE))[["game_id", "asb_home_odds_open", "asb_away_odds_open"]]
    x = load_oof().merge(m, on="game_id", how="inner")
    ph, pa = 1 / x["asb_home_odds_open"], 1 / x["asb_away_odds_open"]
    x["p_open"] = ph / (ph + pa)
    return x[x["home_win"].isin([0, 1])].dropna(subset=["p_open", "p_weighted_average"])


def fit_weights(x: pd.DataFrame) -> dict:
    from sklearn.linear_model import LogisticRegression
    X = np.c_[_logit(x["p_weighted_average"]), _logit(x["p_open"])]
    f = LogisticRegression(C=1e6, max_iter=5000).fit(X, x["home_win"].astype(int))
    return {"intercept": float(f.intercept_[0]), "champion": float(f.coef_[0][0]), "open": float(f.coef_[0][1]), "games": int(len(x))}


def _summary(y, p) -> dict:
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    if not len(y):
        return {"games": 0}
    return {"games": int(len(y)), "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
            "brier": float(np.mean((p - y) ** 2)), "accuracy": float(np.mean((p > 0.5) == (y == 1)))}


def retrospective(x: pd.DataFrame) -> dict:
    """Frozen weights on 2022-25 ASB openers vs the champion's OOF probability. Descriptive only (research-exposed seasons)."""
    from .prospective import _paired
    d = x[x["season"].between(*RETRO_SEASONS)]
    y = d["home_win"].to_numpy(float)
    pc = blend(d["p_weighted_average"], d["p_open"])
    out = {"seasons": list(RETRO_SEASONS), "note": "descriptive only; seasons exposed in Phase 8, not a holdout or gate",
           "challenger": _summary(y, pc), "champion": _summary(y, d["p_weighted_average"]), "opening_market": _summary(y, d["p_open"]),
           "challenger_minus_champion": _paired(y, d["p_weighted_average"].to_numpy(float), pc),
           "challenger_minus_open": _paired(y, d["p_open"].to_numpy(float), pc)}
    out["by_season"] = [{"season": int(s), **{k: _summary(z["home_win"], v)["log_loss"] for k, v in
                                              (("challenger", blend(z["p_weighted_average"], z["p_open"])),
                                               ("champion", z["p_weighted_average"]), ("opening_market", z["p_open"]))}, "games": int(len(z))}
                        for s, z in d.groupby("season")]
    return out


# --------------------------------------------------------------------------- prospective scoring from the archives

def _prep_archive(arc: pd.DataFrame) -> pd.DataFrame:
    if arc is None or not len(arc):
        return pd.DataFrame(columns=["home", "away", "kickoff", "retrieved_at"])
    a = arc.copy()
    a["retrieved_at"] = pd.to_datetime(a["retrieved_at"], utc=True)
    a["kickoff"] = pd.to_datetime(a["kickoff"], utc=True, errors="coerce")
    if "provider" in a:
        a = a[a["provider"].fillna("").str.contains("DraftKings", case=False)]
    for c in ("home_ml_open", "away_ml_open", "home_ml_close", "away_ml_close"):
        if c not in a:
            a[c] = None
    a["p_open"] = [ml_novig(h, w) for h, w in zip(a["home_ml_open"], a["away_ml_open"])]
    a["p_current"] = [ml_novig(h, w) for h, w in zip(a["home_ml_close"], a["away_ml_close"])]
    return a.sort_values("retrieved_at")


def _rows_for(a: pd.DataFrame, home, away, kickoff) -> pd.DataFrame:
    if not len(a):
        return a.assign(p_open=pd.Series(dtype=float), p_current=pd.Series(dtype=float))
    return a[(a["home"] == home) & (a["away"] == away) & ((a["kickoff"] - kickoff).abs() <= KICKOFF_TOL)]


def opener_before(a: pd.DataFrame, home, away, kickoff, at) -> tuple[float, str | None]:
    """Earliest archived DraftKings opener retrieved before `at` (the stage's snapshot time)."""
    r = _rows_for(a, home, away, kickoff)
    r = r[(r["retrieved_at"] < at) & r["p_open"].notna()]
    return (float(r["p_open"].iloc[0]), r["retrieved_at"].iloc[0].isoformat()) if len(r) else (np.nan, None)


def closer_before(a: pd.DataFrame, home, away, kickoff) -> float:
    """Latest archived DraftKings current moneyline retrieved before kickoff."""
    r = _rows_for(a, home, away, kickoff)
    r = r[(r["retrieved_at"] < kickoff) & r["p_current"].notna()]
    return float(r["p_current"].iloc[-1]) if len(r) else np.nan


def score_table(t: pd.DataFrame, arc: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    """One row per scored (game, stage): champion, opener, challenger (champion fallback, flagged), closing market."""
    if t is None or not len(t):
        return pd.DataFrame()
    a = _prep_archive(arc)
    t = t[t["home_win"].notna()].merge(teams[["game_id", "home_team", "away_team"]], on="game_id", how="left")
    rows = []
    for r in t.itertuples(index=False):
        kick, at = pd.Timestamp(r.kickoff_utc), pd.Timestamp(r.predicted_at)
        kick = kick.tz_localize("UTC") if kick.tzinfo is None else kick
        at = at.tz_localize("UTC") if at.tzinfo is None else at
        po, src = opener_before(a, r.home_team, r.away_team, kick, at)
        fb = bool(np.isnan(po))
        rows.append({"game_id": r.game_id, "season": r.season, "week": r.week, "stage": r.window, "predicted_at": at, "kickoff_utc": kick,
                     "home_win": float(r.home_win), "p_champion": float(r.p_home), "p_open": po, "opener_retrieved_at": src,
                     "p_challenger": float(r.p_home) if fb else float(blend(r.p_home, po)), "fallback_no_opener": fb,
                     "p_close": closer_before(a, r.home_team, r.away_team, kick),
                     "counts_for_primary": bool(r.window == "final" and at > REGISTERED_AT)})
    return pd.DataFrame(rows)


def evaluate(s: pd.DataFrame) -> dict:
    """Primary (counted final-stage games only) and descriptive summaries. Never promotes anything."""
    from .prospective import _paired
    out = {"registered_at": REGISTERED_AT.isoformat(), "doc": DOC, "weights": WEIGHTS, "min_games": MIN_GAMES}
    if s is None or not len(s):
        return out | {"primary": {"games": 0, "status": "no scored games yet"}}

    def block(d):
        y = d["home_win"].to_numpy(float)
        res = {"games": int(len(d)), "fallback_games": int(d["fallback_no_opener"].sum()),
               "challenger": _summary(y, d["p_challenger"]), "champion": _summary(y, d["p_champion"]),
               "challenger_minus_champion": _paired(y, d["p_champion"].to_numpy(float), d["p_challenger"].to_numpy(float))}
        op = d[~d["fallback_no_opener"]]
        if len(op):
            yo = op["home_win"].to_numpy(float)
            res["opener_subset"] = {"games": int(len(op)), "challenger": _summary(yo, op["p_challenger"]), "champion": _summary(yo, op["p_champion"]),
                                    "opening_market": _summary(yo, op["p_open"]),
                                    "challenger_minus_champion": _paired(yo, op["p_champion"].to_numpy(float), op["p_challenger"].to_numpy(float))}
        cm = op[op["p_close"].notna()]
        if len(cm):
            yc = cm["home_win"].to_numpy(float)
            res["secondary_vs_closing"] = {"games": int(len(cm)), "challenger": _summary(yc, cm["p_challenger"]),
                                           "closing_market": _summary(yc, cm["p_close"]),
                                           "challenger_minus_closing": _paired(yc, cm["p_close"].to_numpy(float), cm["p_challenger"].to_numpy(float))}
        return res

    fin = s[s["stage"] == "final"]
    prim = block(fin[fin["counts_for_primary"]]) if fin["counts_for_primary"].any() else {"games": 0}
    n = prim["games"]
    if n < MIN_GAMES:
        prim["status"] = f"accumulating ({n}/{MIN_GAMES} games; no conclusion)"
    else:
        hi = prim["challenger_minus_champion"]["ci"][1]
        prim["status"] = ("passes: eligible for a promotion review by Travis (never automatic)" if hi < 0 else "does not pass")
    out["primary"] = prim
    pre = fin[~fin["counts_for_primary"]]
    out["descriptive_pre_registration_final"] = block(pre) if len(pre) else {"games": 0}
    out["by_stage_all_games"] = {st_: block(d) for st_, d in s.groupby("stage")}
    return out


def run(retro: bool = True) -> dict:
    from .data_pipeline import GAMES_TABLE
    from .market81 import espn_archive
    from .prospective import scored_table
    OUT.mkdir(parents=True, exist_ok=True)
    teams = pd.read_parquet(GAMES_TABLE)[["game_id", "home_team", "away_team"]]
    s = score_table(scored_table(), espn_archive(), teams)
    res = evaluate(s)
    res["generated_at"] = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    if retro:
        try:
            x = fit_frame()
            fz = x[x["season"].between(*FIT_SEASONS)]
            refit = fit_weights(fz)
            res["weights_check"] = {"refit": refit, "max_abs_diff": max(abs(refit[k] - WEIGHTS[k]) for k in WEIGHTS)}
            res["retrospective_2022_25"] = retrospective(x)
        except Exception as exc:                      # ASB file is local-only; prospective scoring does not need it
            res["retrospective_error"] = repr(exc)[:200]
    if len(s):
        s.to_csv(OUT / "scored.csv", index=False)
    (OUT / "results.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    return res


def load() -> dict:
    out = {}
    if (OUT / "results.json").exists():
        out["results"] = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    if (OUT / "scored.csv").exists():
        out["scored"] = pd.read_csv(OUT / "scored.csv")
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
