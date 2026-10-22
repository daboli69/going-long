@echo off
setlocal
cd /d "%~dp0..\.."
if not exist ".venv\Scripts\python.exe" exit /b 1
if "%~1"=="" goto menu
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_manual %*
exit /b %errorlevel%
:menu
echo Local FPDS: full history, shadow only, no publishing or promotion.
echo 1. Projections and simulations for the next unstarted week
echo 2. Matched development comparison: games and props with/without FPDS
echo 3. Inspect source plan and recent jobs
choice /c 123 /n /m "Choose 1, 2 or 3: "
if errorlevel 3 goto status
if errorlevel 2 goto compare
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_manual project
goto done
:compare
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_manual compare
goto done
:status
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_manual plan
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_manual status
:done
pause
