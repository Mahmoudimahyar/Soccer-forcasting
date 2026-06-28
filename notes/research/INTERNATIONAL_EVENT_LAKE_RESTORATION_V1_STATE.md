# International Event Lake Restoration v1 — State / Backlog / Blockers / Resume

_research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible_

## State (as built)
- 13-job durable controller wired to the existing `scripts/deep_research_supervisor.py` harness via
  `configs/international_event_lake_restoration_v1.yaml` (run <=10h, 2 workers, per-job timeout 36000s,
  collector heartbeat guard, fail-closed preflight before each job, atomic state checkpoints, resume).
- Jobs `scripts/lake_jobs/lk_job01..lk_job13` + shared harness `scripts/lake_jobs/_lk.py`.
- Runner `scripts/run_international_event_lake_restoration.ps1` (resumes the same run id from
  `outputs/research_runs/active_run_id.txt`).
- Task installers/uninstallers under `scripts/windows/` for `WorldCupInternationalEventLakeRun`
  (one-time <=10h, IgnoreNew, StartWhenAvailable, RestartCount 3/5min) and
  `WorldCupInternationalEventLakeWatchdog` (every 10 min).
- Watchdog `scripts/international_event_lake_watchdog.py` (global lock; collector isolation + lock +
  heartbeat + lake retention + raw-not-git-tracked checks; restart only crashed; never restart a terminal
  clean run; disable main task on FAILED_INTEGRITY).
- Runbook `docs/INTERNATIONAL_EVENT_LAKE_RESTORATION_V1_RUNBOOK.md`.
- Tests `tests/test_lake_jobs_controller.py` (40 deterministic, hermetic).

## Verified on REAL data (current persistent lake)
- Lake objects: **60** (all hash-verified; sentinel all_ok; retention ok; isolation ok; 210,667 events;
  60/60 carry statsbomb_xg).
- Restore JOB04 is idempotent (60->60; already_present=58; copied=0; quarantined=0).
- Cohort JOB08 (raw-backed): **60 matches**, 4 excluded, **56 WDL-eligible**, 7,652 regulation-only causal
  snapshots, leakage self-test all_ok, no-2026-WC guarantee true.
- Exact senior-men's-international bridge: **258** rows (ambiguity-free).
- Prior StatsBomb cache (read-only source): 62 event files surviving.
- Dry-run: `queue_complete` with 13 complete.

## Backlog (real work the durable run will do when launched unattended)
- JOB3 official catalog: fetch official open-data competitions + match lists (network; official only).
- JOB5 strict bridge: classify official catalog vs local exact fixtures (needs JOB3).
- JOB6 acquire-official: bring the remaining exact-bridge matches into the lake from the official source
  (bridge 258 vs lake 60 -> up to ~198 candidates; copy-local first, then official retrieval). May end
  `waiting_for_official_source` for ids the official tree genuinely cannot serve (it lists exact ids).
- JOB9-12 power/eval/decision: rerun preregistered families on the expanded cohort once JOB6 grows it.

## Blockers
- None blocking the controller. JOB3/JOB6 require outbound access to
  `raw.githubusercontent.com/statsbomb/open-data` (the ONLY permitted host). If unavailable, those jobs
  emit `waiting_for_official_source` / `data_insufficient` honestly and resume later; the lake + cohort +
  eval still run on the 60 already-restored matches.

## Resume
- Run id persisted in `outputs/research_runs/active_run_id.txt`; relaunch resumes the same id and skips
  `complete` jobs. Restart is idempotent: the lake is content-addressed + first-write-wins; restore/acquire
  copy-only and never re-download a locally valid + hash-verified file.

## Guardrails (enforced + tested)
- Raw event JSON lives ONLY in the external lake (0 git-tracked here). External retrieval = OFFICIAL
  StatsBomb Open Data only. No API-Football/Odds/paid/scrape/mirror/browser/360/video/credentials.
- Never modifies `worldcup_draw_model_lab_FINAL` (collector dc73318), B1, frozen M1-M5, candidate.py,
  approved_models.yaml, trading/Kalshi/risk, .env, or existing raw/manifests.
- Strict EXACT bridge only; ambiguous never enters evaluation; no completed-2026-WC match anywhere.
- Independent unit = MATCH (match-level clustered power/bootstrap). Preregistered families only.
