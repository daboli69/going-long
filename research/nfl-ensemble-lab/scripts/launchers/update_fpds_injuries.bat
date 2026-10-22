@echo off
setlocal
cd /d "%~dp0..\.."
if not exist ".venv\Scripts\python.exe" (
    echo Local Python environment missing. Open START_HERE.bat for setup guidance.
    exit /b 1
)
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_drop injuries %*
exit /b %errorlevel%
