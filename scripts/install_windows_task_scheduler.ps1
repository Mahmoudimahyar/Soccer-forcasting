# Register the prospective collector as a Windows Scheduled Task (V1.5).
# YOU run this manually; it is NOT auto-installed. It only schedules bounded single-pass runs of
# run_prospective_collection.ps1 (which is dry-run unless you set EXECUTE=1). It never trades.
#
# Usage (from an elevated PowerShell, in the repo root):
#   ./scripts/install_windows_task_scheduler.ps1 -IntervalMinutes 15
# To actually capture (not dry-run), set the EXECUTE env var for the task after reviewing the runbook.
param(
  [int]$IntervalMinutes = 15,
  [string]$TaskName = "WCDrawLab_ProspectiveCollector"
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $repo "scripts\run_prospective_collection.ps1"
if (-not (Test-Path $runner)) { throw "runner not found: $runner" }

Write-Host "About to register a scheduled task:"
Write-Host "  name     : $TaskName"
Write-Host "  action   : powershell -NoProfile -ExecutionPolicy Bypass -File `"$runner`""
Write-Host "  schedule : every $IntervalMinutes minutes (bounded single-pass each run; no daemon)"
Write-Host "  mode     : DRY-RUN by default (set EXECUTE=1 in the task environment to capture)"
Write-Host ""
Write-Host "This script does NOT start collection itself; Task Scheduler will invoke the runner."

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`"" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
  -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "Registered '$TaskName'. Remove it with scripts/uninstall_windows_task_scheduler.ps1."
