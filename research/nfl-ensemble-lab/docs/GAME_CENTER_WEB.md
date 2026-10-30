# Game Center web app

A local, read-only page for the NFL ensemble. It replaces nothing: the Streamlit lab on port 8501 keeps the operator
pages (runs, archives, research tabs). The Game Center is the plain-English view.

## Run it

Double-click `scriptsaunchersaunch_game_center.bat`, or run
`.venv\Scripts\python.exe -m uvicorn web.server:app --host 127.0.0.1 --port 8510`.
Open http://localhost:8510. The first launch installs the Python packages and builds the page, which needs Node.js 22
once. Nothing leaves this computer.

## Layout

| Piece | Where | Job |
|---|---|---|
| Data layer | `lab/gamecenter_data.py` | Reads saved forecasts, games, injuries and props. No Streamlit. |
| Display names and glossary | `lab/gamecenter_meta.py` | Team names, colors, plain-English terms. |
| API | `web/server.py` | FastAPI, GET only, bound to 127.0.0.1. Endpoints `/api/meta`, `/api/week/{week}`, `/api/game/{gid}`, `/api/glossary`. |
| Front end | `web/ui/` | React, TypeScript, Vite, Tailwind, Recharts, TanStack Table. Built into `web/ui/dist`. |
| Tests | `tests/test_gamecenter_api.py` | Input rejection, GET-only, probability tables sum to 1, jargon-free glossary. |

## Develop

`cd web/ui`, then `npm install`, `npm run dev` (proxies `/api` to port 8510) and `npm run shots` for headless screenshots
into `web/ui/test-results/`. The headline numbers follow the Kalshi betting market when it exists, because the model has
not beaten it. The API never invents a number: missing data comes back as null and the page shows a dash.
