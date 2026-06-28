# Residual Goal-Intensity, Selective Dynamic Correction & Near-Term Scoring Intelligence V1 — COMPLETION
research_only=true experimental=true not_runtime_approved=true not_trade_eligible=true not_live_eligible=true
KALSHI_ENABLE_LIVE_TRADING=false TRADING_MODE=paper

Run id `rg_20260627_155623_run1`, worktree `worldcup-residual-goal-intensity`, branch `residual-goal-intensity-v1`,
base tag `event-process-intelligence-v1` @ 8447f34. Durable controller (14-job queue) ran to a clean terminal end
via WorldCupResidualGoalIntensityResearchRun; all JOB1-14 complete; api_used=0 (offline).

## Dependency (verified)
Prior Event-Process Intelligence V1 is finalized + traceable: terminal, adjudicated (0 candidates, honest negative),
committed 8447f34, tagged event-process-intelligence-v1. This program is based on that verified commit.

## Datasets (real, leakage-safe)
- Residual goal-intensity snapshots: **7,376 international rows across 58 exact-bridge matches, 5 competitions**
  (WC2018, Euro2020, WC2022, CopaAmerica2024, Euro2024 — **no 2026 WC**). W2 = remaining-time Poisson treated as a
  REFERENCE INTENSITY (home/away remaining-goal rates), reconstructed deterministically + audited.
- Near-term competing-risk targets (right-censored at min 90): next-5m H 7.21% / A 6.33% / no-goal 86.46%;
  next-10m H 12.26% / A 10.63% / no 77.12%; next-15m H 16.93% / A 13.88% / no 69.18%.
- Residual targets (observed − W2) + 11 causal regime labels (16 regime cells populated). Descriptive residual:
  remaining-total −0.186 (W2 slightly over-predicts, mostly away) — DESCRIPTIVE ONLY.
- Availability gate, regime classifier, selective-correction gate (alpha=0 W2 fallback) — all validate.
- **43 deterministic leakage/integrity tests** (>=25 required); full suite **451 passed / 20 skipped**.

## Evaluation (preregistered, match-level)
Forward-chaining by tournament + LOCO, training-only fitting/calibration, **match-level** bootstrap (58 matches the
unit, NOT 7,376 snapshot rows). Intensity I0-I3, near-term H0-H4, W/D/L R0-R6 all evaluated.

**W/D/L pooled forward-chain RPS — the W2 reference R0 is BEST (0.15263).** Every residual-correction model is worse:
R4 selective-correction 0.15767, R3 event-process-boost 0.16722, R1 intensity-GLM 0.19068, R5 calibrated-sim 0.19059.
The selective gate's correction did not beat W2 even where applied. The descriptive −0.186 residual did NOT translate
into a forward-chaining/LOCO improvement under calibration + match-level bootstrap.

## Decision ledger (`data/reference/residual_goal_intensity_decision_ledger.{csv,json}`)
16 model records: **7 reference_only, 6 rejected, 3 data_insufficient, 0 research candidates.** No model clears the
preregistered candidate bar (lower RPS than W2 R0 + no calibration degradation + >=75% folds + bootstrap-favored +
LOCO-persistent + not club-only + adequate completeness). **Honest NEGATIVE** — accepted by the success standard; no
fabricated improvement, no candidate promoted, no live-use claim.

## Hard completion conditions — all 25 verified
Dependency finalized (1); dataset (2) + 5/10/15m targets (3) + availability gate (4) + selective gate (5) + regimes
(6) exist+validate; 43 residual tests pass (7); I0-I3 (8), H0-H4 (9), R0-R6 (10), LOCO (11), selective-gate audit
(12), ablations (13), calibration+match-bootstrap+diagnostics (14), failure analysis (15) complete; feature catalog
(16), model registry (17), decision ledger (18) exist; integrity audit all_ok incl no_2026_ok=True (19); collector
unchanged (20); B1/M2/M1-M5/candidate.py/approved_models/trading/paper/Kalshi/risk unchanged (21); no external API
(22, api_used=0); raw gitignored (23); no secret exposed (24); conclusions follow preregistration (25).

## Isolation proof
Active collector WorldCupShadowCollector = main checkout `worldcup_draw_model_lab_FINAL`, branch
v1-5-prospective-operations @ dc73318, clean, task Ready (never the research worktree). No runtime/shadow/trading
path changed. No API-Football / Odds / external call. Research worker ran only from the residual worktree.
