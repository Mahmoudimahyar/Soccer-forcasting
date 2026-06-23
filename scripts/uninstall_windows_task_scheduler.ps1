# Remove the prospective collector scheduled task (V1.5). YOU run this manually.
#   ./scripts/uninstall_windows_task_scheduler.ps1
param([string]$TaskName = "WCDrawLab_ProspectiveCollector")
$ErrorActionPreference = "Stop"
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $existing) {
  Write-Host "No scheduled task named '$TaskName' found. Nothing to do."
} else {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  Write-Host "Removed scheduled task '$TaskName'."
}
