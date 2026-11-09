"""Coverage matchup for one game: each side's expected quarterback against the opposing defense.

Descriptive history only; nothing here is a forecast, a fitted model or a pick, and nothing feeds the simulation.

Sources, all local files:
- FantasyPoints (FPDS) coverage matrix: how often a defense plays man, zone, each shell, one-high and two-high looks, press and blitz.
  2026 weeks before the game's week, with last season counting as K_WEEKS weeks of prior (the same rule the lab uses for this table).
- FPDS fantasy points allowed by position: targets, yards, yards per target and fantasy points per game, same blend.
- FPDS receiving separation by coverage: each receiver's yards per route against man and against zone, 2025 and 2026 before the game's week.
- nflverse play-by-play and participation (lab.covcard): the quarterback's targets and EPA by coverage and position (2022 to 2025 tags),
  and each defense's explosive-play rate and EPA per target by position.
Row-level FPDS values stay on this computer; this module returns derived rates only.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import covcard as cc
from . import fpds_usage as X
from .config import RAW_DIR
from .ingest import normalize_team

K_WEEKS = 6.0          # weeks of last-season prior behind a defense's blended rate
SHRINK_ROUTES = 30.0   # routes a receiver needs against one coverage before his split counts as much as his overall number
MIN_ROUTES = 60
POS = cc.POS
OUT_STATUSES = {"Out", "Doubtful", "Injured Reserve", "IR", "Suspended"}
MIX_ROWS = [("c0", "coverages__cover_0_pct", "Cover 0"), ("c1", "coverages__cover_1_pct", "Cover 1"), ("c2", "coverages__cover_2_pct", "Cover 2"),
            ("c2m", "coverages__cover_2_man_pct", "2-man"), ("c3", "coverages__cover_3_pct", "Cover 3"), ("c4", "coverages__cover_4_pct", "Cover 4"),
            ("c6", "coverages__cover_6_pct", "Cover 6")]
LOOK_ROWS = [("hi1", "middle_of_field_look_closed_open__1_hi_mof_c_pct", "One-high look"),
             ("hi2", "middle_of_field_look_closed_open__2_hi_mof_o_pct", "Two-high look"),
             ("man", "man_zone__man_pct", "Man"), ("zone", "man_zone__zone_pct", "Zone"),
             ("press", "personnel_press__press_pct_any", "Press"), ("blitz", "blitz__blitz_pct", "Blitz")]
CCOV_FROM = {"COVER_1": ["c1"], "COVER_2": ["c2"], "COVER_3": ["c3"], "COVER_4": ["c4"], "OTHER": ["c0", "c2m", "c6"]}
_cache: dict = {}


def _table(name: str) -> pd.DataFrame:
    if name not in _cache:
        d = X._a6_dir()
        if d is None:
            raise FileNotFoundError("the FantasyPoints import")
        t = pd.read_parquet(d / f"{name}__working_usable.parquet")
        t["team"] = t["team"].map(lambda s: normalize_team(s) if isinstance(s, str) else s)
        t["season"], t["week"] = t["season"].astype(int), t["week"].astype(int)
        _cache[name] = t
    return _cache[name]


def _num(s) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _blend(cur_sum: float, cur_n: float, prior_mean: float | None) -> float | None:
    if prior_mean is None or np.isnan(prior_mean):
        return cur_sum / cur_n if cur_n else None
    return (cur_sum + K_WEEKS * prior_mean) / (cur_n + K_WEEKS)


def _rates(frame: pd.DataFrame, cols: dict[str, str], season: int, week: int) -> pd.DataFrame:
    """Per team: blended mean of each column (percent / 100) from this season's weeks before `week` and last season as a prior."""
    rows = {}
    for team, g in frame.groupby("team"):
        cur = g[(g["season"] == season) & (g["week"] < week)]
        pri = g[g["season"] == season - 1]
        r = {"weeks": int(cur["week"].nunique()), "prior_weeks": int(pri["week"].nunique())}
        for k, c in cols.items():
            cv, pv = _num(cur[c]).dropna(), _num(pri[c]).dropna()
            r[k] = _blend(float(cv.sum()), len(cv), float(pv.mean()) if len(pv) else None)
            if r[k] is not None:
                r[k] /= 100.0
        rows[team] = r
    return pd.DataFrame.from_dict(rows, orient="index")


def defense_mix(season: int, week: int) -> pd.DataFrame:
    cols = {k: c for k, c, _ in MIX_ROWS + LOOK_ROWS}
    return _rates(_table("coverage_matrix"), cols, season, week)


def _fpa(pos: str, season: int, week: int) -> pd.DataFrame:
    t = _table(f"fantasy_points_allowed_{pos.lower()}")
    out = {}
    for team, g in t.groupby("team"):
        cur = g[(g["season"] == season) & (g["week"] < week)]
        pri = g[g["season"] == season - 1]

        def blend(c):
            cv, pv = _num(cur[c]).dropna(), _num(pri[c]).dropna()
            return _blend(float(cv.sum()), len(cv), float(pv.mean()) if len(pv) else None)
        tgt, yds, fp = blend("receiving__tgt"), blend("receiving__yds"), blend("fp__fp")
        out[team] = {"tgt_pg": tgt, "yds_pg": yds, "fp_pg": fp, "ypt": (yds / tgt) if tgt else None, "games": int(cur["week"].nunique())}
    return pd.DataFrame.from_dict(out, orient="index")


def _starter(team: str, season: int, week: int) -> tuple[str | None, str | None, str | None]:
    """(gsis id, name, note): the quarterback with the most dropbacks in the team's latest game, unless the latest injury report has him out."""
    snaps = sorted((RAW_DIR / "archive").glob("nflverse_injuries_*.parquet"))
    out_ids = set()
    if snaps:
        inj = pd.read_parquet(snaps[-1])
        q = inj[(inj["season"] == season) & (inj["week"] == week) & (inj["team"] == team) & (inj["position"] == "QB")]
        out_ids = set(q.loc[q["report_status"].isin(OUT_STATUSES), "gsis_id"])
    cols = ["posteam", "week", "passer_id", "passer", "pass_attempt"]
    p = pd.read_parquet(RAW_DIR / f"play_by_play_{season}.parquet", columns=cols)
    p = p[(p["pass_attempt"] == 1) & (p["posteam"] == team) & p["passer_id"].notna() & (p["week"] < week)]
    if p.empty:
        return None, None, "No earlier game this season to pick a starter from."
    last = p[p["week"] == p["week"].max()]
    ranked = list(last["passer_id"].value_counts().index) + [i for i in p["passer_id"].value_counts().index if i not in set(last["passer_id"])]
    note = None
    for i, qid in enumerate(ranked):
        if qid in out_ids:
            continue
        if i > 0 and ranked[0] in out_ids:
            note = f"{p.loc[p['passer_id'] == ranked[0], 'passer'].iloc[0]} is out on the latest injury report. This is the next quarterback by passes."
        nm = p.loc[p["passer_id"] == qid, "passer"].iloc[0]
        return qid, nm, note
    return None, None, "Every quarterback on this team is out on the latest injury report."


def _display_name(qid: str, fallback: str) -> str:
    pl = pd.read_parquet(RAW_DIR / "players.parquet").drop_duplicates("gsis_id").set_index("gsis_id")
    return str(pl["display_name"].get(qid, fallback))


def _receivers(team: str, season: int, week: int, man_rate: float | None) -> list[dict]:
    t = _table("receiving_separation_by_coverage")
    t = t[(((t["season"] == season) & (t["week"] < week)) | (t["season"] == season - 1))].copy()
    for c in ("overall__rte", "overall__yprr", "man__rte", "man__yprr", "zone__rte", "zone__yprr", "overall__tgt"):
        t[c] = _num(t[c]).fillna(0.0)
    cur_team = t[(t["season"] == season) & (t["team"] == team)]["pid"].unique()
    rows = []
    for pid in cur_team:
        g = t[t["pid"] == pid]
        rte = float(g["overall__rte"].sum())
        if rte < MIN_ROUTES:
            continue
        yds = float((g["overall__yprr"] * g["overall__rte"]).sum())
        base = yds / rte
        r = {"name": str(g.sort_values(["season", "week"])["player_details__name"].iloc[-1]),
             "pos": str(g.sort_values(["season", "week"])["position_asof"].iloc[-1]), "routes": int(round(rte)), "yprr": round(base, 2)}
        for k in ("man", "zone"):
            rk = float(g[f"{k}__rte"].sum())
            yk = float((g[f"{k}__yprr"] * g[f"{k}__rte"]).sum())
            r[f"{k}_routes"] = int(round(rk))
            r[f"{k}_yprr_raw"] = round(yk / rk, 2) if rk else None
            r[f"{k}_yprr"] = round((yk + SHRINK_ROUTES * base) / (rk + SHRINK_ROUTES), 2)
        r["tgt"] = int(g["overall__tgt"].sum())
        rows.append(r)
    rows = [r for r in rows if r["pos"] in POS]
    rows.sort(key=lambda r: -r["routes"])
    rows = rows[:8]
    for r in rows:
        d = r["man_yprr"] - r["zone_yprr"]
        r["man_minus_zone"] = round(d, 2)
        if man_rate is not None:
            r["edge"] = round(man_rate * r["man_yprr"] + (1 - man_rate) * r["zone_yprr"] - r["yprr"], 2)
    return rows


def _read(share_diff_pts: float, ypt_diff: float, expl_diff: float | None, n: int) -> str:
    """Volume is the position's share of the targets the defense faces (not targets per game, which follows how many passes it sees)."""
    hv, lv = share_diff_pts >= 2.0, share_diff_pts <= -2.0
    ex = expl_diff is not None and expl_diff >= 1.0
    hy = ypt_diff >= 0.5 or ex
    ly = ypt_diff <= -0.5 and (expl_diff is None or expl_diff <= 0.5)
    t = "Near league average on volume and yards."
    if hv and ly:
        t = "Lots of targets, few yards. Throws get caught short."
    elif hv and hy:
        t = "Targeted a lot and hurt on those throws."
    elif lv and ex:
        t = "Few targets, but chunk plays when they come."
    elif lv and ly:
        t = "Rarely targeted, and quiet when tested."
    elif lv:
        t = "Rarely targeted."
    elif hv:
        t = "Targeted more than usual, yards about average."
    elif ex:
        t = "Average volume, but gives up chunk plays."
    elif ly:
        t = "Average volume, holds yards down."
    return t + (" Small sample." if n < 100 else "")


def _qb_share(q: dict, c: str, lg: dict) -> dict:
    g = q["cov"][c]
    t = sum(g["tgt"][p] for p in POS)
    return {p: (g["tgt"][p] + cc.K_QB_SHARE * lg[c]["share"][p]) / (t + cc.K_QB_SHARE) for p in POS}


def _qb_epa(q: dict, c: str, lg: dict) -> float:
    g = q["cov"][c]
    return (g["att"] * (g["epa"] or 0.0) + cc.K_QB_EPA * lg[c]["epa"]) / (g["att"] + cc.K_QB_EPA)


def _side(qb_team: str, def_team: str, season: int, week: int, data: dict, mix: pd.DataFrame, fpa: dict, qb_id: str | None = None) -> dict:
    if qb_id:  # retrospective: the quarterback who actually played
        qid, qname, note = qb_id, qb_id, None
    else:
        qid, qname, note = _starter(qb_team, season, week)
    q = data["qbs"].get(qid) if qid else None
    lg = {}
    for c in cc.COVS:
        g = data["league"]["cov"][c]
        t = sum(g["tgt"][p] for p in POS)
        lg[c] = {"share": {p: g["tgt"][p] / t for p in POS}, "epa": g["epa"]}
    dm = mix.loc[def_team]
    lgm = mix.mean(numeric_only=True)
    out = {"qb_team": qb_team, "defense": def_team, "note": note}
    out["defense_mix"] = {
        "weeks": int(dm["weeks"]), "prior_weeks": int(dm["prior_weeks"]),
        "shells": [{"key": k, "label": lab, "pct": round(float(dm[k]), 4), "league": round(float(lgm[k]), 4)} for k, _, lab in MIX_ROWS],
        "looks": [{"key": k, "label": lab, "pct": round(float(dm[k]), 4), "league": round(float(lgm[k]), 4)} for k, _, lab in LOOK_ROWS]}
    # defense coverage weights in the nflverse groups, normalised to 1
    w = {c: sum(float(dm[k]) for k in ks) for c, ks in CCOV_FROM.items()}
    tot = sum(w.values()) or 1.0
    w = {c: v / tot for c, v in w.items()}
    # positions: FPDS volume and yards, nflverse explosive rate and EPA
    d_nfl = data["defs"][def_team]
    Lp = data["def_league"]["pos"]
    T = d_nfl["tgt_known"]
    positions = []
    raw_share = {p: (d_nfl["pos"][p]["tgt"] + cc.K_DEF_POS * Lp[p]["share"]) / (T + cc.K_DEF_POS) for p in POS}
    norm = sum(raw_share.values())
    share = {p: v / norm for p, v in raw_share.items()}
    for p in POS:
        f = fpa[p].loc[def_team]
        lgf = fpa[p].mean(numeric_only=True)
        x = d_nfl["pos"][p]
        K = cc.K_DEF_POS
        expl = (x["expl"] + K * Lp[p]["expl"]) / (x["tgt"] + K)
        epa = (x["epa"] + K * Lp[p]["epa"]) / (x["tgt"] + K)
        share_diff = (share[p] - Lp[p]["share"]) * 100.0
        ypt_diff = f["ypt"] - lgf["ypt"]
        expl_diff = (expl - Lp[p]["expl"]) * 100.0
        rank_t = int((fpa[p]["tgt_pg"] > f["tgt_pg"]).sum()) + 1
        rank_fp = int((fpa[p]["fp_pg"] > f["fp_pg"]).sum()) + 1
        positions.append({"pos": p, "tgt_pg": round(float(f["tgt_pg"]), 1), "tgt_pg_league": round(float(lgf["tgt_pg"]), 1), "tgt_rank": rank_t,
                          "ypt": round(float(f["ypt"]), 2), "ypt_league": round(float(lgf["ypt"]), 2),
                          "fp_pg": round(float(f["fp_pg"]), 1), "fp_rank": rank_fp,
                          "expl": round(float(expl), 4), "expl_league": round(float(Lp[p]["expl"]), 4),
                          "epa": round(float(epa), 3), "epa_league": round(float(Lp[p]["epa"]), 3), "nfl_targets": int(x["tgt"]),
                          "share": round(share[p], 4), "share_league": round(Lp[p]["share"], 4),
                          "read": _read(share_diff, ypt_diff, expl_diff, int(x["tgt"]))})
    out["positions"] = positions
    out["allowed_share"] = {p: round(v, 4) for p, v in share.items()}
    out["receivers"] = _receivers(qb_team, season, week, float(dm["man"]) if dm.get("man") is not None else None)
    if q is None:
        out["qb"] = {"id": qid, "name": qname, "missing": True}
        return out
    shares = {c: _qb_share(q, c, lg) for c in cc.COVS}
    epas = {c: _qb_epa(q, c, lg) for c in cc.COVS}
    base_t = sum(sum(q["cov"][c]["tgt"][p] for c in cc.COVS) for p in POS)
    lg_all = {p: sum(data["league"]["cov"][c]["tgt"][p] for c in cc.COVS) for p in POS}
    lg_tot = sum(lg_all.values())
    usual = {p: (sum(q["cov"][c]["tgt"][p] for c in cc.COVS) + cc.K_QB_SHARE * lg_all[p] / lg_tot) / (base_t + cc.K_QB_SHARE) for p in POS}
    expected = {p: sum(w[c] * shares[c][p] for c in cc.COVS) for p in POS}
    a = q["all"]
    usual_epa = (a["att"] * (a["epa"] or 0.0) + cc.K_QB_EPA * data["league"]["all"]["epa"]) / (a["att"] + cc.K_QB_EPA)
    out["qb"] = {"id": qid, "name": _display_name(qid, qname), "tagged": q["att_tagged"], "seasons": q["by_season"], "untagged_2026": q["att_2026_untagged"]}
    out["by_coverage"] = [{"key": c, "att": q["cov"][c]["att"], "epa": round(epas[c], 3), "raw_epa": q["cov"][c]["epa"],
                           "shares": {p: round(shares[c][p], 4) for p in POS}, "defense_weight": round(w[c], 4)} for c in cc.COVS]
    out["compare"] = {"usual": {p: round(v, 4) for p, v in usual.items()}, "expected": {p: round(v, 4) for p, v in expected.items()},
                      "usual_epa": round(usual_epa, 3), "expected_epa": round(sum(w[c] * epas[c] for c in cc.COVS), 3)}
    return out


def card(gid: str, qbs: dict | None = None, data: dict | None = None) -> dict | None:
    """`qbs` maps team to a quarterback id (retrospective use); `data` is a covcard.build(before=...) result for an as-of view."""
    parts = gid.split("_")
    if len(parts) != 4:
        return None
    season, week, away, home = int(parts[0]), int(parts[1]), parts[2], parts[3]
    if data is None:
        if not cc.OUT_JSON.exists():
            cc.OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
            cc.OUT_JSON.write_text(json.dumps(cc.build()), encoding="utf-8")
        data = json.loads(cc.OUT_JSON.read_text(encoding="utf-8"))
    qbs = qbs or {}
    if away not in data["defs"] or home not in data["defs"]:
        return None
    mix = defense_mix(season, week)
    fpa = {p: _fpa(p, season, week) for p in POS}
    weeks_2026 = int(_table("coverage_matrix").query("season == @season and week < @week")["week"].nunique())
    return {"gid": gid, "season": season, "week": week, "away": away, "home": home, "fpds_weeks": weeks_2026,
            "params": {"k_weeks": K_WEEKS, "shrink_routes": SHRINK_ROUTES, "k_qb_share": cc.K_QB_SHARE, "k_qb_epa": cc.K_QB_EPA, "min_routes": MIN_ROUTES},
            "sides": [_side(away, home, season, week, data, mix, fpa, qbs.get(away)), _side(home, away, season, week, data, mix, fpa, qbs.get(home))]}
