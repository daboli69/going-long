@echo off
setlocal
cd /d "%~dp0..\.."
if not exist ".venv\Scripts\python.exe" (
  echo Missing local Python environment.
  exit /b 1
)
if "%~1"=="" (
  ".venv\Scripts\python.exe" -m lab.fpds_next research --hours 2
) else (
  ".venv\Scripts\python.exe" -m lab.fpds_next %*
)
exit /b %errorlevel%
