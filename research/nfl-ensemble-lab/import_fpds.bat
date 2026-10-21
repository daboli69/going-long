@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: local Python environment missing.
    exit /b 1
)
echo Importing local FPDS files. Inbox is read-only; no website access.
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_ingest %*
if errorlevel 1 (
    echo ERROR: FPDS import incomplete. Review metadata and local private report; do not share raw files.
    exit /b 1
)
echo Complete. Coverage and gaps: docs\FPDS_INGEST.md
exit /b 0
