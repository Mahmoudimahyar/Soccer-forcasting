# Durable event-process research launcher (research_only; offline; <=10h). Resumes the same run id.
$ErrorActionPreference="Stop"; $wt="C:/Users/Mahyar/worldcup-event-process-intelligence"; Set-Location $wt
$af="$wt/outputs/research_runs/active_run_id.txt"
if (Test-Path $af) { $rid=(Get-Content $af -Raw).Trim() } else { $rid="ep_20260627_run1"; New-Item -ItemType Directory -Force -Path "$wt/outputs/research_runs" | Out-Null; Set-Content -Path $af -Value $rid -NoNewline }
python "$wt/scripts/deep_research_supervisor.py" --resume-run-id $rid --config "configs/event_process_intelligence_v1.yaml" --hours 10 --max-workers 2
