@echo off
setlocal
cd /d "%~dp0..\.."
title NFL Ensemble Lab - Upset Research Run
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup_windows.bat first.
    pause
    exit /b 1
)
echo Running the Upset Discovery research workflow:
echo   refresh data, readiness gate, discovery, validation, weekly forecasts, Excel.
echo This does NOT retrain or replace the Phase 1 models. Expect a few minutes.
echo.
".venv\Scripts\python.exe" -W ignore -m lab.cli research
if errorlevel 1 (
    echo.
    echo [ERROR] The research run stopped. Read the message above.
    echo If it says the readiness gate failed, open artifacts\readiness_report.json
) else (
    echo Done. Opening the reports folder.
    start "" "reports"
)
pause
