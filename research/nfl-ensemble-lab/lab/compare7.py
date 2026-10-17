"""Phase 7.1 prospective comparison of the tracked versions on IDENTICAL archived games.

Only immutable pregame snapshots are used; a game counts once it is completed. Every number comes
with its sample size and a paired bootstrap interval. Nothing here promotes a model: the decision
rule stays the registered one (128+ games, Holm-corrected, in prospective.evaluate_challengers).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from . import metrics as M
from .config import SNAPSHOTS_DIR

TRACKED = {"v20261016_212540": "Champion", "v20261017_021344_p5_player_continuity": "Phase 5 player-continuity",
           "v20261017_142546_p7_qb_snap": "Phase 7 QB + snap"}
MIN_GAMES = 128


def collect() -> pd.DataFrame:
    """One row per (game, stage, version) from archived snapshots of completed games."""
    from .data_pipeline import GAMES_TABLE
    from .prospective import load_ledger
    led = load_ledger()
    if led.empty:
        return pd.DataFrame()
    g = pd.read_parquet(GAMES_TABLE).set_index("game_id")
    led = led[led["predicted_at"] < led["kickoff_utc"]]
    rows = []
    for r in led.itertuples(index=False):
        if r.game_id not in g.index or not bool(g.loc[r.game_id, "completed"]):
            continue
        res = g.loc[r.game_id]
        try:
            s = json.loads((SNAPSHOTS_DIR / str(r.path).replace("\\", os.sep)).read_text(encoding="utf-8"))
        except Exception:
            continue
        base = {"game_id": r.game_id, "stage": s.get("stage") or s.get("window"), "predicted_at": s.get("predicted_at"),
                "hours_to_kickoff": s.get("hours_to_kickoff"), "home_win": float(res["home_score"] > res["away_score"]),
                "margin": float(res["home_score"] - res["away_score"]),
                "actual_home_qb": res.get("home_qb_id"), "actual_away_qb": res.get("away_qb_id")}
        av = s.get("availability", {})
        inj = all((av.get(x) or {}).get("inj_report_available") == 1 for x in ("home", "away"))
        ci = s.get("champion_inputs") or {"home_qb_id": (av.get("home") or {}).get("qb_projected_id"),
                                          "away_qb_id": (av.get("away") or {}).get("qb_projected_id")}
        rows.append(base | {"version": s.get("model_version"), "p": s.get("p_champion"), "pred_margin": s.get("margin_ensemble"),
                            "home_qb": ci.get("home_qb_id"), "away_qb": ci.get("away_qb_id"), "injury_complete": inj})
        for v, c in (s.get("shadow_challengers") or {}).items():
            if not isinstance(c, dict) or c.get("p_champion") is None:
                continue
            inp = c.get("inputs") or {}
            rows.append(base | {"version": v, "p": c["p_champion"], "pred_margin": c.get("margin_ensemble"),
                                "home_qb": inp.get("home_qb_id"), "away_qb": inp.get("away_qb_id"), "injury_complete": inj})
    return pd.DataFrame(rows)


def _ece(y, p, bins=5) -> float:
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(y[b == k].mean() - p[b == k].mean()) * (b == k).mean() for k in range(bins) if (b == k).any()))


def compare(df: pd.DataFrame, stage: str = "final", n_boot: int = 2000, seed: int = 0) -> dict:
    """Metrics per version on the games every version predicted at this stage (latest snapshot per stage)."""
    if df.empty:
        return {"games": 0, "note": "no archived game has been completed yet", "by_version": pd.DataFrame(), "paired": pd.DataFrame()}
    d = df[df["stage"] == stage].sort_values("predicted_at").groupby(["game_id", "version"]).tail(1)
    piv = d.pivot(index="game_id", columns="version", values="p").dropna()
    games = piv.index
    out = []
    for v in piv.columns:
        x = d[(d["version"] == v) & d["game_id"].isin(games)].set_index("game_id").loc[games]
        y, p = x["home_win"].to_numpy(), x["p"].to_numpy(float)
        qb_ok = ((x["home_qb"] == x["actual_home_qb"]) & (x["away_qb"] == x["actual_away_qb"])).mean() if x["home_qb"].notna().any() else np.nan
        out.append({"version": v, "label": TRACKED.get(v, v), "games": len(x), "accuracy": float(((p > 0.5) == (y == 1)).mean()),
                    "log_loss": M.log_loss(y, p), "brier": float(np.mean((p - y) ** 2)), "ece_5bins": _ece(y, p),
                    "margin_mae": float((x["pred_margin"] - x["margin"]).abs().mean()) if x["pred_margin"].notna().any() else np.nan,
                    "qb_projection_correct": qb_ok, "injury_report_complete": float(x["injury_complete"].mean())})
    by = pd.DataFrame(out)
    champ = next((v for v in piv.columns if TRACKED.get(v) == "Champion"), piv.columns[0])
    rng = np.random.default_rng(seed)
    y = d[d["version"] == champ].set_index("game_id").loc[games, "home_win"].to_numpy()
    paired = []
    for v in piv.columns:
        if v == champ:
            continue
        l_c = -(y * np.log(np.clip(piv[champ], 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - piv[champ], 1e-6, 1))).to_numpy()
        l_v = -(y * np.log(np.clip(piv[v], 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - piv[v], 1e-6, 1))).to_numpy()
        diff = l_v - l_c
        bs = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n_boot)] if len(diff) > 1 else [np.nan]
        paired.append({"version": v, "label": TRACKED.get(v, v), "games": len(diff), "delta_log_loss_vs_champion": float(diff.mean()),
                       "ci95_low": float(np.nanpercentile(bs, 2.5)), "ci95_high": float(np.nanpercentile(bs, 97.5)),
                       "status": ("accumulating evidence" if len(diff) < MIN_GAMES else "see Holm-corrected evaluation"),
                       "note": f"{len(diff)} of {MIN_GAMES} games required; no conclusion"})
    return {"games": int(len(games)), "stage": stage, "by_version": by, "paired": pd.DataFrame(paired)}


def stage_changes(df: pd.DataFrame) -> pd.DataFrame:
    """Did fresher information help? Early-week vs final forecast for the same game and version."""
    if df.empty:
        return pd.DataFrame()
    first = df.sort_values("predicted_at").groupby(["game_id", "version"]).head(1)
    last = df.sort_values("predicted_at").groupby(["game_id", "version"]).tail(1)
    m = first.merge(last, on=["game_id", "version"], suffixes=("_first", "_last"))
    m = m[m["stage_first"] != m["stage_last"]]
    if m.empty:
        return pd.DataFrame()
    y = m["home_win_first"].to_numpy()

    def ll(p):
        p = np.clip(p.to_numpy(float), 1e-6, 1 - 1e-6)
        return -(y * np.log(p) + (1 - y) * np.log(1 - p))
    m = m.assign(abs_change=(m["p_last"] - m["p_first"]).abs(), ll_first=ll(m["p_first"]), ll_last=ll(m["p_last"]),
                 qb_changed=(m["home_qb_first"] != m["home_qb_last"]) | (m["away_qb_first"] != m["away_qb_last"]))
    return m.groupby("version").agg(games=("game_id", "nunique"), mean_abs_change=("abs_change", "mean"),
                                    log_loss_first=("ll_first", "mean"), log_loss_last=("ll_last", "mean"),
                                    qb_assumption_changed=("qb_changed", "sum")).reset_index()
