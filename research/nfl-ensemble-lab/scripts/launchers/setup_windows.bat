@echo off
setlocal
cd /d "%~dp0..\.."
title NFL Ensemble Lab - Setup
echo ============================================================
echo  NFL Ensemble Lab - one-time setup
echo ============================================================
echo.

set "PYCMD="
where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 -c "import sys" >nul 2>nul && set "PYCMD=py -3.12"
    if not defined PYCMD py -3.11 -c "import sys" >nul 2>nul && set "PYCMD=py -3.11"
)
if not defined PYCMD (
    echo [ERROR] Python 3.12 or 3.11 was not found.
    echo.
    echo   1. Download Python 3.12 from https://www.python.org/downloads/windows/
    echo   2. In the installer, tick "Add python.exe to PATH" and keep "py launcher" selected.
    echo   3. Run this file again.
    echo.
    echo   Python 3.13+ is not supported yet by the pinned PyTorch version.
    pause
    exit /b 1
)
echo Using: %PYCMD%

if not exist ".venv\Scripts\python.exe" (
    echo Creating the local virtual environment in .venv ...
    %PYCMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        pause
        exit /b 1
    )
)

echo Installing packages (first time: several minutes, about 1 GB) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed. Check your internet connection and try again.
    echo         If it keeps failing, copy the red error text above when asking for help.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import torch, xgboost, sklearn, streamlit, openpyxl, pandas; print('All packages import correctly.')"
if errorlevel 1 (
    echo [ERROR] Packages installed but failed to import.
    pause
    exit /b 1
)
echo.
echo ============================================================
echo  Setup complete. Double-click launch_lab.bat to start.
echo ============================================================
pause
