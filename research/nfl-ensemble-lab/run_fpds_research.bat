@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 1
if not "%~1"=="" goto command
call run_manual_fpds.bat
exit /b %errorlevel%
:command
if "%~1"=="compare" goto manual
if "%~1"=="project" goto manual
if "%~1"=="prepare" goto manual
if "%~1"=="plan" goto manual
if "%~1"=="status" goto manual
if "%~1"=="resume" goto manual
if "%~1"=="stop" goto manual
if "%~1"=="walkforward" (
  echo Amendment6 is complete and frozen. Use run_manual_fpds.bat compare for the new matched development comparison.
  exit /b 1
)
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_worker %*
exit /b %errorlevel%
:manual
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_manual %*
exit /b %errorlevel%
