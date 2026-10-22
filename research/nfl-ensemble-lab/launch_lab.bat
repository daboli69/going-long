@echo off
setlocal
cd /d "%~dp0"
title NFL Ensemble Lab
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] The lab is not installed yet. Double-click scripts\launchers\setup_windows.bat first.
    pause
    exit /b 1
)
echo Starting NFL Ensemble Lab at http://localhost:8501
echo Keep this window open while you use the lab. Close it to stop the lab.
echo.
start "" /b cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8501/?page=Projections"
".venv\Scripts\python.exe" -m lab.low_priority -m streamlit run app\streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
if errorlevel 1 (
    echo.
    echo [ERROR] The dashboard stopped with an error, shown above.
    echo   - If port 8501 is busy, close other lab windows and try again.
    echo   - If a package is missing, run scripts\launchers\setup_windows.bat again.
    pause
)
