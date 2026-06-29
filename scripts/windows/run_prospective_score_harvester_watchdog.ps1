# Wrapper invoked by Task Scheduler (WorldCupProspectiveScoreHarvesterWatchdog) each 15-min wake. Runs ONE
# watchdog cycle: inspects scorer health + integrity; restarts ONLY a crashed, non-terminal, unlocked
# scorer; never starts a concurrent scorer; disables restart on integrity failure. Read-only re: collector.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$logdir = Join-Path $repo "outputs\live_shadow\scoring_v1\scheduler_logs"
New-Item -ItemType Directory -Force -Path $logdir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$log = Join-Path $logdir "watchdog_$stamp.log"
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py "scripts\prospective_score_harvester_watchdog.py" *>> $log
exit $LASTEXITCODE
