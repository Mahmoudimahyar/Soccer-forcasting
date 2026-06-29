# Reverts the narrow result-refresh adapter deployed by deploy_prospective_score_adapter.ps1.
# Restores the collector's score-path file from its .rollback backup. Never changes branch/commit/scheduler.
$ErrorActionPreference = "Stop"
$collector = "C:\Users\Mahyar\worldcup_draw_model_lab_FINAL"
$target = Join-Path $collector "scripts\windows\shadow_collector_cycle.py"
$backup = "$target.rollback"
if (-not (Test-Path $backup)) { Write-Output "no rollback backup found; nothing to revert."; exit 0 }
Copy-Item $backup $target -Force
Remove-Item $backup -Force
Write-Output "rolled back collector score path to pre-deploy state."
