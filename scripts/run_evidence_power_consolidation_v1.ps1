# Durable Evidence-Power Consolidation launcher (research_only; LOCAL-ARTIFACT-ONLY; <=8h). Resumes the
# same run id from outputs/research_runs/active_run_id.txt (else mints one). Reuses deep_research_supervisor.py.
# NEVER touches the active collector (worldcup_draw_model_lab_FINAL / WorldCupShadowCollector), B1,
# frozen M1-M5, candidate.py, approved_models.yaml, trading/Kalshi/risk, or .env. paper-only. No external API.
$ErrorActionPreference = "Stop"
$wt = "C:/Users/Mahyar/worldcup-evidence-power-consolidation"; Set-Location $wt
$af = "$wt/outputs/research_runs/active_run_id.txt"
if (Test-Path $af) {
    $rid = (Get-Content $af -Raw).Trim()
} else {
    $rid = "evp_" + (Get-Date -Format "yyyyMMdd_HHmmss") + "_run1"
    New-Item -ItemType Directory -Force -Path "$wt/outputs/research_runs" | Out-Null
    Set-Content -Path $af -Value $rid -NoNewline
}
python "$wt/scripts/deep_research_supervisor.py" --resume-run-id $rid `
    --config "configs/evidence_power_consolidation_v1.yaml" --hours 8 --max-workers 2
