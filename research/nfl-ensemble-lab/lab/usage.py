"""Who gets the ball for each team, and where a missing player's production goes. Measured from local play-by-play.

Usage is a share model. Over the team's last six games, each player's share of the team's receiving yards, catches and
rushing yards is averaged over the games he played. Shares of the players expected to play (played the team's most
recent game, or at least half the window) are scaled to add up to 100% and multiplied by the team's per-game totals,
so every yard of a team's projection belongs to a named player.

When players are ruled out (official report Out or Doubtful), the team keeps a fraction k of their share. Of that, a
fraction `to_new` goes to the player who replaces him (someone without recent snaps: a call-up or the next man on the
depth chart), and the rest goes to the regulars in proportion to their share times a position weight m (a missing WR's
share leans toward other WRs). k, to_new and m are measured on real absences. `evaluate` fits them on one season and
scores every rule on later games only; scripts/redistribution_check.py writes the results and the fitted rule.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from .config import CACHE_DIR, RAW_DIR
from .ingest import normalize_team

STATS = ("rec_yds", "rec", "rush_yds")
POS_GROUP = {"WR": "WR", "TE": "TE", "RB": "RB", "FB": "RB", "HB": "RB", "QB": "QB"}
WINDOW = 6
RELEVANT = 0.08  # a missing player matters for a stat when his share of it is at least 8%
SHRINK_GAMES = 8  # absence games of evidence before a team's own rate counts as much as the league rate
K_GRID = np.round(np.arange(0.0, 1.31, 0.05), 2)
RULE_PATH = CACHE_DIR / "redistribution_rule.json"


def _team(t):
    return normalize_team(t) if isinstance(t, str) else t


def positions() -> dict:
    path = RAW_DIR / "players.parquet"
    if not path.exists():
        return {}
    return D._cached(("positions",), D._mt(path), lambda: {k: POS_GROUP.get(v, "OTHER") for k, v in
                                                           pd.read_parquet(path, columns=["gsis_id", "position"]).dropna().values})


def player_games(seasons) -> pd.DataFrame:
    from .gamesim import player_games as pg
    frames = [pg(s).assign(season=s) for s in seasons if len(pg(s))]
    if not frames:
        return pd.DataFrame()
    g = pd.concat(frames, ignore_index=True)
    g["pos"] = g["pid"].map(positions()).fillna("OTHER")
    return g


def official_out(seasons) -> pd.DataFrame:
    frames = []
    for s in seasons:
        path = RAW_DIR / f"injuries_{s}.parquet"
        if path.exists():
            r = pd.read_parquet(path, columns=["season", "team", "week", "gsis_id", "report_status"])
            frames.append(r[r["report_status"].isin(["Out", "Doubtful"])])
    if not frames:
        return pd.DataFrame(columns=["season", "team", "week", "gsis_id"])
    r = pd.concat(frames, ignore_index=True)
    r["team"] = r["team"].map(_team)
    return r


@dataclass
class Usage:
    team: str
    games: int
    totals: dict            # team per-game average of each stat, plus pass_yds, att and carries
    players: pd.DataFrame   # pid, pos, n, active, share_<stat>, and per-game-played pass_yds, att, carries, rush_yds


def usage(g: pd.DataFrame, season: int, team: str, week: int) -> Usage | None:
    t = g[(g["season"] == season) & (g["posteam"] == team) & (g["week"] < week)]
    weeks = sorted(t["week"].unique())[-WINDOW:]
    if not weeks:
        return None
    t = t[t["week"].isin(weeks)]
    per_game = t.groupby("week")[[*STATS, "pass_yds", "att", "carries"]].sum()
    totals = per_game.mean().to_dict()
    t = t.join(per_game[list(STATS)].add_prefix("team_"), on="week")
    for s in STATS:
        t[f"share_{s}"] = np.where(t[f"team_{s}"] > 0, t[s] / t[f"team_{s}"].where(t[f"team_{s}"] > 0, 1), 0.0)
    p = t.groupby("pid").agg(pos=("pos", "first"), n=("week", "nunique"), last=("week", "max"),
                             **{f"share_{s}": (f"share_{s}", "mean") for s in STATS},
                             pass_yds=("pass_yds", "mean"), att=("att", "mean"), carries=("carries", "mean"),
                             rush_pg=("rush_yds", "mean")).reset_index()
    p["active"] = (p["last"] == weeks[-1]) | (p["n"] >= int(np.ceil(len(weeks) / 2)))
    return Usage(team, len(weeks), totals, p)


# --------------------------------------------------------------------------- redistribution rules

@dataclass
class Rule:
    name: str
    k: dict = field(default_factory=lambda: {s: 1.0 for s in STATS})        # share of a missing player's production the team keeps
    to_new: dict = field(default_factory=dict)                               # part of the kept share that goes to his replacement
    m: dict = field(default_factory=dict)                                    # {"WR->TE": weight}
    team_k: dict = field(default_factory=dict)                               # {"TEN|rec_yds": k}

    def k_for(self, team: str, stat: str) -> float:
        return self.team_k.get(f"{team}|{stat}", self.k.get(stat, 1.0))

    def project(self, u: Usage, out_ids: set) -> pd.DataFrame:
        """Per-game projection of each stat for every expected player not ruled out, plus one replacement row per
        position that lost a player (pid "NEW:<pos>"). Also returns, per out player, where his share went."""
        p = u.players[u.players["active"]].copy()
        gone = p[p["pid"].isin(out_ids)]
        keep = p[~p["pid"].isin(out_ids)].copy().reset_index(drop=True)
        new_rows: dict[str, dict] = {}
        for s in STATS:
            col = f"share_{s}"
            norm = p[col].sum()
            if norm <= 0:
                keep[s] = 0.0
                continue
            share = keep[col] / norm
            k, tn = self.k_for(u.team, s), self.to_new.get(s, 0.0)
            for _, o in gone.iterrows():
                lost = o[col] / norm
                if lost <= 0 or k == 0:
                    continue
                w = share * keep["pos"].map(lambda q: self.m.get(f"{o['pos']}->{q}", 1.0))
                regular = k * (1 - tn) * lost if w.sum() > 0 else 0.0
                if w.sum() > 0:
                    share = share + regular * w / w.sum()
                row = new_rows.setdefault(o["pos"], {"pid": f"NEW:{o['pos']}", "pos": o["pos"], **{x: 0.0 for x in STATS}})
                row[s] += (k * lost - regular) * u.totals[s]
            keep[s] = share * u.totals[s]
        return pd.concat([keep, pd.DataFrame(list(new_rows.values()))], ignore_index=True) if new_rows else keep


def _team_games(seasons, min_week: int = 3):
    """Every team-game from `min_week` on: (season, week, team, usage, ids ruled out among expected players, actual)."""
    g = player_games(seasons)
    if g.empty:
        return []
    outs = official_out(seasons)
    out = []
    for (season, team, week), _ in g.groupby(["season", "posteam", "week"]):
        if week < min_week:
            continue
        u = usage(g, season, team, week)
        if u is None:
            continue
        o = set(outs[(outs["season"] == season) & (outs["team"] == team) & (outs["week"] == week)]["gsis_id"])
        act = u.players[u.players["active"]]
        actual = g[(g["season"] == season) & (g["posteam"] == team) & (g["week"] == week)].set_index("pid")
        lost = {}
        for s in STATS:
            norm = act[f"share_{s}"].sum()
            lost[s] = float(act[act["pid"].isin(o)][f"share_{s}"].sum() / norm) if norm > 0 else 0.0
        out.append({"season": int(season), "week": int(week), "team": team, "usage": u, "out": o & set(act["pid"]), "actual": actual, "lost": lost})
    return out


def _is_case(c) -> bool:
    return any(c["lost"][s] >= RELEVANT for s in STATS)


def measure_split(games) -> dict:
    """Per stat: share of a missing player's production taken by players with no recent snaps, beyond what they get anyway."""
    out = {}
    for s in STATS:
        def new_share(c):
            tot = c["actual"][s].sum() if s in c["actual"] else 0.0
            if tot <= 0:
                return np.nan
            return float(c["actual"][s][~c["actual"].index.isin(c["usage"].players["pid"])].sum() / tot)
        ab = [c for c in games if c["lost"][s] >= RELEVANT]
        ct = [c for c in games if c["lost"][s] == 0]
        if not ab or not ct:
            out[s] = 0.0
            continue
        extra = np.nanmean([new_share(c) for c in ab]) - np.nanmean([new_share(c) for c in ct])
        out[s] = float(np.clip(extra / np.mean([c["lost"][s] for c in ab]), 0.0, 1.0))
    return out


def _score(rule: Rule, cases) -> dict:
    """Per stat: per-player error for the regulars, how far off the replacements' total is, and the team total's average miss."""
    sq = {s: [] for s in STATS}
    ab = {s: [] for s in STATS}
    newmiss = {s: [] for s in STATS}
    bias = {s: [] for s in STATS}
    for c in cases:
        pred = rule.project(c["usage"], c["out"]).set_index("pid")
        window = set(c["usage"].players["pid"])
        regs = list((set(i for i in pred.index if not str(i).startswith("NEW:")) | (set(c["actual"].index) & window)) - c["out"])
        newcomers = [i for i in c["actual"].index if i not in window]
        for s in STATS:
            p = pred[s].reindex(regs).fillna(0).to_numpy()
            a = c["actual"][s].reindex(regs).fillna(0).to_numpy()
            sq[s] += list((p - a) ** 2)
            ab[s] += list(np.abs(p - a))
            pn = float(pred.loc[[i for i in pred.index if str(i).startswith("NEW:")], s].sum())
            an = float(c["actual"][s].reindex(newcomers).fillna(0).sum())
            newmiss[s].append(pn - an)
            bias[s].append(float(pred[s].sum()) - float(c["actual"][s].drop(index=list(c["out"]), errors="ignore").sum()))
    f = lambda v: float(np.mean(v)) if len(v) else float("nan")
    return {s: {"rmse": float(np.sqrt(np.mean(sq[s]))) if sq[s] else float("nan"), "mae": f(ab[s]),
                "replacement_bias": f(newmiss[s]), "replacement_abs": f(np.abs(newmiss[s])),
                "team_bias": f(bias[s]), "team_abs": f(np.abs(bias[s]))} for s in STATS}


def fit_k(cases, base: Rule) -> dict:
    """k per stat: the grid value whose team totals are unbiased on these absences (mean miss closest to zero)."""
    best = {}
    for s in STATS:
        errs = {k: abs(_score(Rule("k", k={**base.k, s: k}, to_new=base.to_new, m=base.m), cases)[s]["team_bias"]) for k in K_GRID}
        best[s] = float(min(errs, key=errs.get))
    return best


def fit_m(cases) -> dict:
    """Position weights: how much more of a missing player's share each position took than its usage alone predicts."""
    num, den = {}, {}
    for c in cases:
        u, o, a = c["usage"], c["out"], c["actual"]
        act = u.players[u.players["active"]]
        keep = act[~act["pid"].isin(o)]
        for s in ("rec_yds", "rush_yds"):
            col = f"share_{s}"
            norm = act[col].sum()
            team_actual = a[s].sum() if s in a else 0.0
            if norm <= 0 or team_actual <= 0:
                continue
            for _, out_p in act[act["pid"].isin(o)].iterrows():
                if out_p[col] / norm < RELEVANT:
                    continue
                for _, j in keep[keep[col] > 0].iterrows():
                    key = f"{out_p['pos']}->{j['pos']}"
                    num[key] = num.get(key, 0.0) + float(a[s].get(j["pid"], 0.0)) / team_actual - j[col] / norm
                    den[key] = den.get(key, 0.0) + j[col] / norm
    gain_tot, base_tot = {}, {}
    for key, v in num.items():
        po = key.split("->")[0]
        gain_tot[po] = gain_tot.get(po, 0.0) + v
        base_tot[po] = base_tot.get(po, 0.0) + den[key]
    m = {}
    for key, v in num.items():
        po = key.split("->")[0]
        if gain_tot[po] > 0 and den[key] > 0:
            m[key] = round(float(np.clip((v / gain_tot[po]) / (den[key] / base_tot[po]), 0.25, 4.0)), 3)
    return m


def fit_team_k(cases, base: Rule) -> dict:
    """Each team's own k (unbiased team totals on its absences), shrunk toward the league k by how many absences it has."""
    out = {}
    for team in sorted({c["team"] for c in cases}):
        sub = [c for c in cases if c["team"] == team]
        for s in STATS:
            errs = {k: abs(_score(Rule("k", k={**base.k, s: k}, to_new=base.to_new, m=base.m), sub)[s]["team_bias"]) for k in K_GRID}
            raw = float(min(errs, key=errs.get))
            out[f"{team}|{s}"] = round((len(sub) * raw + SHRINK_GAMES * base.k[s]) / (len(sub) + SHRINK_GAMES), 3)
    return out


def fit(games) -> Rule:
    cases = [c for c in games if _is_case(c)]
    to_new = measure_split(games)
    m = fit_m(cases)
    rule = Rule("Kept share, split to replacement, by usage and position", to_new=to_new, m=m)
    rule.k = fit_k(cases, rule)
    return rule


def evaluate(train_seasons=(2025,), test_seasons=(2026,)) -> dict:
    """Fit on train seasons, score every rule on test seasons only."""
    tr_games, te_games = _team_games(train_seasons), _team_games(test_seasons)
    train, test = [c for c in tr_games if _is_case(c)], [c for c in te_games if _is_case(c)]
    chosen = fit(tr_games)
    team = Rule("Same, with each team's own kept share", k=chosen.k, to_new=chosen.to_new, m=chosen.m, team_k=fit_team_k(train, chosen))
    rules = [Rule("No redistribution", k={s: 0.0 for s in STATS}),
             Rule("Old rule: 75% to the regulars, by usage", k={s: 0.75 for s in STATS}),
             Rule("All of it to the regulars, by usage", k={s: 1.0 for s in STATS}),
             Rule("All of it to the regulars, by usage and position", k={s: 1.0 for s in STATS}, m=chosen.m),
             chosen, team]
    scores = {r.name: _score(r, test) for r in rules}
    per_team = {}
    for t in sorted({c["team"] for c in tr_games}):
        sub = [c for c in test if c["team"] == t]
        per_team[t] = {"test_cases": len(sub), "train_cases": sum(1 for c in train if c["team"] == t),
                       "team_k": {s: team.k_for(t, s) for s in STATS},
                       "scores": {r.name: _score(r, sub) for r in (rules[0], rules[1], chosen, team)} if sub else {}}
    return {"train": list(train_seasons), "test": list(test_seasons), "train_cases": len(train), "test_cases": len(test),
            "rule": asdict(chosen), "scores": scores, "per_team": per_team}


# --------------------------------------------------------------------------- what the simulation uses

def save_rule(rule: Rule, fitted_on: list[int], path=RULE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fitted_on": fitted_on, "fitted_at": pd.Timestamp.now(tz="UTC").isoformat(), **asdict(rule)}, indent=1), encoding="utf-8")


def current_rule(path=RULE_PATH) -> tuple[Rule, dict]:
    """The rule the simulation applies (written by scripts/redistribution_check.py). Falls back to keeping all of a
    missing player's production with the regulars, by usage, which the 2026 check showed keeps team totals unbiased."""
    if path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        return Rule(d["name"], k=d["k"], to_new=d.get("to_new", {}), m=d.get("m", {}), team_k=d.get("team_k", {})), d
    return Rule("All of it to the regulars, by usage", k={s: 1.0 for s in STATS}), {}
