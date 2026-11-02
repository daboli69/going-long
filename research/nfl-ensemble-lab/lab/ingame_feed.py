"""Live side of the in-game tracker: read saved ESPN snapshots, freeze pregame projections, and update them.

Nothing here is invented: a field the feed does not show is None, and a player the lab cannot match to a player id by name is listed, not guessed.
Snaps and routes are not in the ESPN summary, so opportunity means targets, carries and pass attempts from the box score.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import types
from pathlib import Path

import numpy as np
import pandas as pd

from . import gamecenter_data as D
from . import gamesim as S
from . import ingame as G
from . import ingame2 as I2
from .ingest import normalize_team

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "data" / "raw" / "ingame"
FROZEN = ROOT / "ingame" / "frozen"
LEDGER = ROOT / "ingame" / "ledger.jsonl"


# --------------------------------------------------------------------------- reading snapshots

def snapshots(eid: str) -> list[tuple[str, Path]]:
    return [(p.name.split(".")[0], p) for p in sorted((CAPTURE / eid).glob("*.json.gz"))]


def load(path: Path) -> dict:
    with gzip.open(path, "rb") as f:
        return json.loads(f.read())


def _secs(clock: str | None) -> float | None:
    m = re.fullmatch(r"(\d+):(\d+)", clock or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _td_sentence(text: str) -> str:
    """The sentence of a scoring play that describes the touchdown, without the formation notes before it or the extra point after it."""
    for sent in re.split(r"(?<=[.])\s+", text.strip()):
        if "TOUCHDOWN" in sent.upper():
            return re.split(r"(?<=TOUCHDOWN)", sent, flags=re.I)[0].strip()
    return text.strip()


def parse(raw: dict) -> dict:
    """The facts a snapshot shows: teams, clock, score, possession, and every player's box-score line."""
    comp = raw["header"]["competitions"][0]
    teams = {c["homeAway"]: normalize_team(c["team"]["abbreviation"]) for c in comp["competitors"]}
    score = {c["homeAway"]: int(c["score"]) for c in comp["competitors"]}
    status = comp["status"]
    period, clock = status.get("period"), _secs(status.get("displayClock"))
    elapsed = None
    if period and clock is not None:
        elapsed = (period - 1) * 900 + (900 - clock) if period <= 4 else G.GAME + 1.0
    plays = []
    drv = raw.get("drives") or {}
    for d in (drv.get("previous") or []) + ([drv["current"]] if drv.get("current") else []):
        plays.extend(d.get("plays") or [])
    last = plays[-1] if plays else None
    first_td = next(({"text": _td_sentence(p.get("text") or ""), "period": (p.get("period") or {}).get("number"), "clock": (p.get("clock") or {}).get("displayValue")}
                     for p in plays if p.get("scoringPlay") and "TOUCHDOWN" in (p.get("text") or "").upper()), None)
    end = (last or {}).get("end") or {}
    poss_id = (end.get("team") or {}).get("id")
    team_by_id = {c["team"]["id"]: normalize_team(c["team"]["abbreviation"]) for c in comp["competitors"]}
    if elapsed is None and status["type"]["state"] == "post":      # a finished game shows no running clock
        elapsed = G.GAME if (period or 4) <= 4 else G.GAME + 1.0
    if elapsed is None and status["type"]["state"] == "pre":
        elapsed = 0.0
    out = {"event": comp.get("id"), "home": teams["home"], "away": teams["away"], "score": score, "period": period, "clock": clock, "elapsed": elapsed,
           "state": status["type"]["state"], "completed": bool(status["type"].get("completed")), "possession": team_by_id.get(poss_id),
           "last_wallclock": (last or {}).get("wallclock"), "down": end.get("down"), "yards_to_go": end.get("distance"), "yardline_100": end.get("yardsToEndzone"), "last_play": (last or {}).get("text"),
           "n_plays": len(plays), "first_td": first_td, "players": {}, "team_attempts": {}}
    pw = {t["team"]["abbreviation"]: t for t in raw.get("boxscore", {}).get("players", [])}
    for ab, t in pw.items():
        team = normalize_team(ab)
        att = car = 0
        for grp in t["statistics"]:
            lab = grp["labels"]
            for a in grp["athletes"]:
                name = a["athlete"]["displayName"]
                row = out["players"].setdefault((team, name), {"team": team, "name": name, "id": a["athlete"].get("id")})
                v = dict(zip(lab, a["stats"]))
                if grp["name"] == "passing":
                    c_att = str(v.get("C/ATT", "")).split("/")
                    if len(c_att) == 2:
                        row.update(pass_comp=_num(c_att[0]), pass_att=_num(c_att[1]), pass_yds=_num(v.get("YDS")), pass_td=_num(v.get("TD")))
                        att += int(_num(c_att[1]) or 0)
                elif grp["name"] == "rushing":
                    row.update(rush_att=_num(v.get("CAR")), rush_yds=_num(v.get("YDS")), rush_td=_num(v.get("TD")))
                    car += int(_num(v.get("CAR")) or 0)
                elif grp["name"] == "receiving":
                    row.update(rec=_num(v.get("REC")), rec_yds=_num(v.get("YDS")), targets=_num(v.get("TGTS")), rec_td=_num(v.get("TD")))
        out["team_attempts"][team] = {"pass": att, "rush": car}
    return out


# --------------------------------------------------------------------------- freezing

def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=float)


def freeze(gid: str, adjusted: bool = True) -> dict:
    """Write-once pregame projection for a game: the saved forecast and the Players-tab projections, with a SHA-256 of the canonical content.

    Refuses to overwrite: a second call returns the stored record after checking its hash. `before_kickoff` records whether the freeze happened before the
    scheduled kickoff; a game frozen after kickoff stays usable for tracking but is flagged and left out of any pregame-vs-live scoring."""
    path = FROZEN / f"{gid}.json"
    if path.exists():
        rec = json.loads(path.read_text(encoding="utf-8"))
        check = hashlib.sha256(_canon(rec["projection"]).encode()).hexdigest()
        if check != rec["sha256"]:
            raise RuntimeError(f"frozen projection for {gid} no longer matches its hash")
        return rec
    d = S.game_detail_adjusted(gid, with_props=True) if adjusted else D.game_detail(gid)
    if d is None:
        raise ValueError(f"unknown game {gid}")
    now = pd.Timestamp.now(tz="UTC")
    kick = pd.Timestamp(d.get("kickoff_utc")) if d.get("kickoff_utc") else None
    proj = {"gid": gid, "away": d["away"], "home": d["home"], "week": d["week"], "forecast_saved_at": d.get("forecast_saved_at"), "expected": d.get("expected"),
            "headline": d.get("headline"), "props": [{k: r.get(k) for k in ("player", "team", "stat", "typical", "expected", "range_low", "range_high", "market_line", "market_chance")} for r in d.get("props") or []]}
    rec = {"gid": gid, "frozen_at": now.isoformat(), "kickoff_utc": None if kick is None else kick.isoformat(),
           "before_kickoff": bool(kick is not None and now < kick), "projection": json.loads(_canon(proj)), "sha256": hashlib.sha256(_canon(proj).encode()).hexdigest()}
    FROZEN.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps({"gid": gid, "frozen_at": rec["frozen_at"], "before_kickoff": rec["before_kickoff"], "sha256": rec["sha256"]}) + "\n")
    return rec


# --------------------------------------------------------------------------- baselines and updating

_CACHE: dict = {}


def espn_to_gsis() -> dict:
    """ESPN athlete id -> nflverse player id, from the players table. Names alone are ambiguous (two Justin Jeffersons) and miss suffixes."""
    if "espn" not in _CACHE:
        pl = pd.read_parquet(ROOT / "data" / "raw" / "players.parquet", columns=["gsis_id", "espn_id"]).dropna()
        _CACHE["espn"] = {str(int(float(e))): g for e, g in zip(pl["espn_id"], pl["gsis_id"])}
    return _CACHE["espn"]


def player_id(pl: dict, by_norm: dict) -> str | None:
    """The nflverse id for a box-score line: by ESPN athlete id first, by normalized name only when that id is unknown."""
    g = espn_to_gsis().get(str(pl.get("id")))
    return g or by_norm.get(S._norm(pl["name"]))


def live_context(seasons=(2025, 2026)):
    """Params fitted on every season before the one being played, plus pregame baselines for each team's next game."""
    if "ctx" in _CACHE:
        return _CACHE["ctx"]
    import importlib.util
    spec = importlib.util.spec_from_file_location("ingame_eval", ROOT / "scripts" / "ingame_eval.py")
    ev_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev_mod)
    fit_seasons = list(range(2018, seasons[0]))
    plays_fit = G.load_plays(fit_seasons)
    ev_fit = G.events(plays_fit)
    games_fit = G.games_table(plays_fit)
    ev_mod.HOME.update({r.gid: r.home for r in games_fit.itertuples(index=False)})
    tl = ev_mod.Timeline(plays_fit, ev_fit)
    params = ev_mod.fit_params(plays_fit, ev_fit, games_fit, tl)
    allp = G.load_plays([seasons[0] - 1, *seasons])
    ev = G.events(allp)
    games = G.games_table(allp)
    tv = G.team_volume(ev, games)
    nxt = []
    for team, g in tv.groupby("team"):
        i = int(g["idx"].max()) + 1
        nxt.append({"gid": f"NEXT_{team}", "team": team, "idx": i, "n_pass": 0, "n_rush": 0, "season": 2026, "week": 99})
    tv2 = pd.concat([tv, pd.DataFrame(nxt)], ignore_index=True)
    for k in ("n_pass", "n_rush"):
        tv2["pre_" + k] = tv2.groupby("team")[k].transform(lambda s: s.shift(1).rolling(G.WINDOW, min_periods=3).mean())
    base = G.baselines(ev, tv2, params.pool, params.pool_catch, params.m_eff, params.m_catch)
    next_base = {fam: b[b["gid"].str.startswith("NEXT_")] for fam, b in base.items()}
    pre_vol = {r.team: (r.pre_n_pass, r.pre_n_rush) for r in tv2[tv2["gid"].str.startswith("NEXT_")].itertuples(index=False)}
    pid_name = pd.read_parquet(ROOT / "data" / "raw" / "players.parquet")
    # version 2 baseline (snap counts across teams, hierarchical share prior) for receiving and rushing, the stats where it beat version 1 out of sample
    # (docs/ingame_eval_v2.json). Passing stays on version 1: it did not beat it. The share priors come from the fit through 2023 that was tested.
    next2, hier = {}, None
    hf = ROOT / "data" / "cache" / "ingame_hier_main_2023.json"
    if hf.exists():
        hier = json.loads(hf.read_text(encoding="utf-8"))
        snaps = I2.snap_table(range(2018, 2027))
        last = snaps[snaps["snaps"] > 0].sort_values(["season", "week"]).groupby("pid").tail(1)
        last = last[last["season"] >= seasons[0]]
        syn = pd.DataFrame({"gid": "NEXT_" + last["team"], "team": last["team"], "pid": last["pid"], "pos": last["pos"], "snaps": 1, "pct": 0.0, "season": 2026, "week": 99})
        b2 = I2.baselines2(ev, tv2, pd.concat([snaps, syn], ignore_index=True), params.pool, params.pool_catch, params.m_eff, params.m_catch)
        next2 = {fam: b2[fam][b2[fam]["gid"].str.startswith("NEXT_")] for fam in ("rec", "rush")}
    _CACHE["ctx"] = {"params": params, "next": next_base, "next2": next2, "hier": hier, "pre_vol": pre_vol, "pid_name": pid_name}
    return _CACHE["ctx"]


def _candidates(snap: dict, ctx: dict, week: int | None) -> list[dict]:
    """Who to track: version 2 rows for receiving and rushing, version 1 rows for passing and for anyone version 2 has too little history on (said so in
    `baseline`). Players on the team's ruled-out list are left out when the week is known."""
    out_names: dict[str, set] = {}
    if week is not None:
        for t in (snap["home"], snap["away"]):
            o, _ = S.unavailable(t, week)
            out_names[t] = set(o)
    cands, have = [], set()
    for fam, b in (ctx.get("next2") or {}).items():
        for r in b.itertuples(index=False):
            if r.team in (snap["home"], snap["away"]):
                share, kap = I2.calibrated_share(ctx["hier"][fam], r.grp, r.share)
                cands.append({"fam": fam, "team": r.team, "pid": r.pid, "mu_O": r.mu_O, "share": share, "ypo": r.ypo, "cr": r.cr, "kappa": kap, "baseline": "v2"})
                have.add((fam, r.team, r.pid))
    for fam, b in ctx["next"].items():
        for r in b.itertuples(index=False):
            if r.team in (snap["home"], snap["away"]) and (fam, r.team, r.pid) not in have:
                cands.append({"fam": fam, "team": r.team, "pid": r.pid, "mu_O": r.mu_O, "share": r.share, "ypo": r.ypo, "cr": r.cr, "kappa": None,
                              "baseline": "v1" if fam == "pass" or not ctx.get("next2") else "v1 (too little history for v2)"})
    if week is not None:
        cands = [c for c in cands if S._norm(D_name(ctx, c["pid"])) not in out_names.get(c["team"], set())]
    return cands


def tracked_states(snap: dict, ctx=None, week: int | None = None) -> list[dict]:
    """Every tracked player in a parsed snapshot with his model state, the updated and the frozen projection, the split of the change and any role warning."""
    ctx = ctx or live_context()
    p = ctx["params"]
    by_norm = S._pid_by_norm()
    el = snap["elapsed"]
    if el is None:
        return []
    h, a = snap["score"]["home"], snap["score"]["away"]
    rows, seen = [], set()
    for c in _candidates(snap, ctx, week):
        fam, team, kap = c["fam"], c["team"], c["kappa"]
        kind = "rush" if fam == "rush" else "pass"
        r = types.SimpleNamespace(pid=c["pid"], mu_O=c["mu_O"], share=c["share"], ypo=c["ypo"], cr=c["cr"])
        if True:
            name = None
            for (tm, nm), pl in snap["players"].items():
                if tm == team and player_id(pl, by_norm) == r.pid:
                    name, line = nm, pl
                    break
            d = (h - a) if team == snap["home"] else (a - h)
            pv = ctx["pre_vol"][team][1 if kind == "rush" else 0]
            A = snap["team_attempts"].get(team, {}).get(kind, 0)
            line = line if name else {}
            if fam == "rec":
                O, Y, C = line.get("targets") or 0, line.get("rec_yds") or 0.0, line.get("rec") or 0.0
            elif fam == "rush":
                O, Y, C = line.get("rush_att") or 0, line.get("rush_yds") or 0.0, 0.0
            else:
                O, Y, C = line.get("pass_att") or 0, line.get("pass_yds") or 0.0, line.get("pass_comp") or 0.0
            st = G.PlayerState(fam, r.mu_O, r.share, r.ypo, r.cr, int(O), float(Y), float(C), int(A), float(el), float(d), float(pv), kap)
            st0 = G.PlayerState(fam, r.mu_O, r.share, r.ypo, r.cr, 0, 0.0, 0.0, 0, 0.0, 0.0, float(pv), kap)
            up, fr = G.predict_player(p, st, 400, 1), G.predict_player(p, st0, 400, 2)
            rc = G.role_check(p, st)
            parts = G.decompose(p, st)
            rows.append({"team": team, "name": name or D_name(ctx, r.pid), "pid": r.pid, "fam": fam, "stat": G.FAMILIES[fam], "baseline": c["baseline"], "seen": name is not None,
                         "targets_or_carries": int(O), "yards": float(Y), "team_attempts": int(A), "share_pre": rc["share_pre"], "share_post": rc["share_post"],
                         "frozen": float(fr["yards"].mean()), "updated": float(up["yards"].mean()), "low": float(np.percentile(up["yards"], 10)),
                         "high": float(np.percentile(up["yards"], 90)), "p_lower": rc["p_lower"], "p_higher": rc["p_higher"], "parts": parts,
                         "catches": float(C) if fam == "rec" else None,
                         "catches_frozen": float(fr["catches"].mean()) if fam == "rec" else None, "catches_updated": float(up["catches"].mean()) if fam == "rec" else None,
                         "catches_low": float(np.percentile(up["catches"], 10)) if fam == "rec" else None, "catches_high": float(np.percentile(up["catches"], 90)) if fam == "rec" else None,
                         "yards_draws": up["yards"], "frozen_draws": fr["yards"]})
    return rows


def D_name(ctx, pid) -> str:
    pn = ctx["pid_name"]
    col = "gsis_id" if "gsis_id" in pn.columns else pn.columns[0]
    m = pn[pn[col] == pid]
    for c in ("display_name", "full_name", "name"):
        if c in m.columns and len(m):
            return str(m.iloc[0][c])
    return str(pid)


_TD_SIM: dict = {}


def _td_model(gid: str) -> dict:
    """(player, team) -> {chance, exp_td} for anytime touchdown from the simulated game, kept ten minutes because building it takes a few seconds."""
    hit = _TD_SIM.get(gid)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    from . import rankings as RK
    try:
        sim = S.simulate(gid, "typical", 0)
        out = RK.td_chances(sim) if sim and sim.get("ok") else {}
    except Exception:
        out = {}
    _TD_SIM[gid] = (time.time(), out)
    return out


def touchdown_rows(gid: str, snap: dict, rows: list[dict]) -> list[dict]:
    """Touchdowns so far (from the box score) and the chance each player scores one: already scored is 100%; otherwise his pregame touchdown rate scaled by the
    share of the game left and by how his share of his team's attempts has moved. It does not yet account for the score or the field position."""
    td = _td_model(gid)
    rho = max(0.0, (G.GAME - min(snap["elapsed"] or 0.0, G.GAME)) / G.GAME)
    ratios: dict = {}
    for r in rows:
        if r["share_pre"] > 0:
            ratios.setdefault((S._norm(r["name"]), r["team"]), []).append(float(np.clip(r["share_post"] / r["share_pre"], 0.2, 3.0)))
    scored, names = {}, {}
    for (tm, nm), pl in snap["players"].items():
        k = (tm, S._norm(nm))
        scored[k] = int((pl.get("rec_td") or 0) + (pl.get("rush_td") or 0))
        names[k] = nm
    out, seen = [], set()
    for (nm, team), t in td.items():
        if team not in (snap["home"], snap["away"]):
            continue
        k = (team, S._norm(nm))
        seen.add(k)
        n = scored.get(k, 0)
        ratio = float(np.mean(ratios.get((S._norm(nm), team), [1.0])))
        now = 1.0 if n > 0 else float(1 - np.exp(-t["exp_td"] * rho * ratio))
        out.append({"team": team, "name": nm, "td_so_far": n, "chance_pre": float(t["chance"]), "chance_now": now, "scored": n > 0})
    for k, n in scored.items():
        if n > 0 and k not in seen:
            out.append({"team": k[0], "name": names[k], "td_so_far": n, "chance_pre": None, "chance_now": 1.0, "scored": True})
    out.sort(key=lambda r: (-r["td_so_far"], -r["chance_now"], r["name"]))
    return out[:40] + [r for r in out[40:] if r["scored"]]


def warnings(rows: list[dict], min_attempts: int = 12, threshold: float = 0.95) -> list[dict]:
    """Only role changes: his share of the team's attempts has moved far from pregame, with enough attempts seen to tell. Luck and script are not warned."""
    out = []
    for r in rows:
        if r["team_attempts"] < min_attempts:
            continue
        if r["p_lower"] >= threshold:
            out.append({**r, "kind": "role: share well below pregame"})
        elif r["p_higher"] >= threshold and r.get("fam") != "pass":      # a quarterback's share rising is a stale baseline (new team, new starter), not news
            out.append({**r, "kind": "role: share well above pregame"})
    return out


def win_probability(snap: dict, pregame_margin: float, params: G.Params, M: int = 4000, seed: int = 0) -> dict | None:
    """Home win chance and final-margin draws from the score, clock, drive in progress and the frozen pregame margin; None when the feed has no clock."""
    el = snap["elapsed"]
    if el is None or el > G.GAME:
        return None
    rho = (G.GAME - el) / G.GAME
    margin = snap["score"]["home"] - snap["score"]["away"]
    ep = 0.0
    if snap["possession"] and snap["down"] and snap["yardline_100"] is not None:
        ep = G.ep_of(params, snap["down"], snap["yardline_100"]) * (1 if snap["possession"] == snap["home"] else -1)
    rng = np.random.default_rng(seed)
    draws = G.margin_samples(params, margin, rho, pregame_margin, ep, M, rng)
    return {"p_home": float((draws > 0).mean() + 0.5 * (draws == 0).mean()), "margin": draws, "ep_home": ep}


SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
FRESH_SECONDS = 15


def _age_seconds(stamp: str) -> float:
    t = pd.Timestamp(f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}Z")
    return (pd.Timestamp.now(tz="UTC") - t).total_seconds()


def scoreboard_event(home: str, away: str) -> str | None:
    """ESPN's event id for a game, from the live scoreboard (the game must be on it); None when it cannot be reached or the game is not there."""
    import requests
    try:
        sb = requests.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", timeout=10).json()
    except Exception:
        return None
    for ev in sb.get("events", []):
        t = {c["homeAway"]: normalize_team(c["team"]["abbreviation"]) for c in ev["competitions"][0]["competitors"]}
        if t.get("home") == home and t.get("away") == away:
            return ev["id"]
    return None


def pull(eid: str) -> str | None:
    """Fetch the game's summary from ESPN now and store it as a new snapshot when it differs from the newest stored one. Returns the new stamp, or None if
    nothing changed or ESPN could not be reached (the caller keeps using the stored snapshot)."""
    import requests
    try:
        raw = requests.get(SUMMARY, params={"event": eid}, timeout=10).content
    except Exception:
        return None
    snaps = snapshots(eid)
    if snaps:
        with gzip.open(snaps[-1][1], "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() == hashlib.sha256(raw).hexdigest():
                return None
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
    d = CAPTURE / eid
    d.mkdir(parents=True, exist_ok=True)
    with gzip.open(d / f"{stamp}.json.gz", "wb") as f:
        f.write(raw)
    return stamp


def feed_lag() -> dict | None:
    """ESPN's measured delay (seconds from its own play timestamp to our first sight of the play) from docs/ingame_latency.json; None when never measured.
    Dense-polling plays are used once there are 30 of them, otherwise every play, where the gap includes the polling interval."""
    f = ROOT / "docs" / "ingame_latency.json"
    if not f.exists():
        return None
    j = json.loads(f.read_text(encoding="utf-8"))
    dense, allp = j.get("dense_polling_only", {}), j.get("all_snapshots", {})
    if dense.get("n", 0) >= 30:
        return {**dense, "basis": "polled every 30 seconds or faster"}
    return {**allp, "basis": "includes the polling gap, so an upper bound"} if allp.get("n") else None


def latest(gid: str, ctx=None, refresh: bool = True) -> dict | None:
    """What the tracker shows for a game right now: the newest stored snapshot, updated players, role warnings, win chance and where the frozen numbers came from.
    None when no snapshot of this game has been captured."""
    ctx = ctx or live_context()
    g = D.games_table()
    m = g[g["game_id"] == gid]
    if m.empty:
        return None
    home, away = m["home_team"].iloc[0], m["away_team"].iloc[0]
    idx = CAPTURE / "index.jsonl"
    eid = None
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["teams"].get("home") and normalize_team(r["teams"]["home"]) == home and normalize_team(r["teams"]["away"]) == away:
                eid = r["event"]
    snaps = snapshots(eid) if eid else []
    if not snaps:
        # the recorder was not running for this game: find it on ESPN's scoreboard and take a snapshot now
        eid = eid or scoreboard_event(home, away)
        if eid and pull(eid):
            snaps = snapshots(eid)
    if not snaps:
        return None
    stamp, path = snaps[-1]
    snap = parse(load(path))
    if refresh and snap["state"] != "post" and _age_seconds(stamp) > FRESH_SECONDS:      # the recorder may be off or between polls: ask ESPN directly
        new = pull(eid)
        if new:
            stamp, path = new, CAPTURE / eid / f"{new}.json.gz"
            snap = parse(load(path))
    fr = None
    f = FROZEN / f"{gid}.json"
    if f.exists():
        fr = freeze(gid)
    margin = (fr or {}).get("projection", {}).get("expected", {}) or {}
    wp = win_probability(snap, margin.get("margin"), ctx["params"]) if margin.get("margin") is not None else None
    rows = tracked_states(snap, ctx, int(gid.split("_")[1]))
    keep = ("team", "name", "stat", "yards", "targets_or_carries", "team_attempts", "frozen", "updated", "low", "high", "share_pre", "share_post")
    players = [{k: r[k] for k in keep + ("baseline",)} for r in rows if r["seen"]]
    players += [{**{k: r[k] for k in keep + ("baseline",)}, "stat": "Receptions", "yards": r["catches"], "frozen": r["catches_frozen"], "updated": r["catches_updated"],
                 "low": r["catches_low"], "high": r["catches_high"]} for r in rows if r["seen"] and r["fam"] == "rec"]
    return {"gid": gid, "event": eid, "snapshot": stamp, "age_seconds": round(_age_seconds(stamp)),
            "newest_play_seconds": None if not snap.get("last_wallclock") else round((pd.Timestamp.now(tz="UTC") - pd.Timestamp(snap["last_wallclock"])).total_seconds()),
            "feed_lag": feed_lag(), "state": snap["state"], "period": snap["period"], "clock": snap["clock"], "score": snap["score"],
            "possession": snap["possession"], "last_play": snap["last_play"], "win_chance_home": None if wp is None else wp["p_home"],
            "frozen": None if fr is None else {"sha256": fr["sha256"], "frozen_at": fr["frozen_at"], "before_kickoff": fr["before_kickoff"]},
            "players": players, "touchdowns": touchdown_rows(gid, snap, rows), "first_td": snap.get("first_td"), "warnings": [{k: r[k] for k in keep + ("kind",)} for r in warnings(rows)],
            "not_in_feed": ["snaps", "routes", "red-zone touches (box score only)"]}
