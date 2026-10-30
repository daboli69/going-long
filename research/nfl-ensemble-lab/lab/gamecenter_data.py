"""Game Center data: everything the dashboard shows, as plain Python and JSON. No Streamlit. Local files only, read-only.

The headline numbers follow the Kalshi betting market when it exists, because in our tests the market has been at least as accurate as our model.
Used by the web app (web/server.py) and by the Streamlit page (app/game_center.py).
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from .archive10 import ARCHIVE, canonical
from .config import CACHE_DIR, LAB_ROOT, RAW_DIR
from .gamecenter_meta import GLOSSARY, STAT_PLAIN, TEAM_COLORS, TEAM_NAMES
from .ingest import normalize_team

SEASON = 2026
ET = "America/New_York"
GAMES_PATH = CACHE_DIR / "games.parquet"
DEFAULT_SD = {"margin": 13.5, "total": 13.0}
STATUS_PLAIN = {"Out": ("Out", "red", "will not play"), "Injured Reserve": ("Out for weeks", "red", "on injured reserve"),
                "Doubtful": ("Doubtful", "amber", "very unlikely to play"), "Questionable": ("Questionable", "amber", "could go either way")}
STATUS_ORDER = {"Out": 0, "Injured Reserve": 1, "Doubtful": 2, "Questionable": 3}
POS_ORDER = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}
STAT_CODE = {"Passing yards": "pass_yds", "Rushing yards": "rush_yds", "Receiving yards": "rec_yds", "Receptions": "rec", "Catches": "rec"}
GID_PATTERN = r"^\d{4}_\d{2}_[A-Z]{2,3}_[A-Z]{2,3}$"


# --------------------------------------------------------------------------- generic helpers

def clean(x):
    """Make anything JSON-safe: numpy to Python, NaN/inf to None, Timestamps to ISO text."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if (math.isnan(float(x)) or math.isinf(float(x))) else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    if x is pd.NaT:
        return None
    return x


def p_over(mu: float, sd: float, line: float) -> float:
    return float(1 - norm.cdf((line - mu) / sd))


def kickoff_label(ts: pd.Timestamp) -> str:
    return ts.strftime("%a %I:%M %p").replace(" 0", " ")


def read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


_cache: dict = {}


def _cached(key, fingerprint, build):
    hit = _cache.get(key)
    if hit and hit[0] == fingerprint:
        return hit[1]
    value = build()
    _cache[key] = (fingerprint, value)
    return value


def _mt(path: Path) -> int:
    try:
        return Path(path).stat().st_mtime_ns
    except OSError:
        return 0


# --------------------------------------------------------------------------- loading

def games_table(path: Path | None = None) -> pd.DataFrame:
    path = Path(path or GAMES_PATH)
    if not path.exists():
        return pd.DataFrame()

    def build():
        g = pd.read_parquet(path)
        g["kickoff_utc"] = pd.to_datetime(g["kickoff_utc"], utc=True)
        g["kickoff_et"] = g["kickoff_utc"].dt.tz_convert(ET)
        return g.sort_values("kickoff_utc").reset_index(drop=True)
    return _cached(("games", str(path)), _mt(path), build)


def load_freezes(kind: str, root: Path | None = None) -> dict:
    """{(season, week): record} for the latest archive of each week; each record carries a recomputed hash check."""
    root = Path(root or ARCHIVE)
    files = sorted((root / kind).glob("*.json"))

    def build():
        out = {}
        recs = []
        for p in files:
            d = read_json(p)
            if not d or "content" not in d:
                continue
            ok = hashlib.sha256(canonical(d["content"])).hexdigest() == d.get("content_sha256")
            recs.append({"frozen_at": d.get("frozen_at") or d.get("archived_at"), "content": d["content"], "hash_ok": ok, "file": p.name})
        for r in sorted(recs, key=lambda r: r["frozen_at"] or ""):
            out[(int(r["content"]["season"]), int(r["content"]["week"]))] = r
        return out
    return _cached(("freeze", kind, str(root)), tuple((p.name, _mt(p)) for p in files), build)


def injuries_now(raw: Path | None = None) -> tuple[pd.DataFrame, str | None]:
    raw = Path(raw or RAW_DIR)
    files = sorted(glob.glob(str(raw / "archive" / "espn_injuries_*.json")))
    if not files:
        return pd.DataFrame(), None
    f = files[-1]

    def build():
        c = json.loads(Path(f).read_text(encoding="utf-8"))
        rows = []
        for t in c.get("injuries", []):
            for e in t.get("injuries", []):
                a = e.get("athlete", {})
                team = (a.get("team") or {}).get("abbreviation") if isinstance(a.get("team"), dict) else None
                try:
                    team = normalize_team(team) if team else team
                except ValueError:
                    pass
                pos = (a.get("position") or {}).get("abbreviation") if isinstance(a.get("position"), dict) else None
                rows.append({"team": team, "player": a.get("displayName"), "pos": pos, "status": e.get("status"), "note": e.get("shortComment") or ""})
        return pd.DataFrame(rows)
    return _cached(("inj", f), _mt(Path(f)), build), Path(f).name.split("_")[-1][:13]


def preview_table() -> pd.DataFrame:
    try:
        from .props import weekly as W
        files = list((W.OUT / "preview").glob("*/*.parquet"))
        if not files:
            return pd.DataFrame()
        return _cached(("preview",), tuple(sorted((f.name, _mt(f)) for f in files)), lambda: W.load_archive(preview=True))
    except Exception:
        return pd.DataFrame()


def kpis() -> dict:
    files = [LAB_ROOT / "reports" / "homewin_deep" / "backtest.json", LAB_ROOT / "reports" / "forecast" / "results.json", GAMES_PATH,
             CACHE_DIR / "homewin_deep" / "kalshi_history.parquet", CACHE_DIR / "homewin_deep" / "walk_forward.parquet"]

    def build():
        out = {}
        bt = read_json(files[0])
        if bt:
            try:
                out["elo_acc_long"] = {"accuracy": bt["models"]["elo"]["accuracy"], "games": bt["models"]["elo"]["n"], "window": bt["window"]}
            except KeyError:
                pass
        try:
            hist = pd.read_parquet(files[3])
            g = pd.read_parquet(GAMES_PATH)
            g = g[g["completed"] & ~g["tie"].astype(bool)].set_index("game_id")
            h = hist[hist["ts"] <= hist["kickoff_utc"] - pd.Timedelta(minutes=90)].sort_values("ts")
            w = h.groupby(["gid", "side"])["mid"].last().unstack()
            p = (w["home"] / (w["home"] + w["away"])).dropna()
            p = p[p.index.isin(g.index)]
            y = g.loc[p.index, "home_win"].astype(float)
            wf = pd.read_parquet(files[4]).set_index("gid")
            common = p.index.intersection(wf.index)
            out["market_acc"] = {"accuracy": float(((p[common] >= 0.5) == (y[common] == 1)).mean()), "games": int(len(common)),
                                 "elo_accuracy_same_games": float(((wf.loc[common, "p_elo"] >= 0.5) == (y[common] == 1)).mean())}
        except Exception:
            pass
        fr = read_json(files[1])
        if fr:
            pn = fr.get("pinnacle_descriptive")
            if pn:
                out["margin_miss"] = {"market": pn["margin_mae"]["kalshi"], "model": pn["margin_mae"]["model"], "games": pn["games"]}
            cov = fr.get("prop_interval_coverage")
            if cov:
                out["range_hit"] = {k: v["raw_80_coverage"] for k, v in cov.items()}
        return out
    return _cached(("kpis",), tuple(_mt(f) for f in files), build)


# --------------------------------------------------------------------------- per-game logic

def team_summary(g: pd.DataFrame, team: str) -> dict:
    d = g[g["completed"] & ((g["home_team"] == team) | (g["away_team"] == team))].sort_values("kickoff_utc")
    w = l = t = 0
    pf = pa = 0.0
    last = []
    for r in d.itertuples(index=False):
        mine, theirs = (r.home_score, r.away_score) if r.home_team == team else (r.away_score, r.home_score)
        pf, pa = pf + mine, pa + theirs
        res = "W" if mine > theirs else "L" if mine < theirs else "T"
        w, l, t = w + (res == "W"), l + (res == "L"), t + (res == "T")
        opp = r.away_team if r.home_team == team else r.home_team
        last.append(f"{res} {int(mine)}-{int(theirs)} {'vs' if r.home_team == team else 'at'} {opp}")
    n = len(d)
    return {"record": f"{w}-{l}" + (f"-{t}" if t else ""), "games": n, "pf": pf / n if n else None, "pa": pa / n if n else None, "last": last[-5:][::-1]}


def best_numbers(row, fz: dict | None) -> dict:
    """Headline win chance, margin and total, each with a plain label of where it came from."""
    out = {"p_home": None, "p_label": None, "mu_m": None, "m_label": None, "mu_t": None, "t_label": None, "sd_m": DEFAULT_SD["margin"], "sd_t": DEFAULT_SD["total"]}
    if fz:
        mod = fz["model"]
        out["sd_m"], out["sd_t"] = float(mod["sd_m"]), float(mod["sd_t"])
        if fz.get("kalshi_winner_p_home") is not None:
            out["p_home"], out["p_label"] = float(fz["kalshi_winner_p_home"]), "the Kalshi betting market"
        if fz.get("margin"):
            out["mu_m"], out["m_label"] = float(fz["margin"]["mu_kalshi"]), "the Kalshi betting market"
        if fz.get("total"):
            out["mu_t"], out["t_label"] = float(fz["total"]["mu_kalshi"]), "the Kalshi betting market"
    if out["p_home"] is None and pd.notna(row.get("market_p_home_novig")):
        out["p_home"], out["p_label"] = float(row["market_p_home_novig"]), "sportsbook lines"
    if out["mu_m"] is None and pd.notna(row.get("spread_line")):
        out["mu_m"], out["m_label"] = float(row["spread_line"]), "sportsbook lines"
    if out["mu_t"] is None and pd.notna(row.get("total_line")):
        out["mu_t"], out["t_label"] = float(row["total_line"]), "sportsbook lines"
    if fz:
        mod = fz["model"]
        if out["p_home"] is None:
            out["p_home"], out["p_label"] = float(mod["p_elo"]), "Elo team ratings"
        if out["mu_m"] is None:
            out["mu_m"], out["m_label"] = float(mod["mu_m"]), "our model"
        if out["mu_t"] is None:
            out["mu_t"], out["t_label"] = float(mod["mu_t"]), "our model"
    return out


def pmf(mu: float, sd: float, lo: int, hi: int) -> list[dict]:
    x = np.arange(lo, hi + 1)
    p = norm.cdf((x + 0.5 - mu) / sd) - norm.cdf((x - 0.5 - mu) / sd)
    return [{"x": int(a), "p": float(b)} for a, b in zip(x, p)]


def _outcomes(b: dict, home: str, away: str) -> list[dict]:
    mu_m, mu_t, sm, stt, p_home = b["mu_m"], b["mu_t"], b["sd_m"], b["sd_t"], b["p_home"]
    fav, sign = (home, 1) if mu_m >= 0 else (away, -1)
    line_t = round(mu_t * 2) / 2
    close = norm.cdf((3.5 - mu_m) / sm) - norm.cdf((-3.5 - mu_m) / sm)
    return [{"label": "Game is decided by 3 points or fewer", "p": float(close)},
            {"label": f"{fav} wins by 7 or more", "p": p_over(sign * mu_m, sm, 6.5)},
            {"label": f"{fav} wins by 10 or more", "p": p_over(sign * mu_m, sm, 9.5)},
            {"label": "Underdog wins outright", "p": float(1 - (p_home if fav == home else 1 - p_home))},
            {"label": f"Both teams combine for more than {line_t:g} points", "p": p_over(mu_t, stt, line_t)},
            {"label": f"Both teams combine for fewer than {line_t:g} points", "p": 1 - p_over(mu_t, stt, line_t)}]


def _lean(fz: dict | None, home: str, away: str) -> dict | None:
    if not fz or not fz.get("margin"):
        return None
    m = fz["margin"]
    diff = m["mu_model"] - m["mu_kalshi"]
    if m["abstain"]:
        return {"abstain": True, "diff_points": float(diff), "toward": None,
                "text": f"No strong opinion. Our model expects the margin within {abs(diff):.1f} points of the market, so we go with the market."}
    who = home if diff > 0 else away
    return {"abstain": False, "diff_points": float(diff), "toward": who,
            "text": f"Our model disagrees with the market. It likes {who} by about {abs(diff):.1f} more points than the market does. "
                    "In our tests this kind of disagreement has not beaten the market, so treat it as something to think about, not a tip."}


def _ladders(fz: dict | None, home: str) -> dict:
    out = {"margin": [], "total": []}
    if not fz:
        return out
    mod = fz["model"]
    if fz.get("margin"):
        m = fz["margin"]
        th = sorted(sorted(m["thresholds"], key=lambda x: abs(x["c"] - m["mu_kalshi"]))[:9], key=lambda x: x["c"])
        out["margin"] = [{"question": f"{home} wins by more than {t['c']:g}" if t["c"] >= 0 else f"{home} loses by fewer than {abs(t['c']):g}",
                          "market": float(t["p_kalshi"]), "model": p_over(mod["mu_m"], mod["sd_m"], t["c"])} for t in th]
    if fz.get("total"):
        m = fz["total"]
        th = sorted(sorted(m["thresholds"], key=lambda x: abs(x["c"] - m["mu_kalshi"]))[:9], key=lambda x: x["c"])
        out["total"] = [{"question": f"Total points go over {t['c']:g}", "market": float(t["p_kalshi"]), "model": p_over(mod["mu_t"], mod["sd_t"], t["c"])} for t in th]
    return out


def _injury_lists(inj: pd.DataFrame, teams: tuple[str, str]) -> dict:
    out = {}
    for team in teams:
        d = inj[(inj["team"] == team) & inj["status"].isin(STATUS_PLAIN)].copy() if not inj.empty else pd.DataFrame()
        rows = []
        if not d.empty:
            d["o"] = d["status"].map(STATUS_ORDER)
            d["p"] = d["pos"].map(POS_ORDER).fillna(9)
            for r in d.sort_values(["o", "p"]).head(14).itertuples(index=False):
                label, tone, expl = STATUS_PLAIN[r.status]
                note = (r.note[:160] + "…") if len(r.note) > 160 else r.note
                rows.append({"player": r.player, "pos": r.pos, "status": label, "tone": tone, "meaning": expl, "note": note})
        out[team] = rows
    return out


def _props(gid: str, home: str, away: str, props_fz: dict | None) -> list[dict]:
    prev = preview_table()
    if prev.empty or gid not in set(prev["game_id"]):
        return []
    from .props import weekly as W
    sub = prev[prev["game_id"] == gid].drop(columns=[c for c in ("_src",) if c in prev])
    t = W.projection_table(sub, keep_pid=True)
    ladders = {}
    if props_fz:
        for lad in props_fz["content"]["ladders"]:
            if lad["gid"] == gid:
                ladders[(lad["pid"], lad["stat"])] = lad
    rows = []
    for _, r in t.sort_values("v2 median", ascending=False).head(60).iterrows():
        lad = ladders.get((r["Player ID"], STAT_CODE.get(r["Stat"], "")))
        line = mchance = ochance = None
        if lad:
            cand = [th for th in lad["thresholds"] if th.get("mid") is not None]
            if cand:
                th = min(cand, key=lambda x: abs(x["mid"] - 0.5))
                line, mchance, ochance = th["k"], th["mid"], th.get("p_corr", th.get("p_sim"))
        lo, hi = (str(r["v2 10-90%"]).split(" - ") + [None, None])[:2]
        rows.append({"player": r["Player"], "team": r["Team"], "stat": r["Stat"], "typical": float(r["v2 median"]),
                     "range_low": float(lo) if lo else None, "range_high": float(hi) if hi else None, "market_line": line, "market_chance": mchance, "our_chance": ochance})
    return rows


# --------------------------------------------------------------------------- public API (what the web app calls)

def meta() -> dict:
    G = games_table()
    if G.empty:
        return {"ok": False, "reason": "The games table is missing. Open the Streamlit page 'Update NFL data' to download it."}
    G = G[(G["season"] == SEASON) & (G["game_type"] == "REG")]
    now = pd.Timestamp.now(tz="UTC")
    up = G[G["kickoff_utc"] > now]
    weeks = sorted(int(w) for w in G["week"].unique())
    default = int(up["week"].min()) if len(up) else weeks[-1]
    fz = load_freezes("forecast_games")
    saved = {w: r["frozen_at"] for (s, w), r in fz.items() if s == SEASON}
    return {"ok": True, "season": SEASON, "weeks": weeks, "default_week": default, "forecast_saved_at": saved, "kpis": kpis(),
            "reality_check": "Over the last two seasons the betting market has been at least as accurate as our model, so every headline number follows the market "
                             "and our model is shown next to it. Nothing here is betting advice."}


def week_games(week: int) -> list[dict]:
    G = games_table()
    G = G[(G["season"] == SEASON) & (G["game_type"] == "REG") & (G["week"] == week)]
    fz_rec = load_freezes("forecast_games").get((SEASON, week))
    fzg = {g["gid"]: g for g in fz_rec["content"]["games"]} if fz_rec else {}
    now = pd.Timestamp.now(tz="UTC")
    out = []
    for _, r in G.iterrows():
        b = best_numbers(r, fzg.get(r["game_id"]))
        out.append({"gid": r["game_id"], "away": r["away_team"], "home": r["home_team"], "away_color": TEAM_COLORS.get(r["away_team"]), "home_color": TEAM_COLORS.get(r["home_team"]),
                    "kickoff_utc": r["kickoff_utc"], "kickoff_label": kickoff_label(r["kickoff_et"]),
                    "completed": bool(r["completed"]), "started": bool(r["kickoff_utc"] <= now), "away_score": r["away_score"] if r["completed"] else None,
                    "home_score": r["home_score"] if r["completed"] else None, "p_home": b["p_home"], "p_label": b["p_label"]})
    return clean(out)


def game_detail(gid: str) -> dict | None:
    G = games_table()
    G = G[(G["season"] == SEASON) & (G["game_type"] == "REG")]
    match = G[G["game_id"] == gid]
    if match.empty:
        return None
    row = match.iloc[0]
    away, home, week = row["away_team"], row["home_team"], int(row["week"])
    fz_rec = load_freezes("forecast_games").get((SEASON, week))
    fz = next((g for g in fz_rec["content"]["games"] if g["gid"] == gid), None) if fz_rec else None
    pr_rec = load_freezes("props_kalshi").get((SEASON, week))
    b = best_numbers(row, fz)
    summ = {t: team_summary(G, t) for t in (away, home)}
    d = {"gid": gid, "week": week, "away": away, "home": home, "away_name": TEAM_NAMES.get(away, away), "home_name": TEAM_NAMES.get(home, home),
         "away_color": TEAM_COLORS.get(away), "home_color": TEAM_COLORS.get(home), "kickoff_utc": row["kickoff_utc"],
         "date_label": row["kickoff_et"].strftime("%A, %b %d").replace(" 0", " "), "kickoff_label": kickoff_label(row["kickoff_et"]), "stadium": row.get("stadium") or "",
         "completed": bool(row["completed"]), "away_score": row["away_score"] if row["completed"] else None, "home_score": row["home_score"] if row["completed"] else None,
         "forecast_saved_at": fz_rec["frozen_at"] if fz_rec else None, "forecast_hash_ok": fz_rec["hash_ok"] if fz_rec else None,
         "records": {away: summ[away]["record"], home: summ[home]["record"]}, "matchup": {away: summ[away], home: summ[home]},
         "has_forecast": b["p_home"] is not None}
    if b["p_home"] is None:
        return clean(d)
    p_home = b["p_home"]
    favored, p_fav = (home, p_home) if p_home >= 0.5 else (away, 1 - p_home)
    srcs = [("Betting market (Kalshi)", fz and fz.get("kalshi_winner_p_home")), ("Our model", fz and fz["model"]["p_win"]), ("Elo team ratings", fz and fz["model"]["p_elo"]),
            ("ESPN's forecast (FPI)", fz and fz.get("fpi_p_home"))]
    sources = [{"name": n, "p_home": float(v)} for n, v in srcs if v is not None]
    gap = (max(s["p_home"] for s in sources) - min(s["p_home"] for s in sources)) * 100 if sources else 0.0
    d["headline"] = {"p_home": p_home, "p_label": b["p_label"], "favored": favored, "favored_name": TEAM_NAMES.get(favored, favored), "p_favored": p_fav}
    d["sources"] = sources
    d["agreement"] = {"gap_points": gap, "agree": bool(gap <= 6)}
    exp = {"margin": b["mu_m"], "margin_label": b["m_label"], "total": b["mu_t"], "total_label": b["t_label"], "sd_m": b["sd_m"], "sd_t": b["sd_t"]}
    if b["mu_m"] is not None and b["mu_t"] is not None:
        exp["home_pts"], exp["away_pts"] = (b["mu_t"] + b["mu_m"]) / 2, (b["mu_t"] - b["mu_m"]) / 2
        d["outcomes"] = _outcomes(b, home, away)
        d["distribution"] = {"margin": pmf(b["mu_m"], b["sd_m"], -40, 40), "total": pmf(b["mu_t"], b["sd_t"], 10, 90)}
    d["expected"] = exp
    d["lean"] = _lean(fz, home, away)
    d["ladders"] = _ladders(fz, home)
    inj, stamp = injuries_now()
    d["injuries"] = {"stamp": stamp, "teams": _injury_lists(inj, (away, home))}
    d["props"] = _props(gid, home, away, pr_rec)
    if d["completed"]:
        won = home if row["home_score"] > row["away_score"] else away if row["away_score"] > row["home_score"] else "Tie"
        d["result"] = {"winner": won, "favorite_won": bool(won == favored)}
    return clean(d)


def glossary() -> list[dict]:
    return [{"term": t, "text": x} for t, x in GLOSSARY]
