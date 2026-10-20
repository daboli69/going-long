@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python environment missing. Run setup_windows.bat first.
    exit /b 1
)
echo Local Phase 10 shadow pipeline. Earlier forecasts remain unchanged.
".venv\Scripts\python.exe" -m lab.low_priority -m lab.props.weekly10 %*
if errorlevel 1 (
    echo ERROR: Pipeline stopped. See the failed phase and partial revision path above.
    exit /b 1
)
echo Complete. Open launch_lab.bat and choose Projections or Leans.
exit /b 0
