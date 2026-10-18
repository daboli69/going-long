"""Phase 8.5: combined upset angles on new data (AusSportsBetting 2006-25 lines, nflverse 1999-2014 pbp).
Exactly as pre-registered in docs/PHASE8_5_PREREGISTRATION.md. Lab-only. Run: python -m lab.upsets85"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

from .config import ARTIFACTS_DIR, RAW_DIR
from .ingest import normalize_team
from .upsets84 import _logit, _test

OUT = ARTIFACTS_DIR / "phase85"
ASB_FILE = RAW_DIR / "market" / "aussportsbetting_nfl.xlsx"
HIST_DIR = RAW_DIR / "history"
FIRST, LAST = 2006, 2025
CONTINUOUS = {"E1", "E5", "E6", "E7", "E9", "E10", "C2"}
# Amendment A: movement exists only 2014+, so families are split by data need (angles unchanged).
SPEC = {
    "EM": {"angles": ["E1", "E2", "E3", "E4", "E5", "E6"], "disc": (2014, 2018), "conf": (2019, 2024), "movement": True,
           "y": "fav_won", "base": "p_close_fav", "dog_dec": "dog_close_decimal"},
    "ES": {"angles": ["E7", "E8", "E9", "E10", "E11", "E12", "E13"], "disc": (2006, 2015), "conf": (2016, 2025), "movement": False,
           "y": "cfav_won", "base": "cp_close_fav", "dog_dec": "cdog_close_decimal"},
    "C": {"angles": ["C1", "C2", "C3"], "disc": (2018, 2021), "conf": (2022, 2024), "movement": True,
          "y": "fav_won", "base": "p_close_fav", "dog_dec": "dog_close_decimal"},
}
FAMILIES = {k: v["angles"] for k, v in SPEC.items()}
N_PERM = 10_000

NAMES = {
    "arizona cardinals": "ARI", "atlanta falcons": "ATL", "baltimore ravens": "BAL", "buffalo bills": "BUF",
    "carolina panthers": "CAR", "chicago bears": "CHI", "cincinnati bengals": "CIN", "cleveland browns": "CLE",
    "dallas cowboys": "DAL", "denver broncos": "DEN", "detroit lions": "DET", "green bay packers": "GB",
    "houston texans": "HOU", "indianapolis colts": "IND", "jacksonville jaguars": "JAX", "kansas city chiefs": "KC",
    "miami dolphins": "MIA", "minnesota vikings": "MIN", "new england patriots": "NE", "new orleans saints": "NO",
    "new york giants": "NYG", "new york jets": "NYJ", "philadelphia eagles": "PHI", "pittsburgh steelers": "PIT",
    "seattle seahawks": "SEA", "san francisco 49ers": "SF", "tampa bay buccaneers": "TB", "tennessee titans": "TEN",
    "washington redskins": "WAS", "washington football team": "WAS", "washington commanders": "WAS", "washington": "WAS",
    "los angeles rams": "LA", "st. louis rams": "LA", "st louis rams": "LA", "los angeles chargers": "LAC",
    "san diego chargers": "LAC", "oakland raiders": "LV", "las vegas raiders": "LV",
}


def _norm(code) -> str:
    return normalize_team(code)


def _team(name) -> str | None:
    n = str(name).strip().lower()
    if n in NAMES:
        return _norm(NAMES[n])
    try:
        return _norm(name)
    except ValueError:
        return None


def _dec_to_prob(d):
    d = pd.to_numeric(d, errors="coerce")
    return np.where(d > 1, 1 / d, np.nan)


def _col(df, *alts):
    low = {c.lower().strip(): c for c in df.columns}
    for a in alts:
        if a.lower() in low:
            return df[low[a.lower()]]
    return pd.Series(np.nan, index=df.index)


# --------------------------------------------------------------------------- data
def load_asb(path=ASB_FILE) -> pd.DataFrame:
    """AusSportsBetting nfl.xlsx -> one row per game. Home line is the home handicap (negative = home favoured);
    odds are decimal. The header row is located by content, so a leading notes row is tolerated."""
    raw = pd.read_excel(path, header=None)
    hdr = next(i for i in range(min(10, len(raw))) if raw.iloc[i].astype(str).str.lower().str.contains("home team").any())
    df = pd.read_excel(path, header=hdr)
    out = pd.DataFrame({
        "date": pd.to_datetime(_col(df, "Date"), errors="coerce").dt.normalize(),
        "home": _col(df, "Home Team").map(_team), "away": _col(df, "Away Team").map(_team),
        "asb_home_line_open": pd.to_numeric(_col(df, "Home Line Open"), errors="coerce"),
        "asb_home_line_close": pd.to_numeric(_col(df, "Home Line Close", "Home Line"), errors="coerce"),
        "asb_home_odds_open": pd.to_numeric(_col(df, "Home Odds Open"), errors="coerce"),
        "asb_away_odds_open": pd.to_numeric(_col(df, "Away Odds Open"), errors="coerce"),
        "asb_home_odds_close": pd.to_numeric(_col(df, "Home Odds Close", "Home Odds"), errors="coerce"),
        "asb_away_odds_close": pd.to_numeric(_col(df, "Away Odds Close", "Away Odds"), errors="coerce"),
        "asb_total_open": pd.to_numeric(_col(df, "Total Score Open"), errors="coerce"),
        "asb_total_close": pd.to_numeric(_col(df, "Total Score Close", "Total Score"), errors="coerce"),
    })
    return out.dropna(subset=["date", "home", "away"])


def match_asb(asb: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Join ASB rows to games.csv by teams and date (+/- 1 day for time zones)."""
    g = games.copy()
    g["date"] = pd.to_datetime(g["gameday"]).dt.normalize()
    g["home_n"], g["away_n"] = g["home_team"].map(_norm), g["away_team"].map(_norm)
    rows = []
    for shift in (0, 1, -1):
        a = asb.assign(date=asb["date"] + pd.Timedelta(days=shift))
        rows.append(g.merge(a, left_on=["date", "home_n", "away_n"], right_on=["date", "home", "away"], how="inner"))
    m = pd.concat(rows).drop_duplicates("game_id")
    return m.drop(columns=["home", "away"])


def provenance(asb_path=ASB_FILE) -> dict:
    p = {"asb_file": str(asb_path.name), "asb_exists": asb_path.exists()}
    if asb_path.exists():
        b = asb_path.read_bytes()
        p |= {"asb_sha256": hashlib.sha256(b).hexdigest(), "asb_bytes": len(b),
              "asb_modified": pd.Timestamp(asb_path.stat().st_mtime, unit="s", tz="UTC").isoformat(),
              "asb_source": "https://www.aussportsbetting.com/data/historical-nfl-results-and-odds-data/ (manual browser download by Travis)",
              "timestamp_class": "T2 opening (time unrecorded) / T3 closing"}
    sums = HIST_DIR / "SHA256SUMS.txt"
    p["history_pbp_sha256"] = sums.read_text().splitlines() if sums.exists() else []
    p["history_pbp_source"] = "https://github.com/nflverse/nflverse-data/releases/tag/pbp"
    return p


def data_checks(m: pd.DataFrame, games: pd.DataFrame) -> dict:
    """Outcome-free: opening coverage by season and agreement of ASB openers with SBR openers (2016-21)."""
    cov = {}
    both = m["asb_home_line_open"].notna() & m["asb_home_line_close"].notna() & m["asb_home_odds_close"].notna()
    for s in range(FIRST, LAST + 1):
        n = int(((games["season"] == s) & games["home_score"].notna()).sum())
        k = int((both & (m["season"] == s)).sum())
        cov[s] = {"games": n, "with_open_and_close": k, "coverage": k / n if n else 0.0}
    seasons_ok = [s for s, c in cov.items() if c["coverage"] >= 0.90]          # movement seasons (Amendment A)
    sbr_path = RAW_DIR / "market" / "sbr_lines.parquet"
    agree = None
    if sbr_path.exists():
        sb = pd.read_parquet(sbr_path)[["game_id", "sbr_home_spread_open"]]
        j = m.merge(sb, on="game_id").dropna(subset=["asb_home_line_open", "sbr_home_spread_open"])
        if len(j):
            d = (j["sbr_home_spread_open"] - (-j["asb_home_line_open"])).abs()   # SBR + = home favoured; ASB - = home favoured
            agree = {"games": int(len(j)), "median_abs_diff": float(d.median()), "share_within_1": float((d <= 1).mean())}
    return {"coverage": cov, "seasons_ok": seasons_ok, "sbr_agreement": agree,
            "family_e_allowed": bool(agree is None or agree["median_abs_diff"] <= 1.0)}


def _pbp(season: int) -> pd.DataFrame:
    f = (HIST_DIR if season <= 2014 else RAW_DIR) / f"play_by_play_{season}.parquet"
    cols = ["game_id", "game_date", "posteam", "defteam", "epa", "play_type", "qb_kneel", "qb_spike", "season_type"]
    p = pd.read_parquet(f, columns=cols)
    p = p[p["play_type"].isin(["run", "pass"]) & p["epa"].notna() & (p["qb_kneel"] != 1) & (p["qb_spike"] != 1)]
    return p


def team_ratings(seasons) -> pd.DataFrame:
    """As-of R (season-to-date net EPA/play blended with last season, k=4) and last-3 form, per (game_id, team).
    Every value uses only games strictly before the target game."""
    out, prev_final = [], {}
    for s in seasons:
        p = _pbp(s)
        off = p.groupby(["game_id", "game_date", "posteam"])["epa"].mean().rename("off").reset_index().rename(columns={"posteam": "team"})
        de = p.groupby(["game_id", "defteam"])["epa"].mean().rename("def").reset_index().rename(columns={"defteam": "team"})
        tg = off.merge(de, on=["game_id", "team"])
        tg["team"] = tg["team"].map(_norm)
        tg["net"] = tg["off"] - tg["def"]
        tg = tg.sort_values("game_date")
        final = {}
        for t, d in tg.groupby("team"):
            net = d["net"].to_numpy()
            prev = prev_final.get(t, 0.0)
            for i, gid in enumerate(d["game_id"]):
                n = i
                cur = net[:i].mean() if i else 0.0
                r = (n * cur + 4 * prev) / (n + 4)
                form = (net[max(0, i - 3):i].mean() - cur) if i >= 3 else 0.0
                out.append({"game_id": gid, "team": t, "season": s, "R": r, "form": form})
            final[t] = net.mean()
        prev_final = final
    return pd.DataFrame(out)


def frame(asb: pd.DataFrame | None = None) -> pd.DataFrame:
    """All 2006-2025 completed, untied games. Two orientations:
    opening favourite (ASB, movement families EM/C) and closing favourite (nflverse, static family ES)."""
    from .market81 import american_to_prob, novig
    games = pd.read_csv(RAW_DIR / "games.csv")
    games = games[games["season"].between(FIRST, LAST) & games["home_score"].notna() & (games["home_score"] != games["away_score"])]
    asb = load_asb() if asb is None else asb
    m = games.merge(match_asb(asb, games)[["game_id"] + [c for c in asb.columns if c.startswith("asb_")]], on="game_id", how="left")
    hw = (m["home_score"] > m["away_score"]).to_numpy()
    # p_close (all families): nflverse closing no-vig moneyline, fallback Phi(closing spread / 13.5); spread_line + = home favoured
    hml, aml = pd.to_numeric(m["home_moneyline"], errors="coerce"), pd.to_numeric(m["away_moneyline"], errors="coerce")
    with np.errstate(invalid="ignore"):
        pc_home = np.asarray(novig(american_to_prob(hml), american_to_prob(aml)), float)
    sl = pd.to_numeric(m["spread_line"], errors="coerce").to_numpy(float)
    pc_home = np.where(np.isnan(pc_home), stats.norm.cdf(sl / 13.5), pc_home)

    def dec(ml):
        ml = pd.to_numeric(ml, errors="coerce")
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(ml > 0, 1 + ml / 100, np.where(ml < 0, 1 + 100 / -ml, np.nan))

    # ---- closing-favourite orientation (ES)
    ch = sl > 0
    m["cfav_ok"] = ~np.isnan(sl) & (sl != 0)
    m["cfav_won"] = np.where(ch, hw, ~hw).astype(float)
    m["cp_close_fav"] = np.where(ch, pc_home, 1 - pc_home)
    m["cdog_close_decimal"] = np.where(ch, dec(m["away_moneyline"]), dec(m["home_moneyline"]))
    r = team_ratings(range(FIRST - 1, LAST + 1)).set_index(["game_id", "team"])
    ht, at = m["home_team"].map(_norm), m["away_team"].map(_norm)
    hk = pd.MultiIndex.from_arrays([m["game_id"], ht])
    ak = pd.MultiIndex.from_arrays([m["game_id"], at])
    hR, aR = r["R"].reindex(hk).to_numpy(), r["R"].reindex(ak).to_numpy()
    hF, aF = r["form"].reindex(hk).to_numpy(), r["form"].reindex(ak).to_numpy()
    m["E7"] = np.where(ch, m["away_rest"] - m["home_rest"], m["home_rest"] - m["away_rest"])
    tl = pd.to_numeric(m["total_line"], errors="coerce")
    m["E8"] = np.where(tl.isna(), np.nan, (tl <= 41).astype(float))
    m["E9"] = np.where(ch, aR - hR, hR - aR)
    m["E10"] = np.where(ch, aF - hF, hF - aF)
    m["E11"] = m["div_game"].astype(float)
    m["E12"] = (~ch).astype(float)
    m["E13"] = (pd.to_numeric(m["wind"], errors="coerce").fillna(0) >= 15).astype(float)
    for c in ("E7", "E8", "E9", "E10", "E11", "E12", "E13"):
        m.loc[~m["cfav_ok"], c] = np.nan
    # ---- opening-favourite orientation (EM, C, R1): needs ASB open and close
    lo, lc = m["asb_home_line_open"], m["asb_home_line_close"]
    mv_ok = (lo.notna() & lc.notna() & (lo != 0)).to_numpy()
    fh = (lo < 0).to_numpy()                                   # ASB home line negative = home favoured
    m["mv_ok"] = mv_ok
    m["fav_home"] = fh
    m["fav_open"] = lo.abs()
    m["fav_close"] = np.where(fh, -lc, lc)
    m["m"] = m["fav_open"] - m["fav_close"]
    m["fav_won"] = np.where(fh, hw, ~hw).astype(float)
    m["p_close_fav"] = np.where(fh, pc_home, 1 - pc_home)
    ho, ao = _dec_to_prob(m["asb_home_odds_open"]), _dec_to_prob(m["asb_away_odds_open"])
    hc, ac = _dec_to_prob(m["asb_home_odds_close"]), _dec_to_prob(m["asb_away_odds_close"])
    po, pca = ho / (ho + ao), hc / (hc + ac)
    p_open_fav, p_close_asb = np.where(fh, po, 1 - po), np.where(fh, pca, 1 - pca)
    m["dog_close_decimal"] = np.where(fh, m["asb_away_odds_close"], m["asb_home_odds_close"])
    m["E1"] = m["m"]
    m["E2"] = (((m["fav_open"] > 3) & (m["fav_close"] <= 3)) | ((m["fav_open"] > 7) & (m["fav_close"] <= 7))).astype(float)
    m["E3"] = np.where(np.isnan(p_open_fav) | np.isnan(p_close_asb), np.nan, ((m["m"] >= 1) & (p_close_asb > p_open_fav)).astype(float))
    m["E4"] = np.where(m["asb_total_open"].isna() | m["asb_total_close"].isna(), np.nan,
                       ((m["asb_total_open"] - m["asb_total_close"]) >= 1.5).astype(float))
    m["E5"] = m["m"] * (m["fav_open"] >= 7)
    m["E6"] = m["m"] * (m["week"] <= 4)
    from .specialists.baseline import load_oof
    m = m.merge(load_oof()[["game_id", "p_weighted_average"]], on="game_id", how="left")
    pch = np.where(m["fav_home"], m["p_weighted_average"], 1 - m["p_weighted_average"])
    m["p_champ_fav"] = pch
    m["C1"] = np.where(np.isnan(pch), np.nan, (pch < 0.5).astype(float))
    m["C2"] = np.where(np.isnan(pch), np.nan, -(_logit(pch) - _logit(m["p_close_fav"])))   # larger = champion more bearish
    m["C3"] = m["m"] * m["C1"]
    for c in ("E1", "E2", "E3", "E4", "E5", "E6", "C1", "C2", "C3", "p_champ_fav"):
        m.loc[~m["mv_ok"], c] = np.nan
    return m


# --------------------------------------------------------------------------- tests
def _prep(d: pd.DataFrame, a: str, scale: dict, base: str):
    d = d.dropna(subset=[a, base])
    z = d[a].to_numpy(float)
    if a in CONTINUOUS:
        z = (z - scale[a][0]) / scale[a][1]
    return d, z


def _perm_p(y, base, z, seasons, obs_coef, n_perm, rng):
    """Within-season shuffle of the angle; one-sided share of permuted coefficients <= observed."""
    X = np.c_[base, z]
    hits = 0
    for _ in range(n_perm):
        zp = z.copy()
        for s in np.unique(seasons):
            k = np.where(seasons == s)[0]
            zp[k] = z[rng.permutation(k)]
        X[:, 1] = zp
        c = LogisticRegression(C=1e6, max_iter=500).fit(X, y).coef_[0][1]
        hits += c <= obs_coef
    return (hits + 1) / (n_perm + 1)


def _holm(p: dict) -> dict:
    o = sorted(p, key=p.get)
    out, run = {}, 0.0
    for i, k in enumerate(o):
        run = max(run, min(1.0, (len(o) - i) * p[k]))
        out[k] = run
    return out


def _rows(df, fam, seasons, seasons_ok):
    sp = SPEC[fam]
    k = df["season"].between(*seasons)
    if sp["movement"]:
        k &= df["season"].isin(seasons_ok)
    return df[k]


def discover(df: pd.DataFrame, seasons_ok: list, family_e_allowed: bool) -> dict:
    res, scale = {}, {}
    for fam, sp in SPEC.items():
        if fam == "EM" and not family_e_allowed:
            res[fam] = {"skipped": "ASB opening lines failed the SBR agreement check"}
            continue
        sub = _rows(df, fam, sp["disc"], seasons_ok)
        res[fam] = {}
        for a in sp["angles"]:
            d = sub.dropna(subset=[a, sp["base"]])
            if a in CONTINUOUS and len(d):
                scale[a] = (float(d[a].mean()), float(d[a].std()) or 1.0)
            if len(d) < 100 or d[a].nunique() < 2:
                res[fam][a] = {"games": int(len(d)), "status": "insufficient data", "carried": False}
                continue
            d, z = _prep(d, a, scale, sp["base"])
            t = _test(d[sp["y"]].to_numpy(), _logit(d[sp["base"]]), z, d["season"].to_numpy())
            t["flagged"] = int((d[a] > 0).sum()) if a not in CONTINUOUS else None
            t["carried"] = bool(t["p_one_sided"] < 0.10 and t["coef_per_sd"] < 0)
            res[fam][a] = t
    carried = {fam: [a for a, t in r.items() if t.get("carried")] for fam, r in res.items() if "skipped" not in r}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "carried.json").write_text(json.dumps({"written_at": pd.Timestamp.now(tz="UTC").isoformat(), "carried": carried,
                                                  "scale": scale}, indent=2))
    (OUT / "discovery.json").write_text(json.dumps(res, indent=2, default=str))
    return {"results": res, "carried": carried, "scale": scale}


def confirm(df: pd.DataFrame, seasons_ok: list, n_perm: int = N_PERM, log=print) -> dict:
    """Scores ONLY the angles frozen in carried.json; refuses to run without it."""
    c = json.loads((OUT / "carried.json").read_text())
    carried, scale = c["carried"], {k: tuple(v) for k, v in c["scale"].items()}
    rng = np.random.default_rng(85)
    res = {}
    for fam, angles in carried.items():
        sp = SPEC[fam]
        sub = _rows(df, fam, sp["conf"], seasons_ok)
        res[fam] = {}
        for a in angles:
            d, z = _prep(sub, a, scale, sp["base"])
            y, base, seas = d[sp["y"]].to_numpy(), _logit(d[sp["base"]]), d["season"].to_numpy()
            t = _test(y, base, z, seas)
            log(f"confirm {a}: {len(d)} games, permutation test ({n_perm})")
            t["perm_p"] = _perm_p(y, base, z, seas, t["coef_per_sd"], n_perm, rng) if n_perm else None
            flag = (d[a] > 0).to_numpy() if a not in CONTINUOUS else (z >= 1)
            dec = d.loc[flag, sp["dog_dec"]].to_numpy(float)
            won = 1 - y[flag]
            ok = ~np.isnan(dec)
            t["dog_bets"] = int(ok.sum())
            t["dog_flat_roi_at_close"] = float(np.mean(won[ok] * (dec[ok] - 1) - (1 - won[ok]))) if ok.any() else None
            t["dog_win_rate_flagged"] = float(won.mean()) if len(won) else None
            t["implied_by_close_flagged"] = float(1 - d.loc[flag, sp["base"]].mean()) if flag.any() else None
            res[fam][a] = t
        h = _holm({a: t["p_one_sided"] for a, t in res[fam].items()}) if res[fam] else {}
        for a, t in res[fam].items():
            t["holm"] = h[a]
            t["passes"] = bool(h[a] < 0.05 and t["coef_per_sd"] < 0 and t["seasons_with_predeclared_sign"] >= math.ceil(t["seasons"] / 2))
    (OUT / "confirmation.json").write_text(json.dumps(res, indent=2, default=str))
    return res


def replicate_s2(df: pd.DataFrame, seasons_ok: list) -> dict:
    """R1: Phase 8.4 S2 on ASB movement 2022-24 (2025 fails coverage), champion as base, frozen 2018-21 scale."""
    r84 = json.loads((ARTIFACTS_DIR / "phase84" / "results.json").read_text())["m_scale_2018_21"]
    d = df[df["season"].between(2022, 2024) & df["season"].isin(seasons_ok)].dropna(subset=["p_champ_fav", "m"])
    z = ((d["m"] - r84["mean"]) / r84["sd"]).to_numpy()
    t = _test(d["fav_won"].to_numpy(), _logit(d["p_champ_fav"]), z, d["season"].to_numpy())
    t["passes"] = bool(t["p_one_sided"] < 0.05 and t["coef_per_sd"] < 0)
    flag = d[d["m"] >= 1.5]
    t["flag_1p5"] = {"games": int(len(flag)), "dog_win_rate": float(1 - flag["fav_won"].mean()) if len(flag) else None,
                     "implied_by_champion": float(1 - flag["p_champ_fav"].mean()) if len(flag) else None,
                     "implied_by_close": float(1 - flag["p_close_fav"].mean()) if len(flag) else None}
    return t


def robustness_s2(n_boot: int = 2000) -> dict:
    """Descriptive: Phase 8.4 S2 (SBR 2018-21) bootstrap CI and breakdowns."""
    from .upsets84 import movement_frame
    mv = movement_frame()
    s2 = mv[mv["season"].between(2018, 2021)].dropna(subset=["p_champ_fav"]).reset_index(drop=True)
    mu, sd = s2["m"].mean(), s2["m"].std()
    rng = np.random.default_rng(84)

    def coef(d):
        X = np.c_[_logit(d["p_champ_fav"]), (d["m"] - mu) / sd]
        return float(LogisticRegression(C=1e6, max_iter=1000).fit(X, d["fav_won"]).coef_[0][1]) if d["fav_won"].nunique() > 1 else np.nan

    boots = [coef(s2.iloc[rng.integers(0, len(s2), len(s2))]) for _ in range(n_boot)]
    key = (((s2["fav_open"] > 3) & (s2["fav_close"] <= 3)) | ((s2["fav_open"] > 7) & (s2["fav_close"] <= 7)) |
           ((s2["fav_open"] <= 3) & (s2["fav_close"] > 3)) | ((s2["fav_open"] <= 7) & (s2["fav_close"] > 7)))
    groups = {
        "all": s2,
        "fav_open_lt3": s2[s2["fav_open"] < 3], "fav_open_3_6.5": s2[s2["fav_open"].between(3, 6.5)], "fav_open_ge7": s2[s2["fav_open"] >= 7],
        "no_key_number_cross": s2[~key], "key_number_cross": s2[key],
    }
    gs = pd.read_csv(RAW_DIR / "games.csv")[["game_id", "week"]]
    s2w = s2.merge(gs, on="game_id", how="left")
    groups |= {"weeks_1_4": s2w[s2w["week"] <= 4], "weeks_5_12": s2w[s2w["week"].between(5, 12)], "weeks_13plus": s2w[s2w["week"] >= 13]}
    groups |= {f"season_{s}": s2[s2["season"] == s] for s in range(2018, 2022)}
    return {"bootstrap_coef_ci95": [float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5))],
            "share_boot_negative": float(np.nanmean(np.array(boots) < 0)),
            "by_group": {k: {"games": int(len(d)), "coef_per_sd": coef(d) if len(d) >= 60 else None} for k, d in groups.items()}}


def run(n_perm: int = N_PERM, log=print) -> dict:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    status = OUT / "status.json"

    def st(msg, **kw):
        log(msg)
        status.write_text(json.dumps({"at": pd.Timestamp.now(tz="UTC").isoformat(), "stage": msg, "elapsed_s": round(time.time() - t0)} | kw, indent=2))

    st("provenance")
    prov = provenance()
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2))
    if not prov["asb_exists"]:
        st("stopped: AusSportsBetting file missing", done=True)
        return {"error": "missing ASB file"}
    st("data checks")
    games = pd.read_csv(RAW_DIR / "games.csv")
    asb = load_asb()
    g = games[games["season"].between(FIRST, LAST)]
    checks = data_checks(match_asb(asb, g), g)
    (OUT / "data_checks.json").write_text(json.dumps(checks, indent=2, default=str))
    st("building frame and ratings")
    df = frame(asb)
    st("discovery")
    disc = discover(df, checks["seasons_ok"], checks["family_e_allowed"])
    st("confirmation (permutation tests)")
    conf = confirm(df, checks["seasons_ok"], n_perm, log)
    st("replication R1")
    r1 = replicate_s2(df, checks["seasons_ok"])
    st("robustness S2")
    rob = robustness_s2()
    res = {"data_checks": {k: v for k, v in checks.items() if k != "coverage"}, "carried": disc["carried"],
           "confirmation": conf, "R1": r1, "robustness_s2": rob, "elapsed_s": round(time.time() - t0)}
    (OUT / "results.json").write_text(json.dumps(res, indent=2, default=str))
    st("done", done=True)
    return res


def load() -> dict:
    out = {}
    for k in ("results", "discovery", "carried", "data_checks", "status", "provenance"):
        p = OUT / f"{k}.json"
        if p.exists():
            out[k] = json.loads(p.read_text())
    return out


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_PERM
    with open(OUT.parent / "phase85_run.log", "a", encoding="utf-8") as fh:
        def log(m):
            fh.write(f"{pd.Timestamp.now(tz='UTC').isoformat()} {m}\n")
            fh.flush()
        try:
            run(n, log)
        except Exception as e:  # recorded for the morning check
            import traceback
            log("ERROR " + traceback.format_exc())
            (OUT / "status.json").write_text(json.dumps({"stage": "error", "error": repr(e), "done": True}))
            raise
