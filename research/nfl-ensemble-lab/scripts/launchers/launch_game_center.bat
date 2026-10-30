@echo off
setlocal
cd /d "%~dp0..\.."
title NFL Game Center
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] The lab is not installed yet. Double-click scripts\launchers\setup_windows.bat first.
    pause
    exit /b 1
)
.venv\Scripts\python.exe -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo Installing the Game Center server packages ^(free, one time^) ...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if not exist "web\ui\dist\index.html" (
    where npm >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Node.js is needed once to build the page. Install it from https://nodejs.org then run this again.
        pause
        exit /b 1
    )
    echo Building the Game Center page ^(one time, about a minute^) ...
    pushd web\ui
    call npm install --no-audit --no-fund
    call npm run build
    popd
)
echo.
echo NFL Game Center is starting at http://localhost:8510
echo Keep this window open while you use it. Close it to stop.
echo ^(Everything here is read-only and stays on this computer.^)
echo.
start "" http://localhost:8510
".venv\Scripts\python.exe" -m uvicorn web.server:app --host 127.0.0.1 --port 8510 --log-level warning
