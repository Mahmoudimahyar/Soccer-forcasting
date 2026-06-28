# Register the durable International Event Lake Restoration v1 run as a ONE-TIME <=10h Task Scheduler task.
# IgnoreNew (never a 2nd worker), StartWhenAvailable, RestartCount 3 / RestartInterval 5min. research_only.
# NEVER touches the active collector / B1 / frozen M1-M5 / candidate.py / trading / .env.
$ErrorActionPreference = "Stop"; $n = "WorldCupInternationalEventLakeRun"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$wt = "C:/Users/Mahyar/worldcup-international-event-lake"
$a = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wt/scripts/run_international_event_lake_restoration.ps1`"" `
    -WorkingDirectory $wt
# one-time, start ~2 min from now, run when available
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2)
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 10) `
    -MultipleInstances IgnoreNew -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $n -Action $a -Trigger $t -Settings $s `
    -Description "research_only durable International Event Lake Restoration v1 (<=10h, one-time, IgnoreNew, StartWhenAvailable, RestartCount 3/5min; official StatsBomb open-data only; never modifies WorldCupShadowCollector / the active collector)"
Write-Host "registered $n"
