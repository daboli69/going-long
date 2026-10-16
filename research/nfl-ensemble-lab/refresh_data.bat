@echo off
setlocal
cd /d "%~dp0"
title NFL Ensemble Lab - Data Refresh
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup_windows.bat first.
    exit /b 1
)
rem Refreshes schedule, play-by-play and injury reports, and archives the live injury file.
rem Schedule this daily (Windows Task Scheduler) to build a timestamped injury history.
".venv\Scripts\python.exe" -m lab.cli refresh > "data\last_refresh.log" 2>&1
if errorlevel 1 (
    echo [ERROR] Refresh failed. See data\last_refresh.log
    exit /b 1
)
echo Refresh complete. Log: data\last_refresh.log
