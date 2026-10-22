@echo off
setlocal
cd /d "%~dp0..\.."
title NFL Ensemble Lab - Long-Run Model Research
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup_windows.bat first.
    pause
    exit /b 1
)
echo ============================================================
echo  Long-run model research (all six model families)
echo ============================================================
echo  It runs in the background at low priority, so you can keep
echo  using the PC. Close this window any time; the research continues.
echo  Watch or stop it on the dashboard page "Long-Run Research",
echo  or double-click stop_research.bat.
echo.
echo  How many hours?  1, 4, 8 (overnight) or 12.  Press Enter for 8.
set /p HOURS="Hours: "
if "%HOURS%"=="" set HOURS=8
".venv\Scripts\python.exe" -W ignore -m lab.longrun start --hours %HOURS%
if errorlevel 1 (
    echo.
    echo [ERROR] Could not start. If a job is already running, stop it first.
)
echo.
pause
