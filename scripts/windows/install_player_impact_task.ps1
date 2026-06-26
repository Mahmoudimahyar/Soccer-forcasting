# Register the ONE-TIME WorldCupPlayerImpactResearchRun task (<=6h, from THIS worktree).
# Does NOT touch WorldCupShadowCollector or any other task. research_only / experimental.
param([string]$StartIn = "00:05:00")  # default start 5 minutes from now
$ErrorActionPreference = "Stop"
$name = "WorldCupPlayerImpactResearchRun"
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { Write-Host "task already exists"; exit 0 }
$worktree = "C:/Users/Mahyar/worldcup-player-impact-xg"
$ps1 = "$worktree/scripts/run_player_impact_night.ps1"
$action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ps1`"" -WorkingDirectory $worktree
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date) + [TimeSpan]::Parse($StartIn))
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 6) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "research_only one-time player-impact + xG fusion run (<=6h)"
Write-Host "registered $name (one-time, <=6h, ignores duplicate instances)"
