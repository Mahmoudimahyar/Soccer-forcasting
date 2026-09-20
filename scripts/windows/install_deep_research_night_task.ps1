# Register the ONE-TIME WorldCupDeepResearchNightRun task. Does NOT touch WorldCupShadowCollector.
param([string]$StartIn = "00:05:00")  # default start 5 minutes from now
$ErrorActionPreference = "Stop"
$name = "WorldCupDeepResearchNightRun"
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { Write-Host "task already exists"; exit 0 }
$ps1 = "C:/Users/Mahyar/worldcup-deep-research/scripts/run_deep_research_night.ps1"
$action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ps1`"" -WorkingDirectory "C:/Users/Mahyar/worldcup-deep-research"
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date) + [TimeSpan]::Parse($StartIn))
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 4) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "research_only one-time deep research run (<=4h)"
Write-Host "registered $name (one-time, <=4h, ignores duplicate instances)"
