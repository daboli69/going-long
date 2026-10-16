@echo off
rem Pregame shadow capture of the P5-2 total forecasts (research only). NOT scheduled by this repository.
rem Run it after the data refresh so the market board is fresh (it refuses a board older than 6 hours), well before kickoff.
rem Captures go to %LOCALAPPDATA%\GOING\private\fp-shadow (never inside Git). Existing captures are never overwritten.
setlocal
cd /d "%~dp0\.."
set PYTHONPATH=scripts
if "%FP_ROOT%"=="" set FP_ROOT=C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\FantasyPoints
.venv\Scripts\python.exe scripts\fp_shadow.py capture --root "%FP_ROOT%" --market data\nfl_betting.json
.venv\Scripts\python.exe scripts\fp_shadow.py verify
endlocal
