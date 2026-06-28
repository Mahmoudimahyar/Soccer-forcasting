# Register the International Event Lake watchdog (every 10 min, indefinitely). A self-supervising watchdog
# with a global lock -> never starts a 2nd worker. Verifies collector isolation + lock + heartbeat + lake
# retention + raw-not-git-tracked; restarts ONLY a crashed run; never restarts a terminal COMPLETE run;
# disables restart on FAILED_INTEGRITY. NEVER modifies the active collector. research_only.
$ErrorActionPreference = "Stop"; $n = "WorldCupInternationalEventLakeWatchdog"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$wt = "C:/Users/Mahyar/worldcup-international-event-lake"
$a = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"python $wt/scripts/international_event_lake_watchdog.py`"" `
    -WorkingDirectory $wt
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(3) `
    -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration ([TimeSpan]::MaxValue)
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 9) `
    -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $n -Action $a -Trigger $t -Settings $s `
    -Description "research_only International Event Lake watchdog (every 10min; global lock; verifies collector isolation + lock + heartbeat + lake retention + raw-not-git-tracked; restarts only crashed/stale run; never restarts a terminal clean run; disables restart on FAILED_INTEGRITY; never modifies WorldCupShadowCollector)"
Write-Host "registered $n"
