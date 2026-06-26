# Durable research-truth run launcher (research_only). Runs the bounded controller ONCE, <=10h, from THIS
# worktree. Resumes the EXISTING active run id (outputs/research_runs/active_run_id.txt) when present so quota
# windows continue the SAME run; otherwise starts a fresh run id. Dynamic quota reserve is enforced inside the
# corpus backfill (configs/research_quota_policy.yaml). Never touches WorldCupShadowCollector.
$ErrorActionPreference = "Stop"
$wt = "C:/Users/Mahyar/worldcup-research-truth-fusion"; Set-Location $wt
$activeFile = "$wt/outputs/research_runs/active_run_id.txt"
if (Test-Path $activeFile) {
    $runId = (Get-Content $activeFile -Raw).Trim()
    python "$wt/scripts/deep_research_supervisor.py" --hours 10 --resume-run-id $runId --max-api-requests 2000 --config "configs/research_truth_full_corpus_xg_fusion_run_v1.yaml"
} else {
    $runId = "truth_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    python "$wt/scripts/deep_research_supervisor.py" --hours 10 --run-id $runId --max-api-requests 2000 --config "configs/research_truth_full_corpus_xg_fusion_run_v1.yaml"
}
