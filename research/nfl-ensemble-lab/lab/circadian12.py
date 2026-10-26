"""Phase 12: circadian night-game advantage (Smith et al., SLEEP 2013), replicated on 2012-2025.
Exactly as pre-registered in docs/PHASE12_CIRCADIAN_PREREGISTRATION.md. Lab-only; one look."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

from .config import ARTIFACTS_DIR, RAW_DIR
from .ingest import normalize_team

OUT = ARTIFACTS_DIR / "phase12"
EASTERN = {"ATL", "BAL", "BUF", "CAR", "CIN", "CLE", "DET", "IND", "JAX", "MIA", "NE", "NYG", "NYJ", "PHI", "PIT", "TB", "WAS"}
CENTRAL = {"CHI", "DAL", "GB", "HOU", "KC", "MIN", "NO", "TEN"}


def zone(team: str, season: int) -> str:
    """Home-stadium time zone that season (Rams: St. Louis Central through 2015)."""
    if team == "LA":
        return "P" if season >= 2016 else "C"
    if team in ("SF", "SEA", "LV", "LAC"):
        return "P"
    if team == "ARI":
        return "AZ"
    if team == "DEN":
        return "M"
    if team in EASTERN:
        return "E"
    if team in CENTRAL:
        return "C"
    raise ValueError(team)


OFFSET = {"E": 0, "C": 1, "M": 2, "AZ": 2, "P": 3}          # hours behind Eastern (B2 counts Arizona as Mountain)


def frame() -> pd.DataFrame:
    g = pd.read_csv(RAW_DIR / "games.csv")
    g = g[g["season"].between(2012, 2025) & g["home_score"].notna() & g["spread_line"].notna() & (g["location"] != "Neutral")].copy()
    g["home"], g["away"] = g["home_team"].map(normalize_team), g["away_team"].map(normalize_team)
    g["hz"] = [zone(t, s) for t, s in zip(g["home"], g["season"])]
    g["az"] = [zone(t, s) for t, s in zip(g["away"], g["season"])]
    hh = g["gametime"].astype(str).str.slice(0, 2).astype(int) + g["gametime"].astype(str).str.slice(3, 5).astype(int) / 60
    g["night"], g["day"] = hh >= 20.0, hh <= 13.0 + 5 / 60
    return g


def x_for_west(g: pd.DataFrame, west_is_home: np.ndarray) -> np.ndarray:
    """West team's points - east team's points + west team's handicap (spread_line + = home favoured)."""
    margin_home = g["home_score"] - g["away_score"]
    return np.where(west_is_home, margin_home - g["spread_line"], -margin_home + g["spread_line"])


def _summary(x):
    x = np.asarray(x, float)
    nz = x[x != 0]
    t = stats.ttest_1samp(nz, 0, alternative="greater") if len(nz) > 2 else None
    w = stats.wilcoxon(nz, alternative="greater") if len(nz) > 5 else None
    return {"games": int(len(x)), "pushes": int((x == 0).sum()), "west_covers": int((nz > 0).sum()), "east_covers": int((nz < 0).sum()),
            "mean_x": float(nz.mean()) if len(nz) else None, "se_x": float(nz.std(ddof=1) / np.sqrt(len(nz))) if len(nz) > 1 else None,
            "t": float(t.statistic) if t else None, "p_t_one_sided": float(t.pvalue) if t else None,
            "p_wilcoxon_one_sided": float(w.pvalue) if w else None}


def run() -> dict:
    g = frame()
    wc_ec = ((g["hz"] == "P") & (g["az"] == "E")) | ((g["hz"] == "E") & (g["az"] == "P"))
    res = {}
    for name, m in (("night", g["night"]), ("day", g["day"])):
        s = g[wc_ec & m]
        x = x_for_west(s, (s["hz"] == "P").to_numpy())
        res[name] = _summary(x) | {"rows": s.assign(x=x)[["game_id", "season", "gametime", "home", "away", "spread_line", "home_score", "away_score", "x"]]}
    nx = res["night"]["rows"]
    for label, lo, hi in (("night_2012_18", 2012, 2018), ("night_2019_25", 2019, 2025), ("night_2014_25_post_publication", 2014, 2025)):
        res[label] = _summary(nx.loc[nx["season"].between(lo, hi), "x"])
    a, b = res["night"], res["day"]
    tab = np.array([[a["west_covers"], a["east_covers"]], [b["west_covers"], b["east_covers"]]])
    chi = stats.chi2_contingency(tab, correction=False)
    res["night_vs_day_chi2"] = {"chi2": float(chi[0]), "p": float(chi[1])}
    halves_pos = all((res[k]["mean_x"] or 0) > 0 for k in ("night_2012_18", "night_2019_25"))
    res["R_passes"] = bool(a["p_t_one_sided"] is not None and a["p_t_one_sided"] < 0.05 and halves_pos)
    # B1: beyond the champion (2018-25)
    try:
        from .specialists.baseline import load_oof
        from .upsets84 import _logit
        from sklearn.linear_model import LogisticRegression
        o = load_oof()[["game_id", "p_weighted_average"]]
        s = g[wc_ec & g["night"] & g["season"].between(2018, 2025)].merge(o, on="game_id")
        wh = (s["hz"] == "P").to_numpy()
        p_w = np.where(wh, s["p_weighted_average"], 1 - s["p_weighted_average"])
        y = np.where(wh, s["home_score"] > s["away_score"], s["away_score"] > s["home_score"]).astype(float)
        off = _logit(p_w)
        # intercept-only logistic with offset via a tiny Newton solve
        b0 = 0.0
        for _ in range(50):
            pr = 1 / (1 + np.exp(-(off + b0)))
            b0 += np.sum(y - pr) / max(np.sum(pr * (1 - pr)), 1e-9)
        se = 1 / np.sqrt(np.sum(pr * (1 - pr)))
        res["B1_beyond_champion"] = {"games": int(len(s)), "west_won": float(y.mean()), "champion_west_prob": float(p_w.mean()),
                                     "intercept_logit": float(b0), "p_one_sided": float(1 - stats.norm.cdf(b0 / se))}
    except Exception as e:  # noqa: BLE001
        res["B1_beyond_champion"] = {"error": repr(e)}
    # B2: generalised zone gap, all night games between different home zones
    s = g[g["night"]].copy()
    gap = np.array([OFFSET[h] - OFFSET[a] for h, a in zip(s["hz"], s["az"])])        # >0: home is west
    s = s[gap != 0]
    gap = gap[gap != 0]
    west_home = gap > 0
    xs = x_for_west(s, west_home)
    slope = stats.linregress(np.abs(gap), xs)
    res["B2_zone_gap"] = {"games": int(len(xs)), "mean_x_by_gap": {int(k): float(xs[np.abs(gap) == k].mean()) for k in (1, 2, 3)},
                          "n_by_gap": {int(k): int((np.abs(gap) == k).sum()) for k in (1, 2, 3)},
                          "slope": float(slope.slope), "p_one_sided": float(slope.pvalue / 2 if slope.slope > 0 else 1 - slope.pvalue / 2)}
    OUT.mkdir(parents=True, exist_ok=True)
    nx.to_csv(OUT / "night_games.csv", index=False)
    out = {k: ({kk: vv for kk, vv in v.items() if kk != "rows"} if isinstance(v, dict) else v) for k, v in res.items()}
    (OUT / "results.json").write_text(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
