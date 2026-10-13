param(
 [Parameter(Mandatory=$true)][string]$PrivateRoot,
 [Parameter(Mandatory=$true)][string]$PythonPath
)
$ErrorActionPreference='Stop'
$repoPath=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$privatePath=(Resolve-Path -LiteralPath $PrivateRoot).Path
if(!(Test-Path -LiteralPath (Join-Path $privatePath 'Inbox'))){throw 'FantasyPoints Inbox is missing'}
$pythonBinary=(Resolve-Path -LiteralPath $PythonPath).Path
$sourceFiles=@((Join-Path $repoPath 'scripts/fp_autoload.py'))+@(Get-ChildItem -LiteralPath (Join-Path $repoPath 'scripts/fp_ingest') -Filter '*.py' -File | Sort-Object Name | ForEach-Object {$_.FullName})
$signature=($sourceFiles | ForEach-Object {(Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash}) -join ''
$hashBytes=[System.Text.Encoding]::UTF8.GetBytes($signature)
$version=[Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($hashBytes)).Substring(0,16).ToLowerInvariant()
$runtimePath=Join-Path $privatePath "runtime/$version"
New-Item -ItemType Directory -Force -Path (Join-Path $runtimePath 'scripts/fp_ingest'),(Join-Path $runtimePath 'config'),(Join-Path $runtimePath 'data') | Out-Null
Copy-Item -LiteralPath (Join-Path $repoPath 'scripts/fp_autoload.py') -Destination (Join-Path $runtimePath 'scripts/fp_autoload.py')
foreach($file in $sourceFiles | Select-Object -Skip 1){Copy-Item -LiteralPath $file -Destination (Join-Path $runtimePath 'scripts/fp_ingest')}
Copy-Item -LiteralPath (Join-Path $repoPath 'config/fantasy_points_tables.json') -Destination (Join-Path $runtimePath 'config/fantasy_points_tables.json')
Copy-Item -LiteralPath (Join-Path $repoPath 'data/nfl_betting.json') -Destination (Join-Path $runtimePath 'data/nfl_betting.json')
$taskName='GoingLong-FP-Autoload'
$old=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if($old -and $old.Description -notlike 'GOING-owned private CSV intake*'){throw 'Task name is already owned by another process'}
$arguments='"'+(Join-Path $runtimePath 'scripts/fp_autoload.py')+'" --root "'+$privatePath+'" --schedule "'+(Join-Path $runtimePath 'data/nfl_betting.json')+'"'
$action=New-ScheduledTaskAction -Execute $pythonBinary -Argument $arguments -WorkingDirectory $runtimePath
$triggers=@((New-ScheduledTaskTrigger -AtLogOn),(New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)))
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
$principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
try {
 Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description "GOING-owned private CSV intake; five-minute scan while this user is logged in. No alerts or paid provider calls. Runtime $version." -Force -ErrorAction Stop | Out-Null
 if(!(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)){throw 'Scheduled task registration was not confirmed'}
 Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
 Write-Output "Installed $taskName. Private backend sync still requires configured server credentials."
} catch {
 # Task Scheduler is restricted on some user accounts. Per-user Startup needs
 # no elevated privileges and does not modify other tasks or user shortcuts.
 $startupPath=Join-Path ([Environment]::GetFolderPath('Startup')) 'GOING FantasyPoints Inbox.lnk'
 $shell=New-Object -ComObject WScript.Shell
 $shortcut=$shell.CreateShortcut($startupPath)
 if((Test-Path -LiteralPath $startupPath) -and $shortcut.Description -ne 'GOING-owned private inbox watcher'){throw 'Startup shortcut is already owned by another process'}
 $shortcut.TargetPath=$pythonBinary
 $shortcut.Arguments=$arguments+' --watch'
 $shortcut.WorkingDirectory=$runtimePath
 $shortcut.WindowStyle=7
 $shortcut.Description='GOING-owned private inbox watcher'
 $shortcut.Save()
 $process=Start-Process -FilePath $pythonBinary -ArgumentList ($arguments+' --watch') -WorkingDirectory $runtimePath -WindowStyle Hidden -PassThru
 Write-Output "Installed per-user Startup watcher (Task Scheduler restricted); started PID $($process.Id). Five-minute checks while Windows is running. Private backend sync is not yet configured."
}
