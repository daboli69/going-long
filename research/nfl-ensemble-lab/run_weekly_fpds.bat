@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 1
echo Local FPDS shadow pipeline. Never promotes, publishes or overwrites earlier forecasts.
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_research weekly %*
if errorlevel 1 (
  echo STOPPED. See private data\cache\fpds\amendment6\errors and the new partial revision. Earlier forecasts are unchanged.
  exit /b 1
)
exit /b 0
