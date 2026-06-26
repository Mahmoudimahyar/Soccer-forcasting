# Register the self-supervising watchdog (every 15 min, research worktree only; never touches the collector).
$ErrorActionPreference="Stop"; $name="WorldCupResearchTruthFusionWatchdog"
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$cmd = "cd 'C:/Users/Mahyar/worldcup-research-truth-fusion'; python scripts/research_truth_fusion_watchdog.py"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$cmd`"" -WorkingDirectory "C:/Users/Mahyar/worldcup-research-truth-fusion"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 14)
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "research_only self-supervising watchdog (15min); never modifies WorldCupShadowCollector"
Write-Host "registered $name (every 15 min)"
