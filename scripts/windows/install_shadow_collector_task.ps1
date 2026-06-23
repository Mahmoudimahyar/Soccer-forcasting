# Install the WorldCupShadowCollector scheduled task (you run this; authorized after dry-run).
# Wakes every 5 minutes ONLY to run one bounded collector cycle (the cycle enforces all provider/snapshot
# rate limits + the 500-credit budget, and HALTS if trading flags are unsafe). Stops at the hard-end.
# It runs a local Python collector — NOT Claude Code — and can never trade.
param(
  [int]$IntervalMinutes = 5,
  [string]$TaskName = "WorldCupShadowCollector",
  [datetime]$HardEndUtc = "2026-07-05T00:00:00Z"
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runner = Join-Path $repo "scripts\windows\run_shadow_collector.ps1"
if (-not (Test-Path $runner)) { throw "runner missing: $runner" }

Write-Host "Registering scheduled task:"
Write-Host "  name        : $TaskName"
Write-Host "  runs        : powershell -File $runner   (one bounded cycle per wake)"
Write-Host "  every       : $IntervalMinutes min, until $($HardEndUtc.ToString('u'))"
Write-Host "  working dir : $repo"
Write-Host "  logs        : outputs\live_shadow\scheduler_logs\  | heartbeat+state: outputs\live_shadow\"
Write-Host "  safety      : HALTs unless KALSHI_ENABLE_LIVE_TRADING=false & TRADING_MODE=paper; never trades"

$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`"" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
  -RepetitionDuration ($HardEndUtc.ToLocalTime() - (Get-Date))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew
# Runs only while the user is logged in (no stored credentials, no secret exposure).
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
  -Description "World Cup 2026 shadow odds/forecast collector (research_only; never trades)." -Force
Write-Host "Registered '$TaskName'. Stop/remove: scripts\windows\uninstall_shadow_collector_task.ps1"
