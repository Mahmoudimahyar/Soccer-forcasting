# Bounded single-pass prospective collection (V1.5). SAFE BY DEFAULT: dry-run unless $env:EXECUTE -eq "1".
# Invoked by Windows Task Scheduler in short windows — NOT a daemon. Never trades, never changes the model.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$execArg = ""
if ($env:EXECUTE -eq "1") { $execArg = "--execute" }
$sid = "sched_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

# Collector handles a missing queue as a graceful no-op.
python scripts/prospective_collect.py $execArg --session-id $sid
# Score finished matches (metrics only; never updates the model).
try { python scripts/prospective_score.py } catch { }
exit 0
