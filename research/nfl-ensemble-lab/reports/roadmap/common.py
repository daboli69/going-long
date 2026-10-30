"""Shared helpers for the checklist protocol (reports/roadmap/PROTOCOL.md). numpy, pandas, scipy only."""
import hashlib, json, subprocess
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
import os
OUT = Path(os.environ["ROADMAP_OUT"]) if os.environ.get("ROADMAP_OUT") else ROOT / "reports" / "roadmap"
SRC = ROOT / "reports" / "roadmap"
CACHE = ROOT / "data" / "cache"
HW = CACHE / "homewin_deep"
PK = CACHE / "props_kalshi"
SEED = 0
LEAD = pd.Timedelta(minutes=90)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git_head() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def protocol_hash() -> str:
    return sha(SRC / "PROTOCOL.md")


def header(step: str) -> dict:
    return {"step": step, "git_head": git_head(), "protocol_sha256": protocol_hash()}


def write(name: str, obj: dict):
    (OUT / name).write_text(json.dumps(obj, indent=1, default=float), encoding="utf-8")


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + np.exp(-np.asarray(x, float)))


def ll(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def entropy(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return -(p * np.log(p) + (1 - p) * np.log(1 - p))


def crps_normal(y, mu, sd):
    z = (np.asarray(y, float) - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def cluster_index(keys: np.ndarray):
    """(codes, n_clusters) for week-cluster resampling."""
    codes, uniq = pd.factorize(pd.Series(keys))
    return np.asarray(codes), len(uniq)


def cluster_boot_mean(x: np.ndarray, codes: np.ndarray, k: int, B: int = 2000, seed: int = SEED):
    """Mean of x with whole clusters resampled; returns (mean, lo, hi, boot array)."""
    rng = np.random.default_rng(seed)
    s = np.bincount(codes, weights=x, minlength=k)
    n = np.bincount(codes, minlength=k).astype(float)
    idx = rng.integers(0, k, (B, k))
    bs = s[idx].sum(1) / n[idx].sum(1)
    return float(x.mean()), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), bs


def design_effect(x: np.ndarray, codes: np.ndarray, k: int) -> dict:
    """One-way ANOVA intra-cluster correlation, design effect and effective sample size."""
    n = len(x); sizes = np.bincount(codes, minlength=k).astype(float)
    means = np.bincount(codes, weights=x, minlength=k) / sizes
    grand = x.mean()
    ssb = (sizes * (means - grand) ** 2).sum(); ssw = ((x - means[codes]) ** 2).sum()
    msb = ssb / max(k - 1, 1); msw = ssw / max(n - k, 1)
    m0 = (n - (sizes ** 2).sum() / n) / max(k - 1, 1)
    rho = float(max(0.0, (msb - msw) / (msb + (m0 - 1) * msw))) if (msb + (m0 - 1) * msw) > 0 else 0.0
    de = 1 + (n / k - 1) * rho
    return {"n": n, "clusters": k, "icc": rho, "design_effect": float(de), "effective_n": float(n / de)}


def winners_frame() -> pd.DataFrame:
    """Completed, non-tied games with the walk-forward model columns, decision time and Kalshi prices at three cutoffs."""
    import sys; sys.path.insert(0, str(ROOT))
    from lab import kalshi as K
    w = pd.read_parquet(HW / "walk_forward.parquet")
    g = pd.read_parquet(CACHE / "games.parquet")[["game_id", "completed", "tie"]].rename(columns={"game_id": "gid"})
    hist = pd.read_parquet(HW / "kalshi_history.parquet")
    w = w[w.gid.isin(hist.gid.unique())].merge(g, on="gid", how="left")
    w = w[(w.completed == True) & (~w.tie.astype(bool))].copy()
    by = {gid: d for gid, d in hist.groupby("gid")}
    rows = []
    for r in w.itertuples(index=False):
        d = by[r.gid]; ko = pd.Timestamp(r.kickoff_utc)
        rows.append({"gid": r.gid,
                     "p_dec": K.probability(d, r.gid, pd.Timestamp(r.decision_utc), ko)["p_home"],
                     "p_t90": K.probability(d, r.gid, ko - LEAD, ko)["p_home"],
                     "p_close": K.probability(d, r.gid, ko, ko)["p_home"]})
    out = w.merge(pd.DataFrame(rows), on="gid")
    out["wk"] = out.season.astype(str) + "_" + out.week.astype(int).astype(str).str.zfill(2)
    return out


def logit_fit(X, y, iters=50):
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        mu = sigmoid(X @ b); W = np.clip(mu * (1 - mu), 1e-9, None)
        H = X.T @ (X * W[:, None]) + 1e-9 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - mu)); b = b + step
        if np.abs(step).max() < 1e-9: break
    return b


def fit_normal(c, p, w=None):
    """Least-squares normal fit to a survival ladder P(Y > c) = 1 - Phi((c - mu) / sd). Returns (mu, sd, ok)."""
    from scipy.optimize import least_squares
    c = np.asarray(c, float); p = np.asarray(p, float); w = np.ones_like(c) if w is None else np.asarray(w, float)
    i = np.argsort(c); c, p, w = c[i], p[i], w[i]
    mu0 = float(np.interp(0.5, p[::-1], c[::-1])) if p.min() < 0.5 < p.max() else float(c.mean())
    sd0 = max(float(c.max() - c.min()) / 4, 1.0)
    f = lambda t: np.sqrt(w) * ((1 - norm.cdf((c - t[0]) / t[1])) - p)
    r = least_squares(f, [mu0, sd0], bounds=([c.min() - 200, 0.3], [c.max() + 200, 500]))
    return float(r.x[0]), float(r.x[1]), bool(r.success)


def ladder_frame(qfilter=None) -> pd.DataFrame:
    """One row per (gid, target) market ladder at T-90 with its normal fit and the outcome (margin = home - away)."""
    import sys; sys.path.insert(0, str(ROOT))
    from lab import forecast_core as fc, kalshi as K
    q = pd.read_parquet(PK / "quotes.parquet"); q = q[q.series.isin(["KXNFLSPREAD", "KXNFLTOTAL"])]
    q = qfilter(q) if qfilter else q
    hist = pd.read_parquet(HW / "kalshi_history.parquet")
    gids = sorted(q.gid.dropna().unique())
    games = pd.DataFrame({"gid": gids}); games["away"] = games.gid.str.split("_").str[2]; games["home"] = games.gid.str.split("_").str[3]
    ko = hist.groupby("gid").kickoff_utc.first()
    by = {g: d for g, d in hist.groupby("gid")}
    wp = {g: K.probability(by[g], g, ko[g] - LEAD, ko[g])["p_home"] for g in gids if g in by}
    lad = fc.ladder_tables(q, games, wp, "90")
    wf = pd.read_parquet(HW / "forecast_wf.parquet").set_index("gid")
    rows = []
    for (gid, tgt), d in lad.items():
        if gid not in wf.index or not bool(wf.at[gid, "played"]): continue
        mu, sd, ok = fit_normal(d["c"], d["p_iso"], d["w"])
        y = wf.at[gid, "y_m"] if tgt == "margin" else wf.at[gid, "y_t"]
        yes = (y > d["c"].to_numpy()).astype(float)
        rows.append({"gid": gid, "target": tgt, "season": int(wf.at[gid, "season"]), "week": int(wf.at[gid, "week"]), "n_thr": len(d), "mu": mu, "sd": sd, "fit_ok": ok,
                     "y": float(y), "ladder_ceiling": float((d["p_iso"] * (1 - d["p_iso"])).sum()), "ladder_realized": float(((d["p_iso"] - yes) ** 2).sum()),
                     "c": d["c"].to_numpy(), "p_iso": d["p_iso"].to_numpy()})
    f = pd.DataFrame(rows); f["wk"] = f.season.astype(str) + "_" + f.week.astype(str).str.zfill(2)
    return f
