# Residual Goal-Intensity — Scientific Report (DRAFT)

research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible

## Question
Treating the remaining-time Poisson model (W2) as a **REFERENCE INTENSITY** (side-specific
remaining-goal rates) rather than a competing classifier, does a leakage-safe event-process
*correction* to those intensities improve in-play W/D/L, near-term scoring, or the side-specific
intensities themselves **beyond the parameter-free W2 reference**, out-of-sample?

## Data
- International population: 58 exact-bridge senior-men matches, 5 competitions, 7376 causal regulation snapshots (StatsBomb-derived; **2026 World Cup EXCLUDED** from every fit / calibration / selection).
- Club auxiliary snapshots train ONLY the frozen club-transfer representation; club rows are NEVER
  used as international test rows.

## Protocol
- Every model is expressed RELATIVE to its W2 family anchor (residual r0 / horizon h0 / intensity i0).
- W/D/L: forward-chaining (kickoff order) + leave-one-competition-out (LOCO). Candidates must beat
  r0 out-of-sample on pooled RPS, in a majority of folds, with a match-level paired-bootstrap 95% CI
  upper bound < 0, and without degrading draw-channel calibration.
- Intensity: LOCO side-specific Poisson deviance vs i0. Horizon: LOCO right-censored Brier vs h0.
- Selective correction (r4) chooses its blend weight IN-TRAIN via held-out CV and ALWAYS permits
  alpha=0 (pure W2 fallback); coverage + corrected-vs-fallback performance are audited.
- Match-level bootstrap only; no row-level resampling.

## Integrity
- self_test all_passed=True (real_rows_used=True); leakage_ok=True; no_2026_ok=True; model_output_simplex_ok=True; isolation_ok=True.

## Headline finding
- LOCO W/D/L RPS (lower better): w2_reference_r0=0.14906, selective_correction_r4=0.15394, event_process_boost_r3=0.16356, intensity_glm_r1=0.17193, calibrated_simulation_r5=0.17193
- **No model met the promotion bar.** On this international sample the event-process
  correction did NOT beat the parameter-free W2 reference intensity out-of-sample; the
  selective gate correctly degenerates toward the pure-W2 fallback. Honest negative.

## Verdict summary
- data_insufficient: 3 | reference_only: 7 | rejected: 6

## Limitations
- Small international event corpus → wide bootstrap CIs; a true in-play edge below the reference's
  noise floor can be neither ruled in nor out here.
- Right-censoring of the 5/10/15-min horizons near minute 90 reduces effective late-game labels.
- StatsBomb-derived international coverage is the binding constraint; expanding the exact-bridge
  population is the highest-value next step before any of these models is reconsidered.

_All numbers are produced by RG_JOB04–13 in this run; see the decision ledger for per-model
evidence._