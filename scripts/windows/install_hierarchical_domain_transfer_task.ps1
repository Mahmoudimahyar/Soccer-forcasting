$ErrorActionPreference = "Stop"; $n = "WorldCupHierarchicalDomainTransferRun"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\Users\Mahyar\worldcup-hierarchical-transfer\scripts\run_hierarchical_domain_transfer_v1.ps1"' -WorkingDirectory "C:/Users/Mahyar/worldcup-hierarchical-transfer"
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 10) -MultipleInstances IgnoreNew -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $n -Action $a -Trigger $t -Settings $s -Description "research_only Hierarchical Cross-Domain Transfer worker (<=10h; OFFLINE local-data-only; never modifies WorldCupShadowCollector / B1 / frozen models / candidate.py / trading / .env)"
Write-Host "registered $n"
