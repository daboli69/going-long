@echo off
setlocal
cd /d "%~dp0"
title NFL Ensemble Lab - Scheduled Update
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup_windows.bat first.
    exit /b 1
)
rem Scheduled routine (Windows Task Scheduler): refresh data and archive injury reports,
rem freeze pre-kickoff predictions for upcoming games, and score finished games.
rem It never runs discovery research and never retrains models.
".venv\Scripts\python.exe" -W ignore -m lab.cli scheduled > "data\last_refresh.log" 2>&1
if errorlevel 1 (
    echo [ERROR] Scheduled update reported errors. See data\last_refresh.log
    exit /b 1
)
echo Scheduled update complete. Log: data\last_refresh.log
