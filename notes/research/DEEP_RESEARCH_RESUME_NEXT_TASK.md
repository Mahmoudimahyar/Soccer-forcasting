# Resume Next Task
Controller run_id night_main launched (finite queue, <=4h). If interrupted, resume idempotently:
`python scripts/deep_research_supervisor.py --resume-run-id night_main` (skips complete jobs). After the queue
completes -> Phase 8: read outputs/research_runs/night_main/run_summary.json, audit, remove the scheduled task,
write completion report, commit, tag deep-research-inplay-foundation-v1 (or -blocked on critical data-integrity failure).
