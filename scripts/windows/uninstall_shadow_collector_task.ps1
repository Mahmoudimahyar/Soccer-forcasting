# Remove the WorldCupShadowCollector scheduled task (you run this). Stops all future collection cycles.
param([string]$TaskName = "WorldCupShadowCollector")
$ErrorActionPreference = "Stop"
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $t) { Write-Host "No task '$TaskName'. Nothing to do." }
else { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false; Write-Host "Removed '$TaskName'." }
