# Hierarchical Cross-Domain Transfer v1 — Runbook

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

A durable, restart-safe, bounded (≤10h) controller that fits and evaluates a hierarchical cross-domain
**transfer ladder** (`research.transfer.{w2_reference_t0 … calibrated_transfer_simulation_t7}`) on the
leakage-safe, domain-normalized transfer dataset. The international event lake is the **PRIMARY test
population**; the club event-process auxiliary corpus is **auxiliary training only** (never an
international test row). Every candidate is judged against the **T0 remaining-time Poisson reference**
(`research.transfer.w2_reference_t0`) — never a weaker anchor.

It is **OFFLINE / LOCAL-DATA-ONLY**: it reads verified local products already on disk (the persistent
international event lake objects, the club auxiliary manifest, and the already-materialised
`data/processed/domain_normalized_transfer/transfer_dataset_v1.csv`) and performs **no** network /
API-Football / Odds API / StatsBomb / scrape / paid / credential / browser access. It **never** modifies the
active collector (`worldcup_draw_model_lab_FINAL` / `WorldCupShadowCollector`), B1, frozen M1–M5,
`candidate.py`, `approved_models.yaml`, trading/Kalshi/risk, or `.env`. The independent unit is the
**MATCH** (all bootstrap is match-level clustered). No completed-2026-World-Cup match is touched in any fold.

## Components

| file | role |
|---|---|
| `configs/hierarchical_domain_transfer_v1.yaml` | run policy + 14-job queue (JOB1..JOB14) |
| `scripts/ht_jobs/_ht.py` | shared harness (run-dir / artifacts / isolation / dataset loader / ladder scoring / emit) |
| `scripts/ht_jobs/ht_job01..14_*.py` | the 14 jobs (each calls a REAL module / builder / audit) |
| `src/wcdrawlab/research/transfer/w2_reference_t0.py` | the parameter-free T0 reference (anchor) |
| `src/wcdrawlab/research/transfer/domain_normalized_dataset.py` | the leakage-safe fold/baseline/stable-feature engine |
| `src/wcdrawlab/research/transfer/hierarchical_models.py` | the T1..T7 ladder fitters (ridge residual / partial-pooling / domain-weighted / selective / calibrated MC) |
| `scripts/deep_research_supervisor.py` | reused controller (deadline + budget + collector-health + checkpoints) |
| `scripts/run_hierarchical_domain_transfer_v1.ps1` | launcher (resume `active_run_id.txt` else mint) |
| `scripts/hierarchical_domain_transfer_watchdog.py` | self-supervising watchdog (global lock; restart only crashed; disable on FAILED_INTEGRITY) |
| `scripts/windows/install_hierarchical_domain_transfer_task.ps1` | register the run task `WorldCupHierarchicalDomainTransferRun` |
| `scripts/windows/install_hierarchical_domain_transfer_watchdog_task.ps1` | register the watchdog task `WorldCupHierarchicalDomainTransferWatchdog` |
| `scripts/windows/uninstall_*` | tear down both tasks |

## The 14 jobs

1. **JOB1** deps + isolation + worktree + test-baseline + dry-run preflight (critical)
2. **JOB2** domain inventory + contract (intl cohort + club auxiliary manifest) (critical)
3. **JOB3** feature-overlap / domain-shift audit (cross-domain SMD honestly `data_insufficient` when club absent)
4. **JOB4** freeze the feature-stability registry (kept subset + classes)
5. **JOB5** fold-specific domain-normalized transfer datasets — build (if absent) + strict leakage audit (critical)
6. **JOB6** fit the T0–T7 ladder (TRAIN rows only) and persist fitted coefficients + gate decisions
7. **JOB7** primary forward-chain international eval (held-out tournament rows vs T0, match-level bootstrap)
8. **JOB8** leave-one-competition-out (LOCO) eval (international population)
9. **JOB9** transfer-coverage / overlap / selective-fallback audit + isolation re-assert
10. **JOB10** ablations (no-xG / no-shot / no-possession / state-only) + club-family removal control
11. **JOB11** calibration + match-bootstrap + reliability + domain-shift diagnostics
12. **JOB12** failure analysis (honest verdict; single-domain caveat)
13. **JOB13** model registry + feature-stability registry + decision ledger →
    `data/reference/hierarchical_transfer_decision_ledger.{json,csv}`
14. **JOB14** scientific report + final integrity audit (critical) →
    `notes/research/HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md`

Each job emits its last stdout line as JSON `{status, reason, state_updates}` with
`status ∈ {complete, skipped, failed, blocked, data_insufficient}`. An honest `skipped` /
`data_insufficient` (with a concrete reason) is allowed when an input product is genuinely absent; a false
`complete` is **never** emitted. Each job records start/end, source manifests, hashes, cohort counts,
status, and resumes idempotently (the supervisor skips already-`complete` jobs on restart).

## How to run

```powershell
# dry-run: verify the queue (script presence) without doing work
python scripts/deep_research_supervisor.py --config configs/hierarchical_domain_transfer_v1.yaml --dry-run
# -> expect stop_reason=queue_complete, 14 'complete' jobs

# real durable run (resumes active_run_id.txt or mints ht_<stamp>_run1)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_hierarchical_domain_transfer_v1.ps1

# install as scheduled tasks (one-time ≤10h run + 10-min watchdog)
powershell -File scripts/windows/install_hierarchical_domain_transfer_task.ps1
powershell -File scripts/windows/install_hierarchical_domain_transfer_watchdog_task.ps1

# tear down
powershell -File scripts/windows/uninstall_hierarchical_domain_transfer_watchdog_task.ps1
powershell -File scripts/windows/uninstall_hierarchical_domain_transfer_task.ps1
```

## Outputs

- per-run artifacts: `outputs/research_runs/<run_id>/hierarchical_transfer/job0N_*.json`,
  `fitted_ladder.json`, `state.json`, `heartbeat.json`, `run_summary.json`, `artifact_manifest.json`;
- durable registries: `data/reference/hierarchical_feature_stability_registry.{json,csv}`,
  `data/reference/hierarchical_transfer_decision_ledger.{json,csv}`;
- report: `notes/research/HIERARCHICAL_DOMAIN_TRANSFER_V1_COMPLETION.md`;
- watchdog log: `notes/research/HIERARCHICAL_DOMAIN_TRANSFER_OPERATIONS_LOG.md`.

## Safety / isolation invariants (enforced by JOB1/JOB9/JOB14 + the watchdog)

- this worktree is never the active collector checkout; no data root resolves into the collector
  (`data_roots` fails closed);
- `data/raw` is never git-tracked; the international event lake lives outside the worktree;
- no HT job imports a network/provider/scrape/odds/credential token at module scope;
- no completed-2026-World-Cup row appears in any fold (re-asserted from the materialised CSV);
- every model and artifact is `research_only` and **not** runtime/trade/live approved.

## Watchdog policy

Runs every 10 min under a global lock (`outputs/research_runs/.ht_global.lock`) so it never starts a second
worker. It restarts **only** a crashed/stale run (run task not `Running` + heartbeat stale >15 min + a job
stuck `running` + collector healthy). It **never** restarts a terminal clean run (`queue_complete` / all
jobs terminal / `run_state=COMPLETE`). On a `FAILED_INTEGRITY` (a violation we could cause: raw git-tracked,
a data root in the collector) it **stops the worker and disables restart** and writes
`INCIDENT_failed_integrity.json`. A collector-commit change is an independent system event → observe only.
```
