# Wrapper invoked by Task Scheduler each 5-min wake. Runs ONE bounded collector cycle (not a loop, not
# Claude Code). Uses the project venv if present; loads .env locally; logs stdout/stderr. Never trades.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$logdir = Join-Path $repo "outputs\live_shadow\scheduler_logs"
New-Item -ItemType Directory -Force -Path $logdir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$log = Join-Path $logdir "cycle_$stamp.log"

# Prefer project venv interpreter if it exists; else system python.
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py "scripts\windows\shadow_collector_cycle.py" *>> $log
exit $LASTEXITCODE
