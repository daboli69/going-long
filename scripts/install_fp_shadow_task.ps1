param(
 [string]$PrivateRoot = 'C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\FantasyPoints',
 [string]$PythonPath = 'C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\.venv\Scripts\python.exe',
 [string]$Commit = 'HEAD',
 [int]$EveryMinutes = 30,
 [switch]$Activate
)
# Durable installer for the PRE-GAME research shadow capture (scripts/fp_shadow.py). Not bets, alerts or production freezes.
#  * The task runs from a self-contained, commit-pinned runtime copy under %LOCALAPPDATA%\GOING\private\runtime\fp-shadow\<sha12>
#    (made with `git archive`), so it no longer depends on a checkout or worktree that may be removed or switched to another branch.
#  * The board is read over HTTPS from the project's own PUBLIC repository (no git, no credentials, no provider call, no paid request).
#  * DEFAULT IS A DRY RUN that creates nothing. With -Activate: build the runtime, TEST it (a dry-run capture that writes nothing), refuse if any OTHER task already runs
#    fp_shadow.py (no duplicates), and only then replace the existing task of the same name. A failed test leaves the current task untouched.
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$privatePath = (Resolve-Path -LiteralPath $PrivateRoot).Path
if (!(Test-Path -LiteralPath (Join-Path $privatePath 'research/cache/games.csv'))) { throw 'FantasyPoints research cache is missing' }
$pythonBinary = (Resolve-Path -LiteralPath $PythonPath).Path
if ($EveryMinutes -lt 15) { throw 'EveryMinutes must be at least 15' }
$sha = (& git -C $repoPath rev-parse --verify "$Commit^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or $sha -notmatch '^[0-9a-f]{40}$') { throw "Cannot resolve commit $Commit" }
$runtime = Join-Path $env:LOCALAPPDATA ("GOING\private\runtime\fp-shadow\" + $sha.Substring(0, 12))
$taskName = 'GoingLong-FP-Shadow-Capture'
$description = "GOING-owned research shadow capture of pregame total forecasts (not bets, alerts or production freezes). Every $EveryMinutes min; write-once; refuses boards older than 6h and games within 30 min of kickoff. Runtime $($sha.Substring(0, 12))."
$arguments = '"' + (Join-Path $runtime 'scripts\fp_shadow.py') + '" capture --root "' + $privatePath + '" --market-from-url main --weeks 6-10'
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing -and $existing.Description -notlike 'GOING-owned research shadow capture*') { throw 'Task name is already owned by another process' }
# Duplicate prevention: any task with another name that runs fp_shadow.py is a conflict.
$others = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -ne $taskName -and (($_.Actions | ForEach-Object { "$($_.Arguments)" }) -join ' ') -match 'fp_shadow\.py' })
if ($others.Count -gt 0) { throw ('Another scheduled task already runs fp_shadow.py: ' + (($others | ForEach-Object { $_.TaskName }) -join ', ')) }
Write-Output "Task:        $taskName"
Write-Output "Commit:      $sha"
Write-Output "Runtime:     $runtime"
Write-Output "Command:     $pythonBinary $arguments"
Write-Output "Schedule:    every $EveryMinutes minutes while this user is logged in (local time zone of this PC: $((Get-TimeZone).Id)); MultipleInstances IgnoreNew; 5 minute limit"
Write-Output "Output:      $env:LOCALAPPDATA\GOING\private\fp-shadow (captures, ledger.jsonl, runs, settled)"
Write-Output "Existing:    $([bool]$existing)"
if (-not $Activate) { Write-Output 'DRY RUN: nothing was created or registered. Re-run with -Activate to build the runtime, test it and replace the task.'; return }
if (!(Test-Path -LiteralPath (Join-Path $runtime 'scripts\fp_shadow.py'))) {
 New-Item -ItemType Directory -Force -Path $runtime | Out-Null
 $tar = Join-Path ([IO.Path]::GetTempPath()) ("fp-shadow-" + $sha.Substring(0, 12) + ".tar")
 & git -C $repoPath archive --format=tar -o $tar $sha scripts config research/trend-intelligence/ledger.json
 if ($LASTEXITCODE -ne 0) { throw 'git archive failed' }
 & tar -xf $tar -C $runtime
 if ($LASTEXITCODE -ne 0) { throw 'tar extraction failed' }
 Remove-Item -LiteralPath $tar
 Set-Content -LiteralPath (Join-Path $runtime 'RUNTIME_COMMIT') -Value $sha -Encoding ascii
}
# Test the runtime BEFORE touching the current task: a dry-run capture writes nothing.
$test = & $pythonBinary (Join-Path $runtime 'scripts\fp_shadow.py') capture --root $privatePath --market-from-url main --weeks 6-10 --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Runtime test failed; the existing task was not changed' }
$report = ($test -join "`n") | ConvertFrom-Json
if (-not $report.dry_run) { throw 'Runtime test did not run as a dry run; the existing task was not changed' }
Write-Output "Runtime test OK (dry run at $($report.captured_at))."
$action = New-ScheduledTaskAction -Execute $pythonBinary -Argument $arguments -WorkingDirectory $runtime
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description $description -Force -ErrorAction Stop | Out-Null
$now = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (!$now -or $now.Actions[0].WorkingDirectory -ne $runtime) { throw 'Scheduled task registration was not confirmed' }
Write-Output "Registered $taskName from $runtime. Remove with: Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
