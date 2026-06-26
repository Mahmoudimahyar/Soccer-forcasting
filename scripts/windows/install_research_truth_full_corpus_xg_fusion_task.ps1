param([string]$StartIn = "00:02:00")
$ErrorActionPreference = "Stop"; $name = "WorldCupResearchTruthFusionRun"
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$ps1 = "C:/Users/Mahyar/worldcup-research-truth-fusion/scripts/run_research_truth_full_corpus_xg_fusion.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ps1`"" -WorkingDirectory "C:/Users/Mahyar/worldcup-research-truth-fusion"
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date) + [TimeSpan]::Parse($StartIn))
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 10) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "research_only one-time research-truth run (<=10h)"
Write-Host "registered $name"
