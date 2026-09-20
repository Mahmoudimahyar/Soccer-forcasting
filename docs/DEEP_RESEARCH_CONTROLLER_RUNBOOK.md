# Deep Research Controller — Runbook
research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

## What it is
A restart-safe, bounded (<=4h) local controller that runs a FINITE ordered job queue
(configs/deep_research_run_v1.yaml) for in-play research. It writes ONLY to outputs/research_runs/<run_id>/ and
gitignored raw. It NEVER touches WorldCupShadowCollector, uses NO Odds API, prints no secrets, and STOPS on
deadline / API-budget / stale-collector-heartbeat (fail-closed). No infinite loop (finite queue + hard deadline).

## Commands (from this worktree)
- Dry-run validation:  `python scripts/deep_research_supervisor.py --dry-run --run-id dryrun`
- Direct run:          `python scripts/deep_research_supervisor.py --hours 4 --run-id <id>`
- Resume:              `python scripts/deep_research_supervisor.py --resume-run-id <id>`  (idempotent; skips complete jobs)
- Scheduled (one-time): `powershell -File scripts/windows/install_deep_research_night_task.ps1`
  then it runs once via scripts/run_deep_research_night.ps1; remove with uninstall_deep_research_night_task.ps1.

## Outputs (per run)
outputs/research_runs/<run_id>/{state.json, heartbeat.json, job_log.jsonl, run_summary.json, *.json, draft_report.md}

## Safety invariants
collector untouched; KALSHI_ENABLE_LIVE_TRADING=false; TRADING_MODE=paper; API-Football only; raw gitignored;
no model trained/promoted; unresolved fixtures excluded from datasets.
