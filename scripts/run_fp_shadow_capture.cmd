@echo off
rem Pregame shadow capture of the P5-2 total forecasts (research only; not bets, alerts or production freezes).
rem NOT scheduled by this repository: see scripts\install_fp_shadow_task.ps1 (dry run by default, needs owner approval to activate).
rem It reads the published board from origin/main and refuses a board older than 6 hours or a game within 30 minutes of kickoff.
rem Captures go to %LOCALAPPDATA%\GOING\private\fp-shadow (never inside Git). Existing captures are never overwritten.
setlocal
cd /d "%~dp0\.."
if "%FP_ROOT%"=="" set FP_ROOT=C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\FantasyPoints
.venv\Scripts\python.exe scripts\fp_shadow.py capture --root "%FP_ROOT%" --market-from-git origin/main
.venv\Scripts\python.exe scripts\fp_shadow.py verify
endlocal
