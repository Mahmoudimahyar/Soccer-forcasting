$ErrorActionPreference = "SilentlyContinue"; $n = "WorldCupEvidencePowerConsolidationWatchdog"
Stop-ScheduledTask -TaskName $n
Unregister-ScheduledTask -TaskName $n -Confirm:$false
Write-Host "unregistered $n"
