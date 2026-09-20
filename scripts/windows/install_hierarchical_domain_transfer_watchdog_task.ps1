$ErrorActionPreference = "Stop"; $n = "WorldCupHierarchicalDomainTransferWatchdog"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -Command "python C:\Users\Mahyar\worldcup-hierarchical-transfer\scripts\hierarchical_domain_transfer_watchdog.py"' -WorkingDirectory "C:/Users/Mahyar/worldcup-hierarchical-transfer"
# every 10 min, indefinitely (a self-supervising watchdog with a global lock; never starts a 2nd worker)
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration ([TimeSpan]::MaxValue)
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 9) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $n -Action $a -Trigger $t -Settings $s -Description "research_only Hierarchical Cross-Domain Transfer watchdog (every 10min; global lock; checks collector isolation + lock + heartbeat + raw-not-git-tracked; restarts only a crashed run; never restarts a terminal COMPLETE; disables restart on FAILED_INTEGRITY; never modifies WorldCupShadowCollector)"
Write-Host "registered $n"
