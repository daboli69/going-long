"""Version 2 against version 1 and outside forecasts, under the rules fixed in docs/INGAME_PREREG_V2.md.

    .venv\\Scripts\\python.exe scripts\\ingame_eval2.py [--validation-only]

Fits on seasons up to 2023, calibrates on 2024, and scores the test seasons (2025 and 2026 weeks 1 to 8) once. Nothing is tuned on the test seasons.
Writes docs/ingame_eval_v2.json. Reads local files only.
"""
from __future__ import annotations

import argparse
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import ingame_eval as E  # noqa: E402
from lab import ingame as G  # noqa: E402
from lab import ingame2 as I2  # noqa: E402

CP = G.CHECKPOINTS


def dm_test(d: pd.Series) -> dict:
    """Diebold-Mariano on per-game mean loss differences (positive favours the first forecast). Games are independent, so no autocorrelation term."""
    x = d.dropna().to_numpy()
    n = len(x)
    t = x.mean() / (x.std(ddof=1) / np.sqrt(n))
    return {"games": int(n), "mean_diff": float(x.mean()), "t": float(t), "p": float(2 * (1 - norm.cdf(abs(t))))}


def holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    out, prev = {}, 0.0
    for i, (k, p) in enumerate(items):
        prev = max(prev, min(1.0, (len(items) - i) * p))
        out[k] = prev
    return out


def score_v2(p1, base2, hier, tl, M=300):
    rows = []
    for fam, b in base2.items():
        kind = "rush" if fam == "rush" else "pass"
        for r in b.itertuples(index=False):
            share, kap = I2.calibrated_share(hier[fam], r.grp, r.share)
            pre_vol = E.PRE_VOL[(r.gid, r.team, kind)]
            for c in CP:
                O, Y, C, Of, Yf, Cf = tl.player(fam, r.gid, r.team, r.pid, c)
                A, At = tl.team_attempts(r.gid, r.team, kind, c)
                h, a = tl.scores(r.gid, c)
                d = (h - a) if E.HOME[r.gid] == r.team else (a - h)
                seed = zlib.crc32(f"{r.gid}{r.pid}{c}".encode())
                st = G.PlayerState(fam, r.mu_O, share, r.ypo, r.cr, O, Y, C, A, c, d, pre_vol, kap)
                st0 = G.PlayerState(fam, r.mu_O, share, r.ypo, r.cr, 0, 0.0, 0.0, 0, 0.0, 0.0, pre_vol, kap)
                up, fr = G.predict_player(p1, st, M, seed), G.predict_player(p1, st0, M, seed + 1)
                rows.append({"gid": r.gid, "fam": fam, "t": c, "pid": r.pid, "team": r.team, "pos": r.pos, "actual": Yf, "crps_v2": G.crps_samples(up["yards"], Yf),
                             "crps_v2_frozen": G.crps_samples(fr["yards"], Yf), "mean_v2": float(up["yards"].mean())})
    return pd.DataFrame(rows)


def score_games(plays, games, wpm, iso, p1, tl, gids):
    f = I2.wp_frame(plays)
    f = f[f["gid"].isin(gids)].sort_values(["gid", "t"])
    rows = []
    for gid, g in f.groupby("gid", sort=False):
        ts = g["t"].to_numpy()
        for c in CP:
            i = np.searchsorted(ts, c, side="right") - 1
            if i < 0:
                continue
            rows.append({**g.iloc[i].to_dict(), "cp": c})
    s = pd.DataFrame(rows)
    s = s[~s["tie"]].dropna(subset=I2.WP_FEATURES)
    rho = (G.GAME - s["cp"]) / G.GAME
    ep = np.array([G.ep_of(p1, d, y) for d, y in zip(s["down"], s["yl"])]) * np.where(s["poss_home"] == 1, 1.0, -1.0)
    s["p_v2"] = I2.wp_predict(wpm, iso, s)
    s["p_v2_raw"] = I2.wp_predict(wpm, iso, s, calibrated=False)
    s["p_v1"] = norm.cdf((s["margin"] + s["spread"] * rho + p1.gamma_ep * ep) / (p1.sigma_m * np.sqrt(rho.clip(lower=1e-6))))
    s["p_frozen"] = norm.cdf(s["spread"] / p1.sigma_m)
    s["p_nfl"] = s["nfl_wp"]
    return s


def game_report(s: pd.DataFrame) -> dict:
    out = {"n": int(len(s)), "games": int(s["gid"].nunique()), "by_checkpoint": {}, "versus": {}}
    eps = 1e-4
    for k in ("p_v2", "p_v2_raw", "p_v1", "p_frozen", "p_nfl"):
        s["b_" + k] = (s[k] - s["y"]) ** 2
        s["l_" + k] = -(s["y"] * np.log(np.clip(s[k], eps, 1)) + (1 - s["y"]) * np.log(np.clip(1 - s[k], eps, 1)))
    for c in CP:
        x = s[s["cp"] == c]
        out["by_checkpoint"][f"{c // 60}min"] = {k: {"brier": round(float(x["b_" + k].mean()), 4), "log": round(float(x["l_" + k].mean()), 4)} for k in ("p_v2", "p_v1", "p_frozen", "p_nfl")}
    raw_p = {}
    for other in ("p_v1", "p_nfl", "p_frozen"):
        s["gain"] = s["b_" + other] - s["b_p_v2"]
        m, lo, hi = E.block_ci(s, "gain")
        dm = dm_test(s.groupby("gid")["gain"].mean())
        s["lgain"] = s["l_" + other] - s["l_p_v2"]
        lm, llo, lhi = E.block_ci(s, "lgain")
        out["versus"][other] = {"brier_gain": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)], "dm_p": dm["p"], "log_gain": round(lm, 4), "log_ci95": [round(llo, 4), round(lhi, 4)]}
        raw_p[other] = dm["p"]
    h = holm(raw_p)
    for k in out["versus"]:
        out["versus"][k]["dm_p_holm"] = h[k]
        out["versus"][k]["beats"] = bool(out["versus"][k]["ci95"][0] > 0 and h[k] < 0.05)
    out["reliability_v2"] = E.reliability(s["p_v2"].to_numpy(), s["y"].to_numpy())
    out["reliability_v2_raw"] = E.reliability(s["p_v2_raw"].to_numpy(), s["y"].to_numpy())
    out["reliability_v1"] = E.reliability(s["p_v1"].to_numpy(), s["y"].to_numpy())
    return out


def player_report(v1: pd.DataFrame, v2: pd.DataFrame) -> dict:
    key = ["gid", "fam", "t", "pid"]
    both = v1.merge(v2, on=key, how="inner", suffixes=("", "_2"))
    out = {"rows_v1": int(len(v1)), "rows_compared": int(len(both)), "families": {}}
    raw_p = {}
    for fam in G.FAMILIES:
        x = both[both["fam"] == fam].copy()
        entry = {"n": int(len(x)), "games": int(x["gid"].nunique()), "crps_v1": round(float(x["crps_up"].mean()), 3), "crps_v2": round(float(x["crps_v2"].mean()), 3),
                 "crps_v1_frozen": round(float(x["crps_fr"].mean()), 3), "crps_v2_frozen": round(float(x["crps_v2_frozen"].mean()), 3)}
        x["g1"] = x["crps_up"] - x["crps_v2"]
        m, lo, hi = E.block_ci(x, "g1")
        dm = dm_test(x.groupby("gid")["g1"].mean())
        x["g2"] = x["crps_fr"] - x["crps_v2"]
        m2, lo2, hi2 = E.block_ci(x, "g2")
        entry["vs_v1"] = {"gain": round(m, 3), "ci95": [round(lo, 3), round(hi, 3)], "dm_p": dm["p"]}
        entry["vs_frozen_v1"] = {"gain": round(m2, 3), "ci95": [round(lo2, 3), round(hi2, 3)], "dm_p": dm_test(x.groupby("gid")["g2"].mean())["p"]}
        entry["by_checkpoint"] = {}
        for c in CP:
            y = x[x["t"] == c]
            d = dm_test((y["crps_up"] - y["crps_v2"]).groupby(y["gid"]).mean())
            entry["by_checkpoint"][f"{c // 60}min"] = {"crps_v1": round(float(y["crps_up"].mean()), 3), "crps_v2": round(float(y["crps_v2"].mean()), 3), "gain": round(d["mean_diff"], 3), "dm_p": d["p"]}
        out["families"][fam] = entry
        raw_p[fam] = dm["p"]
    h = holm(raw_p)
    for fam in out["families"]:
        e = out["families"][fam]["vs_v1"]
        e["dm_p_holm"] = h[fam]
        e["beats_v1"] = bool(e["ci95"][0] > 0 and h[fam] < 0.05)
    excl = v1.merge(v2[key], on=key, how="left", indicator=True)
    out["v1_rows_not_compared"] = {"n": int((excl["_merge"] == "left_only").sum()), "mean_crps_v1_on_them": round(float(excl.loc[excl["_merge"] == "left_only", "crps_up"].mean()), 3),
                                   "mean_crps_v1_on_compared": round(float(both["crps_up"].mean()), 3)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validation-only", action="store_true")
    ap.add_argument("--train-end", type=int, default=2023)
    ap.add_argument("--definition", default="nflfastr", choices=["nflfastr", "espn"], help="how attempts and rushes are counted (lab/ingame.py EVENT_DEFINITION)")
    ap.add_argument("--hier-draws", type=int, default=700)
    ap.add_argument("--hier-rows", type=int, default=6000)
    ap.add_argument("--tag", default="main", help="name of the cache for the hierarchical fits; a smoke test uses its own")
    a = ap.parse_args()
    G.EVENT_DEFINITION = a.definition
    seasons = list(range(2018, 2027))
    plays = G.load_plays(seasons)
    ev = G.events(plays)
    games = G.games_table(plays)
    tl = E.Timeline(plays, ev)
    E.HOME.update({r.gid: r.home for r in games.itertuples(index=False)})
    tv = G.team_volume(ev, games)
    for r in tv.itertuples(index=False):
        E.PRE_VOL[(r.gid, r.team, "pass")] = 0.0 if pd.isna(r.pre_n_pass) else r.pre_n_pass
        E.PRE_VOL[(r.gid, r.team, "rush")] = 0.0 if pd.isna(r.pre_n_rush) else r.pre_n_rush
    tr = plays["season"] <= a.train_end
    p1 = E.fit_params(plays[tr], ev[ev["season"] <= a.train_end], games[games["season"] <= a.train_end], tl)
    gr = E.game_rows(plays, games, tl, p1)
    E.fit_game_noise(gr[gr["season"] <= a.train_end], p1)
    snaps = I2.snap_table(seasons)
    base1 = G.baselines(ev, tv, p1.pool, p1.pool_catch, p1.m_eff, p1.m_catch)
    base2 = I2.baselines2(ev, tv, snaps, p1.pool, p1.pool_catch, p1.m_eff, p1.m_catch)
    season_of = dict(zip(games["gid"], games["season"]))
    hier = {}
    cache = ROOT / "data" / "cache" / f"ingame_hier_{a.tag}_{a.train_end}.json"
    if cache.exists():
        hier = json.loads(cache.read_text(encoding="utf-8"))
    for fam in G.FAMILIES:
        if fam in hier:
            continue
        b = base2[fam]
        hier[fam] = I2.fit_hier(b[b["gid"].map(season_of) <= a.train_end], n=a.hier_rows, draws=a.hier_draws)
        cache.write_text(json.dumps(hier), encoding="utf-8")
        print(fam, "hierarchical fit", {k: v for k, v in hier[fam].items() if k != "groups"}, flush=True)
    wf = I2.wp_frame(plays)
    wpm, iso = I2.fit_wp(wf[wf["season"] <= a.train_end], wf[wf["season"] == a.train_end + 1])
    report = {"prereg": "docs/INGAME_PREREG_V2.md", "fit_through": a.train_end, "calibration_season": a.train_end + 1,
              "hierarchical": {f: {k: (v if k != "groups" else {g: {x: round(y, 3) for x, y in d.items()} for g, d in v.items()}) for k, v in h.items()} for f, h in hier.items()},
              "v1_constants": {"kappa": p1.kappa, "m_eff": p1.m_eff}}
    sets = {"validation": [a.train_end + 1]}
    if not a.validation_only:
        sets["test"] = [2025, 2026]
    for name, seas in sets.items():
        gids = set(games.loc[games["season"].isin(seas), "gid"])
        b1 = {f: b[b["gid"].isin(gids)] for f, b in base1.items()}
        b2 = {f: b[b["gid"].isin(gids)] for f, b in base2.items()}
        v1 = E.score_players(p1, b1, games, tl)
        v2 = score_v2(p1, b2, hier, tl)
        v2.to_parquet(ROOT / "data" / "cache" / f"ingame_rows_v2_{a.tag}_{name}.parquet")
        report[name] = {"players": player_report(v1, v2)}
        s = score_games(plays, games, wpm, iso, p1, tl, gids)
        report[name]["game"] = game_report(s)
        print(name, json.dumps({"players": {f: {k: e[k] for k in ("n", "crps_v1", "crps_v2", "vs_v1")} for f, e in report[name]["players"]["families"].items()},
                                "game": report[name]["game"]["versus"]}, indent=1, default=float), flush=True)
    (ROOT / "docs" / ("ingame_eval_v2_validation.json" if a.validation_only else "ingame_eval_v2.json") if a.tag == "main" else ROOT / "data" / "cache" / f"ingame_eval_v2_{a.tag}.json").write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
