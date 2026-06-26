# Research Truth + Full Corpus + xG Fusion — Runbook
research_only. Durable <=10h controller (reuses scripts/deep_research_supervisor.py) running the 16-job finite
queue in configs/research_truth_full_corpus_xg_fusion_run_v1.yaml. Writes ONLY to outputs/research_runs/ +
gitignored raw; never touches WorldCupShadowCollector; no Odds API; fails closed; marks INCOMPLETE if any
Phase-10 gate is unmet. Status: Phase 0-1 (truth registry + execution manifest) DONE; JOB4 corpus completion is
quota-bounded MULTI-DAY (1,940 fixtures outstanding > one-day budget). rt_jobNN wrappers reuse inherited
player_history_backfill / statsbomb acquire / snapshot+eval; the xG-snapshot JOIN (JOB9) is the key remaining build.
## Commands
- Dry-run: python scripts/deep_research_supervisor.py --dry-run --run-id dry --config configs/research_truth_full_corpus_xg_fusion_run_v1.yaml
- Run/resume: python scripts/deep_research_supervisor.py --resume-run-id <id> --config configs/research_truth_full_corpus_xg_fusion_run_v1.yaml
- Scheduled: powershell -File scripts/windows/install_research_truth_full_corpus_xg_fusion_task.ps1
## Hard completion gates (Phase 10) — current objective status
#2 AF manifest >=95%: FALSE (3%). #5 StatsBomb >=90%: FALSE (23%). #6 xG join nonzero: FALSE (0). -> INCOMPLETE.
