<#
  run_dynamic_inplay_modeling_phase.ps1
  Launcher for the Dynamic In-Play MODELING PHASE (Component 5 / Phase 7).
  research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

  Resumes the SAME canonical research run id (truth_20260626_134931) via the durable supervisor's
  --resume-run-id path, so the 16-job modeling queue checkpoints into the existing run directory and every
  job writes its artifacts under <run>/model_phase. The workdir is the research worktree. Restart-safe:
  re-running skips already-complete jobs and continues from the first incomplete one.

  This phase is OFFLINE by construction (no Odds API / API-Football / StatsBomb network); the config caps
  external API budget so the supervisor fail-closes if any job ever reported a network request.

  Usage:
    pwsh -File scripts/run_dynamic_inplay_modeling_phase.ps1            # run / resume the phase
    pwsh -File scripts/run_dynamic_inplay_modeling_phase.ps1 -DryRun    # validate the queue only
#>
param(
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"

# workdir = research worktree (this script lives in <worktree>/scripts)
$Worktree = Split-Path -Parent $PSScriptRoot
Set-Location $Worktree

$RunId  = "truth_20260626_134931"
$Config = "configs/dynamic_inplay_modeling_phase_v1.yaml"
$Supervisor = "scripts/deep_research_supervisor.py"

# resolve a python interpreter
$Py = "python"
if (Test-Path (Join-Path $Worktree ".venv/Scripts/python.exe")) {
  $Py = Join-Path $Worktree ".venv/Scripts/python.exe"
}

Write-Host "[modeling-phase] worktree   = $Worktree"
Write-Host "[modeling-phase] run id      = $RunId (resume same run; artifacts -> outputs/research_runs/$RunId/model_phase)"
Write-Host "[modeling-phase] config      = $Config"
Write-Host "[modeling-phase] interpreter = $Py"

if ($DryRun) {
  Write-Host "[modeling-phase] DRY-RUN: validating the 16-job queue (expect queue_complete)"
  & $Py $Supervisor --dry-run --run-id mp_dry --config $Config
  exit $LASTEXITCODE
}

# Real run: resume the canonical run id; the supervisor enforces deadline + offline budget + collector health.
& $Py $Supervisor --resume-run-id $RunId --config $Config --hours 8 --max-workers 2
$rc = $LASTEXITCODE

$summary = Join-Path $Worktree "outputs/research_runs/$RunId/run_summary.json"
if (Test-Path $summary) {
  Write-Host "[modeling-phase] run_summary.json:"
  Get-Content $summary -Raw | Write-Host
}
$mp = Join-Path $Worktree "outputs/research_runs/$RunId/model_phase"
if (Test-Path $mp) {
  Write-Host "[modeling-phase] model_phase artifacts:"
  Get-ChildItem $mp -Filter "mj_job*.json" | Select-Object Name, Length | Format-Table | Out-String | Write-Host
}
exit $rc
