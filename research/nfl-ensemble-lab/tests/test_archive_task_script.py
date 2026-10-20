"""Parse scheduler authoring without executing the script or task cmdlets."""
from pathlib import Path
import subprocess


def test_registration_command_is_inside_shouldprocess_guard():
    path=(Path(__file__).resolve().parents[1]/'scripts/register_archive_tasks.ps1').as_posix().replace("'","''")
    command="""
$tokens=$null; $errors=$null
$tree=[System.Management.Automation.Language.Parser]::ParseFile('PATH',[ref]$tokens,[ref]$errors)
if ($errors.Count -gt 0) { throw 'Script parse failed' }
$nodes=@($tree.FindAll({param($n) $n -is [System.Management.Automation.Language.CommandAst] -and $n.GetCommandName() -eq 'Register-ScheduledTask'},$true))
if ($nodes.Count -ne 1) { throw 'Expected one guarded registration command' }
foreach ($node in $nodes) {
  $owner=$node.Parent; $guarded=$false
  while ($null -ne $owner) {
    if ($owner -is [System.Management.Automation.Language.IfStatementAst] -and $owner.Clauses[0].Item1.Extent.Text.Contains('ShouldProcess')) { $guarded=$true }
    $owner=$owner.Parent
  }
  if (-not $guarded) { throw 'Task registration bypasses WhatIf/ShouldProcess guard' }
}
Write-Output 'AST guard verified; scheduler script not executed'
""".replace('PATH',path)
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'AST guard verified' in result.stdout
