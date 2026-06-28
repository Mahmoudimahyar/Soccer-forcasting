# Evidence-Power Consolidation v1 — Runbook

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

A durable, restart-safe, bounded (≤8h) controller that consolidates the research lab's existing
**evidence** into a single audited package and quantifies the **statistical power** behind its headline
claim (the residual in-play W/D/L evaluation). It is **LOCAL-ARTIFACT-ONLY**: it reads validated artifacts
already on disk and performs **no** network / API-Football / Odds API / StatsBomb / scrape / credential /
browser access. It **never** modifies the active collector (`worldcup_draw_model_lab_FINAL` /
`WorldCupShadowCollector`), B1, frozen M1–M5, `candidate.py`, `approved_models.yaml`, trading/Kalshi/risk,
or `.env`. The independent unit is the **MATCH**, never a snapshot row; all power/bootstrap is match-level
clustered. No 2026 WC is touched in any rerun.

## Components

| file | role |
|---|---|
| `configs/evidence_power_consolidation_v1.yaml` | run policy + 12-job queue (JOB1..JOB12) |
| `scripts/evidence_jobs/_ev.py` | shared harness (run-dir / shared / emit / read-only builder runner) |
| `scripts/evidence_jobs/ev_job01..12_*.py` | the 12 jobs (each calls a REAL module / builder) |
| `scripts/deep_research_supervisor.py` | reused controller (deadline + budget + collector-health + checkpoints) |
| `scripts/run_evidence_power_consolidation_v1.ps1` | launcher (resume `active_run_id.txt` else mint) |
| `scripts/research_evidence_watchdog.py` | self-supervising watchdog (global lock, restart only crashed/stale) |
| `scripts/windows/install_evidence_power_consolidation_task.ps1` | register the run task |
| `scripts/windows/install_evidence_power_consolidation_watchdog_task.ps1` | register the watchdog task |
| `scripts/windows/uninstall_*` | tear down |

## The 12 jobs

1. **JOB1** preflight + dependency + isolation + test-baseline + dry-run note (critical)
2. **JOB2** research evidence registry
3. **JOB3** cohort lineage + exclusion ledger — match-level funnel (critical)
4. **JOB4** 58-match audit + independent reconstruction (critical)
5. **JOB5** reproducibility audit (7 evaluations)
6. **JOB6** detect + repair **verified** bugs only (else records `no_repair_required`)
7. **JOB7** rerun affected evals **only if** a verified repair (else skip with reason)
8. **JOB8** match-level statistical power
9. **JOB9** live-readiness matrix
10. **JOB10** decision memo (next-investment)
11. **JOB11** cross-artifact consistency audit
12. **JOB12** final report + decision memo + integrity audit (critical) → writes
    `notes/research/EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md`

Each job emits its last stdout line as JSON `{status, reason, state_updates}` with
`status ∈ {complete, skipped, failed, blocked, data_insufficient}`. An honest `skipped` /
`data_insufficient` (with a reason) is allowed when an input product is genuinely absent; a false
`complete` is never emitted.

## How to run

```powershell
# dry-run: verify the queue (script presence) without doing work
python scripts/deep_research_supervisor.py --config configs/evidence_power_consolidation_v1.yaml --dry-run
# -> expect stop_reason=queue_complete, 12 'complete' jobs

# real durable run (resumes active_run_id.txt or mints evp_<stamp>_run1)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_evidence_power_consolidation_v1.ps1

# install as scheduled tasks (one-time ≤8h run + 10-min watchdog)
powershell -File scripts/windows/install_evidence_power_consolidation_task.ps1
powershell -File scripts/windows/install_evidence_power_consolidation_watchdog_task.ps1
```

## Restart / watchdog semantics

- Single **global lock** (`outputs/research_runs/.global.lock`) — the watchdog never launches a 2nd worker.
- The supervisor is **idempotent**: completed jobs are skipped on resume (`state.json`).
- The watchdog **restarts only** a crashed/stale run (task not Running + heartbeat stale >15m + a job stuck
  `running` + collector healthy). It **never** restarts a terminal clean run (`queue_complete` / all jobs
  terminal) — no restart loops.
- **Fail-closed integrity gate:** raw git-tracked, or any canonical root resolving into the collector, →
  `FAILED_INTEGRITY` + stop + incident file. A collector-commit change is recorded as WATCH only (the
  collector is an independent system in a separate checkout).

## Outputs

- per-run: `outputs/research_runs/<run_id>/evidence_power/*.json`, `state.json`, `heartbeat.json`,
  `job_log.jsonl`, `run_summary.json`, `watchdog_log.jsonl`.
- canonical: `data/reference/*.json|.csv` (registry, lineage, exclusion ledger, 58-match audit, power,
  live-readiness, consistency, integrity).
- reports: `notes/research/EVIDENCE_POWER_CONSOLIDATION_V1_COMPLETION.md`,
  `EVIDENCE_POWER_DECISION_MEMO.md`, `evaluation_cohort_lineage_report.md`,
  `EVIDENCE_POWER_CONSOLIDATION_OPERATIONS_LOG.md`.

## The WHY-58 answer (verified)

258 exact-international bridge matches → intersect with the StatsBomb event JSONs **physically on disk**
→ **58** evaluable matches (200 drop with reason `missing_statsbomb_events`). Forward-chain test set = 46
(earliest competition `FIFA World Cup 2018` is train-only under `held_out_fold_rule`); LOCO = 58. The
independent cold recompute reproduces the reported pooled forward-chain R0 RPS **0.15263** and LOCO RPS
**0.14906** exactly. **58 is a preregistered data-availability boundary, not a bug.** Restoring the cohort
toward 258 is a *data-acquisition* step (re-pull StatsBomb events), not a modeling change.
