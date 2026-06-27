# Residual Goal-Intensity v1 — Runbook (Phase 7 durable controller)

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

A bounded (≤8h), restart-safe, fail-closed research run that evaluates whether a leakage-safe
**event-process correction** improves in-play forecasting **beyond a parameter-free W2 reference
intensity** — treating the remaining-time Poisson model (W2) as a REFERENCE INTENSITY (side-specific
remaining-goal rates), **not** a competing classifier. Reuses the existing
`scripts/deep_research_supervisor.py` controller and the `wcdrawlab.research.residual_intensity` package.

## Isolation guarantees (hard constraints)
- Runs ONLY in `C:/Users/Mahyar/worldcup-residual-goal-intensity`. Absolute paths everywhere.
- NEVER touches `C:/Users/Mahyar/worldcup_draw_model_lab_FINAL` (the live `WorldCupShadowCollector`),
  B1, frozen M1–M5, `candidate.py`, `approved_models.yaml`, trading/Kalshi/risk, or `.env`.
- **NO network / NO API** (no API-Football, no Odds API, no download). Validated LOCAL data only.
- `paper` trading mode; `kalshi_live_trading: false`. Every artifact carries the research-only labels.
- The collector is on `data_roots.forbidden_roots()`; `_rg.py` raises if it ever resolves inside it.

## What it consumes (already on disk, gitignored raw)
- `data/processed/event_process_snapshots/intl_event_process_snapshots.csv` (+ `intl_targets_*.csv`)
  — the leakage-safe international causal-snapshot panel (regulation only, minute ≤ cutoff, 2026 WC
  EXCLUDED), loaded + annotated through `residual_intensity.datasets.load_residual_rows()`.
- Club auxiliary snapshots train ONLY the frozen club-transfer representation (never intl test rows).

## What it writes (derived, committed)
- `outputs/research_runs/<run_id>/residual_goal_intensity/*.json` — per-job artifacts + manifest.
- `data/reference/residual_goal_intensity_decision_ledger.{csv,json}` — canonical per-model verdicts.
- `data/reference/residual_goal_intensity/feature_catalog.csv` — feature catalog mirror.
- `notes/research/residual_goal_intensity_scientific_report_draft.md` — honest scientific report draft.

## The 14 jobs (`scripts/residual_jobs/rg_jobNN_*.py`)
| Job | Purpose |
|-----|---------|
| JOB1  | preflight + dependency-verify (event-process **terminal**) + isolation + dry-run note |
| JOB2  | build residual dataset + horizon targets (no-2026, intl-only, censoring recorded) |
| JOB3  | availability gate + interpretable regimes + feature catalog |
| JOB4  | side-specific intensity family **I0–I3** (LOCO Poisson deviance vs i0) |
| JOB5  | near-term horizon family **H0–H4** (5/10/15min, right-censored, LOCO Brier vs h0) |
| JOB6  | residual W/D/L family **R0–R6** (LOCO pooled + per-match RPS series) |
| JOB7  | **primary** forward-chain intl W/D/L (kickoff order; r0 anchor) |
| JOB8  | secondary LOCO W/D/L + per-fold wins + paired match-level bootstrap vs r0 |
| JOB9  | selective-gate coverage / fallback audit (α=0 reachable; corrected-vs-fallback) |
| JOB10 | mandatory ablations (leave-one-family-out, only-one-in, availability-gate on/off) |
| JOB11 | calibration + match-bootstrap + draw-channel reliability + intensity diagnostics |
| JOB12 | failure analysis (RPS delta r4−r0 by regime / state / tier / minute / xG) |
| JOB13 | model registry + feature catalog + **decision ledger** (preregistered promotion rule) |
| JOB14 | scientific report + **integrity audit** (self-test + leakage + no-2026 + isolation) |

Each job prints, as its LAST stdout line, a JSON `{"status","reason","state_updates",...}` with status in
`{complete, skipped, data_insufficient, failed}`. Honest `data_insufficient` (with a concrete reason) is
allowed when an input product is genuinely absent; a false `complete` is never emitted. The supervisor
checkpoints `state.json` atomically, writes a heartbeat, and always writes `run_summary.json`.

## Promotion rule (preregistered; `_rg.candidate_verdict`)
A candidate is promoted to `research_candidate_for_future_shadow_review` ONLY if ALL hold out-of-sample:
beats its W2 reference on pooled RPS/Brier/deviance; favorable in a fold majority (≥0.6); match-level
paired-bootstrap 95% CI upper bound < 0; draw-channel calibration not degraded (ECE within 0.02); all
test rows international; adequate completeness (≥30 matches, ≥200 test rows). Otherwise it is
`reference_only` (honest default), `rejected`, or `data_insufficient`. The W2 anchors (r0/h0/i0) are
always `reference_only`. The selective correction (r4) always permits **alpha=0 = pure W2 fallback**.

## Run it
Dry-run (validates the queue + script presence; prints `queue_complete`):
```
python scripts/deep_research_supervisor.py --dry-run --run-id rg_dry \
    --config configs/residual_goal_intensity_v1.yaml
```
Foreground (resumes the active run id, ≤8h):
```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_residual_goal_intensity_v1.ps1
```
Scheduled (one-time, ≤8h, `IgnoreNew`, `StartWhenAvailable`):
```
powershell -File scripts/windows/install_residual_goal_intensity_task.ps1     # task: WorldCupResidualGoalIntensityResearchRun
powershell -File scripts/windows/uninstall_residual_goal_intensity_task.ps1
```

## Restart / resume semantics
- The run id is read from `outputs/research_runs/active_run_id.txt` (minted on first launch). Completed
  jobs are skipped idempotently on restart; the supervisor fail-closes on deadline / collector-staleness /
  API budget before each job and blocks the remainder. JOB1 and JOB2 and JOB14 are `critical: true`
  (a critical failure stops the run with a recorded reason).

## Honest-negative expectation
Given the small international event corpus (≈58 matches / 5 competitions), the expected and acceptable
outcome is that **no model beats the parameter-free W2 reference out-of-sample** and the selective gate
degenerates toward pure fallback. That is a real scientific result, recorded as such — not a tuning
failure, and never tuned to 2026.
