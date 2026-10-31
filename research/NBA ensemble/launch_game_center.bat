@echo off
setlocal
cd /d "%~dp0"
title NBA Game Center - Local Only
set "NBA_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%NBA_PYTHON%" (
 echo No NBA Python runtime found. See README.md for standalone setup.
 pause
 exit /b 1
)
if not exist "web\ui\dist\index.html" (
 echo Building the Game Center page once. This needs Node.js and takes about a minute.
 pushd web\ui
 call npm ci --no-audit --no-fund || goto :build_failed
 call npm run build || goto :build_failed
 popd
)
echo Starting NBA Game Center at http://localhost:8512
echo Keep this window open while you use it. Close it to stop.
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:8512"
"%NBA_PYTHON%" -m uvicorn web.server:app --host 127.0.0.1 --port 8512
pause
exit /b 0

:build_failed
popd
echo The page build failed; see the message above. Is Node.js installed?
pause
exit /b 1
