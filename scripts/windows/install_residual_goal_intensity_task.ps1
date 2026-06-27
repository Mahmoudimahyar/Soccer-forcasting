$ErrorActionPreference = "Stop"; $n = "WorldCupResidualGoalIntensityResearchRun"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) { Write-Host "exists"; exit 0 }
$a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\Users\Mahyar\worldcup-residual-goal-intensity\scripts\run_residual_goal_intensity_v1.ps1"' -WorkingDirectory "C:/Users/Mahyar/worldcup-residual-goal-intensity"
$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 8) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $n -Action $a -Trigger $t -Settings $s -Description "research_only residual goal-intensity worker (<=8h; offline; never modifies WorldCupShadowCollector)"
Write-Host "registered $n"
