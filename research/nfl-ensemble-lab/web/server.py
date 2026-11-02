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
from lab import tdmarket as td_market

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
def leans(market: str = "All", week_from: int | None = None, week_to: int | None = None, size: str = "All", season: int | None = None, model: str = "recal", mode: str = "exec"):
    import json as _json
    import pandas as _pd
    if model not in ("recal", "raw") or mode not in ("exec", "mid"):
        raise HTTPException(400, "model is recal or raw; mode is exec or mid")
    f = ROOT / "data" / "leans" / "backtest_leans.parquet"
    if not f.exists():
        raise HTTPException(503, "Leans have not been scored yet. Run scripts/leans_run.py.")
    if _LEANS.get("mtime") != f.stat().st_mtime:
        _LEANS.update(mtime=f.stat().st_mtime, x=_pd.read_parquet(f), bt=_json.loads((ROOT / "docs" / "leans_backtest.json").read_text()))
    x, bt = _LEANS["x"], _LEANS["bt"]
    x = x[(x["model"] == model) & (x["mode"] == mode)]
    sel = leans_lab.select(x, market, week_from, week_to, size, season=season)
    rows = sel.sort_values(["season", "week"], ascending=False).head(150)
    pending = []
    fdir = ROOT / "data" / "leans" / "frozen"
    for fp in sorted(fdir.glob("*.json")) if fdir.exists() else []:
        rec = _json.loads(fp.read_text())
        pending += [{**p, "week": rec["forecast"]["week"], "sha256": rec["sha256"]} for p in rec["forecast"]["leans"] if market in ("All", p["market"])]
    head = bt["models"][model][mode]
    return JSONResponse(D.clean({"markets": [{"name": n, "testable": True} for n in leans_lab.STAT_NAME.values()] + [{"name": n, "testable": False, "why": w} for n, w in leans_lab.NOT_TESTABLE.items()],
                                 "summary": leans_lab.summarize(sel), "benchmarks": head["benchmarks"], "dropped": head["dropped"], "headline": bt["models"]["recal"]["exec"]["summary"], "raw_headline": bt["models"]["raw"]["exec"]["summary"],
                                 "recal_compare": bt["recal_compare"], "placebo": bt["placebo"], "pass": bt["pass"], "calibration": bt["calibration"], "rows": rows.to_dict("records"), "pending": pending,
                                 "rule_sha256": bt["rule_sha256"], "universe_rows": bt["universe_rows"]}))


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
