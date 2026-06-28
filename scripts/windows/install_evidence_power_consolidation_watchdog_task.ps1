$ErrorActionPreference = "Stop"; $n = "WorldCupEvidencePowerConsolidationWatchdog"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -Command "python C:\Users\Mahyar\worldcup-evidence-power-consolidation\scripts\research_evidence_watchdog.py"' -WorkingDirectory "C:/Users/Mahyar/worldcup-evidence-power-consolidation"
# every 10 min, indefinitely (a self-supervising watchdog with a global lock; never starts a 2nd worker)
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration ([TimeSpan]::MaxValue)
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 9) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $n -Action $a -Trigger $t -Settings $s -Description "research_only Evidence-Power Consolidation watchdog (every 10min; global lock; restarts only crashed/stale run; never restarts a terminal clean run; never modifies WorldCupShadowCollector)"
Write-Host "registered $n"
