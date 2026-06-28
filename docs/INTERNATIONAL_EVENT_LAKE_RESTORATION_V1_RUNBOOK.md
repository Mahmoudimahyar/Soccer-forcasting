# International Event Lake Restoration v1 — Runbook

_research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible_

A durable, restart-safe, bounded (<=10h) 13-job controller that restores and audits the **International
Event Lake** — a content-addressed, fail-closed StatsBomb Open Data event store for senior **men's
international** matches — then builds the frozen evaluation cohort and reruns the preregistered model
families under the locked protocol.

## What this is (and is not)
- **Is**: a guarded restoration + evaluation pipeline over the *persistent external lake* at
  `C:/Users/Mahyar/worldcup_data_lake/statsbomb_open/international_event_lake_v1`. Raw event JSON lives
  **only** in that lake (outside every git worktree, 0 git-tracked here).
- **Is not**: a trading/runtime/live system. It never touches the active collector
  (`worldcup_draw_model_lab_FINAL` / `WorldCupShadowCollector`), B1, frozen M1-M5, `candidate.py`,
  `approved_models.yaml`, trading/Kalshi/risk, or `.env`.

## Hard guarantees (fail-closed)
- **External retrieval = OFFICIAL StatsBomb Open Data ONLY**
  (`raw.githubusercontent.com/statsbomb/open-data`), and only in JOB6 acquisition (engine-owned:
  <=4 concurrent, exponential backoff, <=2 retries, atomic tmp->rename, sha256, immutable manifest append).
  No API-Football / Odds / paid / scrape / mirror / browser / 360 / video / credentials.
- **Strict EXACT international bridge only.** Ambiguous ids are dropped and never enter evaluation.
- **No completed-2026-World-Cup match** in any cohort / fit / calibration / selection.
- **The independent unit is the MATCH**, never a snapshot row; all power/bootstrap is match-level clustered.
- **Reuses ONLY preregistered model families** (remaining-time Poisson reference + time-score + xG-state +
  event-process + residual/selective-correction). No new features / search / neural / market.

## The 13 jobs (`configs/international_event_lake_restoration_v1.yaml`)
| id | script | what |
| --- | --- | --- |
| JOB1  | `lk_job01_preflight.py`                | preflight + dependency + isolation + test-baseline + dry-run note (critical) |
| JOB2  | `lk_job02_init_lake.py`                | init the external lake + bind the retention contract (critical) |
| JOB3  | `lk_job03_official_catalog.py`         | official senior men's international catalog + selection manifest |
| JOB4  | `lk_job04_legacy_restore.py`           | legacy restoration manifest + COPY valid local events INTO the lake (critical) |
| JOB5  | `lk_job05_strict_bridge.py`            | expanded STRICT exact bridge (official -> local exact fixtures) |
| JOB6  | `lk_job06_acquire_official.py`         | acquire + validate MISSING official events INTO the lake (official-source-only) |
| JOB7  | `lk_job07_quality_retention_audit.py`  | event-lake quality + retention audit — **FAIL CLOSED** (critical) |
| JOB8  | `lk_job08_cohort.py`                   | frozen cohort + exclusion ledger + causal datasets (raw-backed) (critical) |
| JOB9  | `lk_job09_power.py`                    | match-level statistical power |
| JOB10 | `lk_job10_forward_chain_eval.py`       | strict forward-chain evaluation (preregistered families; locked rule) |
| JOB11 | `lk_job11_loco_calibration_bootstrap.py` | LOCO + calibration + bootstrap + ablations |
| JOB12 | `lk_job12_decision_ledger.py`          | decision ledger + reproducibility + source-quality |
| JOB13 | `lk_job13_completion_report.py`        | completion report + final integrity audit (critical) |

Each job is invoked by the supervisor as `python <script> --run-dir <dir>` and prints, as its LAST stdout
line, a JSON object `{"status", "reason", "api_requests", "state_updates"}`. Status is one of
`complete / skipped / failed / blocked / waiting_for_official_source / data_insufficient`. A job records
start/end/source-roots/input+output-hashes/cohort-counts/status/resume; a false `complete` is never emitted.
**JOB6 may end `waiting_for_official_source`** if the official source genuinely cannot serve a match after
retries — it lists the exact missing sb_match_ids and the durable run resumes them later.

## Run it
Dry-run (verify the queue resolves all 13 scripts; no work):
```powershell
python scripts/deep_research_supervisor.py --dry-run `
  --config configs/international_event_lake_restoration_v1.yaml
# -> {"supervisor":"done","stop_reason":"queue_complete", ...} with 13 complete
```
Foreground durable run (resumes the same run id; <=10h):
```powershell
pwsh scripts/run_international_event_lake_restoration.ps1
```
Unattended (Task Scheduler, one-time <=10h, RestartCount 3/5min, IgnoreNew, StartWhenAvailable):
```powershell
pwsh scripts/windows/install_international_event_lake_task.ps1
pwsh scripts/windows/install_international_event_lake_watchdog_task.ps1   # every 10 min
```
Uninstall:
```powershell
pwsh scripts/windows/uninstall_international_event_lake_watchdog_task.ps1
pwsh scripts/windows/uninstall_international_event_lake_task.ps1
```

## Resume semantics
- The run id is persisted in `outputs/research_runs/active_run_id.txt`. Re-launching resumes the same id;
  the supervisor skips jobs already `complete` and re-runs the rest. Restart is idempotent (the lake is
  content-addressed + first-write-wins; the restore/acquire jobs copy-only and never re-download a locally
  valid file).

## Watchdog (`scripts/international_event_lake_watchdog.py`)
- Runs every 10 min under a single **global lock** — never a 2nd worker. Each cycle verifies collector
  isolation, the lock, the collector heartbeat (commit drift = WATCH only), lake retention, and that raw +
  the lake objects/ tree are 0 git-tracked. It restarts **only** a crashed/stale run; **never** restarts a
  terminal-clean (`queue_complete`) run; on a **FAILED_INTEGRITY** violation it stops AND **disables** the
  main task (no auto-restart).

## Products (`data/reference/`)
- `official_modern_international_catalog.{csv,json}` + `_selection_manifest.{csv,json}`
- `expanded_international_bridge_manifest.{csv,json}`
- `international_event_lake_cohort_manifest.{csv,json}`, `_cohort_exclusions.csv`, `_cohort_report.md`
- `international_event_lake_power_analysis.json`, `_minimum_evidence_requirements.json`
- `international_event_lake_evaluation_metrics.json`, `_calibration.json`, `_bootstrap.json`,
  `_reproducibility_audit.json`, `_model_decision_ledger.{csv,json}`, `_decision_package.json`
- Lake objects/index/manifests/integrity/logs under the external lake root.
- `notes/research/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_COMPLETION.md` (JOB13).

## Integrity / verification
```powershell
python scripts/audit_international_event_lake.py            # fail-closed sentinel (exit!=0 on any failure)
python scripts/verify_international_event_lake_retention.py # retention guarantees
python -m pytest -q tests/test_lake_jobs_controller.py      # controller + isolation tests
```
