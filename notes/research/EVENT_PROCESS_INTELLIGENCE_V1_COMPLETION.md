# Event-Process Intelligence, Possession-State & Dynamic Goal-Intensity Research V1 — COMPLETION
research_only=true experimental=true not_runtime_approved=true not_trade_eligible=true not_live_eligible=true
KALSHI_ENABLE_LIVE_TRADING=false TRADING_MODE=paper

Run id `ep_20260627_run1`, worktree `worldcup-event-process-intelligence`, branch `event-process-intelligence-v1`
off `tags/dynamic-inplay-intelligence-v1`. Durable controller (16-job queue) ran to terminal: EPJOB1–12,14–16
complete; **EPJOB13 (discipline) data_insufficient** (positive-event threshold not met — honest threshold-block).
Heartbeat `done:EPJOB16`; task Ready; api_used=0 (offline).

## Built (real, source-traceable, committed)
- **Auxiliary official StatsBomb event corpus: 669/669 valid event files** (club; deterministic diversity-capped
  manifest, La Liga≤150; pre-2025-01-01; selected without scoreline/goals/xG/fame). Catalog: 2,651 men's matches.
- Provider-neutral **possession/territory/transition/pressure/set-piece/chance-quality engine** (13 modules + 5
  schemas; source quality classified available_verified/partial/unavailable/unknown, never imputed).
- **Causal event-process snapshot datasets** (7,377 international rows; leakage-verified) + targets (W/D/L,
  next-goal, 5/10/15-min scoring) + club auxiliary snapshots + source-quality/completeness tables.
- Model families E0–E9 (W/D/L via goal intensity), Q0–Q4 (next-goal), H0–H3 (near-term), Y0–Y2 (discipline).
- **71 deterministic integrity/leakage tests**; full suite **408 passed / 20 skipped**.

## Evaluation (preregistered, leakage-safe) + decision ledger (`data/reference/event_process_model_decision_ledger.{csv,json}`)
Forward-chaining by tournament + LOCO, training-only fitting/calibration, match-level bootstrap, pre-2026
international only (no 2026 WC in selection). **22 model records: 20 reference_only, 2 data_insufficient, 0
research candidates.** Honest NEGATIVE: causal event-process state did not clear the preregistered RPS /
bootstrap-CI / calibration / fold-consistency bar over the remaining-time-Poisson reference (E2). A negative
result, which the success standard accepts; no fabricated improvement.

## Gates / isolation
All applicable hard gates met (auxiliary corpus ≥500; engine + snapshots + completeness audit; ≥50 integrity
tests; primary + LOCO W/D/L; next-goal; near-term; discipline threshold-blocked w/ evidence; ablations;
calibration + bootstrap; failure analysis; feature catalog; decision ledger; no 2026 WC used; raw gitignored; no
secret; conclusions follow preregistration). **Active collector WorldCupShadowCollector unchanged (dc73318,
clean, Ready, main checkout); B1, frozen M2, M1–M5, candidate.py, approved_models.yaml, trading, paper trading,
Kalshi, risk untouched.** No API-Football / Odds / external call. No model promoted; nothing live-eligible.
