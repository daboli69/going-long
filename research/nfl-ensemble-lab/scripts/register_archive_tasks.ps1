# Authoring only: Codex does not execute this script or register any task.
# Review with: .\scripts\register_archive_tasks.ps1 -WhatIf
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param([string]$TaskPrefix = 'NFL Lab Phase 10')
$ErrorActionPreference = 'Stop'
$labPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$helperPath = Join-Path $labPath 'scripts\archive_tick.ps1'
$powershellPath = Join-Path $PSHOME 'powershell.exe'
if (-not (Test-Path -LiteralPath $powershellPath)) { $powershellPath = (Get-Process -Id $PID).Path }
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
foreach ($spec in @(@{Name='Quote Archive'; Mode='Quotes'; Interval='PT3H'}, @{Name='T90 Inactives'; Mode='Inactives'; Interval='PT5M'})) {
    $taskName = "$TaskPrefix - $($spec.Name)"
    $arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $helperPath + '" -Mode ' + $spec.Mode
    $action = New-ScheduledTaskAction -Execute $powershellPath -Argument $arguments -WorkingDirectory $labPath
    $trigger = New-ScheduledTaskTrigger -Daily -At '00:00'
    $trigger.Repetition = New-CimInstance -Namespace 'Root/Microsoft/Windows/TaskScheduler' -ClassName MSFT_TaskRepetitionPattern -ClientOnly -Property @{Interval=$spec.Interval;Duration='P1D';StopAtDurationEnd=$false}
    Write-Host "Task: $taskName"
    Write-Host "  Daily, repeat $($spec.Interval) for P1D; interactive user; no elevation"
    Write-Host "  $powershellPath $arguments"
    Write-Host "  Working directory: $labPath"
    if ($PSCmdlet.ShouldProcess($taskName, 'Register local read-only archive task')) {
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Local Phase 10 read-only archives. No odds API, alerts, database writes or deployment.' -Force | Out-Null
    }
}
