$ErrorActionPreference="Stop"; $n="WorldCupEventProcessResearchRun"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue){Write-Host "exists";exit 0}
$a=New-ScheduledTaskAction -Execute "powershell.exe" -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\Users\Mahyar\worldcup-event-process-intelligence\scripts\run_event_process_intelligence.ps1"' -WorkingDirectory "C:/Users/Mahyar/worldcup-event-process-intelligence"
$t=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1)
$s=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 10) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $n -Action $a -Trigger $t -Settings $s -Description "research_only event-process worker (<=10h; offline; never modifies WorldCupShadowCollector)"
Write-Host "registered $n"
