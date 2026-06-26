$name = "WorldCupDeepResearchNightRun"
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $name -Confirm:$false; Write-Host "removed $name"
} else { Write-Host "$name not present" }
