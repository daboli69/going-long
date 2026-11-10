# Hourly: record pre-kickoff evaluations, settle finished games, verify the record. Local files only, no network, no paid APIs.
$ErrorActionPreference = 'Continue'
$lab = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $lab
$py = Join-Path $lab '.venv\Scripts\python.exe'
$logDir = Join-Path $lab 'reports\tracker'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir 'tick.log'
"== $(Get-Date -Format o)" | Add-Content $log
foreach ($cmd in 'select', 'settle', 'verify') {
    & $py -W ignore scripts\track.py $cmd 2>&1 | Add-Content $log
    if ($cmd -eq 'verify' -and $LASTEXITCODE -ne 0) { "ALERT: tracker verify failed" | Add-Content (Join-Path $logDir 'ALERT.txt') }
}
