@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title NBA Ensemble - Local Only
set "NBA_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%NBA_PYTHON%" set "NBA_PYTHON=%~dp0..\nfl-ensemble-lab\.venv\Scripts\python.exe"
if not exist "%NBA_PYTHON%" (
 echo No local Python runtime found. See README.md for standalone setup.
 pause
 exit /b 1
)
echo NBA Ensemble - separate NBA data and models; no NFL predictions used.
echo 1  Open NBA dashboard [Enter]
echo 2  Daily refresh + frozen-model refit + archive winners
echo 3  Show saved research report
echo Q  Quit
set "NBA_ACTION="
set /p "NBA_ACTION=Choose: "
if /i "%NBA_ACTION%"=="Q" exit /b 0
if "%NBA_ACTION%"=="2" (
 "%NBA_PYTHON%" -m nba_lab.cli daily
 set "NBA_RESULT=!errorlevel!"
 pause
 exit /b !NBA_RESULT!
)
if "%NBA_ACTION%"=="3" (
 "%NBA_PYTHON%" -m nba_lab.cli report
 set "NBA_RESULT=!errorlevel!"
 pause
 exit /b !NBA_RESULT!
)
if not "%NBA_ACTION%"=="" if not "%NBA_ACTION%"=="1" exit /b 1
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:8502"
"%NBA_PYTHON%" -m nba_lab.cli app
pause
