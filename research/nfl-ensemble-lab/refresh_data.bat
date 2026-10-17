@echo off
setlocal
cd /d "%~dp0"
title NFL Ensemble Lab - Refresh Now
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup_windows.bat first.
    exit /b 1
)
rem Manual "refresh now": full data refresh, then one scheduler tick (runs any refresh or
rem pregame snapshot that is currently due). The Windows task already does this automatically
rem every 5 minutes; this file is only for running it by hand.
echo Refreshing data (a few minutes) ...
".venv\Scripts\python.exe" -W ignore -m lab.cli refresh > "data\last_refresh.log" 2>&1
if errorlevel 1 (
    echo [ERROR] Refresh failed. See data\last_refresh.log
    exit /b 1
)
".venv\Scripts\python.exe" -W ignore -m lab.scheduler tick >> "data\last_refresh.log" 2>&1
echo Done. Log: data\last_refresh.log
