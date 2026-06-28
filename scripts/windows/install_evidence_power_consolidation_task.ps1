$ErrorActionPreference = "Stop"; $n = "WorldCupEvidencePowerConsolidationRun"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\Users\Mahyar\worldcup-evidence-power-consolidation\scripts\run_evidence_power_consolidation_v1.ps1"' -WorkingDirectory "C:/Users/Mahyar/worldcup-evidence-power-consolidation"
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 8) -MultipleInstances IgnoreNew -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $n -Action $a -Trigger $t -Settings $s -Description "research_only Evidence-Power Consolidation worker (<=8h; local-artifact-only; never modifies WorldCupShadowCollector)"
Write-Host "registered $n"
