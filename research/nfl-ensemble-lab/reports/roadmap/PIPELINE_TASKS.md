# Weekly freeze and scoring: scheduled tasks (registered 2026-10-31 with Travis's approval)

Registered as written below, except each trigger's start time was saved as plain local time (no UTC offset) so the tasks keep 22:00 and 09:00 after daylight saving ends. First runs: score Tue 2026-11-03 09:00, freeze Wed 2026-11-04 22:00.

2026-10-31: the Weekly Score task also runs `scripts
2026-10-31: the Weekly Score task also runs `scripts/redistribution_check.py` after `verify_results.py` (approved by Travis). It refits where injured players' production goes, rewrites docs/REDISTRIBUTION_CHECK.md and docs/redistribution_check.json, and saves data/cache/redistribution_rule.json for the simulation. About 6 minutes.

2026-10-31: the Weekly Score task also runs `scripts/fpds_usage_check.py` last (approved by Travis). It re-tests whether FantasyPoints metrics improve the simulated game, rewrites docs/FPDS_USAGE_CHECK.md and docs/fpds_usage_check.json, and saves data/cache/fpds_usage_rule.json. A blend is kept only while it passes the gate, so a stat can drop back to nflverse-only. About 3 minutes; it uses whatever FantasyPoints files were imported before Tuesday.

2026-10-31: the Weekly Score task also runs `scripts/drivesim_check.py` last (approved by Travis). It re-tests the independent drive simulation against the betting market on completed 2025 and 2026 games, rewrites docs/DRIVE_SIM_CHECK.md and docs/drivesim_check.json, and saves data/cache/drivesim_rule.json. The blend weights stay at zero unless the simulation beats the market in both years, so the market keeps setting the center of the simulated games until then.

2026-11-01: the Weekly Score task also runs `scripts/availability_check.py` and then `scripts/recvsim_check.py` (approved by Travis). The first re-tests whether roster absences (injured reserve and others) improve who-plays, receiving, winner and props predictions, and rewrites docs/AVAILABILITY_CHECK.md and docs/availability_check.json. The second re-scores the sampled receiving model on completed 2025 and 2026 games, rewrites docs/RECEIVING_SIM_CHECK.md and docs/recvsim_check.json, and saves data/cache/recvsim_rule.json. The replay uses the sampled receiving only while that file says it passed; otherwise it falls back to the averaged method. About 3.5 and 1 minute; the task keeps its one-hour limit.

2026-11-01: the Weekly Score task also runs `scripts/coverage_check.py` last (approved by Travis). It re-tests whether defensive coverage mix (man, zone, Cover 1 to 6, blitz) improves receiving yard and catch predictions on completed 2025 and 2026 games, rewrites docs/COVERAGE_CHECK.md and docs/coverage_check.json, and saves data/cache/coverage_rule.json. Nothing reads that rule yet, so the simulation stays unchanged even if a family passes; a pass would be a prompt to wire it in. About 1 to 2 minutes.

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
