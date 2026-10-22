@echo off
setlocal
cd /d "%~dp0..\.."
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: local Python environment missing.
    exit /b 1
)
echo Importing local FPDS files. Inbox is read-only; no website access.
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_worker ingest %*
if errorlevel 1 (
    echo ERROR: FPDS import incomplete. Review metadata and local private report; do not share raw files.
    exit /b 1
)
".venv\Scripts\python.exe" -m lab.low_priority -m lab.fpds_worker audit
if errorlevel 1 exit /b 1
echo Complete. Metadata dictionary: docs\FPDS_DATA_DICTIONARY.md
exit /b 0
