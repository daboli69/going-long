[CmdletBinding()]
param([ValidateSet('Quotes','Inactives')][string]$Mode = 'Quotes')
$ErrorActionPreference = 'Stop'
$labPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location -LiteralPath $labPath
try {
    $pythonPath = Join-Path $labPath '.venv\Scripts\python.exe'
    if ($Mode -eq 'Quotes') {
        & git fetch origin main
        if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed; archive skipped' }
        & $pythonPath -m lab.low_priority -m lab.phase10_archive --remote-main
    } else {
        & $pythonPath -m lab.low_priority -m lab.inactives10 collect
    }
    if ($LASTEXITCODE -ne 0) { throw "$Mode archive failed, exit $LASTEXITCODE" }
} finally {
    Pop-Location
}
