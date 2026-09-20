# Durable HIERARCHICAL CROSS-DOMAIN TRANSFER launcher (research_only; OFFLINE local-data-only; <=10h).
# Resumes the SAME run id from outputs/research_runs/active_run_id.txt (else mints one). Reuses
# deep_research_supervisor.py with configs/hierarchical_domain_transfer_v1.yaml (JOB1..JOB14).
# NEVER touches the active collector (worldcup_draw_model_lab_FINAL / WorldCupShadowCollector), B1,
# frozen M1-M5, candidate.py, approved_models.yaml, trading/Kalshi/risk, or .env. paper-only. No external API.
$ErrorActionPreference = "Stop"
$wt = "C:/Users/Mahyar/worldcup-hierarchical-transfer"; Set-Location $wt
$af = "$wt/outputs/research_runs/active_run_id.txt"
if (Test-Path $af) {
    $rid = (Get-Content $af -Raw).Trim()
} else {
    $rid = "ht_" + (Get-Date -Format "yyyyMMdd_HHmmss") + "_run1"
    New-Item -ItemType Directory -Force -Path "$wt/outputs/research_runs" | Out-Null
    Set-Content -Path $af -Value $rid -NoNewline
}
python "$wt/scripts/deep_research_supervisor.py" --resume-run-id $rid `
    --config "configs/hierarchical_domain_transfer_v1.yaml" --hours 10 --max-workers 2
