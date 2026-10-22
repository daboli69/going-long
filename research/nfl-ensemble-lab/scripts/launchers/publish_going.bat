@echo off
rem Publish the sanitised NFL lab feed for the GOING website.
rem   publish_going.bat          -> build + validate + write publish\nfl_lab_feed.json (nothing leaves this PC)
rem   publish_going.bat --push   -> also push it to the nfl-lab-feed branch on GitHub (read by /api/nfl-lab)
cd /d "%~dp0..\.."
".venv\Scripts\python.exe" -W ignore -m lab.publish_going %*
