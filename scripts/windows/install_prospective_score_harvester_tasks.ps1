# Registers the durable prospective score harvester + watchdog scheduled tasks (every 15 min).
# Safe by default: tasks run a bounded single cycle each; append-only; no Odds API; no trading path.
# Does NOT modify the WorldCupShadowCollector or any hierarchical-transfer task.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Register-Cycle($name, $script) {
  $action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument ("-NoProfile -ExecutionPolicy Bypass -File `"" + (Join-Path $repo $script) + "`"") `
    -WorkingDirectory $repo
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 9)
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Write-Output ("registered: " + $name)
}

Register-Cycle "WorldCupProspectiveScoreHarvester"        "scripts\windows\run_prospective_score_harvester.ps1"
Register-Cycle "WorldCupProspectiveScoreHarvesterWatchdog" "scripts\windows\run_prospective_score_harvester_watchdog.ps1"
Write-Output "done. (disable with uninstall_prospective_score_harvester_tasks.ps1)"
