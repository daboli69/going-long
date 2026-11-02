"""Referee trends: records, shrunken estimates and the pre-registered tests (docs/REFS_PREREG.md). No staking, no sizing."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[1]
RULE_PATH = ROOT / "docs" / "refs_rule.json"
GAMES = ROOT / "data" / "raw" / "games.csv"
OFFICIALS = ROOT / "data" / "raw" / "officials.parquet"
SBR = ROOT / "data" / "raw" / "market" / "sbr_lines.parquet"
PEN_CACHE = ROOT / "data" / "cache" / "refs_pen.parquet"
FROZEN = ROOT / "data" / "refs" / "frozen"
LEDGER = ROOT / "data" / "refs" / "ledger.jsonl"
ALPHA = 0.002
CTRL = 10.0
MEASURES = {"home_ats": "Home team against the spread", "home_fav_ats": "Home favorite (up to 4) against the spread", "over": "Over", "pen_home": "Penalties on the home team", "pen_away": "Penalties on the away team"}
BINARY = {"home_ats", "home_fav_ats", "over"}


def rule() -> dict:
    return json.loads(RULE_PATH.read_text())


def rule_sha() -> str:
    return hashlib.sha256(RULE_PATH.read_bytes()).hexdigest()


def holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def pen_games(force: bool = False) -> pd.DataFrame:
    """Per game: accepted-penalty rows by side, offensive plays, and the home team's mean score differential. One penalty per play."""
    if PEN_CACHE.exists() and not force:
        return pd.read_parquet(PEN_CACHE)
    cols = ["game_id", "home_team", "posteam", "play_type", "score_differential", "penalty", "penalty_team"]
    out = []
    for s in range(rule()["seasons"][0], rule()["seasons"][1] + 1):
        f = ROOT / "data" / "raw" / f"play_by_play_{s}.parquet"
        if not f.exists():
            continue
        p = pd.read_parquet(f, columns=cols)
        rp = p[p["play_type"].isin(["run", "pass"])]
        sd = pd.Series(np.where(rp["posteam"] == rp["home_team"], rp["score_differential"], -rp["score_differential"]), index=rp.index)
        pen = p[p["penalty"] == 1]
        a = pd.DataFrame({"plays": rp.groupby("game_id").size(), "msd_home": sd.groupby(rp["game_id"]).mean(),
                          "pen_home": pen[pen["penalty_team"] == pen["home_team"]].groupby("game_id").size(),
                          "pen_away": pen[pen["penalty_team"] != pen["home_team"]].groupby("game_id").size()}).fillna({"pen_home": 0, "pen_away": 0})
        out.append(a.reset_index())
    d = pd.concat(out)
    PEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(PEN_CACHE)
    return d


def schedule() -> pd.DataFrame:
    R = rule()
    g = pd.read_csv(GAMES)
    return g[(g["game_type"] == R["game_type"]) & g["season"].between(*R["seasons"])].copy()


ALIAS = {"Bradley Rogers": "Brad Rogers", "Ronald Torbert": "Ron Torbert", "John Perry": "John Parry", "Adrian Hall": "Adrian Hill"}   # one person spelled two ways in the schedule file


def frame() -> pd.DataFrame:
    """Completed regular-season games with a referee, one row each, with the measures."""
    R = rule()
    g = schedule()
    g = g[g["result"].notna() & g["referee"].notna()].merge(pen_games(), on="game_id", how="left")
    g["referee"] = g["referee"].replace(ALIAS)
    g["home_ats"] = np.where(g["result"] > g["spread_line"], 1.0, np.where(g["result"] < g["spread_line"], 0.0, np.nan))
    lo, hi = R["home_fav_range"]
    g["home_fav_ats"] = g["home_ats"].where((g["spread_line"] > lo) & (g["spread_line"] <= hi))
    g["over"] = np.where(g["total"] > g["total_line"], 1.0, np.where(g["total"] < g["total_line"], 0.0, np.nan))
    g["pen_gap"] = g["pen_home"] - g["pen_away"]
    return g.sort_values(["season", "week", "game_id"]).reset_index(drop=True)


def coverage() -> dict:
    """Referee coverage for completed games by season, and agreement of games.csv with the nflverse officials table."""
    g = schedule()
    g = g[g["result"].notna()]
    cov = g.groupby("season").agg(games=("game_id", "size"), with_referee=("referee", lambda s: int(s.notna().sum())))
    o = pd.read_parquet(OFFICIALS)
    o = o[o["position"] == "Referee"].drop_duplicates("game_key").assign(gsis=lambda x: x["game_key"].astype(str))[["gsis", "official_name"]]
    m = g[g["referee"].notna()].assign(gsis=lambda x: x["gsis"].astype("Int64").astype(str)).merge(o, on="gsis", how="left")
    m["both"] = m["official_name"].notna()
    m["same"] = m["both"] & (m["referee"].str.lower().str.strip() == m["official_name"].str.lower().str.strip())
    cross = m.groupby("season").agg(in_both=("both", "sum"), same=("same", "sum"))
    out = cov.join(cross).fillna(0).astype(int)
    mism = m[m["both"] & ~m["same"]][["game_id", "referee", "official_name"]].head(10)
    return {"by_season": {int(k): v for k, v in out.to_dict("index").items()}, "mismatches": mism.to_dict("records"),
            "missing": "umpire, line judge, down judge, field judge, side judge and back judge are in the officials table but are not analyzed; the gamebooks (full crew and every penalty) were not read"}


def shrink_binary(d: pd.DataFrame, col: str) -> pd.DataFrame:
    """Per referee: n, wins, raw rate, exact 95% interval, shrunken rate toward the league rate (method of moments)."""
    R = rule()
    d = d[d[col].notna()]
    p0 = float(d[col].mean())
    t = d.groupby("referee")[col].agg(["size", "sum"]).rename(columns={"size": "n", "sum": "k"})
    t["rate"] = t["k"] / t["n"]
    vb = max(float(t["rate"].var(ddof=1)) - float((p0 * (1 - p0) / t["n"]).mean()), 0.0) if len(t) > 1 else 0.0
    m = float(np.clip(p0 * (1 - p0) / vb - 1, *R["shrink_m_clip"])) if vb > 0 else R["shrink_m_clip"][1]
    t["shrunk"] = (t["k"] + m * p0) / (t["n"] + m)
    ci = [binomtest(int(k), int(n)).proportion_ci(method="exact") for k, n in zip(t["k"], t["n"])]
    t["lo"], t["hi"] = [c.low for c in ci], [c.high for c in ci]
    t["league"], t["m"] = p0, m
    return t.reset_index()


def shrink_count(d: pd.DataFrame, col: str) -> pd.DataFrame:
    """Per referee: games, mean per game, 95% interval, shrunken mean (normal-normal, method of moments)."""
    d = d[d[col].notna()]
    mu = float(d[col].mean())
    t = d.groupby("referee")[col].agg(["size", "mean", "std"]).rename(columns={"size": "n", "mean": "rate", "std": "sd"})
    se2 = (t["sd"] ** 2 / t["n"]).fillna(0)
    tau2 = max(float(t["rate"].var(ddof=1)) - float(se2.mean()), 0.0) if len(t) > 1 else 0.0
    t["shrunk"] = mu + (t["rate"] - mu) * (tau2 / (tau2 + se2) if tau2 > 0 else 0.0)
    t["lo"], t["hi"] = t["rate"] - 1.96 * np.sqrt(se2), t["rate"] + 1.96 * np.sqrt(se2)
    t["league"] = mu
    t["k"] = np.nan
    return t.drop(columns="sd").reset_index()


def table(f: pd.DataFrame, measure: str, a: int, b: int, referee: str | None = None) -> pd.DataFrame:
    R = rule()
    w = f[f["season"].between(a, b)]
    t = shrink_binary(w, measure) if measure in BINARY else shrink_count(w, measure)
    need = R["min_games"]["home_fav"] if measure == "home_fav_ats" else R["min_games"]["ats"]
    t["too_few"] = t["n"] < need
    return t.sort_values("n", ascending=False).reset_index(drop=True)


def _ats_tests(f: pd.DataFrame, a: int, b: int) -> pd.DataFrame:
    R = rule()
    w = f[f["season"].between(a, b)]
    rows = []
    for m in ("home_ats", "home_fav_ats", "over"):
        d = w[w[m].notna()]
        p0 = float(d[m].mean())
        need = R["min_games"]["home_fav"] if m == "home_fav_ats" else R["min_games"]["ats"]
        for ref, gx in d.groupby("referee"):
            n, k = len(gx), int(gx[m].sum())
            if n < need:
                continue
            rows.append({"measure": m, "referee": ref, "n": n, "k": k, "rate": k / n, "league": p0, "p": float(binomtest(k, n, p0).pvalue), "side": "above" if k / n > p0 else "below"})
    t = pd.DataFrame(rows)
    if len(t):
        h = holm({f"{r.measure}|{r.referee}": r.p for r in t.itertuples()})
        t["p_holm"] = [h[f"{r.measure}|{r.referee}"] for r in t.itertuples()]
    return t


def _fit_pen(f: pd.DataFrame, refs: list[str]) -> pd.Series:
    """Poisson ridge on team-game rows with a play offset; returns each referee's extra home-side penalty rate (log scale)."""
    from sklearn.linear_model import PoissonRegressor
    f = f.dropna(subset=["plays", "pen_home", "pen_away", "msd_home", "spread_line"])
    idx = f["referee"].map({r: i for i, r in enumerate(refs)}).to_numpy()
    n, k = len(f), len(refs)
    D = np.zeros((n, k))
    D[np.arange(n), idx] = 1.0
    plays = f["plays"].to_numpy(float)
    line, msd = f["spread_line"].to_numpy(float) / 6.0, f["msd_home"].to_numpy(float) / 6.0   # roughly unit scale so the optimizer behaves
    ctrl_h = np.column_stack([np.ones(n), line, msd]) * CTRL
    ctrl_a = np.column_stack([np.zeros(n), -line, -msd]) * CTRL
    X = np.vstack([np.hstack([ctrl_h, D, D]), np.hstack([ctrl_a, D, np.zeros((n, k))])])
    y = np.concatenate([f["pen_home"].to_numpy(float), f["pen_away"].to_numpy(float)]) / np.concatenate([plays, plays])
    w = np.concatenate([plays, plays])
    m = PoissonRegressor(alpha=ALPHA, max_iter=2000, tol=1e-12).fit(X, y, sample_weight=w)
    return pd.Series(m.coef_[3 + k:], index=refs)


def _shuffle(f: pd.DataFrame, rng) -> np.ndarray:
    out = f["referee"].to_numpy().copy()
    for ix in f.groupby(["season", "week"]).indices.values():
        out[ix] = out[rng.permutation(ix)]
    return out


def pen_test(f: pd.DataFrame, a: int, b: int, draws: int, seed: int) -> pd.DataFrame:
    """Referee x home penalty effect per referee with max-statistic and one-sided permutation p-values."""
    R = rule()
    w = f[f["season"].between(a, b)]
    n = w.groupby("referee").size()
    refs = sorted(n[n >= R["min_games"]["ats"]].index)
    w = w[w["referee"].isin(refs)].reset_index(drop=True)
    obs = _fit_pen(w, refs)
    rng = np.random.default_rng(seed)
    perms = []
    for _ in range(draws):
        s = w.copy()
        s["referee"] = _shuffle(w, rng)
        perms.append(_fit_pen(s, refs))
    P = pd.DataFrame(perms)
    mx = P.abs().max(axis=1).to_numpy()
    return pd.DataFrame({"referee": refs, "games": n[refs].to_numpy(), "extra_home_penalty_pct": (np.exp(obs.to_numpy()) - 1) * 100, "coef": obs.to_numpy(),
                         "p_max": [float((mx >= abs(o)).mean()) for o in obs], "p_up": [float((P[r] >= obs[r]).mean()) for r in refs], "p_down": [float((P[r] <= obs[r]).mean()) for r in refs]})


def year_to_year(f: pd.DataFrame, col: str, agg: str) -> dict:
    R = rule()
    t = f[f[col].notna()].groupby(["referee", "season"])[col].agg(["size", "mean"]).reset_index()
    t = t[t["size"] >= R["min_games"]["year_pair"]]
    nxt = t.assign(season=t["season"] - 1)
    j = t.merge(nxt, on=["referee", "season"], suffixes=("", "_next"))
    j = j[j["season"] <= 2025]
    if len(j) < 5:
        return {"pairs": int(len(j)), "r": None, "ci": None}
    r = float(np.corrcoef(j["mean"], j["mean_next"])[0, 1])
    rng = np.random.default_rng(R["year_to_year"]["seed"])
    bs = []
    for _ in range(R["year_to_year"]["draws"]):
        i = rng.integers(0, len(j), len(j))
        x, y = j["mean"].to_numpy()[i], j["mean_next"].to_numpy()[i]
        if x.std() > 0 and y.std() > 0:
            bs.append(np.corrcoef(x, y)[0, 1])
    return {"pairs": int(len(j)), "referees": int(j["referee"].nunique()), "r": r, "ci": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]}


def tweet_check(f: pd.DataFrame) -> dict:
    R = rule()
    T = R["tweet"]
    w = f[f["season"] >= T["since"]]
    s = w[w["referee"] == T["referee"]]
    wins, losses, pushes = int((s["home_ats"] == 1).sum()), int((s["home_ats"] == 0).sum()), int(s["home_ats"].isna().sum())
    hf = s[s["home_fav_ats"].notna()]
    s25 = f[(f["season"] == 2025) & (f["referee"] == T["referee"])]
    by25 = f[f["season"] == 2025].groupby("referee").apply(lambda x: float((x["pen_away"] - x["pen_home"]).sum()), include_groups=False)
    n, k = wins + losses, wins
    p0 = float(w["home_ats"].mean())
    pv = float(binomtest(k, n, p0).pvalue) if n else None
    # how often is the most extreme referee (>= 20 games) this far from the league, by luck
    ww = w[w["home_ats"].notna()].reset_index(drop=True)
    rng = np.random.default_rng(R["permutation"]["smith_seed"])

    def mx(refcol):
        g = pd.DataFrame({"r": refcol, "y": ww["home_ats"]}).groupby("r")["y"].agg(["size", "mean"])
        g = g[g["size"] >= R["min_games"]["ats"]]
        return float((g["mean"] - p0).abs().max())
    obs = abs(k / n - p0) if n else 0.0
    nulls = []
    for _ in range(R["permutation"]["smith_draws"]):
        nulls.append(mx(_shuffle(ww, rng)))
    return {"referee": T["referee"], "since": T["since"], "tweet": {k2: T[k2] for k2 in ("home_ats", "home_fav_up_to_4_ats", "away_minus_home_penalties_2025")},
            "rebuilt": {"games": int(len(s)), "home_ats": f"{wins}-{losses}-{pushes}", "home_ats_rate_ex_push": (k / n if n else None), "league_rate_since": p0,
                        "home_fav_up_to_4_ats": f"{int((hf['home_ats'] == 1).sum())}-{int((hf['home_ats'] == 0).sum())}", "games_2025": int(len(s25)),
                        "away_minus_home_penalties_2025": float((s25["pen_away"] - s25["pen_home"]).sum()),
                        "away_minus_home_2025_league_rank": int((by25 > by25.get(T["referee"], np.nan)).sum() + 1) if T["referee"] in by25 else None, "referees_2025": int(len(by25))},
            "exact_p_vs_league": pv, "luck_check": {"extreme_referees_considered": int((ww.groupby("referee").size() >= R["min_games"]["ats"]).sum()),
                                                   "share_of_shuffles_with_a_referee_this_far": float((np.array(nulls) >= obs).mean())}}


def market_check(f: pd.DataFrame) -> dict:
    """Does a referee's earlier home-cover tendency predict the open to close move or the cover, on the seasons sbr_lines covers."""
    R = rule()
    s = pd.read_parquet(SBR)
    g = f.merge(s[["game_id", "sbr_home_spread_open", "sbr_home_spread_close"]], on="game_id", how="inner").dropna(subset=["sbr_home_spread_open", "sbr_home_spread_close", "home_ats"])
    if not len(g):
        return {"games": 0}
    sign = float(np.sign(np.corrcoef(g["sbr_home_spread_close"], g["spread_line"])[0, 1]))
    all_g = f[f["home_ats"].notna()].sort_values(["season", "week", "game_id"])
    p0 = float(all_g["home_ats"].mean())
    belief = {}
    prior_k, prior_n = {}, {}
    for r in all_g.itertuples():
        n = prior_n.get(r.referee, 0)
        belief[r.game_id] = (prior_k.get(r.referee, 0) / n - p0) if n >= R["market"]["belief_min_prior_games"] else 0.0
        prior_n[r.referee] = n + 1
        prior_k[r.referee] = prior_k.get(r.referee, 0) + r.home_ats
    g["belief"] = g["game_id"].map(belief)
    move = (g["sbr_home_spread_close"] - g["sbr_home_spread_open"]) * (1 if sign < 0 else -1)   # in sbr's own sign, negative = home favored; move below 0 = line shortened toward home
    p = np.clip(p0 + g["belief"], 0.3, 0.7).to_numpy()
    y = g["home_ats"].to_numpy()
    ls_ref = y * np.log(p0) + (1 - y) * np.log(1 - p0)
    ls_bel = y * np.log(p) + (1 - y) * np.log(1 - p)
    d = ls_bel - ls_ref
    rng = np.random.default_rng(R["market"]["seed"])
    gid = g["game_id"].to_numpy()
    bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(R["market"]["draws"])]
    return {"games": int(len(g)), "seasons": sorted(int(x) for x in g["season"].unique()), "nonzero_belief_games": int((g["belief"] != 0).sum()), "spread_sign_vs_spread_line": sign,
            "corr_belief_with_move": float(np.corrcoef(g["belief"], move)[0, 1]) if g["belief"].std() > 0 else None,
            "log_score_gain_vs_constant": {"gain": float(d.mean()), "ci": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]},
            "note": "sbr_lines has open and close only, with no timestamp at the referee announcement, so the move is open to close, a proxy"}


def run() -> dict:
    R = rule()
    f = frame()
    da, db = R["discovery"]
    ca, cb = R["confirmation"]
    res = {"rule_sha256": rule_sha(), "games": int(len(f)), "referees": int(f["referee"].nunique()), "coverage": coverage()}
    disc, conf = _ats_tests(f, da, db), _ats_tests(f, ca, cb)
    pd_ = pen_test(f, da, db, R["permutation"]["penalty_draws"], R["permutation"]["penalty_seed"])
    pc = pen_test(f, ca, cb, R["permutation"]["penalty_draws"], R["permutation"]["penalty_seed"])
    yy = {"home_ats": year_to_year(f, "home_ats", "mean"), "pen_gap": year_to_year(f, "pen_gap", "mean")}
    res["year_to_year"] = yy
    claims = []
    for r in disc.itertuples():
        if r.p_holm >= R["pass"]["discovery_holm_p_lt"]:
            continue
        c = conf[(conf["measure"] == r.measure) & (conf["referee"] == r.referee)]
        ok_conf = False
        if len(c):
            c = c.iloc[0]
            k, n, p0 = int(c["k"]), int(c["n"]), float(c["league"])
            pv = binomtest(k, n, p0, alternative="greater" if r.side == "above" else "less").pvalue
            ok_conf = bool(c["side"] == r.side and pv < R["pass"]["confirmation_one_sided_p_lt"])
        yc = yy.get(r.measure, {}).get("ci")
        claims.append({"measure": r.measure, "referee": r.referee, "discovery_holm": r.p_holm, "confirmed": ok_conf, "year_corr_ci_lower_gt_0": bool(yc and yc[0] > 0)})
    for r in pd_.itertuples():
        if r.p_max >= R["pass"]["discovery_holm_p_lt"]:
            continue
        c = pc[pc["referee"] == r.referee]
        ok_conf = bool(len(c) and ((r.coef > 0 and c.iloc[0]["p_up"] < 0.05) or (r.coef < 0 and c.iloc[0]["p_down"] < 0.05)))
        yc = yy["pen_gap"].get("ci")
        claims.append({"measure": "pen_home_extra", "referee": r.referee, "discovery_max_p": r.p_max, "confirmed": ok_conf, "year_corr_ci_lower_gt_0": bool(yc and yc[0] > 0)})
    res["claims"] = claims
    res["any_effect_claimed"] = bool([c for c in claims if c["confirmed"] and c["year_corr_ci_lower_gt_0"]])
    res["discovery_ats"] = disc.sort_values("p_holm").head(12).to_dict("records")
    res["confirmation_ats"] = conf.sort_values("p_holm").head(12).to_dict("records")
    res["discovery_ats_tests"] = int(len(disc))
    res["penalty_discovery"] = pd_.sort_values("p_max").to_dict("records")
    res["penalty_confirmation"] = pc.sort_values("p_up").to_dict("records")
    h = f.dropna(subset=["plays"]).assign(tot=lambda x: x["pen_home"] + x["pen_away"])
    res["penalty_dispersion"] = {"mean_per_team_game": float(h["tot"].mean() / 2), "var_over_mean": float(h["pen_home"].var() / h["pen_home"].mean())}
    res["tweet_check"] = tweet_check(f)
    res["market"] = market_check(f)
    return res, f


def this_week(f: pd.DataFrame | None = None) -> dict:
    """Assigned referees for games not yet played, from the nflverse schedule (games.csv), as of the file's last refresh."""
    g = schedule()
    s = g["season"].max()
    g = g[(g["season"] == s) & g["result"].isna()]
    if not len(g):
        return {"season": int(s), "week": None, "games": [], "source": "nflverse schedule, data/raw/games.csv"}
    wk = int(g["week"].min())
    gw = g[g["week"] == wk]
    return {"season": int(s), "week": wk, "source": "nflverse schedule, data/raw/games.csv (referee column, refreshed with the data pipeline)", "assigned": int(gw["referee"].notna().sum()),
            "games": [{"gid": r.game_id, "away": r.away_team, "home": r.home_team, "kickoff": r.gameday, "referee": None if pd.isna(r.referee) else r.referee} for r in gw.itertuples()]}


def tab_numbers(f: pd.DataFrame, refs: list[str]) -> dict:
    R = rule()
    a, b = R["seasons"]
    out = {}
    cover, ph, pa = (table(f, m, a, b).set_index("referee") for m in ("home_ats", "pen_home", "pen_away"))
    for r in refs:
        out[r] = {"games": int(cover["n"].get(r, 0)), "home_cover_shrunk": None if r not in cover.index else float(cover.loc[r, "shrunk"]), "league_home_cover": float(cover["league"].iloc[0]),
                  "home_pen_per_game_shrunk": None if r not in ph.index else float(ph.loc[r, "shrunk"]), "away_pen_per_game_shrunk": None if r not in pa.index else float(pa.loc[r, "shrunk"]),
                  "league_pen_per_game": float(ph["league"].iloc[0])}
    return out


def freeze_week(week: int, now: dt.datetime | None = None) -> dict:
    """Write-once: assigned referees for the week's unplayed games with the tab numbers shown for them. Returns the saved file on a second call."""
    path = FROZEN / f"{week}.json"
    if path.exists():
        rec = json.loads(path.read_text())
        if hashlib.sha256(json.dumps(rec["forecast"], sort_keys=True, separators=(",", ":")).encode()).hexdigest() != rec["sha256"]:
            raise RuntimeError(f"saved referee record for week {week} does not match its hash")
        return rec
    tw = this_week()
    games = [x for x in tw["games"] if x["referee"]] if tw.get("week") == week else []
    if not games:
        return {"week": week, "games": [], "note": "no referee assignments in the schedule for this week yet; nothing written"}
    now = now or dt.datetime.now(dt.timezone.utc)
    nums = tab_numbers(frame(), sorted({x["referee"] for x in games}))
    fc = {"week": week, "season": tw["season"], "created": now.isoformat(), "rule_sha256": rule_sha(), "source": tw["source"], "games": [{**x, "tab": nums[x["referee"]]} for x in games]}
    rec = {"sha256": hashlib.sha256(json.dumps(fc, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "forecast": fc}
    FROZEN.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec))
    with LEDGER.open("a") as fh:
        fh.write(json.dumps({"week": week, "sha256": rec["sha256"], "created": fc["created"], "games": len(games)}) + "\n")
    return rec


def score_week(week: int) -> dict:
    """After the games: realized cover and penalty gap against the league-average baseline for the frozen assignments."""
    rec = freeze_week(week)
    if not rec.get("forecast"):
        return {"week": week, "scored": 0}
    g = schedule().set_index("game_id")
    rows = []
    pen = pen_games().set_index("game_id")
    for x in rec["forecast"]["games"]:
        r = g.loc[x["gid"]]
        if pd.isna(r["result"]):
            continue
        cover = 1.0 if r["result"] > r["spread_line"] else 0.0 if r["result"] < r["spread_line"] else None
        t = x["tab"]
        gap = None if x["gid"] not in pen.index else float(pen.loc[x["gid"], "pen_home"] - pen.loc[x["gid"], "pen_away"])
        rows.append({"gid": x["gid"], "referee": x["referee"], "cover": cover, "gap": gap, "p_ref": t["home_cover_shrunk"], "p_league": t["league_home_cover"],
                     "gap_ref": None if t["home_pen_per_game_shrunk"] is None else t["home_pen_per_game_shrunk"] - t["away_pen_per_game_shrunk"]})
    d = pd.DataFrame(rows)
    out = {"week": week, "scored": int(len(d))}
    if len(d):
        c = d.dropna(subset=["cover"])
        out["cover_brier_ref"] = float(((c["p_ref"] - c["cover"]) ** 2).mean()) if len(c) else None
        out["cover_brier_league"] = float(((c["p_league"] - c["cover"]) ** 2).mean()) if len(c) else None
        gg = d.dropna(subset=["gap", "gap_ref"])
        out["gap_abs_error_ref"] = float((gg["gap"] - gg["gap_ref"]).abs().mean()) if len(gg) else None
        out["gap_abs_error_zero"] = float(gg["gap"].abs().mean()) if len(gg) else None
    return out
