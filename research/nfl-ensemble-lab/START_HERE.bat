@echo off
setlocal
cd /d "%~dp0"
title NFL Ensemble Lab - Start Here
if not exist ".venv\Scripts\python.exe" (
    echo First-time setup is needed. Run scripts\launchers\setup_windows.bat, then open this file again.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m lab.launcher %*
set "LAB_EXIT_CODE=%errorlevel%"
if not "%LAB_EXIT_CODE%"=="0" pause
exit /b %LAB_EXIT_CODE%
