"""Market gate: is the champion a better forecaster than the closing consensus price?

Audit 2026-11-10, fixes 1 and 5. A model probability is a price signal only while the 95% paired-bootstrap interval
of (champion log loss minus market log loss) on walk-forward games lies entirely below zero. Odds rows whose hold
is outside HOLD_RANGE are excluded before de-vig, and the benchmark is reported per hold era because the consensus
series changes character in 2023 (mean hold about 2.7% through 2022, about 4.3% after).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import LAB_ROOT, RAW_DIR
from .ingest import american_to_prob, canonical_game_id

HOLD_RANGE = (0.005, 0.08)
ERAS = {"2016-2022": (2016, 2022), "2023+": (2023, 2100)}
GATE_SEASONS = (2023, 2100)
GATE_DIR = LAB_ROOT / "reports" / "market_gate"
GATE_JSON = GATE_DIR / "GATE.json"


def hold(home_ml, away_ml) -> float:
    return american_to_prob(home_ml) + american_to_prob(away_ml) - 1.0


def valid_hold(h) -> bool:
    return bool(pd.notna(h) and HOLD_RANGE[0] <= h <= HOLD_RANGE[1])


def log_loss_rows(p, y) -> np.ndarray:
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def paired_bootstrap(diff, n_boot: int = 10000, seed: int = 20261110) -> dict:
    """Mean and 95% interval of a per-game loss difference (model minus market). Negative favours the model."""
    diff = np.asarray(diff, float)
    if len(diff) == 0:
        return {"n": 0, "mean": None, "lo": None, "hi": None}
    rng = np.random.default_rng(seed)
    means = diff[rng.integers(0, len(diff), size=(n_boot, len(diff)))].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {"n": int(len(diff)), "mean": float(diff.mean()), "lo": float(lo), "hi": float(hi)}


def evaluate(oof: pd.DataFrame, games: pd.DataFrame, model_col: str = "p_weighted_average") -> dict:
    g = games[["home_moneyline", "away_moneyline"]].copy()
    g["game_id"] = [canonical_game_id(s, w, a, h) for s, w, a, h in zip(games.season, games.week, games.away_team, games.home_team)]
    g["hold"] = [hold(h, a) for h, a in zip(g.home_moneyline, g.away_moneyline)]
    d = oof.merge(g[["game_id", "hold"]], on="game_id", how="left")
    d = d[d.home_win.isin([0.0, 1.0]) & d[model_col].notna() & d.market_p_home_novig.notna()]
    bad = d[~d.hold.map(valid_hold)]
    d = d[d.hold.map(valid_hold)].copy()
    d["diff"] = log_loss_rows(d[model_col], d.home_win) - log_loss_rows(d.market_p_home_novig, d.home_win)

    def block(lo, hi):
        x = d[(d.season >= lo) & (d.season <= hi)]
        out = paired_bootstrap(x["diff"].to_numpy())
        if len(x):
            out.update(model_log_loss=float(log_loss_rows(x[model_col], x.home_win).mean()),
                       market_log_loss=float(log_loss_rows(x.market_p_home_novig, x.home_win).mean()),
                       mean_hold=float(x.hold.mean()))
        return out

    gate = block(*GATE_SEASONS)
    passed = bool(gate["n"] and gate["hi"] < 0)
    return {"model": model_col, "gate_seasons": "2023 onward", "gate": gate, "price_signal": passed,
            "status": "model beats the close; rule may be evaluated" if passed else
                      "RETIRED as a price signal: the model does not beat the closing price out of sample",
            "eras": {k: block(*v) for k, v in ERAS.items()},
            "excluded_invalid_hold": bad.game_id.tolist(), "hold_range": list(HOLD_RANGE)}


def run(oof_path=None) -> dict:
    runs = LAB_ROOT / "artifacts" / "runs"
    oof_path = oof_path or runs / "v20261016_212540" / "oof_predictions.parquet"
    res = evaluate(pd.read_parquet(oof_path), pd.read_csv(RAW_DIR / "games.csv"))
    res["oof"] = str(oof_path)
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    GATE_JSON.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def status() -> dict | None:
    return json.loads(GATE_JSON.read_text(encoding="utf-8")) if GATE_JSON.exists() else None
