"""Walk-forward test of King of the End Zone v2, exactly as pre-registered in docs/KINGZONE_PREREG.md.

    python scripts/kz2_backtest.py fit  SEASON      refit the tail model at weeks 1,4,7,10,13,16 (2026: 1,4,7) using only earlier weeks
    python scripts/kz2_backtest.py play SEASON [W]  predict every regular-season game of SEASON (2026: weeks 1-8) with the latest earlier fit, W worker processes
    python scripts/kz2_backtest.py report           score everything, apply the pass rule, write docs/kingzone_walkforward.json

Scoring is the log of the probability given to the real longest-touchdown scorer (floor 0.002; ties averaged; defense, special teams and players off the
roster score as the field). Baselines: the plain expected-touchdown split and the plain touch-share split, with the field share set from earlier history.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import sys
import warnings
from multiprocessing import Pool
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import kz2 as K  # noqa: E402

FIT_WEEKS = {2026: [1, 4, 7]}
DEFAULT_FIT_WEEKS = [1, 4, 7, 10, 13, 16]
TEST = [2022, 2023, 2024, 2025]
HOLDOUT = (2026, 8)
N_SIMS = 6000
OUT = ROOT / "data" / "cache" / "kz2"
FLOOR = K.FLOOR
BOOT, BOOT_SEED = 10000, 1
PASS_MEAN, POWER_TARGET = 0.03, 0.05


def fit_path(season: int, week: int) -> Path:
    return OUT / f"fit_{season}_{week:02d}.pkl"


def load_fit(season: int, week: int) -> dict:
    ws = [w for w in FIT_WEEKS.get(season, DEFAULT_FIT_WEEKS) if w <= week]
    return pickle.loads(fit_path(season, max(ws)).read_bytes())


def fit_stage(season: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for w in FIT_WEEKS.get(season, DEFAULT_FIT_WEEKS):
        if not fit_path(season, w).exists():
            f = K.fit_tail(season, w)
            fit_path(season, w).write_bytes(pickle.dumps(f))
            print(season, w, f["n_units"], f["n_exceed"], round(f["seconds"]), f["rhat_max"], flush=True)


def _game(a: tuple) -> dict:
    season, week, gid, home, away = a
    fit = load_fit(season, week)
    seed = int(hashlib.sha256(gid.encode()).hexdigest()[:8], 16)
    out = K.predict(season, week, home, away, fit, n=N_SIMS, seed=seed)
    win = K.actual_winners(gid)
    f0 = K.field_rate(season, week)
    b1, _ = K.baseline_split(season, week, [home, away], f0)
    b2, _ = K.baseline_touch(season, week, [home, away], f0)
    rec = {"gid": gid, "season": season, "week": week, "rows": [(r["pid"], r["chance"], r["anytime"]) for r in out["rows"]], "field": out["field"], "none": out["none"],
           "expected_longest": out["expected_longest"], "f0": f0, "b1": sorted(b1.items(), key=lambda kv: -kv[1])[:40], "b2": sorted(b2.items(), key=lambda kv: -kv[1])[:40],
           "winners": None if win is None else win["entities"], "length": None if win is None else win["length"]}
    return rec


def play_stage(season: int, workers: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = K.load()["plays"]
    g = p[(p["season"] == season) & p["home_team"].notna()][["season", "week", "game_id", "home_team", "away_team"]].drop_duplicates("game_id").sort_values(["week", "game_id"])
    if season == HOLDOUT[0]:
        g = g[g["week"] <= HOLDOUT[1]]
    args = [tuple(r) for r in g.itertuples(index=False)]
    with Pool(workers) as pool:
        res = []
        for i, r in enumerate(pool.imap(_game, args, chunksize=2), 1):
            res.append(r)
            if i % 40 == 0:
                print(season, i, len(args), flush=True)
    (OUT / f"results_{season}.json").write_text(json.dumps(res))


def _ls(p: float) -> float:
    return float(np.log(max(p, FLOOR)))


def _entity_p(rows: dict, field: float, ents: list[str]) -> float:
    return float(np.mean([field if e == "FIELD" else rows.get(e, field) for e in ents]))


def _boot(x: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(BOOT_SEED)
    m = np.array([x[rng.integers(0, len(x), len(x))].mean() for _ in range(BOOT)])
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def score(res: list[dict]) -> dict:
    d1, d2, lm, l1, l2, season = [], [], [], [], [], []
    top_stated, top_hit, pg_p, pg_o, ex_long, real_long, field_pred, field_obs = [], [], [], [], [], [], [], []
    for r in res:
        if not r["winners"]:
            continue
        ents = r["winners"]
        pm = _entity_p({p: c for p, c, _ in r["rows"]}, r["field"], ents)
        p1 = _entity_p(dict(r["b1"]), r["f0"], ents)
        p2 = _entity_p(dict(r["b2"]), r["f0"], ents)
        lm.append(_ls(pm)); l1.append(_ls(p1)); l2.append(_ls(p2))
        d1.append(_ls(pm) - _ls(p1)); d2.append(_ls(pm) - _ls(p2)); season.append(r["season"])
        top = r["rows"][0]
        top_stated.append(top[1]); top_hit.append((1.0 / len(ents)) if top[0] in ents else 0.0)
        for pid, c, _ in r["rows"]:
            pg_p.append(c); pg_o.append((1.0 / len(ents)) if pid in ents else 0.0)
        field_pred.append(r["field"]); field_obs.append(sum(1 for e in ents if e == "FIELD") / len(ents))
        ex_long.append(r["expected_longest"]); real_long.append(r["length"])
    d1, d2 = np.array(d1), np.array(d2)
    n = len(d1)
    out = {"games": n, "mean_log_model": float(np.mean(lm)), "mean_log_b1": float(np.mean(l1)), "mean_log_b2": float(np.mean(l2)),
           "diff_vs_b1": {"mean": float(d1.mean()), "ci95": _boot(d1), "sd": float(d1.std(ddof=1))}, "diff_vs_b2": {"mean": float(d2.mean()), "ci95": _boot(d2), "sd": float(d2.std(ddof=1))},
           "by_season_vs_b1": {int(s): float(d1[np.array(season) == s].mean()) for s in sorted(set(season))},
           "games_needed_80pct_power_for_0.05": float(((1.96 + 0.8416) * d1.std(ddof=1) / POWER_TARGET) ** 2),
           "games_needed_50pct_power_for_0.05": float((1.96 * d1.std(ddof=1) / POWER_TARGET) ** 2),
           "top_pick": {"stated": float(np.mean(top_stated)), "realized": float(np.mean(top_hit)), "se": float(np.sqrt(np.mean(top_hit) * (1 - np.mean(top_hit)) / n)), "n": n},
           "field": {"stated": float(np.mean(field_pred)), "realized": float(np.mean(field_obs))},
           "expected_longest": float(np.mean(ex_long)), "real_longest": float(np.mean(real_long))}
    p, o = np.array(pg_p), np.array(pg_o)
    edges = [0, 0.02, 0.05, 0.10, 0.20, 1.01]
    rel, flagged = [], 0
    for a, b in zip(edges[:-1], edges[1:]):
        m = (p >= a) & (p < b)
        if m.sum() == 0:
            continue
        se = float(np.sqrt((p[m] * (1 - p[m])).sum()) / m.sum())
        row = {"bucket": f"{a:.0%} to {min(b, 1):.0%}", "n": int(m.sum()), "stated": float(p[m].mean()), "realized": float(o[m].mean()), "se": se}
        row["flag"] = bool(m.sum() >= 100 and abs(row["realized"] - row["stated"]) > 2 * se)
        flagged += row["flag"]
        rel.append(row)
    out["reliability"], out["flagged_buckets"] = rel, flagged
    return out


def report() -> None:
    allr = {}
    for s in TEST + [HOLDOUT[0]]:
        f = OUT / f"results_{s}.json"
        if f.exists():
            allr[s] = json.loads(f.read_text())
    test = [r for s in TEST for r in allr.get(s, [])]
    rep = {"test_2022_2025": score(test)}
    if HOLDOUT[0] in allr:
        rep["holdout_2026_w1_8"] = score(allr[HOLDOUT[0]])
    t = rep["test_2022_2025"]
    seasons_pos = sum(v > 0 for v in t["by_season_vs_b1"].values())
    p1 = t["diff_vs_b1"]["mean"] >= PASS_MEAN and t["diff_vs_b1"]["ci95"][0] > 0 and seasons_pos >= 3
    tp = t["top_pick"]
    p2 = abs(tp["stated"] - tp["realized"]) <= 2 * tp["se"] and t["flagged_buckets"] <= 1
    p3 = ("holdout_2026_w1_8" in rep) and rep["holdout_2026_w1_8"]["diff_vs_b1"]["mean"] > 0
    rep["verdict"] = {"P1_beats_expected_td_split": bool(p1), "P2_calibrated": bool(p2), "P3_holdout_positive": bool(p3), "seasons_positive": seasons_pos,
                      "have_enough_games_for_0.05": bool(t["games"] >= t["games_needed_80pct_power_for_0.05"]), "label": "validated" if (p1 and p2) else "not shown to beat the baseline"}
    (ROOT / "docs" / "kingzone_walkforward.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "fit":
        fit_stage(int(sys.argv[2]))
    elif cmd == "play":
        play_stage(int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 4)
    elif cmd == "report":
        report()
