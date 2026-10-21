@echo off
cd /d "%~dp0"
if "%~1"=="" (
  .venv\Scripts\python.exe -m lab.low_priority -m lab.fpds_improve run --hours 3
) else (
  .venv\Scripts\python.exe -m lab.low_priority -m lab.fpds_improve %*
)
if errorlevel 1 (
  echo FPDS improvement study stopped. Private diagnostics and completed blocks were retained.
  exit /b 1
)
.venv\Scripts\python.exe -m lab.low_priority -m lab.fpds_improve_report
