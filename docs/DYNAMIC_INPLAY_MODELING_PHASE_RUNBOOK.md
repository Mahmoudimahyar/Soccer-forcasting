# Dynamic In-Play Modeling Phase — Runbook (Component 5 / Phase 7)

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible` — **paper-only.**

This phase evaluates the transparent dynamic in-play model families (W/D/L, xG-fusion W/D/L, next-goal,
discipline) on the **pre-2026 international** corpus via a durable, restart-safe, fail-closed **16-job
controller queue**. It is **offline by construction** — every source is a local validated product resolved
through the canonical data-root registry; there are **zero external API calls** (Odds API / API-Football /
StatsBomb network). The 2026 World Cup is **never** used for fitting, calibration, or selection.

## Components

| File | Role |
|---|---|
| `configs/dynamic_inplay_modeling_phase_v1.yaml` | Ordered finite JOB1..JOB16 queue + run bounds (`max_hours: 8`, `max_workers: 2`, collector heartbeat + stale gate, per-job timeout) + safety (`kalshi_live_trading: false`, `trading_mode: paper`, `use_odds_api: false`, `external_api: false`). |
| `scripts/deep_research_supervisor.py` | The durable controller (unchanged, reused). Runs each job as `python <script> --run-dir <dir>`, fail-closed preflight (deadline + API budget + collector health), atomic `state.json` checkpoint, heartbeat, `run_summary.json`. |
| `scripts/model_jobs/_mj_common.py` | Shared helpers: run-dir/`model_phase` resolution, registry-resolved source roots, collector-isolation assertion, and the **leakage-safe eval-row loader** (joins the parquet snapshot products + player-impact priors + dynamic xG state into the exact `dynamic_models` schema). |
| `scripts/model_jobs/mj_job01..16_*.py` | The 16 jobs (below). Each imports `scripts/research_jobs/_job.py` and emits a JSON result line. |
| `scripts/run_dynamic_inplay_modeling_phase.ps1` | Launcher. Resumes the **same** run id `truth_20260626_134931` via `--resume-run-id`; workdir = research worktree; artifacts → `outputs/research_runs/truth_20260626_134931/model_phase`. |

## The 16 jobs

1. **JOB1 preflight** — collector isolation + same run id + data-root registry + source manifests + no-external-API assertion + controller dry-run note.
2. **JOB2 rebuild snapshots** — (re)build the canonical dynamic in-play panel via `scripts/build_dynamic_inplay_panel.py`; resume-safe (verifies existing products).
3. **JOB3 player priors** — build + **deterministic audit** of temporal player priors (no-future-leak + shrinkage self-tests + real-output invariants).
4. **JOB4 xG state** — build + **deterministic audit** of dynamic xG state (no-future-xG / monotonic / no-cross-match-leak / regulation-only / no-imputation).
5. **JOB5 data audit** — completeness / leakage invariants (no-2026, international-only test rows, causal `remaining==90-minute`) / source quality.
6. **JOB6 primary W/D/L** — forward-chaining tournament eval of `r0,r1,r2,p1-p5`.
7. **JOB7 primary xG W/D/L** — forward-chaining eval of `r2,x1,x2,x3` on the **exact-bridge xG-eligible subset**.
8. **JOB8 secondary LOCO W/D/L** — leave-one-international-competition-out; persists per-match RPS series + reliability.
9. **JOB9 next-goal** — LOCO eval of `n0-n4` (Brier / logloss / ECE).
10. **JOB10 discipline** — LOCO eval of `c0`; `c1/c2` **preregistered-gated on ≥150 sending-off positives** (honest skip below gate).
11. **JOB11 ablations** — W/D/L, xG, and next-goal feature ladders + a "complex-feature-worsens" detector.
12. **JOB12 calibration + bootstrap** — draw-channel reliability/ECE slices + **match-level paired bootstrap** of candidate−reference RPS deltas.
13. **JOB13 failure analysis** — worst-overconfident / draw-state / late-game / red-card-state / post-sub / sparse-history / club→intl transfer / xG-momentum / complex-feature-worsens.
14. **JOB14 decision ledger** — applies the 8 preregistered promotion rules → verdict per candidate (paper-only; **never auto-promoted**).
15. **JOB15 artifact registry** — machine-readable model registry (id / family / metric / verdict / eligibility=False) + on-disk artifact sha256.
16. **JOB16 report + completion audit** — scientific report draft + completion audit (verifies all 16 jobs reached an honest terminal status).

## Run

```powershell
# validate the queue only (expect: stop_reason queue_complete, counts complete:16, api_used 0)
pwsh -File scripts/run_dynamic_inplay_modeling_phase.ps1 -DryRun

# run / resume the phase (resumes run id truth_20260626_134931; skips already-complete jobs)
pwsh -File scripts/run_dynamic_inplay_modeling_phase.ps1
```

Equivalent direct supervisor invocations:

```bash
python scripts/deep_research_supervisor.py --dry-run --run-id mp_dry \
    --config configs/dynamic_inplay_modeling_phase_v1.yaml          # prints queue_complete

python scripts/deep_research_supervisor.py --resume-run-id truth_20260626_134931 \
    --config configs/dynamic_inplay_modeling_phase_v1.yaml --hours 8 --max-workers 2
```

## Honest-status contract

A job may terminate as `data_insufficient` or `threshold_blocked` **only with an explicit recorded reason**
(missing product, below a preregistered gate, single-competition xG subset, etc.). A false stub-complete is
forbidden. JOB16's completion audit flags any job that ended `data_insufficient`/`threshold_blocked` **without**
a reason as dishonest. Critical jobs (JOB1, JOB2, JOB5) stop the queue on failure.

## Integrity guarantees

- **Collector isolation** — no job reads/writes the active collector checkout `worldcup_draw_model_lab_FINAL`; it is registered as a forbidden root and re-asserted at import.
- **Registry-resolved sources** — all data paths resolve through `wcdrawlab.research.data_roots`; raw stays gitignored.
- **Leakage-safe** — every fit / scaler / calibrator is learned inside training rows only; the 2026 World Cup is filtered out and `dynamic_eval.assert_no_2026` is the backstop; club rows are auxiliary player-prior history, never test rows; bootstrap resamples at the **match** level.
- **Offline** — `max_api_requests` headroom is 1 and every job reports `api_requests: 0`; the supervisor fail-closes if a real API request is ever reported.
- **Paper-only** — nothing here is runtime/trade/live eligible; a passing candidate is labelled `research_candidate_for_future_shadow_review` and is **never** auto-promoted into runtime/B1/approved models.

## Outputs

Under `outputs/research_runs/truth_20260626_134931/model_phase/`:
`mj_job01..16_*.json` (per-job integrity envelopes + results), `candidate_verdicts.json`,
`model_artifact_registry.json`, `scientific_report_dynamic_inplay_phase.md`. Supervisor bookkeeping
(`state.json`, `run_summary.json`, `job_log.jsonl`, `artifact_manifest.json`) is at the run-dir root.
