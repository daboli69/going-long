"""Phase 8.3: nine pre-registered upset-identifier metrics (docs/PHASE8_3_PREREGISTRATION.md). Lab-only research.

Every metric is computed strictly as-of (completed games with kickoff before the target game; the future schedule only
for M6, which is published in advance) and signed so that POSITIVE = expected to favour the underdog.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

from . import metrics as Mx
from .config import ARTIFACTS_DIR, RAW_DIR

OUT = ARTIFACTS_DIR / "phase83"
OFFICIALS_URL = "https://github.com/nflverse/nflverse-data/releases/download/officials/officials.parquet"
METRICS = ["M1_pythag_luck", "M2_one_score_luck", "M3_fumble_luck", "M4_turnover_margin", "M5_letdown", "M6_lookahead",
           "M7_road_fatigue", "M8_referee_penalties", "M9_aggressiveness"]
WINDOW = range(2018, 2026)


def _norm(t):
    from .availability import _team
    return t.map(_team) if hasattr(t, "map") else _team(t)


def team_game_stats(games: pd.DataFrame) -> pd.DataFrame:
    """Per completed (game, team): points, fumble recoveries, giveaways/takeaways, 4th-down decisions, penalties."""
    from .advanced import _id_map
    idm = _id_map(games)
    rows, refpen = [], []
    for s in sorted(games["season"].unique()):
        p = RAW_DIR / f"play_by_play_{s}.parquet"
        if not p.exists():
            continue
        cols = ["game_id", "old_game_id", "posteam", "defteam", "down", "ydstogo", "yardline_100", "play_type", "fumble",
                "fumble_lost", "fumbled_1_team", "fumble_recovery_1_team", "interception", "penalty"]
        d = pd.read_parquet(p, columns=cols)
        d["gid"] = d["game_id"].map(lambda g: idm.get(g, g))
        for c in ("posteam", "defteam", "fumbled_1_team", "fumble_recovery_1_team"):
            d[c] = _norm(d[c])
        f = d[(d["fumble"] == 1) & d["fumble_recovery_1_team"].notna()]
        rec = f.groupby(["gid", "fumble_recovery_1_team"]).size().rename("fum_recovered")
        tot = f.groupby("gid").size().rename("fum_total")
        gv = d.groupby(["gid", "posteam"]).agg(ints=("interception", "sum"), fum_lost=("fumble_lost", "sum"))
        gv["giveaways"] = gv["ints"].fillna(0) + gv["fum_lost"].fillna(0)
        fo = d[(d["down"] == 4) & (d["ydstogo"] <= 3) & (d["yardline_100"] <= 60) & d["play_type"].isin(["run", "pass", "punt", "field_goal"])]
        fo = fo.assign(go=fo["play_type"].isin(["run", "pass"]).astype(int))
        go = fo.groupby(["gid", "posteam"]).agg(fourth_att=("go", "size"), fourth_go=("go", "sum"))
        pen = d.groupby("gid")["penalty"].sum().rename("penalties")
        old = d.groupby("gid")["old_game_id"].first()
        refpen.append(pd.DataFrame({"penalties": pen, "old_game_id": old}).reset_index())
        t = gv.join(go, how="outer").reset_index().rename(columns={"gid": "game_id", "posteam": "team"})
        t = t.merge(rec.reset_index().rename(columns={"gid": "game_id", "fumble_recovery_1_team": "team"}), on=["game_id", "team"], how="left")
        t = t.merge(tot.reset_index().rename(columns={"gid": "game_id"}), on="game_id", how="left")
        rows.append(t)
    tg = pd.concat(rows, ignore_index=True).fillna({"fum_recovered": 0, "fum_total": 0, "fourth_att": 0, "fourth_go": 0, "giveaways": 0})
    opp = {}
    for g, h, a in zip(games["game_id"], games["home_team"], games["away_team"]):
        opp[(g, h)], opp[(g, a)] = a, h
    tg["opp"] = [opp.get((g, t)) for g, t in zip(tg["game_id"], tg["team"])]
    take = tg.set_index(["game_id", "team"])["giveaways"]
    tg["takeaways"] = [take.get((g, o), 0) for g, o in zip(tg["game_id"], tg["opp"])]
    return tg, pd.concat(refpen, ignore_index=True)


def referees(games: pd.DataFrame, refpen: pd.DataFrame) -> pd.DataFrame:
    p = RAW_DIR / "officials.parquet"
    if not p.exists():
        from . import sources
        sources.download("nflverse_officials", OFFICIALS_URL, p, max_age_hours=24, validate=sources._validate_parquet, progress=lambda m: None)
    o = pd.read_parquet(p)
    o = o[o["position"] == "Referee"][["game_id", "official_name"]].rename(columns={"game_id": "old_game_id", "official_name": "referee"})
    o["old_game_id"] = o["old_game_id"].astype(str)
    refpen = refpen.assign(old_game_id=refpen["old_game_id"].astype(str))
    r = refpen.merge(o, on="old_game_id", how="left").rename(columns={"gid": "game_id"})
    sched = o.copy()                                                  # crews are also listed for not-yet-played games
    return r, sched


def build(games: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per game: the nine metrics from the home team's perspective (h) and away team's (a)."""
    from .data_pipeline import GAMES_TABLE
    games = games if games is not None else pd.read_parquet(GAMES_TABLE)
    games = games.sort_values("kickoff_utc").reset_index(drop=True)
    tg, refpen = team_game_stats(games)
    done = games[games["completed"]]
    long = pd.concat([done.assign(team=done["home_team"], pf=done["home_score"], pa=done["away_score"], home=1),
                      done.assign(team=done["away_team"], pf=done["away_score"], pa=done["home_score"], home=0)])
    long = long[["game_id", "season", "kickoff_utc", "team", "pf", "pa", "home"]].merge(tg, on=["game_id", "team"], how="left").fillna(0)
    long["win"] = (long["pf"] > long["pa"]).astype(float) + 0.5 * (long["pf"] == long["pa"])
    long["one_score"] = ((long["pf"] - long["pa"]).abs() <= 8).astype(float)
    long["one_score_win"] = long["one_score"] * (long["pf"] > long["pa"])
    long = long.sort_values(["team", "kickoff_utc"])
    by_team = {t: d.reset_index(drop=True) for t, d in long.groupby("team")}
    season_tot = long.groupby(["team", "season"])[["fourth_att", "fourth_go"]].sum()
    ref_rows, ref_sched = referees(games, refpen)
    ref_games = ref_rows.merge(games[["game_id", "kickoff_utc"]], on="game_id", how="inner").sort_values("kickoff_utc")
    old_by_gid = dict(zip(refpen["gid"] if "gid" in refpen else refpen["game_id"], refpen["old_game_id"].astype(str)))
    sched_ref = dict(zip(ref_sched["old_game_id"], ref_sched["referee"]))
    sched_ix = games.assign(sid=games["season"].astype(str)).set_index("game_id")

    def team_state(team, kick, season):
        d = by_team.get(team)
        if d is None:
            return None
        prior = d[(d["kickoff_utc"] < kick) & (d["season"] == season)]
        return prior

    out = []
    for g in games.itertuples(index=False):
        if g.season < 2016:
            continue
        r = {"game_id": g.game_id}
        for side, team in (("h", g.home_team), ("a", g.away_team)):
            pr = team_state(team, g.kickoff_utc, g.season)
            n = 0 if pr is None else len(pr)
            if pr is not None and n >= 3:
                pf, pa = pr["pf"].sum(), pr["pa"].sum()
                pyth = pf ** 2.37 / (pf ** 2.37 + pa ** 2.37) if pf + pa > 0 else 0.5
                r[f"{side}_m1"] = pr["win"].mean() - pyth
            else:
                r[f"{side}_m1"] = np.nan
            os_g = 0 if pr is None else pr["one_score"].sum()
            os_w = 0 if pr is None else pr["one_score_win"].sum()
            r[f"{side}_m2"] = (os_w + 1) / (os_g + 2)
            fr = 0 if pr is None else pr["fum_recovered"].sum()
            ft = 0 if pr is None else pr["fum_total"].sum()
            r[f"{side}_m3"] = (fr + 0.5 * 10) / (ft + 10)
            tm = 0 if pr is None else (pr["takeaways"] - pr["giveaways"]).sum()
            r[f"{side}_m4"] = tm / (n + 3)
            last = pr.iloc[-1] if pr is not None and n else None
            r[f"{side}_m5"] = float(last is not None and (last["pf"] - last["pa"]) >= 17)
            nxt = games[(games["season"] == g.season) & (games["kickoff_utc"] > g.kickoff_utc) &
                        ((games["home_team"] == team) | (games["away_team"] == team))].head(1)
            r[f"{side}_m6"] = float(len(nxt) > 0 and bool(nxt["div_game"].iloc[0] == 1) and not bool(g.div_game == 1))
            streak = 0
            if pr is not None:
                for hm in pr["home"].iloc[::-1]:
                    if hm == 0:
                        streak += 1
                    else:
                        break
            r[f"{side}_m7"] = float(side == "a" and streak + 1 >= 3)
            att_c = 0 if pr is None else pr["fourth_att"].sum()
            go_c = 0 if pr is None else pr["fourth_go"].sum()
            prev = season_tot.loc[(team, g.season - 1)] if (team, g.season - 1) in season_tot.index else None
            prior = (prev["fourth_go"] / prev["fourth_att"]) if prev is not None and prev["fourth_att"] > 0 else None
            if prior is None:
                r[f"{side}_m9"] = go_c / att_c if att_c > 0 else np.nan
            else:                                             # current season blended with last season's rate, k = 10
                r[f"{side}_m9"] = (go_c + 10 * prior) / (att_c + 10)
        # M8: the referee assigned to this game (crews are published before kickoff); his earlier games only
        old = old_by_gid.get(g.game_id)                       # played games only (old id comes from play-by-play)
        ref = sched_ref.get(old) if old else None
        if ref:
            prev = ref_games[(ref_games["referee"] == ref) & (ref_games["kickoff_utc"] < g.kickoff_utc)]
            r["m8"] = prev["penalties"].mean() if len(prev) >= 8 else np.nan
        else:
            r["m8"] = np.nan
        r["referee"] = ref
        out.append(r)
    m = pd.DataFrame(out)
    OUT.mkdir(parents=True, exist_ok=True)
    m.to_parquet(OUT / "metrics_by_game.parquet", index=False)
    return m


def signed(x: pd.DataFrame) -> pd.DataFrame:
    """Favourite/underdog orientation from the champion probability; positive = favours the underdog."""
    fav_home = x["p_weighted_average"] >= 0.5
    f = lambda k: np.where(fav_home, x[f"h_{k}"], x[f"a_{k}"])
    u = lambda k: np.where(fav_home, x[f"a_{k}"], x[f"h_{k}"])
    s = pd.DataFrame(index=x.index)
    s["M1_pythag_luck"] = f("m1") - u("m1")
    s["M2_one_score_luck"] = f("m2") - u("m2")
    s["M3_fumble_luck"] = f("m3") - u("m3")
    s["M4_turnover_margin"] = f("m4") - u("m4")
    s["M5_letdown"] = f("m5")
    s["M6_lookahead"] = f("m6")
    s["M7_road_fatigue"] = f("m7")
    s["M8_referee_penalties"] = x["m8"]
    s["M9_aggressiveness"] = u("m9") - f("m9")
    s["p_fav"] = np.where(fav_home, x["p_weighted_average"], 1 - x["p_weighted_average"])
    s["fav_won"] = np.where(fav_home, x["home_win"], 1 - x["home_win"])
    s["season"] = x["season"].to_numpy()
    s["game_id"] = x["game_id"].to_numpy()
    return s


def evaluate(n_boot: int = 2000) -> dict:
    from .specialists.baseline import load_oof
    m = pd.read_parquet(OUT / "metrics_by_game.parquet") if (OUT / "metrics_by_game.parquet").exists() else build()
    oof = load_oof()
    x = oof[oof["season"].isin(WINDOW) & oof["home_win"].notna()].merge(m, on="game_id", how="left")
    s = signed(x)
    rows = []
    for k in METRICS:
        d = s.dropna(subset=[k, "p_fav", "fav_won"])
        z = (d[k] - d[k].mean()) / (d[k].std() or 1)
        lc = np.log(np.clip(d["p_fav"], 1e-6, 1 - 1e-6) / (1 - np.clip(d["p_fav"], 1e-6, 1 - 1e-6))).to_numpy()
        y = d["fav_won"].to_numpy()
        X0, X1 = lc.reshape(-1, 1), np.c_[lc, z]
        m0 = LogisticRegression(C=1e6, max_iter=2000).fit(X0, y)
        m1 = LogisticRegression(C=1e6, max_iter=2000).fit(X1, y)
        lr = 2 * len(y) * (Mx.log_loss(y, m0.predict_proba(X0)[:, 1]) - Mx.log_loss(y, m1.predict_proba(X1)[:, 1]))
        coef = float(m1.coef_[0][1])
        p2 = float(stats.chi2.sf(max(lr, 0), 1))
        p1 = p2 / 2 if coef < 0 else 1 - p2 / 2                          # one-sided: pre-declared negative coefficient
        b0, b1 = m1.intercept_[0], m1.coef_[0]
        base = np.log(0.65 / 0.35)
        up0 = 1 - 1 / (1 + np.exp(-(b0 + b1[0] * base)))
        up1 = 1 - 1 / (1 + np.exp(-(b0 + b1[0] * base + b1[1])))
        signs = []
        for sea, dd in d.assign(z=z.to_numpy(), lc=lc).groupby("season"):
            if dd["z"].std() == 0 or len(dd) < 60:
                continue
            mm = LogisticRegression(C=1e6, max_iter=2000).fit(np.c_[dd["lc"], dd["z"]], dd["fav_won"])
            signs.append(int(mm.coef_[0][1] < 0))
        # walk-forward (descriptive): fit on earlier seasons, score later season vs champion-only recalibration
        gains = []
        for sea in sorted(d["season"].unique()):
            tr, te = d.assign(z=z, lc=lc)[d["season"] < sea], d.assign(z=z, lc=lc)[d["season"] == sea]
            if len(tr) < 250:
                continue
            a = LogisticRegression(C=1.0, max_iter=2000).fit(tr[["lc"]], tr["fav_won"]).predict_proba(te[["lc"]])[:, 1]
            bb = LogisticRegression(C=1.0, max_iter=2000).fit(tr[["lc", "z"]], tr["fav_won"]).predict_proba(te[["lc", "z"]])[:, 1]
            yy = te["fav_won"].to_numpy()
            gains.append((Mx.log_loss(yy, a) - Mx.log_loss(yy, bb)) * len(te))
        rows.append({"metric": k, "games": int(len(d)), "share_nonzero": float((d[k] != 0).mean()), "coef_per_sd": coef,
                     "p_one_sided": p1, "upset_prob_at_65pct_fav": float(up0), "upset_prob_plus_1sd": float(up1),
                     "seasons_with_predeclared_sign": f"{sum(signs)}/{len(signs)}", "_signs": sum(signs),
                     "walkforward_ll_gain": float(sum(gains) / max(1, sum(len(d[d['season'] == s_]) for s_ in sorted(d['season'].unique())[1:])))})
    res = pd.DataFrame(rows)
    order = res["p_one_sided"].sort_values().index
    run, adj = 0.0, {}
    for i, idx in enumerate(order):
        run = max(run, min(1.0, (len(res) - i) * res.loc[idx, "p_one_sided"]))
        adj[idx] = run
    res["p_holm"] = pd.Series(adj)
    res["passes"] = (res["p_holm"] < 0.05) & (res["_signs"] >= 5)
    res = res.drop(columns=["_signs"])
    res.to_csv(OUT / "evaluation.csv", index=False)
    (OUT / "evaluation.json").write_text(json.dumps({"window": "2018-2025", "results": res.to_dict("records")}, indent=2, default=str))
    return {"results": res, "signed": s}


def load() -> dict:
    p = OUT / "evaluation.csv"
    return {"results": pd.read_csv(p)} if p.exists() else {}
