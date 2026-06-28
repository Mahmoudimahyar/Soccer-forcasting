$ErrorActionPreference = "Stop"; $n = "WorldCupInternationalEventLakeRun"
if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $n -Confirm:$false
    Write-Host "unregistered $n"
} else { Write-Host "absent" }
