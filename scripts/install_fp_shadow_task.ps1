param(
 [string]$PrivateRoot = 'C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\FantasyPoints',
 [string]$PythonPath = '',
 [int]$EveryMinutes = 60,
 [switch]$Activate
)
# Prepares (and, only with -Activate, registers) a per-user Task Scheduler job that runs the PRE-GAME shadow capture of fp_shadow.py.
# DEFAULT IS A DRY RUN: it validates inputs and prints exactly what would be registered. Nothing is created without -Activate, which needs the owner's approval.
# The task runs as the current user (Limited, no admin), makes no paid or provider call and writes only to %LOCALAPPDATA%\GOING\private\fp-shadow.
# It fetches origin/main read-only and refuses any board older than 6 hours, so it can only capture when a fresh published board exists.
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$privatePath = (Resolve-Path -LiteralPath $PrivateRoot).Path
if (!(Test-Path -LiteralPath (Join-Path $privatePath 'research/cache/games.csv'))) { throw 'FantasyPoints research cache is missing' }
if ($PythonPath -eq '') { $PythonPath = Join-Path $repoPath '.venv\Scripts\python.exe' }
$pythonBinary = (Resolve-Path -LiteralPath $PythonPath).Path
if ($EveryMinutes -lt 15) { throw 'EveryMinutes must be at least 15' }
$script = Join-Path $repoPath 'scripts\fp_shadow.py'
$arguments = '"' + $script + '" capture --root "' + $privatePath + '" --market-from-git origin/main --weeks 6-10'
$taskName = 'GoingLong-FP-Shadow-Capture'
$description = "GOING-owned research shadow capture of pregame total forecasts (not bets, alerts or production freezes). Every $EveryMinutes min; write-once; refuses boards older than 6h and games within 30 min of kickoff."
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -notlike 'GOING-owned research shadow capture*') { throw 'Task name is already owned by another process' }
Write-Output "Task:        $taskName"
Write-Output "Command:     $pythonBinary $arguments"
Write-Output "Working dir: $repoPath  (PYTHONPATH is set by the script itself)"
Write-Output "Schedule:    every $EveryMinutes minutes while this user is logged in; MultipleInstances IgnoreNew; 5 minute limit"
Write-Output "Existing:    $([bool]$existing)"
if (-not $Activate) { Write-Output 'DRY RUN: nothing was registered. Re-run with -Activate after the owner approves.'; return }
$action = New-ScheduledTaskAction -Execute $pythonBinary -Argument $arguments -WorkingDirectory $repoPath
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description $description -Force -ErrorAction Stop | Out-Null
if (!(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) { throw 'Scheduled task registration was not confirmed' }
Write-Output "Registered $taskName. Remove with: Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
