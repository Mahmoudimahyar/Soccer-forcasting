# Research Truth Fusion Watchdog — Runbook
research_only. Self-supervising watchdog (every 15 min, Task Scheduler) for the durable research run. Runs ONLY
from the research worktree; NEVER modifies/restarts WorldCupShadowCollector. Single global lock
(outputs/research_runs/.global.lock) -> no concurrent backfills/controllers.
## Reads only
run state.json/heartbeat.json/job_log.jsonl/artifact_manifest.json; execution manifest; collector heartbeat;
Task Scheduler state of the 3 research tasks. ## Writes only
outputs/research_runs/<run_id>/watchdog_log.jsonl + watchdog_state.json; notes/research/RESEARCH_TRUTH_FUSION_OPERATIONS_LOG.md.
## State machine
RUNNING (healthy + hb<10m -> do nothing). WAITING_FOR_API_QUOTA (ensure daily resume enabled; do not force).
WAITING_FOR_SOURCE (preserve work; continue unrelated AF jobs). FAILED_INTEGRITY (raw git-tracked / research
root in collector -> stop research task + disable resume + incident; never auto-restart). COMPLETE (only when
ALL hard gates objectively true -> stop watchdog + disable research tasks + final audit + tag). Crash (task not
Running + hb stale >15m + no lock + collector healthy -> restart SAME run id, resume unfinished jobs, no re-pull).
## The 3 research-only tasks (none touch the collector)
WorldCupResearchTruthFusionRun (main, <=10h) · WorldCupResearchTruthFusionResume (daily 03:00 quota probe) ·
WorldCupResearchTruthFusionWatchdog (15min). Remove with the uninstall_*.ps1 scripts on COMPLETE.
