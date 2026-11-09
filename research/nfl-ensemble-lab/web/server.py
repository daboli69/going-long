"""NFL Game Center web server. Local, read-only, no accounts: a small JSON API plus the built React app.

  .venv\Scripts\python.exe -m uvicorn web.server:app --host 127.0.0.1 --port 8510
or double-click launch_game_center.bat.

Everything it serves is read from files already on this computer (saved forecasts, reports, the games table), except kickoff
weather, which the Simulated game tab fetches from Open-Meteo (free, no key) and caches in data/cache/weather. There are no write endpoints. It binds to 127.0.0.1 only, so other devices on the network cannot reach it.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Path as PathParam, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from lab import gamecenter_data as D
from lab import gamesim
from lab import ingame_feed
from lab import results as week_results
from lab import rankings as rank_lists
from lab import kingzone
from lab import kz2_board
from lab import leans as leans_lab
from lab import refs as refs_lab
from lab import first_td_allowed as ftd_lab
from lab import snapgame as snapgame_lab
from lab import tdmarket as td_market
from lab import covgame as coverage_lab
from lab import onoff as onoff_lab

ROOT = Path(__file__).resolve().parents[1]
DIST = Path(__file__).resolve().parent / "ui" / "dist"
app = FastAPI(title="NFL Game Center", docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
def warm_live():
    """Build the live tracker's constants in the background so the first Live tab opened during a game does not wait half a minute."""
    import threading
    threading.Thread(target=lambda: ingame_feed.live_context(), daemon=True).start()


@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/meta")
def meta():
    return JSONResponse(D.clean(D.meta()))


@app.get("/api/week/{week}")
def week(week: int = PathParam(ge=1, le=18)):
    return JSONResponse(D.week_games(week))


@app.get("/api/game/{gid}")
def game(gid: str = PathParam(pattern=D.GID_PATTERN)):
    detail = gamesim.game_detail_adjusted(gid, with_props=True)
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown game")
    return JSONResponse(D.clean(detail))


@app.get("/api/sim/{gid}")
def sim(gid: str = PathParam(pattern=D.GID_PATTERN), mode: str = Query("typical", pattern="^(typical|random|upset)$"),
        draw: int = Query(0, ge=0, le=9999)):
    out = gamesim.simulate(gid, mode, draw)
    if out is None:
        raise HTTPException(status_code=404, detail="Unknown game")
    return JSONResponse(out)


@app.get("/api/rankings/{week}")
def rankings(week: int = PathParam(ge=1, le=18)):
    return JSONResponse(D.clean(rank_lists.public(rank_lists.week_rankings(week))))


_LEANS = {}


@app.get("/api/leans")
def leans(market: str = "All", week_from: int | None = None, week_to: int | None = None, size: str = "All", season: int | None = None, model: str = "recal"):
    import json as _json
    import pandas as _pd
    if model not in ("recal", "raw"):
        raise HTTPException(400, "model is recal or raw")
    f = ROOT / "data" / "leans" / "backtest_leans.parquet"
    if not f.exists():
        raise HTTPException(503, "Leans have not been scored yet. Run scripts/leans_run.py.")
    if _LEANS.get("mtime") != f.stat().st_mtime:
        _LEANS.update(mtime=f.stat().st_mtime, x=_pd.read_parquet(f), bt=_json.loads((ROOT / "docs" / "leans_backtest.json").read_text()))
    x, bt = _LEANS["x"], _LEANS["bt"]
    x = x[x["model"] == model]
    sel = leans_lab.select(x, market, week_from, week_to, size, season=season)
    rows = sel.sort_values(["season", "week"], ascending=False).head(150)
    pending = []
    fdir = ROOT / "data" / "leans" / "frozen"
    for fp in sorted(fdir.glob("*.json")) if fdir.exists() else []:
        rec = _json.loads(fp.read_text())
        pending += [{**p, "week": rec["forecast"]["week"], "sha256": rec["sha256"]} for p in rec["forecast"]["leans"] if market in ("All", p["market"])]
    head = bt["models"][model]
    return JSONResponse(D.clean({"markets": [{"name": n, "testable": True} for n in leans_lab.STAT_NAME.values()] + [{"name": n, "testable": False, "why": w} for n, w in leans_lab.NOT_TESTABLE.items()],
                                 "summary": leans_lab.summarize(sel), "benchmarks": head["benchmarks"], "headline": bt["models"]["recal"]["summary"], "raw_headline": bt["models"]["raw"]["summary"], "market_accuracy": bt["market_accuracy"],
                                 "recal_compare": bt["recal_compare"], "placebo": bt["placebo"], "pass": bt["pass"], "calibration": bt["calibration"], "rows": rows.to_dict("records"), "pending": pending,
                                 "rule_sha256": bt["rule_sha256"], "universe_rows": bt["universe_rows"]}))


_REFS = {}


@app.get("/api/ou-calls")
def ou_calls_api():
    from lab import ou_calls
    return JSONResponse(D.clean(ou_calls.calls()))


@app.get("/api/tails")
def tails_api():
    """Tail tests (docs/tails_results.json), the latest saved week of flags and the prospective score."""
    import json as _json
    from lab import tails_ladder, tails_week
    f = ROOT / "docs" / "tails_results.json"
    if not f.exists():
        raise HTTPException(503, "The tail tests have not been run yet. Run scripts/tails_run.py.")
    res = _json.loads(f.read_text())
    saved = sorted(tails_week.FROZEN.glob("*.json")) if tails_week.FROZEN.exists() else []
    week = None
    if saved:
        week = _json.loads(saved[-1].read_text())
        week = {"file": saved[-1].name, "sha256": week["sha256"], "hash_ok": tails_week.verify(week), "created": week["created"], "forecast": week["forecast"]}
    df = ROOT / "docs" / "tails_deep_results.json"
    return JSONResponse(D.clean({"results": res, "week": week, "prospective": tails_week.score(), "deep": _json.loads(df.read_text()) if df.exists() else None,
                                 "ladders": _json.loads((ROOT / "docs" / "tails_ladder_results.json").read_text()) if (ROOT / "docs" / "tails_ladder_results.json").exists() else None,
                                 "ladders_forward": tails_ladder.score_archived(),
                                 "leadlag": _json.loads((ROOT / "docs" / "leadlag_results.json").read_text()) if (ROOT / "docs" / "leadlag_results.json").exists() else None}))


@app.get("/api/refs")
def refs(measure: str = "home_ats", referee: str = "All", season_from: int = 2015, season_to: int = 2026):
    import json as _json
    import pandas as _pd
    if measure not in refs_lab.MEASURES:
        raise HTTPException(400, "measure is one of " + ", ".join(refs_lab.MEASURES))
    f_path = ROOT / "data" / "refs" / "games_refs.parquet"
    if not f_path.exists():
        raise HTTPException(503, "Referee tests have not been run yet. Run scripts/refs_run.py.")
    if _REFS.get("mtime") != f_path.stat().st_mtime:
        _REFS.update(mtime=f_path.stat().st_mtime, f=_pd.read_parquet(f_path), res=_json.loads((ROOT / "docs" / "refs_results.json").read_text()))
    f, res = _REFS["f"], _REFS["res"]
    t = refs_lab.table(f, measure, season_from, season_to)
    rows = t.to_dict("records")
    pick = [r for r in rows if r["referee"] == referee]
    fdir = ROOT / "data" / "refs" / "frozen"
    frozen = [_json.loads(fp.read_text())["forecast"] for fp in sorted(fdir.glob("*.json"))] if fdir.exists() else []
    tw = refs_lab.this_week()
    nums = refs_lab.tab_numbers(f, sorted({g["referee"] for g in tw["games"] if g["referee"]})) if tw.get("games") else {}
    for g in tw.get("games", []):
        g["tab"] = nums.get(g["referee"])
    keep = ("rule_sha256", "games", "referees", "coverage", "year_to_year", "claims", "any_effect_claimed", "tweet_check", "market", "penalty_dispersion", "discovery_ats_tests")
    return JSONResponse(D.clean({"measures": refs_lab.MEASURES, "kind": "rate" if measure in refs_lab.BINARY else "count", "referees": sorted(f["referee"].unique()), "rows": rows, "selected": pick[0] if pick else None,
                                 "this_week": tw, "frozen": frozen, "results": {k: res[k] for k in keep}}))


@app.get("/api/first-td-allowed")
def first_td_allowed(season: int = 2026, weeks: str = "", overall: bool = False):
    try:
        ws = [int(w) for w in weeks.split(",") if w.strip()] or None
    except ValueError:
        raise HTTPException(400, "weeks is a comma list of week numbers")
    if season not in ftd_lab.seasons():
        raise HTTPException(400, "no play-by-play for that season")
    return JSONResponse(D.clean({**ftd_lab.table(season, ws, overall), "seasons": ftd_lab.seasons(), "positions": ftd_lab.POSITIONS}))


@app.get("/api/snapsim/{gid}")
def snapsim(gid: str = PathParam(pattern=D.GID_PATTERN), refresh: bool = False):
    import json as _json
    try:
        res = snapgame_lab.get(gid, refresh)
    except IndexError:
        raise HTTPException(404, "no such game in the schedule file")
    vf = ROOT / "docs" / "snapsim_validation.json"
    res["validation"] = _json.loads(vf.read_text()) if vf.exists() else None
    return JSONResponse(D.clean(res))


@app.get("/api/kingzone/{week}")
def king_week(week: int = PathParam(ge=1, le=18)):
    return JSONResponse(D.clean(kingzone.week_games(week)))


@app.get("/api/kingzone/game/{gid}")
def king_game(gid: str = PathParam(pattern=D.GID_PATTERN)):
    try:
        out = kz2_board.board(gid)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if out is None:
        raise HTTPException(status_code=404, detail="No board for this game")
    return JSONResponse(D.clean({**out, "frozen": kz2_board.frozen_info(gid)}))


@app.get("/api/coverage/{gid}")
def coverage(gid: str = PathParam(pattern=D.GID_PATTERN)):
    """Each side's expected quarterback against the opposing defense's coverage mix and position profile. Descriptive history only."""
    try:
        out = coverage_lab.card(gid)
    except (FileNotFoundError, KeyError) as e:
        raise HTTPException(status_code=503, detail=f"Coverage data is not available yet ({e})")
    if out is None:
        raise HTTPException(status_code=404, detail="Unknown game")
    return JSONResponse(D.clean(out))


@app.get("/api/onoff/{gid}")
def onoff(gid: str = PathParam(pattern=D.GID_PATTERN), team: str = Query(pattern="^[A-Z]{2,3}$"), player: str = Query(pattern=r"^00-\d{7}$")):
    """Teammates with a player on and off the field (2022 to 2025) and in games he did not play (2025 and 2026). Descriptive history only."""
    season, week = int(gid[:4]), int(gid[5:7])
    try:
        out = {"on_field": onoff_lab.on_field(player, team),
               "game_level": [onoff_lab.game_level(player, team, season, week), onoff_lab.game_level(player, team, season - 1)],
               "min_plays": onoff_lab.MIN_PLAYS, "min_targets": onoff_lab.MIN_TGT}
    except (FileNotFoundError, KeyError) as e:
        raise HTTPException(status_code=503, detail=f"With-and-without data is not available yet ({e})")
    return JSONResponse(D.clean(out))


@app.get("/api/tdcard/{gid}")
def tdcard(gid: str = PathParam(pattern=D.GID_PATTERN), team: str = Query(pattern="^[A-Z]{2,3}$"), player: str = Query(min_length=3, max_length=60)):
    out = rank_lists.td_card(gid, team, player)
    if out is None:
        raise HTTPException(status_code=404, detail="No touchdown card for that player")
    return JSONResponse(D.clean(out))


@app.get("/api/tdmarket/{week}")
def tdmarket(week: int = PathParam(ge=1, le=18)):
    try:
        return JSONResponse(D.clean(td_market.week_market(week)))
    except Exception as exc:  # Kalshi unreachable or changed: say so rather than 500
        raise HTTPException(status_code=502, detail=f"Could not read Kalshi prices ({type(exc).__name__})")


@app.get("/api/live/{gid}")
def live(gid: str = PathParam(pattern=D.GID_PATTERN)):
    """In-game tracker: newest captured snapshot, updated player projections against the frozen pregame ones, role warnings and the live win chance."""
    out = ingame_feed.latest(gid)
    if out is None:
        raise HTTPException(status_code=404, detail="No live snapshot captured for this game")
    return JSONResponse(D.clean(out))


@app.get("/api/results/{week}")
def results(week: int = PathParam(ge=1, le=18)):
    """How the saved pregame forecasts did against what happened, for the finished games of a week."""
    return JSONResponse(D.clean(week_results.week_results(week)))


@app.get("/api/glossary")
def glossary():
    return JSONResponse(D.glossary())


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")
else:
    @app.get("/", response_class=HTMLResponse)
    def not_built():
        return ("<body style='font-family:sans-serif;background:#0b1220;color:#e6edf7;padding:2rem'><h2>Game Center is not built yet</h2>"
                "<p>Run <code>launch_game_center.bat</code>, or in <code>web/ui</code> run <code>npm install</code> then <code>npm run build</code>.</p></body>")
