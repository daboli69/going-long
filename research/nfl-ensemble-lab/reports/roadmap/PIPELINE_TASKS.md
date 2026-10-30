# Weekly freeze and scoring: proposed scheduled tasks (not registered; waiting for Travis's approval)

## What exists today (measured by a read-only query of Windows Task Scheduler on 2026-10-30)

| Task | Schedule | What it does |
|---|---|---|
| NFL Ensemble Lab - Data Refresh | every 5 minutes | `releases\run_tick.pyw` runs `lab.scheduler tick` (data refresh). It does not freeze or score forecasts. |
| NFL Lab Dense Capture - Sunday | Sundays 06:00 (next 2026-11-01) | Dense read-only Kalshi books and trades and ESPN injuries. |
| GoingLong-FP-Shadow-Capture | every 30 minutes | FantasyPoints shadow capture (not part of this lab). |

No task freezes forecasts and none scores them. The entry points exist and are run by hand:

| Job | Command (from the lab folder) | Archive it writes |
|---|---|---|
| Winner variants (8 columns) freeze | `.venv\Scripts\python.exe scripts\home_win_deep.py freeze` | `data/raw/archive/homewin_deep` |
| Winner, spread, total joint model freeze | `.venv\Scripts\python.exe scripts\forecast_study.py freeze` | `data/raw/archive/forecast_games` |
| Props freeze | `.venv\Scripts\python.exe scripts\props_kalshi_collect.py freeze` | `data/raw/archive/props_kalshi` |
| Score every frozen week | `.venv\Scripts\python.exe scripts\home_win_deep.py score` | prints to the log |
| Check hashes and protocol order | `.venv\Scripts\python.exe scripts\verify_results.py` | prints to the log |

Each freeze function keeps only games that have not kicked off, so a late run saves fewer games, never later knowledge.

## Proposed task 1: weekly freeze

Wednesday 22:00 local time (the first kickoff of a week is Thursday evening, about 20:15 Eastern, so this leaves about 22 hours).
If the computer is off at 22:00 the task runs when it wakes (`StartWhenAvailable`); a late run saves only games not yet kicked off.

```powershell
$lab = 'C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\nfl-ensemble-lab'
$py  = Join-Path $lab '.venv\Scripts\python.exe'
$log = Join-Path $lab 'reports\forecast\weekly_freeze.log'
$cmd = "/c `"`"$py`" -W ignore scripts\home_win_deep.py freeze >> `"$log`" 2>&1 & `"$py`" -W ignore scripts\forecast_study.py freeze >> `"$log`" 2>&1 & `"$py`" -W ignore scripts\props_kalshi_collect.py freeze >> `"$log`" 2>&1`""
$action   = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $cmd -WorkingDirectory $lab
$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At '22:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'NFL Lab Weekly Freeze' -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
  -Description 'Weekly frozen forecasts before kickoff. Read-only public data, no orders, no database writes, no deployment.'
```

## Proposed task 2: weekly scoring

Tuesday 09:00 local time (after Monday night games).

```powershell
$log = Join-Path $lab 'reports\forecast\weekly_score.log'
$cmd = "/c `"`"$py`" -W ignore scripts\home_win_deep.py score >> `"$log`" 2>&1 & `"$py`" -W ignore scripts\verify_results.py >> `"$log`" 2>&1`""
$action   = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $cmd -WorkingDirectory $lab
$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At '09:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName 'NFL Lab Weekly Score' -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
  -Description 'Scores frozen forecasts against final results and re-checks archive hashes. Read-only.'
```

To review without registering, wrap each `Register-ScheduledTask` in a function with `SupportsShouldProcess` and run with `-WhatIf`, as `scripts\register_capture_task.ps1` does.
Remove with `Unregister-ScheduledTask -TaskName '<name>' -Confirm:$false`.

## Things to know before approving

- The freeze commands have not been timed here. `home_win_deep.py freeze` "catches up new weeks" and may run model training, so the
  first run should be watched by hand. The 3-hour limit is a guess.
- `forecast_study.py` loads games through a function that first tries `api.nfldata.org` (a parked domain) and falls back to local data. That is an outbound request that fails.
- Freeze and scoring do not run the confirmatory look. That stays a manual, rules-fixed step.
- Nothing here sends alerts, places orders or touches any database.
