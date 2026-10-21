@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 1
echo Local FPDS shadow pipeline. Never promotes, publishes or overwrites earlier forecasts.
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_weekly_guard --branch-only
if errorlevel 1 exit /b 1
if "%~1"=="--comparisons-only" goto comparisons
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_weekly_guard --run %*
if errorlevel 1 (
  echo STOPPED. See private data\cache\fpds\amendment6\errors and the new partial revision. Earlier forecasts are unchanged.
  exit /b 1
)
:present
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_sheets
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_clv
if errorlevel 1 (
  echo STOPPED at descriptive quote tracking. The new forecast revision is retained; no earlier files changed.
  exit /b 1
)
exit /b 0
:comparisons
git fetch origin main
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m lab.low_priority -m lab.phase10_archive --remote-main >nul
if errorlevel 1 exit /b 1
goto present
