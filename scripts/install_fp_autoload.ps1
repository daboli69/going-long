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
# Replace only the reader recorded by our own receipt, with verified runtime/executable.
$receiptPath=Join-Path $privatePath 'manifests/autoload_process.json'
if(Test-Path -LiteralPath $receiptPath){
 $receipt=Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
 $ownedProcess=Get-CimInstance Win32_Process -Filter "ProcessId = $($receipt.pid)" -ErrorAction SilentlyContinue
 if($ownedProcess){
  $ownedRuntime=[IO.Path]::GetFullPath($receipt.runtime)
  $runtimeBase=[IO.Path]::GetFullPath((Join-Path $privatePath 'runtime'))+[IO.Path]::DirectorySeparatorChar
  if(!$ownedRuntime.StartsWith($runtimeBase,[StringComparison]::OrdinalIgnoreCase) -or !$ownedProcess.CommandLine.Contains('"'+$ownedRuntime+'"') -or !$ownedProcess.CommandLine.Contains('--watch') -or [IO.Path]::GetFileName($ownedProcess.ExecutablePath) -notin @('python.exe','pythonw.exe')){throw 'Reader ownership cannot be verified; restart required'}
  Stop-Process -Id $receipt.pid -ErrorAction Stop
  Wait-Process -Id $receipt.pid -Timeout 10 -ErrorAction SilentlyContinue
 }
}
$startupPath=Join-Path ([Environment]::GetFolderPath('Startup')) 'GOING FantasyPoints Inbox.lnk'
$shell=New-Object -ComObject WScript.Shell
if(Test-Path -LiteralPath $startupPath){
 $existingShortcut=$shell.CreateShortcut($startupPath)
 if($existingShortcut.Description -ne 'GOING-owned private inbox watcher'){throw 'Startup shortcut is already owned by another process'}
}
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
 if(Test-Path -LiteralPath $startupPath){Remove-Item -LiteralPath $startupPath}
 Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
 Write-Output "Installed $taskName. Private backend sync still requires configured server credentials."
} catch {
 if($old){throw 'Existing scheduled task could not be replaced; restart/configuration required'}
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
 $confirmed=$false
 for($attempt=0;$attempt -lt 20;$attempt++){
  Start-Sleep -Milliseconds 250
  if(Test-Path -LiteralPath $receiptPath){
   $active=Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
   $live=Get-CimInstance Win32_Process -Filter "ProcessId = $($active.pid)" -ErrorAction SilentlyContinue
   if($active.runtime -eq (Join-Path $runtimePath 'scripts/fp_autoload.py') -and $live){$confirmed=$true;break}
  }
 }
 if(!$confirmed){throw 'New reader did not acquire its lock; restart required'}
 Write-Output "Installed per-user Startup watcher (Task Scheduler restricted); started PID $($process.Id). Five-minute checks while Windows is running. Private backend sync is not yet configured."
}
