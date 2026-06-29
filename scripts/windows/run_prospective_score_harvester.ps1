# Wrapper invoked by Task Scheduler (WorldCupProspectiveScoreHarvester) each 15-min wake. Runs ONE bounded
# harvester cycle (not a loop, not Claude Code). Append-only scoring; never calls The Odds API; never
# touches frozen predictions or the collector. Logs stdout/stderr.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # worktree root
Set-Location $repo
$logdir = Join-Path $repo "outputs\live_shadow\scoring_v1\scheduler_logs"
New-Item -ItemType Directory -Force -Path $logdir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$log = Join-Path $logdir "harvest_$stamp.log"
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py "scripts\run_prospective_score_harvester.py" *>> $log
exit $LASTEXITCODE
