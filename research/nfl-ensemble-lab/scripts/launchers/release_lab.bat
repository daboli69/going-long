@echo off
setlocal
cd /d "%~dp0..\.."
title NFL Ensemble Lab - Release
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Run setup_windows.bat first.
    exit /b 1
)
rem Pinned scheduler releases (docs/RELEASES.md). Examples:
rem   release_lab.bat release lab-v7.3 --dry-run   build + test + prewarm, change nothing live
rem   release_lab.bat release lab-v7.3             ... and point the launcher at it
rem   release_lab.bat rollback                     back to the previous release
rem   release_lab.bat status
if "%~1"=="" (
    ".venv\Scripts\python.exe" -W ignore -m lab.release status
) else (
    ".venv\Scripts\python.exe" -W ignore -m lab.release %*
)
exit /b %errorlevel%
