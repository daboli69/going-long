# Registers ONE local Windows task: dense Kalshi capture on game Sundays (Travis approved 2026-10-30).
# Read-only public Kalshi data and the ESPN injury feed; no orders, no account calls, no database writes, no deployment.
# Review with: .\scripts\register_capture_task.ps1 -WhatIf     Remove with: Unregister-ScheduledTask -TaskName 'NFL Lab Dense Capture - Sunday'
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param([string]$TaskName = 'NFL Lab Dense Capture - Sunday', [string]$At = '07:00', [int]$Hours = 14)
$ErrorActionPreference = 'Stop'
$labPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $labPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Lab Python not found: $python" }
$log = Join-Path $labPath 'reports\market_news\capture.log'
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
$command = "/c `"`"$python`" -W ignore scripts\market_news_study.py capture --hours $Hours --interval 5 --window 8 >> `"$log`" 2>&1`""
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $command -WorkingDirectory $labPath
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours ($Hours + 1))
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
Write-Host "Task: $TaskName"
Write-Host "  Weekly, Sunday $At local time, runs $Hours hours, polls every 5 minutes; interactive user; no elevation"
Write-Host "  cmd.exe $command"
Write-Host "  Working directory: $labPath"
if ($PSCmdlet.ShouldProcess($TaskName, 'Register local read-only dense capture task')) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
        -Description 'Dense read-only Kalshi books/trades and ESPN injuries before kickoffs. No orders, alerts, database writes or deployment.' | Out-Null
}
