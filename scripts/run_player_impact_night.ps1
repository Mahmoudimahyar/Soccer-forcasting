# Player-Impact + xG Fusion durable run launcher (research_only / experimental / not_runtime_approved /
# not_trade_eligible / not_live_eligible). Runs the inherited bounded controller ONCE, <=6h, from THIS
# worktree. Never modifies the active WorldCupShadowCollector at worldcup_draw_model_lab_FINAL. No Odds API.
# No secrets printed. Restart-safe: re-running with the same run-id resumes (completed jobs are skipped).
$ErrorActionPreference = "Stop"
$worktree = "C:/Users/Mahyar/worldcup-player-impact-xg"
Set-Location $worktree
$runId = "player_impact_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$env:DR_STAMP = (Get-Date -Format "yyyyMMddHHmmss")
python "$worktree/scripts/deep_research_supervisor.py" `
  --hours 6 `
  --run-id $runId `
  --config "configs/player_impact_xg_fusion_run_v1.yaml"
