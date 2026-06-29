# DEFERRED, dry-run by default. Deploys a narrow result-refresh adapter to the live collector's score path
# ONLY when invoked with -Execute. Backs up the target, atomic-swaps, smoke-tests, auto-restores on failure.
# Never changes the collector branch/commit/scheduler, odds capture, prediction freeze, models, or trading.
param([switch]$Execute)
$ErrorActionPreference = "Stop"
$collector = "C:\Users\Mahyar\worldcup_draw_model_lab_FINAL"
$target = Join-Path $collector "scripts\windows\shadow_collector_cycle.py"
$adapter = Join-Path $collector "scripts\windows\shadow_collector_cycle.with_refresh.py"   # prepared, reviewed adapter
$backup  = "$target.rollback"

Write-Output "Deployment plan (narrow result-refresh adapter):"
Write-Output "  target : $target"
Write-Output "  backup : $backup"
Write-Output "  adapter: $adapter (must be a reviewed, prepared file)"
Write-Output "Preconditions: collector healthy; KALSHI_ENABLE_LIVE_TRADING=false; TRADING_MODE=paper; no Odds API in scoring."

if (-not $Execute) {
  Write-Output "DRY-RUN only. Re-run with -Execute to apply (after preparing and reviewing the adapter file)."
  exit 0
}
if (-not (Test-Path $adapter)) { throw "No prepared adapter at $adapter. Deferral stands; nothing changed." }

Copy-Item $target $backup -Force                       # rollback copy
try {
  Copy-Item $adapter $target -Force                    # atomic swap
  $py = Join-Path $collector ".venv\Scripts\python.exe"; if (-not (Test-Path $py)) { $py = "python" }
  & $py (Join-Path $collector "scripts\windows\shadow_collector_cycle.py") --dry-run
  if ($LASTEXITCODE -ne 0) { throw "smoke test failed rc=$LASTEXITCODE" }
  Write-Output "deployed + smoke test passed."
} catch {
  Copy-Item $backup $target -Force                     # auto-restore
  Write-Output ("DEPLOY FAILED -> rolled back. " + $_.Exception.Message)
  exit 1
}
