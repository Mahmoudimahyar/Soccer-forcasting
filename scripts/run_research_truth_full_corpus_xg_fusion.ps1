# Durable research-truth run launcher (research_only). Runs the bounded controller ONCE, <=10h, from THIS worktree.
$ErrorActionPreference = "Stop"
$wt = "C:/Users/Mahyar/worldcup-research-truth-fusion"; Set-Location $wt
$runId = "truth_" + (Get-Date -Format "yyyyMMdd_HHmmss")
python "$wt/scripts/deep_research_supervisor.py" --hours 10 --run-id $runId --config "configs/research_truth_full_corpus_xg_fusion_run_v1.yaml"
