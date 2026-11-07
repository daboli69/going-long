"""FantasyPoints (FPDS) player metrics as inputs to the simulated game. Local files only; row-level values never leave this computer.

Per-week player tables (2021 to the latest imported 2026 week) and season-to-date snapshots come from the local FPDS import
(lab/fpds_ingest.py). Nothing here is used until `scripts/fpds_usage_check.py` shows, on games the fit never saw, that it beats the
nflverse-only numbers; that script writes data/cache/fpds_usage_rule.json, and the simulation reads the weights from it.

As-of rule: only weeks before the game's week feed a prediction (the lab's rule for FPDS data, since a week's own numbers
include the outcome).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import fpds_ingest as F
from . import gamecenter_data as D
from .config import CACHE_DIR
from .ingest import normalize_team

RULE_PATH = CACHE_DIR / "fpds_usage_rule.json"
WINDOW = 6

# short name -> candidate column suffixes (weekly tables and snapshots name some columns differently)
SPEC = {
    "receiving_advanced": {"tgt_pct": ["receiving__tgt_pct"], "rte_pct": ["receiving__rte_pct"], "ay_share": ["receiving__ay_share"],
                           "yprr": ["receiving__yprr"], "eztgt": ["advanced__eztgt", "receiving__eztgt"],
                           "i20_tgt": ["advanced__i20_tgt", "receiving__i20_tgt"], "a_dot": ["receiving__a_dot"],
                           "yac_rec": ["receiving__yac_rec"], "slot_rte": ["advanced__slot_rte_pct", "alignment__slot_rte_pct"],
                           "wide_rte": ["advanced__wide_rte_pct", "alignment__wide_rte_pct"],
                           "inline_rte": ["advanced__inline_rte_pct", "alignment__inline_rte_pct"]},
    "bell_cow": {"snap_pct": ["snaps__snap_pct"], "att_pct": ["rushing__att_pct"]},
    "rushing_advanced": {"exp_run": ["advanced__exp_run_pct"], "i5_pct": ["advanced__i5_pct"], "succ": ["advanced__success_pct", "advanced__succ_pct"],
                         "yaco_att": ["advanced__yaco_att"]},
    "efficiency": {"exp_rec": ["efficiency__exp_rec_pct"]},
}


def _dir() -> Path | None:
    try:
        return Path(F.latest()["directory"])
    except Exception:
        return None


# the newer import (Amendment 6) holds the latest weeks; its columns carry no fp_ prefix
A6_SPEC = {
    "receiving_stats": {"tgt_pct": ["receiving__tgt_pct"], "rte_pct": ["receiving__rte_pct"], "ay_share": ["receiving__ay_share"],
                        "yprr": ["receiving__yprr"], "a_dot": ["receiving__a_dot"], "yac_rec": ["receiving__yac_rec"]},
    "receiving_basic": {"tgt_pct": ["receiving__tgt_pct"], "i20_tgt": ["receiving__i20_tgt"]},
    "receiving_situation": {"tgt_pct": ["splits__tgt_pct"], "rte_pct": ["splits__rte_pct"], "yprr": ["overall__yprr"]},
    "receiving_alignment": {"rte_pct": ["overall__rte_pct"]},
    "rb_wr_efficiency": {"yprr": ["efficiency__yprr"]},
    "bell_cow_report": {"snap_pct": ["snaps__snap_pct"], "att_pct": ["rushing__att_pct"], "tgt_pct": ["receiving__tgt_pct"], "rte_pct": ["receiving__rte_pct"]},
    "rushing_stats": {"exp_run": ["advanced__exp_run_pct"], "i5_pct": ["advanced__i5_pct"], "succ": ["advanced__succ_pct"], "yaco_att": ["advanced__yaco_att"]},
}


A6_PERCENT = ("tgt_pct", "rte_pct", "snap_pct", "att_pct", "exp_run", "i5_pct", "succ")


def _a6_dir() -> Path | None:
    try:
        return Path(json.loads((CACHE_DIR / "fpds" / "amendment6" / "LATEST_IMPORT.json").read_text(encoding="utf-8"))["path"])
    except Exception:
        return None


def _pick(df: pd.DataFrame, table: str, mapping: dict, prefixes=None) -> pd.DataFrame:
    out = df[["season", "week", "team", "pid"]].copy()
    for short, sufs in mapping.items():
        s = pd.Series(np.nan, index=df.index)
        for suf in sufs:
            for pre in (prefixes if prefixes is not None else (f"fp_{table}__", f"fp_snapshot_{table}__")):
                if pre + suf in df.columns:
                    s = s.fillna(pd.to_numeric(df[pre + suf], errors="coerce"))
        out[short] = s
    return out


def _merge(frames: list[pd.DataFrame]) -> pd.DataFrame:
    keys = ["season", "week", "team", "pid"]
    out = None
    for f in frames:
        f = f.drop_duplicates(keys, keep="last")
        out = f if out is None else out.merge(f, on=keys, how="outer")
    out["team"] = out["team"].map(lambda t: normalize_team(t) if isinstance(t, str) else t)
    out["season"] = out["season"].astype(int)
    out["pid"] = out["pid"].astype(str)
    return out


def _load(suffix: str) -> pd.DataFrame:
    base = _dir()
    if base is None:
        return pd.DataFrame()
    stamp = (base / "REPORT.json").stat().st_mtime_ns if (base / "REPORT.json").exists() else 0

    def build():
        frames = []
        for table, mapping in SPEC.items():
            path = base / f"{table}{suffix}.parquet"
            if path.exists():
                t = pd.read_parquet(path)
                t = t[t["entity_kind"] == "player"] if "entity_kind" in t else t
                frames.append(_pick(t, table, mapping))
        if not frames:
            return pd.DataFrame()
        out = _merge(frames)
        if suffix == "":
            out = _add_latest_weeks(out)
        out["rte_yprr"] = out["rte_pct"] * out["yprr"]
        return _mask_thin_weeks(out) if suffix == "" else out
    return D._cached(("fpds_usage", suffix, _a6_stamp()), stamp, build)


MIN_COVERAGE = 0.1  # a week listing fewer than this share of a normal week's players is treated as empty


def _mask_thin_weeks(w: pd.DataFrame) -> pd.DataFrame:
    """Blank a metric in any week that lists almost no players. Weeks with partial coverage are used as they are: each player's
    average is over the weeks he has rows for, so a partial week adds data for the players it lists and nothing for the rest."""
    w = w.copy()
    for c in [c for c in w.columns if c not in ("season", "week", "team", "pid")]:
        n = w.groupby(["season", "week"])[c].count()
        thin = n < MIN_COVERAGE * n.groupby(level=0).transform("median")
        bad = thin[thin].index
        if len(bad):
            mask = pd.MultiIndex.from_frame(w[["season", "week"]]).isin(bad)
            w.loc[mask, c] = np.nan
    return w


def _a6_stamp() -> int:
    d = _a6_dir()
    return d.stat().st_mtime_ns if d is not None and d.exists() else 0


def _add_latest_weeks(base: pd.DataFrame) -> pd.DataFrame:
    """Fill weeks the first import has not reached (and any missing rows) from the newer import, never overwriting a value."""
    d = _a6_dir()
    if d is None:
        return base
    frames = []
    for table, mapping in A6_SPEC.items():
        path = d / f"{table}__working_usable.parquet"
        if path.exists():
            t = pd.read_parquet(path)
            if {"season", "week", "team", "pid"} <= set(t.columns):
                frames.append(_pick(t, table, mapping, prefixes=("",)))
    if not frames:
        return base
    # several tables carry the same metric for different players; take the first value present, tables in the order above
    cat = pd.concat([f.dropna(subset=["season", "week", "team", "pid"]) for f in frames], ignore_index=True)
    cat["team"] = cat["team"].map(lambda t: normalize_team(t) if isinstance(t, str) else t)
    cat["season"] = cat["season"].astype(int)
    cat["pid"] = cat["pid"].astype(str)
    new = cat.groupby(["season", "week", "team", "pid"], as_index=False).first()
    for c in A6_PERCENT:  # the newer import writes these as percents (46.9); the first writes fractions (0.469)
        if c in new:
            new[c] = new[c] / 100.0
    keys = ["season", "week", "team", "pid"]
    both = base.set_index(keys).combine_first(new.set_index(keys)).reset_index()
    return both


def weekly() -> pd.DataFrame:
    """One row per player per week (2021 on), as exported that week; weeks the export has not reached are absent."""
    return _load("")


def snapshot(season: int = D.SEASON) -> pd.DataFrame:
    """Season-to-date row per player (week is blank) from the latest FPDS snapshot export."""
    s = _load("_snapshots")
    return s[s["season"] == season].drop(columns="week") if len(s) else s


def through(season: int = D.SEASON) -> dict:
    """Latest week the weekly rows reach, and the number of games the snapshot covers."""
    w = weekly()
    wk = int(w.loc[w["season"] == season, "week"].max()) if len(w) and (w["season"] == season).any() else 0
    snap_games = 0
    base = _dir()
    if base is not None and (base / "receiving_advanced_snapshots.parquet").exists():
        t = pd.read_parquet(base / "receiving_advanced_snapshots.parquet")
        t = t[(t["season"] == season) & (t["entity_kind"] == "player")]
        a, b = pd.to_numeric(t.get("fp_snapshot_receiving_advanced__receiving__tgt"), errors="coerce"), \
            pd.to_numeric(t.get("fp_snapshot_receiving_advanced__receiving__tgt_g"), errors="coerce")
        g = (a / b).replace([np.inf, -np.inf], np.nan).dropna().round()
        snap_games = int(g.max()) if len(g) else 0
    return {"weekly_through": wk, "snapshot_games": snap_games}


def features_asof(season: int, team: str, week: int, pids=None, mode: str = "last6") -> pd.DataFrame:
    """Per-player FPDS features from the weekly rows before `week`, indexed by pid (players with no rows are absent).

    `mode` picks the window: the last 6 weeks the team has rows for, or the whole season so far. `fp_weeks` is the number
    of weeks behind each average. A future week uses the latest weeks available."""
    w = weekly()
    if w.empty:
        return pd.DataFrame()
    cols = [c for c in w.columns if c not in ("season", "week", "team", "pid")]
    sub = w[(w["season"] == season) & (w["team"] == team) & (w["week"] < week)]
    weeks = sorted(sub["week"].unique())
    if mode == "last6":
        weeks = weeks[-WINDOW:]
    sub = sub[sub["week"].isin(weeks)]
    out = sub.groupby("pid")[cols].mean()
    counts = [c for c in ("rte_pct", "att_pct") if c in sub]
    out["fp_weeks"] = sub.groupby("pid")[counts].count().max(axis=1) if counts else 0
    return out


def share_from(raw: np.ndarray, base_share: np.ndarray) -> np.ndarray:
    """Turn a metric (NaN where FPDS has no row) into shares of the pool. Missing players take the value their nflverse share implies."""
    raw = np.asarray(raw, float)
    known = ~np.isnan(raw)
    if known.sum() == 0 or raw[known].sum() <= 0 or base_share[known].sum() <= 0:
        return base_share / max(base_share.sum(), 1e-9)
    filled = np.where(known, raw, base_share * raw[known].sum() / base_share[known].sum())
    return filled / filled.sum()


STAT_FEATURES = {"rec_yds": ["tgt_pct", "rte_yprr", "ay_share"], "rec": ["tgt_pct", "rte_pct"], "rush_yds": ["att_pct", "snap_pct"]}


def load_rule(path: Path = RULE_PATH) -> dict:
    """The tested rule written by scripts/fpds_usage_check.py; empty until that has run."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def blend_shares(u, team: str, season: int, week: int, out_ids=frozenset(), rule: dict | None = None):
    """Blend nflverse and FPDS shares for the stats that passed the check, for the players the check covers.

    Each stat in the rule names its group (`max_n`: players who played at most that many of the last six games) and its mix.
    Returns (usage, info)."""
    rule = load_rule() if rule is None else rule
    weights = rule.get("weights", {})
    info = {"used": False, "stats": [], "thin_players": 0}
    if not weights:
        return u, info
    p = u.players
    pool = (p["active"] & ~p["pid"].isin(out_ids)).to_numpy()
    feats = features_asof(season, team, week, None, rule.get("mode", "last6"))
    if feats.empty or pool.sum() < 3:
        return u, info
    q = p.copy()
    n = p["n"].to_numpy()
    for stat, cfg in weights.items():
        col = f"share_{stat}"
        base = q.loc[pool, col].to_numpy(float)
        if base.sum() <= 0:
            continue
        mix = cfg["mix"].get("base", 0.0) * base / base.sum()
        for feat, wt in cfg["mix"].items():
            if feat == "base" or wt == 0 or feat not in feats.columns:
                continue
            mix = mix + wt * share_from(feats[feat].reindex(q.loc[pool, "pid"]).to_numpy(float), base)
        group = pool & (n <= cfg.get("max_n", LOW_N))
        blended = np.zeros(len(q))
        blended[pool] = mix / mix.sum() * base.sum()
        new = q[col].to_numpy(float).copy()
        new[group] = blended[group]
        new[pool] *= base.sum() / new[pool].sum()  # keep the pool's total share unchanged
        q[col] = new
        info["stats"].append(stat)
        info["thin_players"] = max(info["thin_players"], int(group.sum()))
    info["used"] = bool(info["stats"])
    return type(u)(u.team, u.games, u.totals, q), info


_TD_CACHE: dict = {}


def _td_table(season: int) -> pd.DataFrame:
    path = D.RAW_DIR / f"play_by_play_{season}.parquet"
    key = (season, path.stat().st_mtime_ns if path.exists() else 0)
    if key not in _TD_CACHE:
        _TD_CACHE[key] = td_events([season]) if path.exists() else pd.DataFrame(columns=["week", "team", "pid", "rec_td", "rush_td", "season"])
    return _TD_CACHE[key]


def rec_td_weights(u, team: str, season: int, week: int, out_ids=frozenset(), rule: dict | None = None) -> dict:
    """pid -> chance weight to catch a touchdown: yardage share, touchdowns over the same weeks, and (when it passed the check) red-zone targets."""
    rule = load_rule() if rule is None else rule
    td = rule.get("td", {}).get("rec_td", {})
    w = td.get("weights") or {"yards": 0.9, "td_history": 0.1, "fpds": 0.0}
    p = u.players
    pool = p[p["active"] & ~p["pid"].isin(out_ids)]
    yd = np.clip(pool["share_rec_yds"].to_numpy(float), 0, None)  # a player can have negative yards in a game
    if len(pool) == 0 or yd.sum() <= 0:
        return {}
    sy = yd / yd.sum()
    t = _td_table(season)
    weeks = sorted(t.loc[(t["team"] == team) & (t["week"] < week), "week"].unique())[-WINDOW:]
    hist = t[(t["team"] == team) & t["week"].isin(weeks)].groupby("pid")["rec_td"].sum().reindex(pool["pid"]).fillna(0).to_numpy(float)
    prior = (hist + 0.5 * sy * 6) / (hist.sum() + 3.0)
    mix = w["yards"] * sy + w["td_history"] * prior / prior.sum()
    if td.get("uses_fpds") and w.get("fpds", 0) > 0:
        f = features_asof(season, team, week)
        if {"eztgt", "i20_tgt"} <= set(f.columns):
            rz = (f["eztgt"].fillna(0) + f["i20_tgt"].fillna(0)).reindex(pool["pid"]).to_numpy(float)
            mix = mix + w["fpds"] * share_from(rz, sy)
    mix = mix / mix.sum()
    return dict(zip(pool["pid"], map(float, mix)))


def rush_td_weights(u, team: str, season: int, week: int, out_ids=frozenset(), rule: dict | None = None) -> dict:
    """pid -> chance weight to score a rushing touchdown: yardage share, touchdown history and (when the rule uses it) carry share times inside-the-5 share.

    Empty when the rule does not use FantasyPoints for rushing touchdowns, in which case the caller falls back to rushing yardage."""
    rule = load_rule() if rule is None else rule
    td = rule.get("td", {}).get("rush_td", {})
    if not td.get("uses_fpds"):
        return {}
    w = td["weights"]
    p = u.players
    pool = p[p["active"] & ~p["pid"].isin(out_ids)]
    yd = np.clip(pool["share_rush_yds"].to_numpy(float), 0, None)
    if len(pool) == 0 or yd.sum() <= 0:
        return {}
    sy = yd / yd.sum()
    t = _td_table(season)
    weeks = sorted(t.loc[(t["team"] == team) & (t["week"] < week), "week"].unique())[-WINDOW:]
    hist = t[(t["team"] == team) & t["week"].isin(weeks)].groupby("pid")["rush_td"].sum().reindex(pool["pid"]).fillna(0).to_numpy(float)
    prior = (hist + 0.5 * sy * 6) / (hist.sum() + 3.0)
    mix = w["yards"] * sy + w["td_history"] * prior / prior.sum()
    f = features_asof(season, team, week)
    if w.get("fpds", 0) > 0 and {"att_pct", "i5_pct"} <= set(f.columns):
        gl = (f["att_pct"] * f["i5_pct"]).reindex(pool["pid"]).to_numpy(float)
        mix = mix + w["fpds"] * share_from(gl, sy)
    mix = mix / mix.sum()
    return dict(zip(pool["pid"], map(float, mix)))


def rush_td_share(team: str, season: int, week: int, prior_tds: float = 4.0, league: float = 0.38) -> float:
    """Share of the team's recent offensive touchdowns that were rushes, pulled toward the league share (38% in 2025 and 2026) by a prior."""
    t = _td_table(season)
    weeks = sorted(t.loc[(t["team"] == team) & (t["week"] < week), "week"].unique())[-WINDOW:]
    sub = t[(t["team"] == team) & t["week"].isin(weeks)]
    rush, rec = float(sub["rush_td"].sum()), float(sub["rec_td"].sum())
    return float((rush + league * prior_tds) / (rush + rec + prior_tds))


PROFILE = [("tgt_pct", "Target share"), ("rte_pct", "Routes run"), ("ay_share", "Air yards share"), ("yprr", "Yards per route"),
           ("att_pct", "Carry share"), ("snap_pct", "Snap share"), ("exp_run", "Explosive runs")]


def profile(team: str, season: int, week: int, pids) -> dict:
    """pid -> {metric: value, weeks: n} from the last six weeks of FPDS rows; only metrics with data."""
    f = features_asof(season, team, week)
    out = {}
    for pid in pids:
        if pid not in f.index:
            continue
        r = f.loc[pid]
        d = {k: float(r[k]) for k, _ in PROFILE if k in r and pd.notna(r[k])}
        if "ay_share" in d:
            d["ay_share"] /= 100.0  # this metric is a percent in both exports
        if {"eztgt", "i20_tgt"} & set(f.columns):
            rz = float(np.nansum([r.get("eztgt", np.nan), r.get("i20_tgt", np.nan)]))
            if rz > 0:
                d["rz_tgt"] = rz
        if d:
            d["weeks"] = int(r.get("fp_weeks", 0))
            out[pid] = d
    return out


# --------------------------------------------------------------------------- chronological test

def _grid(k: int, step: float = 0.1):
    n = int(round(1 / step))
    def rec(left, parts):
        if parts == 1:
            yield [left]
            return
        for i in range(left + 1):
            for rest in rec(left - i, parts - 1):
                yield [i, *rest]
    return np.array(list(rec(n, k)), float) * step


def _games(seasons_weeks, mode: str):
    """Team-games in the given (season, first_week, last_week) ranges, with the pool of players expected to play."""
    from . import usage as U
    seasons = sorted({s for s, _, _ in seasons_weeks})
    g = U.player_games(seasons)
    outs = U.official_out(seasons)
    out_by = {k: set(v["gsis_id"]) for k, v in outs.groupby(["season", "team", "week"])}
    rows = []
    for (season, team), gdf in g.groupby(["season", "posteam"]):
        lo_hi = [(a, b) for s, a, b in seasons_weeks if s == season]
        for week in sorted(gdf["week"].unique()):
            if not any(a <= week <= b for a, b in lo_hi):
                continue
            u = U.usage(gdf, season, team, int(week))
            if u is None or u.games < 2:
                continue
            o = out_by.get((season, team, int(week)), set())
            pool = u.players[u.players["active"] & ~u.players["pid"].isin(o)]
            if len(pool) < 3:
                continue
            actual = gdf[gdf["week"] == week].set_index("pid")
            feats = features_asof(season, team, int(week), None, mode)
            weeks = sorted(gdf[gdf["week"] < week]["week"].unique())[-WINDOW:]
            rows.append({"season": int(season), "week": int(week), "team": team, "u": u, "pool": pool, "actual": actual, "feats": feats, "weeks": weeks})
    return rows


LOW_N = 3  # a player counts as thin-history when he played this many or fewer of the team's last six games


def _stack(games, stat: str, feats: list[str]):
    X, y, gid, n = [], [], [], []
    for i, c in enumerate(games):
        base = c["pool"][f"share_{stat}"].to_numpy(float)
        T = c["u"].totals[stat]
        if base.sum() <= 0 or T <= 0:
            continue
        cols = [base / base.sum()]
        for f in feats:
            raw = c["feats"][f].reindex(c["pool"]["pid"]).to_numpy(float) if f in c["feats"].columns else np.full(len(base), np.nan)
            cols.append(share_from(raw, base))
        X.append(np.column_stack(cols) * T)
        y.append(c["actual"][stat].reindex(c["pool"]["pid"]).fillna(0).to_numpy(float))
        gid.append(np.full(len(base), i))
        n.append(c["pool"]["n"].to_numpy())
    return np.vstack(X), np.concatenate(y), np.concatenate(gid), np.concatenate(n)


def _paired(pred_new, pred_old, y, gid, mask=None, draws=2000, seed=7) -> dict:
    """RMSE of old and new predictions on the same player-games and a 90% interval for new minus old, resampling team-games."""
    m = np.ones(len(y), bool) if mask is None else mask
    size = int(gid.max()) + 1
    s_new = np.bincount(gid[m], weights=((pred_new - y) ** 2)[m], minlength=size)
    s_old = np.bincount(gid[m], weights=((pred_old - y) ** 2)[m], minlength=size)
    cnt = np.bincount(gid[m], minlength=size)
    keep = cnt > 0
    s_new, s_old, cnt = s_new[keep], s_old[keep], cnt[keep]
    idx = np.random.default_rng(seed).integers(0, len(cnt), (draws, len(cnt)))
    diff = np.sqrt(s_new[idx].sum(1) / cnt[idx].sum(1)) - np.sqrt(s_old[idx].sum(1) / cnt[idx].sum(1))
    return {"rmse_new": float(np.sqrt(s_new.sum() / cnt.sum())), "rmse_old": float(np.sqrt(s_old.sum() / cnt.sum())), "player_games": int(cnt.sum()),
            "diff_lo": float(np.percentile(diff, 5)), "diff_hi": float(np.percentile(diff, 95))}


def evaluate(mode: str = "last6", train=((2022, 3, 18), (2023, 3, 18), (2024, 3, 18)), test_main=((2025, 3, 18),), test_now=((2026, 3, 7),),
             lo_n: int = 0, hi_n: int = LOW_N) -> dict:
    """Fit blend weights on train-season players with thin recent history; score on 2025 and on 2026 so far.

    The hybrid is what the simulation uses: thin-history players get the blend, everyone else keeps the nflverse share."""
    sets = {"train": _games(train, mode), "test_2025": _games(test_main, mode), "test_2026": _games(test_now, mode)}
    out = {"mode": mode, "games": {k: len(v) for k, v in sets.items()}, "stats": {}}
    for stat, feats in STAT_FEATURES.items():
        Xs = {k: _stack(v, stat, feats) for k, v in sets.items()}
        Xt, yt, gt, nt = Xs["train"]
        low = (nt >= lo_n) & (nt <= hi_n)
        grid = _grid(1 + len(feats))
        sse = np.array([((Xt[low] @ w - yt[low]) ** 2).sum() for w in grid])
        best = grid[int(sse.argmin())]
        res = {"weights": dict(zip(["base", *feats], map(float, best))), "train_player_games": int(low.sum())}
        for k in ("test_2025", "test_2026"):
            X, y, g_, n = Xs[k]
            lo = (n >= lo_n) & (n <= hi_n)
            old = X[:, 0]
            new = np.where(lo, X @ best, old)
            res[k] = {"thin_history": _paired(new, old, y, g_, lo), "everyone": _paired(new, old, y, g_),
                      "regulars": _paired(new, old, y, g_, ~lo), "share_thin": float(lo.mean())}
        out["stats"][stat] = res
    return out


def gate(result: dict) -> dict:
    """Keep a blend only when it beats nflverse-only for thin-history players on both 2025 and 2026 with the whole interval below zero."""
    weights = {}
    for stat, r in result["stats"].items():
        if all(r[k]["thin_history"]["diff_hi"] < 0 for k in ("test_2025", "test_2026")):
            weights[stat] = r["weights"]
    return weights


# --------------------------------------------------------------------------- who scores: red-zone and goal-line usage

def td_events(seasons) -> pd.DataFrame:
    """Touchdowns by player and game (receiving and rushing, no two-point tries) from local play-by-play."""
    frames = []
    for season in seasons:
        path = D.RAW_DIR / f"play_by_play_{season}.parquet"
        if not path.exists():
            continue
        p = pd.read_parquet(path, columns=["week", "posteam", "pass_touchdown", "rush_touchdown", "receiver_player_id", "rusher_player_id", "two_point_attempt"])
        p = p[p["two_point_attempt"] != 1]
        r = p[p["pass_touchdown"] == 1].groupby(["week", "posteam", "receiver_player_id"]).size().rename("rec_td").rename_axis(["week", "team", "pid"])
        u = p[p["rush_touchdown"] == 1].groupby(["week", "posteam", "rusher_player_id"]).size().rename("rush_td").rename_axis(["week", "team", "pid"])
        t = pd.concat([r, u], axis=1).fillna(0).reset_index().assign(season=season)
        t["team"] = t["team"].map(lambda x: normalize_team(x) if isinstance(x, str) else x)
        frames.append(t)
    return pd.concat(frames, ignore_index=True)


TD_FEATURES = {"rec_td": ["rz_tgt"], "rush_td": ["gl_att"]}


def _td_rows(games, td: pd.DataFrame, kind: str):
    """Per team-game: candidate share vectors over the pool and which pool players scored."""
    tdx = {k: v for k, v in td.groupby(["season", "team"])}
    out = []
    for c in games:
        pool = c["pool"]
        t = tdx.get((c["season"], c["team"]))
        if t is None:
            continue
        pids = pool["pid"].to_numpy()
        win = t[t["week"].isin(c["weeks"])].groupby("pid")[kind].sum().reindex(pids).fillna(0).to_numpy(float)
        yd = pool["share_rec_yds" if kind == "rec_td" else "share_rush_yds"].to_numpy(float)
        if yd.sum() <= 0:
            continue
        scored = t[(t["week"] == c["week"]) & (t[kind] > 0)].set_index("pid")[kind]
        hit = scored.reindex(pids).fillna(0).to_numpy(float)
        if hit.sum() == 0:
            continue
        f = c["feats"]
        if kind == "rec_td":
            z = (f["eztgt"].fillna(0) + f["i20_tgt"].fillna(0)) if "eztgt" in f else None
            fp = f.assign(rz=z)["rz"].reindex(pids).to_numpy(float) if z is not None else np.full(len(pids), np.nan)
        else:
            fp = (f["att_pct"] * f["i5_pct"]).reindex(pids).to_numpy(float) if {"att_pct", "i5_pct"} <= set(f.columns) else np.full(len(pids), np.nan)
        sy = yd / yd.sum()
        prior = (win + 0.5 * sy * 6) / (win.sum() + 3.0)  # touchdowns so far, with half a touchdown spread by yards share as a prior
        out.append({"cols": np.column_stack([sy, prior / prior.sum(), share_from(fp, sy)]), "hit": hit})
    return out


def _td_loglik(rows, w) -> np.ndarray:
    ll = []
    for r in rows:
        mix = r["cols"] @ w
        ll.append(float((r["hit"] * np.log(np.clip(mix, 1e-6, None) / mix.sum())).sum() / r["hit"].sum()))
    return np.array(ll)


def evaluate_td(mode: str = "last6", train=((2022, 3, 18), (2023, 3, 18), (2024, 3, 18)), test_main=((2025, 3, 18),), test_now=((2026, 3, 7),)) -> dict:
    """Fit the weights on yardage share, touchdown history and FPDS red-zone usage; score who actually scored."""
    sets = {"train": _games(train, mode), "test_2025": _games(test_main, mode), "test_2026": _games(test_now, mode)}
    td = td_events(sorted({y for y, _, _ in (*train, *test_main, *test_now)}))
    out = {"stats": {}}
    grid = _grid(3)
    for kind in ("rec_td", "rush_td"):
        rows = {k: _td_rows(v, td, kind) for k, v in sets.items()}
        fit_all = [(_td_loglik(rows["train"], w).mean(), w) for w in grid]
        nf = [(m, w) for m, w in fit_all if w[2] == 0]  # nflverse only: no FPDS component
        best, w_all = max(fit_all, key=lambda x: x[0])[1], None
        w_best = max(fit_all, key=lambda x: x[0])[1]
        w_nf = max(nf, key=lambda x: x[0])[1]
        res = {"weights_all": dict(zip(["yards", "td_history", "fpds"], map(float, w_best))), "weights_nflverse_only": dict(zip(["yards", "td_history", "fpds"], map(float, w_nf)))}
        for k in ("test_2025", "test_2026"):
            a, b = _td_loglik(rows[k], w_best), _td_loglik(rows[k], w_nf)
            rng = np.random.default_rng(3)
            idx = rng.integers(0, len(a), (2000, len(a)))
            d = (a[idx] - b[idx]).mean(1)
            res[k] = {"games_with_td": len(a), "loglik_with_fpds": float(a.mean()), "loglik_nflverse_only": float(b.mean()), "diff_lo": float(np.percentile(d, 5)), "diff_hi": float(np.percentile(d, 95))}
        out["stats"][kind] = res
    return out
