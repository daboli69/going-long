@echo off
setlocal
cd /d "%~dp0"
title NFL Ensemble Lab - Stop Research
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup_windows.bat first.
    pause
    exit /b 1
)
echo Asking the running research job to stop after its current trial.
echo Completed trials are kept; the job then runs its one validation check.
".venv\Scripts\python.exe" -W ignore -m lab.longrun stop
pause
