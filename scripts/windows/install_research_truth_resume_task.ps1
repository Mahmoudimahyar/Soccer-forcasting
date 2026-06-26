# Daily off-peak resume task (probes quota; resumes backfill if available; harmless otherwise). NOT concurrent
# with the main run. Removes itself once the corpus gate is reached (managed by the operator/runbook).
$ErrorActionPreference="Stop"; $name="WorldCupResearchTruthFusionResume"
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$cmd = "cd 'C:/Users/Mahyar/worldcup-research-truth-fusion'; python scripts/resume_full_player_history_backfill.py"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -Command `"$cmd`"" -WorkingDirectory "C:/Users/Mahyar/worldcup-research-truth-fusion"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 6) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "research_only daily quota-window resume of the player-history backfill"
Write-Host "registered $name (daily 03:00, quota-probe-first)"
