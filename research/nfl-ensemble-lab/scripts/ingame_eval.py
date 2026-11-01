"""Does updating a projection during the game beat the pregame projection? Chronological backtest on play-by-play, replayed as if live.

    .venv\\Scripts\\python.exe scripts\\ingame_eval.py [--train-end 2023] [--valid 2024] [--test 2025 2026]

Fits every constant (team volume, share prior strength, efficiency shrinkage, expected points, score spread) on seasons up to --train-end, picks the
role-warning threshold on the validation season, and scores the untouched test seasons. Each tracked player-game is paused at 10, 20, 30, 40 and 50 minutes
of elapsed time; "frozen" is the same model at kickoff with nothing observed. Scores: CRPS of the final stat, Brier score of beating a line set at the
frozen median, reliability by probability bin, and a block bootstrap by game. For the game itself: win-probability Brier and final-margin CRPS against
frozen pregame and against nflfastR's own in-game win probability. Writes docs/ingame_eval.json. Reads local files only.
"""
from __future__ import annotations

import argparse
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import betabinom, norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import ingame as G  # noqa: E402

CP = G.CHECKPOINTS


class Timeline:
    """Per-game arrays so a state at any elapsed second is a binary search."""

    def __init__(self, plays: pd.DataFrame, ev: pd.DataFrame):
        p = plays[plays["posteam"].notna() & plays["total_home_score"].notna()].copy()
        p["t"] = np.where(p["qtr"] >= 5, G.GAME + 1.0, G.GAME - p["game_seconds_remaining"])
        p = p.sort_values(["game_id", "t"], kind="stable")
        self.score = {}
        self.poss = {}
        for gid, g in p.groupby("game_id", sort=False):
            self.score[gid] = (g["t"].to_numpy(), g["total_home_score"].to_numpy(), g["total_away_score"].to_numpy())
            self.poss[gid] = (g["t"].to_numpy(), g["posteam"].to_numpy(), g["down"].to_numpy(), g["yardline_100"].to_numpy(), g["home_wp"].to_numpy())
        self.ev = {}
        for (gid, team, kind), g in ev.groupby(["gid", "team", "kind"], sort=False):
            self.ev[(gid, team, kind)] = g["t"].to_numpy()
        self.pl = {}
        for fam in G.FAMILIES:
            rows = G._fam_rows(ev, fam)
            for (gid, team, pid), g in rows.groupby(["gid", "team", "pid"], sort=False):
                self.pl[(fam, gid, team, pid)] = (g["t"].to_numpy(), g["yards"].to_numpy(), g["catch"].to_numpy())

    def scores(self, gid, t):
        ts, h, a = self.score[gid]
        i = np.searchsorted(ts, t, side="right") - 1
        return (float(h[i]), float(a[i])) if i >= 0 else (0.0, 0.0)

    def team_attempts(self, gid, team, kind, t):
        arr = self.ev.get((gid, team, kind))
        return 0 if arr is None else int(np.searchsorted(arr, t, side="right")), 0 if arr is None else len(arr)

    def player(self, fam, gid, team, pid, t):
        v = self.pl.get((fam, gid, team, pid))
        if v is None:
            return 0, 0.0, 0.0, 0, 0.0, 0.0
        ts, y, c = v
        k = int(np.searchsorted(ts, t, side="right"))
        return k, float(y[:k].sum()), float(c[:k].sum()), len(ts), float(y.sum()), float(c.sum())


def fit_params(train_plays, train_ev, games, tl, seed=0) -> G.Params:
    p = G.Params()
    for fam in G.FAMILIES:
        rows = G._fam_rows(train_ev, fam)
        p.pool[fam] = rows["yards"].to_numpy(dtype=float)
        p.pool_catch[fam] = float(rows["catch"].mean()) if fam != "rush" else 0.0
    tv = G.team_volume(train_ev, games[games["gid"].isin(train_ev["gid"].unique())])
    # team volume
    for kind, col in (("pass", "n_pass"), ("rush", "n_rush")):
        recs = []
        for r in tv.dropna(subset=["pre_" + col]).itertuples(index=False):
            for c in CP:
                A, tot = tl.team_attempts(r.gid, r.team, kind, c)
                h, a = tl.scores(r.gid, c)
                d = (h - a) if r.team == HOME[r.gid] else (a - h)
                recs.append((max(0.0, (G.GAME - c) / G.GAME), getattr(r, "pre_" + col), d, tot - A))
        G.fit_volume(pd.DataFrame(recs, columns=["rho", "pre", "d", "y"]), kind, p)
    # share prior strength by marginal likelihood of the opportunities still to come
    base = G.baselines(train_ev, tv, p.pool, p.pool_catch, p.m_eff, p.m_catch)
    for fam in G.FAMILIES:
        kind = "rush" if fam == "rush" else "pass"
        b = base[fam]
        samp = b.sample(min(len(b), 6000), random_state=seed)
        st = []
        for r in samp.itertuples(index=False):
            for c in (1200, 1800, 2400):
                O, Y, C, Of, Yf, Cf = tl.player(fam, r.gid, r.team, r.pid, c)
                A, At = tl.team_attempts(r.gid, r.team, kind, c)
                st.append((r.share, O, A, Of - O, At - A))
        st = np.array(st)
        best = None
        for kap in (1, 2, 3, 5, 8, 12, 20, 40, 80, 160, 320, 1000):
            a = np.clip(st[:, 0], 1e-4, 0.999) * kap + st[:, 1]
            bb = (1 - np.clip(st[:, 0], 1e-4, 0.999)) * kap + np.maximum(st[:, 2] - st[:, 1], 0)
            ll = betabinom.logpmf(st[:, 3], st[:, 4].astype(int), a, bb).sum()
            if best is None or ll > best[0]:
                best = (ll, kap)
        p.kappa[fam] = float(best[1])
    # efficiency shrinkage: choose pseudo-opportunities that minimise the error of rest-of-game yards given the opportunities that actually came
    for fam in G.FAMILIES:
        b = base[fam]
        samp = b.sample(min(len(b), 6000), random_state=seed + 1)
        st = []
        for r in samp.itertuples(index=False):
            for c in (1200, 1800, 2400):
                O, Y, C, Of, Yf, Cf = tl.player(fam, r.gid, r.team, r.pid, c)
                st.append((r.ypo, O, Y, Of - O, Yf - Y))
        st = np.array(st)
        errs = {}
        for m in (10, 25, 60, 120, 250, 600, 5000):
            ypo_post = (m * st[:, 0] + st[:, 2]) / (m + st[:, 1])
            errs[m] = float(np.mean((st[:, 4] - st[:, 3] * ypo_post) ** 2))
        p.m_eff[fam] = float(min(errs, key=errs.get))
    # catch rate
    st = []
    b = base["rec"].sample(min(len(base["rec"]), 6000), random_state=seed + 2)
    for r in b.itertuples(index=False):
        for c in (1200, 1800, 2400):
            O, Y, C, Of, Yf, Cf = tl.player("rec", r.gid, r.team, r.pid, c)
            st.append((r.cr, O, C, Of - O, Cf - C))
    st = np.array(st)
    e2 = {m: float(np.mean((st[:, 4] - st[:, 3] * ((m * st[:, 0] + st[:, 2]) / (m + st[:, 1]))) ** 2)) for m in (10, 25, 60, 120, 250, 600, 5000)}
    p.m_catch = float(min(e2, key=e2.get))
    # game level
    G.fit_game(train_plays, games, p)
    return p


def game_rows(plays, games, tl, p: G.Params) -> pd.DataFrame:
    """One row per game and checkpoint: score, possession, expected points of the drive in progress, final margin and total."""
    recs = []
    for g in games.itertuples(index=False):
        if g.gid not in tl.score or pd.isna(g.result):
            continue
        ts, poss, down, yl, hwp = tl.poss[g.gid]
        for c in CP:
            h, a = tl.scores(g.gid, c)
            i = np.searchsorted(ts, c, side="right") - 1
            ep = G.ep_of(p, down[i], yl[i]) if i >= 0 else 0.0
            sign = 1.0 if (i >= 0 and poss[i] == g.home) else -1.0
            recs.append((g.gid, g.season, c, h - a, h + a, sign * ep, float(hwp[i]) if i >= 0 else np.nan, g.spread, g.total_line, g.result, g.total))
    return pd.DataFrame(recs, columns=["gid", "season", "t", "margin_now", "total_now", "ep_home", "nfl_wp", "spread", "total_line", "result", "total"])


def fit_game_noise(gr: pd.DataFrame, p: G.Params) -> None:
    """Sign convention check, EP weight and score spread on the training seasons."""
    gr = gr.dropna(subset=["spread"])
    rho = (G.GAME - gr["t"]) / G.GAME
    resid = gr["result"] - gr["margin_now"] - gr["spread"] * rho
    x = (gr["ep_home"] * 1.0).to_numpy()
    p.gamma_ep = float(np.clip((x * resid).sum() / (x * x).sum(), 0.0, 1.5))
    r2 = resid - p.gamma_ep * x
    p.sigma_m = float(np.sqrt(np.mean(r2 ** 2 / rho.clip(lower=0.05))))


def block_ci(df: pd.DataFrame, col: str, reps: int = 2000, seed: int = 0):
    """Mean and 95% interval of `col` resampling whole games."""
    rng = np.random.default_rng(seed)
    g = df.groupby("gid")[col].agg(["sum", "count"])
    s, n = g["sum"].to_numpy(), g["count"].to_numpy()
    idx = rng.integers(0, len(g), (reps, len(g)))
    boots = s[idx].sum(axis=1) / n[idx].sum(axis=1)
    return float(s.sum() / n.sum()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def reliability(prob: np.ndarray, hit: np.ndarray, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (prob >= lo) & (prob < hi if hi < 1 else prob <= hi)
        if m.sum():
            out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(m.sum()), "predicted": round(float(prob[m].mean()), 3), "observed": round(float(hit[m].mean()), 3)})
    return out


def score_players(p, base, games, tl, M=300):
    rows = []
    for fam, b in base.items():
        kind = "rush" if fam == "rush" else "pass"
        for r in b.itertuples(index=False):
            for c in CP:
                O, Y, C, Of, Yf, Cf = tl.player(fam, r.gid, r.team, r.pid, c)
                A, At = tl.team_attempts(r.gid, r.team, kind, c)
                h, a = tl.scores(r.gid, c)
                is_home = r.gid in HOME and HOME[r.gid] == r.team
                d = (h - a) if is_home else (a - h)
                pre_vol = PRE_VOL[(r.gid, r.team, kind)]
                st = G.PlayerState(fam, r.mu_O, r.share, r.ypo, r.cr, O, Y, C, A, c, d, pre_vol)
                st0 = G.PlayerState(fam, r.mu_O, r.share, r.ypo, r.cr, 0, 0.0, 0.0, 0, 0.0, 0.0, pre_vol)
                seed = zlib.crc32(f"{r.gid}{r.pid}{c}".encode())
                up = G.predict_player(p, st, M, seed)
                nl = G.predict_player(p, G.PlayerState(fam, r.mu_O, r.share, r.ypo, r.cr, 0, 0.0, 0.0, 0, c, d, pre_vol), M, seed + 2)   # clock and score known, nothing learned about him
                nl_y = Y + nl["yards"]
                fr = G.predict_player(p, st0, M, seed + 1)
                line = np.floor(np.median(fr["yards"])) + 0.5
                rows.append({"gid": r.gid, "fam": fam, "t": c, "pid": r.pid, "actual": Yf,
                             "crps_up": G.crps_samples(up["yards"], Yf), "crps_fr": G.crps_samples(fr["yards"], Yf), "crps_nl": G.crps_samples(nl_y, Yf), "mean_nl": float(nl_y.mean()), "p_nl": float((nl_y > line).mean()),
                             "mean_up": float(up["yards"].mean()), "mean_fr": float(fr["yards"].mean()), "pace": (Y / c * G.GAME) if c else 0.0, "line": line,
                             "p_up": float((up["yards"] > line).mean()), "p_fr": float((fr["yards"] > line).mean()), "hit": float(Yf > line),
                             "share_pre": r.share, **{k: v for k, v in G.role_check(p, st).items() if k in ("p_lower", "p_higher", "share_post")},
                             "O_rem": Of - O, "A_rem": At - A, "A_seen": A, "O_seen": O})
    return pd.DataFrame(rows)


HOME: dict = {}
PRE_VOL: dict = {}


def role_eval(ps: pd.DataFrame) -> dict:
    """Do role warnings point at players whose share of the rest of the game really differs from pregame? Precision, and warnings per game, at 30 and 40 minutes."""
    out = {}
    for thr in (0.9, 0.95, 0.99):
        for c in (1800, 2400):
            x = ps[(ps["t"] == c) & (ps["A_seen"] >= 12) & (ps["A_rem"] >= 8)].copy()
            x["rem_share"] = x["O_rem"] / x["A_rem"]
            low, high = x[x["p_lower"] >= thr], x[x["p_higher"] >= thr]
            games = max(x["gid"].nunique(), 1)
            out[f"p>={thr} @{c // 60}min"] = {
                "warnings_per_game": round((len(low) + len(high)) / games, 2),
                "lower_n": int(len(low)), "lower_precision": round(float((low["rem_share"] < 0.8 * low["share_pre"]).mean()), 3) if len(low) else None,
                "higher_n": int(len(high)), "higher_precision": round(float((high["rem_share"] > 1.25 * high["share_pre"]).mean()), 3) if len(high) else None,
                "base_rate_lower": round(float((x["rem_share"] < 0.8 * x["share_pre"]).mean()), 3), "base_rate_higher": round(float((x["rem_share"] > 1.25 * x["share_pre"]).mean()), 3)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-start", type=int, default=2018)
    ap.add_argument("--train-end", type=int, default=2023)
    ap.add_argument("--valid", type=int, nargs="*", default=[2024])
    ap.add_argument("--test", type=int, nargs="*", default=[2025, 2026])
    ap.add_argument("--max-test-games", type=int, default=0)
    a = ap.parse_args()
    seasons = list(range(a.train_start, a.train_end + 1)) + a.valid + a.test
    plays = G.load_plays(seasons)
    ev = G.events(plays)
    games = G.games_table(plays)
    tl = Timeline(plays, ev)
    HOME.update({r.gid: r.home for r in games.itertuples(index=False)})
    tv_all = G.team_volume(ev, games)
    for r in tv_all.itertuples(index=False):
        PRE_VOL[(r.gid, r.team, "pass")] = 0.0 if pd.isna(r.pre_n_pass) else r.pre_n_pass
        PRE_VOL[(r.gid, r.team, "rush")] = 0.0 if pd.isna(r.pre_n_rush) else r.pre_n_rush
    tr = plays["season"] <= a.train_end
    p = fit_params(plays[tr], ev[ev["season"] <= a.train_end], games[games["season"] <= a.train_end], tl)
    gr = game_rows(plays, games, tl, p)
    fit_game_noise(gr[gr["season"] <= a.train_end], p)
    report = {"fit_seasons": [a.train_start, a.train_end], "validation": a.valid, "test": a.test,
              "params": {"kappa": p.kappa, "m_eff": p.m_eff, "m_catch": p.m_catch, "vol_theta": p.vol_theta, "sigma_m": p.sigma_m, "gamma_ep": p.gamma_ep,
                         "vol_beta": {k: [round(float(x), 4) for x in v] for k, v in p.vol_beta.items()}}}
    print(json.dumps(report["params"], indent=1, default=float), flush=True)
    base = G.baselines(ev, tv_all, p.pool, p.pool_catch, p.m_eff, p.m_catch)
    for name, seas in (("validation", a.valid), ("test", a.test)):
        gset = set(games.loc[games["season"].isin(seas), "gid"])
        if name == "test" and a.max_test_games:
            gset = set(sorted(gset)[: a.max_test_games])
        bs = {f: b[b["gid"].isin(gset)] for f, b in base.items()}
        ps = score_players(p, bs, games, tl)
        ps.to_parquet(ROOT / "data" / "cache" / f"ingame_players_{name}.parquet")
        out = {"players": {}, "game": {}}
        for fam in G.FAMILIES:
            for c in CP:
                x = ps[(ps["fam"] == fam) & (ps["t"] == c)].assign(diff=lambda d: d["crps_fr"] - d["crps_up"])
                m, lo, hi = block_ci(x, "diff")
                x = x.assign(diff_nl=lambda d: d["crps_nl"] - d["crps_up"])
                mn, lon, hin = block_ci(x, "diff_nl")
                brier_n = (x["p_nl"] - x["hit"]) ** 2
                brier_u = (x["p_up"] - x["hit"]) ** 2
                brier_f = (x["p_fr"] - x["hit"]) ** 2
                out["players"][f"{fam}@{c // 60}min"] = {
                    "n": int(len(x)), "games": int(x["gid"].nunique()), "crps_frozen": round(float(x["crps_fr"].mean()), 3), "crps_updated": round(float(x["crps_up"].mean()), 3),
                    "crps_gain": round(m, 3), "gain_ci95": [round(lo, 3), round(hi, 3)],
                    "mae_frozen": round(float((x["mean_fr"] - x["actual"]).abs().mean()), 2), "mae_updated": round(float((x["mean_up"] - x["actual"]).abs().mean()), 2),
                    "mae_pace": round(float((x["pace"] - x["actual"]).abs().mean()), 2),
                    "brier_frozen": round(float(brier_f.mean()), 4), "brier_updated": round(float(brier_u.mean()), 4), "brier_clock_only": round(float(brier_n.mean()), 4),
                    "crps_clock_only": round(float(x["crps_nl"].mean()), 3), "gain_vs_clock_only": round(mn, 3), "gain_vs_clock_only_ci95": [round(lon, 3), round(hin, 3)],
                    "mae_clock_only": round(float((x["mean_nl"] - x["actual"]).abs().mean()), 2)}
        allx = ps.assign(diff=lambda d: d["crps_fr"] - d["crps_up"])
        m, lo, hi = block_ci(allx, "diff")
        out["players"]["all_checkpoints"] = {"n": int(len(allx)), "crps_gain": round(m, 3), "ci95": [round(lo, 3), round(hi, 3)]}
        allx = allx.assign(diff_nl=lambda d: d["crps_nl"] - d["crps_up"])
        mn, lon, hin = block_ci(allx, "diff_nl")
        out["players"]["all_checkpoints"]["gain_vs_clock_only"] = [round(mn, 3), round(lon, 3), round(hin, 3)]
        out["role_warnings"] = role_eval(ps)
        out["reliability_updated"] = reliability(ps["p_up"].to_numpy(), ps["hit"].to_numpy())
        out["reliability_frozen"] = reliability(ps["p_fr"].to_numpy(), ps["hit"].to_numpy())
        # game level
        g = gr[gr["gid"].isin(gset)].dropna(subset=["spread"]).copy()
        rho = (G.GAME - g["t"]) / G.GAME
        sd = p.sigma_m * np.sqrt(rho.clip(lower=1e-6))
        mean_up = g["margin_now"] + g["spread"] * rho + p.gamma_ep * g["ep_home"]
        g["p_up"] = norm.cdf(mean_up / sd)
        g["p_fr"] = norm.cdf(g["spread"] / p.sigma_m)
        g["hit"] = (g["result"] > 0).astype(float)
        g = g[g["result"] != 0]
        for col in ("p_up", "p_fr", "nfl_wp"):
            g["b_" + col] = (g[col] - g["hit"]) ** 2
        g["gain_vs_frozen"] = g["b_p_fr"] - g["b_p_up"]
        g["gain_vs_nfl"] = g["b_nfl_wp"] - g["b_p_up"]
        for c in CP:
            x = g[g["t"] == c]
            out["game"][f"{c // 60}min"] = {"n": int(len(x)), "brier_frozen": round(float(x["b_p_fr"].mean()), 4), "brier_updated": round(float(x["b_p_up"].mean()), 4),
                                            "brier_nflfastR": round(float(x["b_nfl_wp"].mean()), 4), "gain_vs_frozen_ci95": [round(v, 4) for v in block_ci(x, "gain_vs_frozen")],
                                            "gain_vs_nflfastR_ci95": [round(v, 4) for v in block_ci(x, "gain_vs_nfl")]}
        out["game_reliability_updated"] = reliability(g["p_up"].to_numpy(), g["hit"].to_numpy())
        report[name] = out
        print(name, json.dumps({k: v for k, v in out.items() if k in ("game",)}, indent=1, default=float), flush=True)
    (ROOT / "docs" / "ingame_eval.json").write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
