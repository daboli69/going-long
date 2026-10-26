"""Phase 15: point-in-time QB knowledge, market-implied QB values, sealed 2025 vault, program discipline.
Exactly as pre-registered in docs/PHASE15_PREREGISTRATION.md (commit ec12b3b2). Lab-only.

  python -m lab.phase15 fetch 2018 2024   Wayback captures of espn.com/nfl/injuries needed for QB-change games (polite, cached)
  python -m lab.phase15 history           A: point-in-time re-run on 2018-24 (one look)
  python -m lab.phase15 market            B: market-implied QB values + Deming scale on 2015-24
  python -m lab.phase15 vault             C: sealed 2025 vault (once, only from a committed tree)
  python -m lab.phase15 freeze            D: point-in-time forecasts for upcoming 2026 games at the current window
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .config import ARTIFACTS_DIR, RAW_DIR

OUT = ARTIFACTS_DIR / "phase15"
WB = RAW_DIR / "wayback15"
ET = "America/New_York"
PUBLIC_STATUSES = ("out", "doubtful", "injured reserve", "ir", "suspension", "suspended")
WAYBACK_URL = "espn.com/nfl/injuries"


def _ll(y, p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def norm_name(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", s)
    return " ".join(s.split())


# --------------------------------------------------------------------------- windows
def windows(kickoff_utc: pd.Timestamp) -> dict:
    k = kickoff_utc.tz_convert(ET)
    d = k.normalize()
    t2 = d - pd.Timedelta(days=2)
    sun = t2 - pd.Timedelta(days=(t2.dayofweek - 6) % 7)
    t1 = d - pd.Timedelta(days=1)
    wed = t1 - pd.Timedelta(days=(t1.dayofweek - 2) % 7)
    return {"open": (sun + pd.Timedelta(hours=20)).tz_convert("UTC"), "mid": (wed + pd.Timedelta(hours=12)).tz_convert("UTC"),
            "kick": kickoff_utc}


# --------------------------------------------------------------------------- Wayback
def _get(url, retries=3):
    import requests
    for i in range(retries):
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "nfl-ensemble-lab research (low volume)"})
            if r.status_code == 200:
                return r
        except Exception:  # noqa: BLE001
            pass
        time.sleep(5 * (i + 1))
    return None


def cdx_index(season: int) -> pd.Series:
    WB.mkdir(parents=True, exist_ok=True)
    f = WB / f"cdx_{season}.json"
    if not f.exists():
        url = (f"https://web.archive.org/cdx/search/cdx?url={WAYBACK_URL}&from={season}0801&to={season + 1}0220"
               "&output=json&fl=timestamp,statuscode&filter=statuscode:200&collapse=timestamp:10")
        r = _get(url)
        rows = r.json()[1:] if r is not None else []
        f.write_text(json.dumps([x[0] for x in rows]))
        time.sleep(2)
    ts = json.loads(f.read_text())
    return pd.Series(pd.to_datetime(ts, format="%Y%m%d%H%M%S", utc=True), index=ts).sort_values()


def capture_before(idx: pd.Series, t: pd.Timestamp, max_hours=72):
    c = idx[idx <= t]
    if c.empty or (t - c.iloc[-1]) > pd.Timedelta(hours=max_hours):
        return None
    return c.index[-1]


def fetch_capture(ts: str) -> Path | None:
    f = WB / f"injuries_{ts}.html"
    if not f.exists():
        r = _get(f"https://web.archive.org/web/{ts}id_/https://www.espn.com/nfl/injuries")
        if r is None:
            return None
        f.write_bytes(r.content)
        time.sleep(2)
    return f


def parse_capture(f: Path) -> pd.DataFrame:
    """Rows (name_norm, pos, status) from either ESPN layout (2018-style single table or per-team tables)."""
    try:
        tabs = pd.read_html(f)
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["name", "pos", "status"])
    rows = []
    for t in tabs:
        cols = [str(c).upper() for c in t.columns]
        if "NAME" in cols and "STATUS" in cols:
            pos = t[t.columns[cols.index("POS")]] if "POS" in cols else ""
            for n, p, s in zip(t[t.columns[cols.index("NAME")]], pos if len(pos) else [""] * len(t), t[t.columns[cols.index("STATUS")]]):
                rows.append((norm_name(n), str(p).upper(), str(s).lower()))
        else:
            for r in t.itertuples(index=False):
                a = str(r[0])
                if "," in a and not a.lower().startswith("comment"):
                    n, p = a.rsplit(",", 1)
                    rows.append((norm_name(n), p.strip().upper(), str(r[1]).lower()))
    return pd.DataFrame(rows, columns=["name", "pos", "status"])


# --------------------------------------------------------------------------- point-in-time classification
def qb_change_games(seasons) -> pd.DataFrame:
    from . import phase14 as P14
    q = P14.qb_games(range(2006, max(seasons) + 1))
    pl = P14._players()
    g = P14.game_frame(q)
    hyper, D = P14._models(q, pl, seasons)
    d = P14.deltas(g[g["season"].isin(list(seasons))], q, pl, hyper, D)
    x = g.merge(d, on="game_id")
    x["kickoff"] = pd.to_datetime(x["gameday"] + " " + x["gametime"]).dt.tz_localize(ET).dt.tz_convert("UTC")
    x.attrs.update(hyper=hyper, D=D)
    return x, q, pl


def _names():
    pl = pd.read_parquet(RAW_DIR / "players.parquet", columns=["gsis_id", "display_name"]).drop_duplicates("gsis_id")
    return dict(zip(pl["gsis_id"], pl["display_name"].map(norm_name)))


def classify(x: pd.DataFrame, use_official=True, fetch=True) -> pd.DataFrame:
    """For each QB-change side: was the previous starter's absence public at T_open / T_mid?"""
    names = _names()
    off = None
    if use_official:
        parts = []
        for s in sorted(x["season"].unique()):
            f = RAW_DIR / f"injuries_{s}.parquet"
            if f.exists():
                i = pd.read_parquet(f, columns=["season", "week", "gsis_id", "report_status", "date_modified"])
                parts.append(i)
        if parts:
            off = pd.concat(parts)
            off = off[off["report_status"].astype(str).str.lower().isin(["out", "doubtful"])]
            off["dm"] = pd.to_datetime(off["date_modified"], utc=True, errors="coerce")
    cap_cache = {}
    rows = []
    for r in x.itertuples(index=False):
        w = windows(r.kickoff)
        idx = cdx_index(r.season)
        rec = {"game_id": r.game_id}
        for side in ("home", "away"):
            if not getattr(r, f"{side}_change"):
                rec[f"{side}_open"] = rec[f"{side}_mid"] = True          # no change: nothing to learn
                rec[f"{side}_class"] = "no_change"
                continue
            old = getattr(r, f"{side}_prev_qb")
            nm = names.get(old, "")
            t_pub = None
            if off is not None:
                o = off[(off["gsis_id"] == old) & (off["season"] == r.season) & (off["week"] == r.week) & off["dm"].notna()]
                if len(o):
                    t_pub = o["dm"].min()
            for lbl in ("open", "mid"):
                ts = capture_before(idx, w[lbl])
                if ts is None:
                    continue
                if ts not in cap_cache:
                    f = fetch_capture(ts) if fetch else (WB / f"injuries_{ts}.html")
                    cap_cache[ts] = parse_capture(f) if f is not None and Path(f).exists() else None
                c = cap_cache[ts]
                if c is not None and nm and len(c):
                    hit = c[(c["name"] == nm) & c["status"].str.contains("|".join(PUBLIC_STATUSES))]
                    if len(hit):
                        t_cap = pd.Timestamp(pd.to_datetime(ts, format="%Y%m%d%H%M%S", utc=True))
                        t_pub = t_cap if t_pub is None else min(t_pub, t_cap)
                rec[f"{side}_cap_{lbl}"] = ts
            rec[f"{side}_open"] = bool(t_pub is not None and t_pub <= w["open"])
            rec[f"{side}_mid"] = bool(t_pub is not None and t_pub <= w["mid"])
            rec[f"{side}_class"] = ("public_by_open" if rec[f"{side}_open"] else "open_to_mid" if rec[f"{side}_mid"]
                                    else "after_mid" if (t_pub is not None and t_pub <= r.kickoff) else "not_visible")
            rec[f"{side}_t_public"] = t_pub
        rows.append(rec)
    return x.merge(pd.DataFrame(rows), on="game_id")


def pit_delta(x, lbl):
    h = np.where(x["home_change"], x["delta_home_team"] * x[f"home_{lbl}"].astype(float), 0.0)
    a = np.where(x["away_change"], x["delta_away_team"] * x[f"away_{lbl}"].astype(float), 0.0)
    return h - a


def _corr_test(a, b):
    r = stats.pearsonr(a, b, alternative="greater")
    return float(r.statistic), float(r.pvalue)


def _boot_ratio(a_pit, a_full, b, n=2000, seed=15):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(b), (n, len(b)))
    out = []
    for k in idx:
        rf = np.corrcoef(a_full[k], b[k])[0, 1]
        rp = np.corrcoef(a_pit[k], b[k])[0, 1]
        out.append(1 - rp / rf if rf > 0 else np.nan)
    return [float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5))]


def history() -> dict:
    if (OUT / "history.json").exists():
        raise FileExistsError("Phase 15 A (historical point-in-time look) already taken")
    m14 = json.loads((ARTIFACTS_DIR / "phase14" / "model.json").read_text())
    gamma = m14["gamma"]
    x = pd.read_parquet(ARTIFACTS_DIR / "phase14" / "qb_change_games.parquet")
    x = x[x["season"].between(2018, 2024)].copy()
    x["kickoff"] = pd.to_datetime(x["gameday"] + " " + x["gametime"]).dt.tz_localize(ET).dt.tz_convert("UTC")
    x = classify(x)
    x["d_open"], x["d_mid"] = pit_delta(x, "open"), pit_delta(x, "mid")
    mv = (_logit(x["p_close"]) - _logit(x["p_open"])).to_numpy()
    lm = (x["close_margin_asb"] - x["open_margin"]).to_numpy()
    def clv(d):
        return (_logit(x["p_champ"]) + gamma * d) - _logit(x["p_open"])
    a1 = _corr_test(clv(x["d_open"]), mv)
    a2 = _corr_test(x["d_open"], lm)
    a3 = _corr_test(x["d_open"], x["market_qb_adj"])
    full = {"A1": np.corrcoef(clv(x["delta_home"]), mv)[0, 1], "A2": np.corrcoef(x["delta_home"], lm)[0, 1],
            "A3": np.corrcoef(x["delta_home"], x["market_qb_adj"])[0, 1]}
    ps = sorted([("A1", a1[1]), ("A2", a2[1]), ("A3", a3[1])], key=lambda t: t[1])
    holm, run = {}, 0.0
    for i, (k, pv) in enumerate(ps):
        run = max(run, min(1.0, (3 - i) * pv))
        holm[k] = run
    res = {"games": int(len(x)), "gamma": gamma}
    for k, (r, p), a_pit, a_full, b in (("A1", a1, clv(x["d_open"]).to_numpy(), clv(x["delta_home"]).to_numpy(), mv),
                                         ("A2", a2, x["d_open"].to_numpy(), x["delta_home"].to_numpy(), lm),
                                         ("A3", a3, x["d_open"].to_numpy(), x["delta_home"].to_numpy(), x["market_qb_adj"].to_numpy())):
        res[k] = {"r_point_in_time": r, "p_one_sided": p, "holm": holm[k], "passes": bool(holm[k] < 0.05 and r > 0),
                  "r_with_hindsight": float(full[k]), "hindsight_share": float(1 - r / full[k]) if full[k] > 0 else None,
                  "hindsight_share_ci95": _boot_ratio(a_pit, a_full, b)}
    sides = pd.concat([x["home_class"].where(x["home_change"]), x["away_class"].where(x["away_change"])]).dropna()
    res["visibility_classes"] = sides.value_counts().to_dict()
    res["coverage"] = {"capture_open_found_share": float(pd.concat([x.get("home_cap_open"), x.get("away_cap_open")]).notna().mean()),
                       "capture_mid_found_share": float(pd.concat([x.get("home_cap_mid"), x.get("away_cap_mid")]).notna().mean())}
    by = {}
    x["cls"] = np.where(x["home_change"], x["home_class"], x["away_class"])
    for c, d in x.groupby("cls"):
        if len(d) >= 10:
            by[c] = {"games": int(len(d)), "mean_abs_open_to_close_move": float((d["close_margin_asb"] - d["open_margin"]).abs().mean()),
                     "corr_full_delta_with_move": float(np.corrcoef(d["delta_home"], d["close_margin_asb"] - d["open_margin"])[0, 1])}
    res["by_visibility_class"] = by
    OUT.mkdir(parents=True, exist_ok=True)
    x.drop(columns=[c for c in x.columns if c.endswith("_t_public")]).to_parquet(OUT / "history_games.parquet", index=False)
    (OUT / "history.json").write_text(json.dumps(res, indent=2, default=str))
    return res


# --------------------------------------------------------------------------- B market-implied values
def deming(x, y, delta):
    sxx, syy, sxy = np.var(x, ddof=1), np.var(y, ddof=1), np.cov(x, y)[0, 1]
    b = (syy - delta * sxx + np.sqrt((syy - delta * sxx) ** 2 + 4 * delta * sxy ** 2)) / (2 * sxy)
    return float(b), float(np.mean(y) - b * np.mean(x))


def _posterior_var(a, qbs, hyper):
    r = a.reindex(qbs)
    n = r["n_eff"].fillna(0).to_numpy()
    return 1 / (1 / hyper["tau2"] + n / hyper["sigma2"])


def market_fit(seasons=range(2015, 2025)) -> dict:
    from . import phase14 as P14
    x, q, pl = qb_change_games(seasons)
    hyper, D = x.attrs["hyper"], x.attrs["D"]
    x = x[x["asb_ok"] & x["market_expected"].notna()].copy()
    x["y"] = x["close_margin_asb"] - x["market_expected"]
    # performance-change error variance from posterior variances
    ev = []
    for r in x.itertuples(index=False):
        a = P14.asof_table(q, r.season, r.wk)
        v = 0.0
        for side in ("home", "away"):
            if getattr(r, f"{side}_change"):
                v += float(_posterior_var(a, [getattr(r, f"{side}_qb_id"), getattr(r, f"{side}_prev_qb")], hyper[r.season]).sum()) * D[r.season] ** 2
        ev.append(v)
    x["perf_err_var"] = ev
    g = P14.game_frame(q)
    nq = g[g["season"].isin(list(seasons)) & ~g["qb_change"] & g["asb_ok"] & g["market_expected"].notna()]
    noise_var = float(np.var(nq["close_margin_asb"] - nq["market_expected"], ddof=1))
    delta = noise_var / float(np.mean(x["perf_err_var"]))
    c, c0 = deming(x["delta_home"].to_numpy(), x["y"].to_numpy(), delta)
    rng = np.random.default_rng(16)
    boots = [deming(x["delta_home"].to_numpy()[k], x["y"].to_numpy()[k], delta)[0] for k in rng.integers(0, len(x), (1000, len(x)))]
    # hierarchical market-implied QB residuals u_q ~ N(0, s_v^2): y - c * delta = sum sign * u + e
    cols = {}
    rows_idx, cols_idx, vals = [], [], []
    for i, r in enumerate(x.itertuples(index=False)):
        for side, sgn in (("home", 1.0), ("away", -1.0)):
            if getattr(r, f"{side}_change"):
                for qb, s2 in ((getattr(r, f"{side}_qb_id"), 1.0), (getattr(r, f"{side}_prev_qb"), -1.0)):
                    j = cols.setdefault(qb, len(cols))
                    rows_idx.append(i)
                    cols_idx.append(j)
                    vals.append(sgn * s2)
    Z = np.zeros((len(x), len(cols)))
    np.add.at(Z, (rows_idx, cols_idx), vals)
    resid = x["y"].to_numpy() - c * x["delta_home"].to_numpy() - c0
    best = None
    for sv2 in (0.25, 0.5, 1, 2, 4, 8, 16):
        K = noise_var * np.eye(len(x)) + sv2 * Z @ Z.T
        sign, logdet = np.linalg.slogdet(K)
        ll = -0.5 * (logdet + resid @ np.linalg.solve(K, resid))
        if best is None or ll > best[1]:
            best = (sv2, ll)
    sv2 = best[0]
    u = np.linalg.solve(Z.T @ Z + (noise_var / sv2) * np.eye(len(cols)), Z.T @ resid)
    uq = dict(zip(cols.keys(), u))
    x["delta_comb"] = c0 + c * x["delta_home"] + Z @ u
    res = {"games": int(len(x)), "noise_var_market": noise_var, "mean_perf_err_var": float(np.mean(x["perf_err_var"])), "deming_delta": delta,
           "c": c, "c_intercept": c0, "c_ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
           "s_v2": sv2, "qbs_with_market_residual": len(cols),
           "corr_y_perf": float(np.corrcoef(x["delta_home"], x["y"])[0, 1]), "corr_y_comb_in_sample": float(np.corrcoef(x["delta_comb"], x["y"])[0, 1]),
           "mean_abs_perf": float(x["delta_home"].abs().mean()), "mean_abs_scaled": float((c * x["delta_home"]).abs().mean()),
           "mean_abs_market": float(x["y"].abs().mean())}
    f = RAW_DIR / "public" / "nfelo_nfelo_games.csv"
    if f.exists():
        n = pd.read_csv(f)[["game_id", "home_538_qb_adj", "away_538_qb_adj"]]
        v = x.merge(n, on="game_id").dropna(subset=["home_538_qb_adj"])
        a538 = (v["home_538_qb_adj"] - v["away_538_qb_adj"]) / 25.0
        res["public_538"] = {"games": int(len(v)), "corr_538_vs_market": float(np.corrcoef(a538, v["y"])[0, 1]),
                             "corr_comb_vs_538": float(np.corrcoef(v["delta_comb"], a538)[0, 1]),
                             "corr_perf_vs_538": float(np.corrcoef(v["delta_home"], a538)[0, 1])}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "market_model.json").write_text(json.dumps({"c": c, "c0": c0, "s_v2": sv2, "noise_var": noise_var, "u": uq}, indent=2))
    (OUT / "market.json").write_text(json.dumps(res, indent=2, default=str))
    return res


# --------------------------------------------------------------------------- C vault
def _committed(path="lab/phase15.py") -> str:
    root = Path(__file__).resolve().parents[1]
    dirty = subprocess.run(["git", "status", "--porcelain", "--", path], cwd=root, capture_output=True, text=True).stdout.strip()
    if dirty:
        raise RuntimeError("phase15.py has uncommitted changes; commit before unblinding the vault")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()


def vault() -> dict:
    f = OUT / "vault.json"
    if f.exists():
        raise FileExistsError("the 2025 vault has already been unblinded")
    sha = _committed()
    mm = json.loads((OUT / "market_model.json").read_text())
    x, q, pl = qb_change_games([2025])
    x = x[x["asb_ok"] & x["market_expected"].notna()].copy()
    x = classify(x, use_official=False)
    for lbl in ("open", "mid"):
        x[f"d_{lbl}"] = pit_delta(x, lbl)
    u = mm["u"]

    def comb(d_col, r):
        base = mm["c0"] + mm["c"] * d_col
        adj = 0.0
        for side, sgn in (("home", 1.0), ("away", -1.0)):
            if getattr(r, f"{side}_change"):
                adj += sgn * (u.get(getattr(r, f"{side}_qb_id"), 0.0) - u.get(getattr(r, f"{side}_prev_qb"), 0.0))
        return base + adj
    x["comb_kick"] = [comb(d, r) for d, r in zip(x["delta_home"], x.itertuples(index=False))]
    x["comb_open"] = [comb(d, r) if d != 0 else 0.0 for d, r in zip(x["d_open"], x.itertuples(index=False))]
    y = (x["close_margin_asb"] - x["market_expected"]).to_numpy()
    r1, p1 = _corr_test(x["comb_kick"], y)
    rng = np.random.default_rng(25)
    sl = []
    for k in rng.integers(0, len(x), (2000, len(x))):
        cx, cy = x["comb_kick"].to_numpy()[k], y[k]
        sl.append(np.cov(cx, cy)[0, 1] / np.var(cx, ddof=1) if np.var(cx) > 0 else np.nan)
    ci = [float(np.nanpercentile(sl, 2.5)), float(np.nanpercentile(sl, 97.5))]
    r2, p2 = _corr_test(x["comb_open"], (x["close_margin_asb"] - x["open_margin"]).to_numpy())
    ps = sorted([("V1", p1), ("V2", p2)], key=lambda t: t[1])
    holm, run = {}, 0.0
    for i, (k, pv) in enumerate(ps):
        run = max(run, min(1.0, (2 - i) * pv))
        holm[k] = run
    res = {"unblinded_at": pd.Timestamp.now(tz="UTC").isoformat(), "code_commit": sha, "games": int(len(x)),
           "V1": {"r": r1, "p_one_sided": p1, "holm": holm["V1"], "slope_ci95": ci,
                  "passes": bool(holm["V1"] < 0.05 and r1 > 0 and ci[0] <= 1 <= ci[1])},
           "V2": {"r": r2, "p_one_sided": p2, "holm": holm["V2"], "passes": bool(holm["V2"] < 0.05 and r2 > 0)},
           "visibility_classes": pd.concat([x["home_class"].where(x["home_change"]), x["away_class"].where(x["away_change"])]).dropna().value_counts().to_dict()}
    nf = RAW_DIR / "public" / "nfelo_nfelo_games.csv"
    if nf.exists():
        n = pd.read_csv(nf)[["game_id", "home_538_qb_adj", "away_538_qb_adj"]]
        v = x.merge(n, on="game_id").dropna(subset=["home_538_qb_adj"])
        if len(v) > 5:
            a538 = (v["home_538_qb_adj"] - v["away_538_qb_adj"]) / 25.0
            res["public_538_2025"] = {"games": int(len(v)), "corr_comb_vs_538": float(np.corrcoef(v["comb_kick"], a538)[0, 1]),
                                      "corr_538_vs_market": float(np.corrcoef(a538, (v["close_margin_asb"] - v["market_expected"]))[0, 1])}
    OUT.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(res, indent=2, default=str))
    return res


# --------------------------------------------------------------------------- D prospective point-in-time freeze (2026)
def freeze() -> dict:
    """Freeze, for upcoming 2026 games, the line now and whether a QB change is public now (window = now)."""
    from .market81 import espn_archive
    from . import phase14 as P14
    arc = espn_archive()
    arc["retrieved_at"] = pd.to_datetime(arc["retrieved_at"], utc=True)
    arc["ko"] = pd.to_datetime(arc["kickoff"], utc=True, errors="coerce")
    now = pd.Timestamp.now(tz="UTC")
    up = arc[arc["ko"] > now].sort_values("retrieved_at").drop_duplicates(["home", "away"], keep="last")
    qv = sorted((P14.OUT / "prospective").glob("qb_values_*.parquet"))
    if not qv:
        return {"error": "run python -m lab.phase14 freeze first"}
    v = pd.read_parquet(qv[-1])
    piv = v.pivot_table(index="team", columns="pos_rank", values="value_points")
    rows = []
    for r in up.itertuples(index=False):
        rows.append({"home": r.home, "away": r.away, "kickoff": r.ko, "line_at_freeze": pd.to_numeric(str(r.home_spread_close).replace("+", ""), errors="coerce"),
                     "home_drop_if_out": float(piv.loc[r.home, 2] - piv.loc[r.home, 1]) if r.home in piv.index else np.nan,
                     "away_drop_if_out": float(piv.loc[r.away, 2] - piv.loc[r.away, 1]) if r.away in piv.index else np.nan,
                     "frozen_at": now, "window": "open" if now.tz_convert(ET).dayofweek in (6, 0, 1) else "mid"})
    out = OUT / "prospective"
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"freeze_{now.strftime('%Y%m%dT%H%M%SZ')}.parquet"
    pd.DataFrame(rows).to_parquet(f, index=False)
    return {"file": f.name, "games": len(rows)}


def fetch(y0: int, y1: int) -> dict:
    """Pre-fetch the captures classify() will need for QB-change games of seasons y0..y1 (cached, polite)."""
    x = pd.read_parquet(ARTIFACTS_DIR / "phase14" / "qb_change_games.parquet")
    x = x[x["season"].between(y0, y1)]
    x["kickoff"] = pd.to_datetime(x["gameday"] + " " + x["gametime"]).dt.tz_localize(ET).dt.tz_convert("UTC")
    need = set()
    for r in x.itertuples(index=False):
        idx = cdx_index(r.season)
        w = windows(r.kickoff)
        for lbl in ("open", "mid"):
            ts = capture_before(idx, w[lbl])
            if ts:
                need.add(ts)
    got = sum(fetch_capture(ts) is not None for ts in sorted(need))
    return {"captures_needed": len(need), "fetched_or_cached": got}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "history"
    OUT.mkdir(parents=True, exist_ok=True)
    if cmd == "fetch":
        r = fetch(int(sys.argv[2]), int(sys.argv[3]))
    else:
        r = {"history": history, "market": market_fit, "vault": vault, "freeze": freeze}[cmd]()
    print(json.dumps(r, indent=2, default=str)[:6000])
