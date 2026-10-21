@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 1
if not "%~1"=="" goto command
for %%C in (ingest audit features screen) do (
  ".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_research %%C
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_research walkforward --phase discovery --resume
exit /b %errorlevel%
:command
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_research %*
exit /b %errorlevel%
