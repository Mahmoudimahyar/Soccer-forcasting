# Deep Research night run launcher (research_only). Runs the bounded controller ONCE, <=4h, from THIS worktree.
# Never modifies the active WorldCupShadowCollector. No Odds API. No secrets printed.
$ErrorActionPreference = "Stop"
$worktree = "C:/Users/Mahyar/worldcup-deep-research"
Set-Location $worktree
$runId = "night_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$env:DR_STAMP = (Get-Date -Format "yyyyMMddHHmmss")
python "$worktree/scripts/deep_research_supervisor.py" --hours 4 --run-id $runId --config "configs/deep_research_run_v1.yaml"
