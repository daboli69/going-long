"""NFL Game Center web server. Local, read-only, no accounts: a small JSON API plus the built React app.

  .venv\Scripts\python.exe -m uvicorn web.server:app --host 127.0.0.1 --port 8510
or double-click launch_game_center.bat.

Everything it serves is read from files already on this computer (saved forecasts, reports, the games table). There are no write endpoints and
no outside calls. It binds to 127.0.0.1 only, so other devices on the network cannot reach it.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Path as PathParam
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from lab import gamecenter_data as D

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
