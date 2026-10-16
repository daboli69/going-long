@echo off
setlocal
cd /d "%~dp0"
title NFL Ensemble Lab - Weekly Predictions
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup_windows.bat first.
    pause
    exit /b 1
)
echo Refreshing data and predicting the next NFL week with the saved models ...
".venv\Scripts\python.exe" -m lab.cli predict
if errorlevel 1 (
    echo [ERROR] Weekly predictions failed. If no models exist yet, train them in the dashboard first.
) else (
    echo Done. Reports are in the "reports" folder; snapshots in "snapshots".
    start "" "%~dp0reports"
)
pause
