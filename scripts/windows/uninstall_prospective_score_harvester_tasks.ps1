# Disables and removes the durable prospective score harvester + watchdog scheduled tasks.
# Never touches WorldCupShadowCollector or any hierarchical-transfer task.
$ErrorActionPreference = "SilentlyContinue"
foreach ($t in "WorldCupProspectiveScoreHarvester", "WorldCupProspectiveScoreHarvesterWatchdog") {
  Disable-ScheduledTask -TaskName $t | Out-Null
  Unregister-ScheduledTask -TaskName $t -Confirm:$false | Out-Null
  Write-Output ("removed: " + $t)
}
