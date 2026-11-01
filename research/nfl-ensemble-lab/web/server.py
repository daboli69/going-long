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
from lab import rankings as rank_lists
from lab import tdmarket as td_market

DIST = Path(__file__).resolve().parent / "ui" / "dist"
app = FastAPI(title="NFL Game Center", docs_url=None, redoc_url=None, openapi_url=None)


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
    detail = D.game_detail(gid)
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown game")
    return JSONResponse(detail)


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
