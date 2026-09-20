# Event-Process Intelligence — Scientific Report (DRAFT)

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible

## Question
Does a leakage-safe, provider-neutral *event-process* representation (possession / territory /
transition / set-piece / chance-quality, plus club-transfer) improve in-play W/D/L, next-goal,
near-term scoring, or discipline forecasting **beyond a parameter-free remaining-time reference**?

## Data
- International population: 58 exact-bridge senior-men matches, 5 competitions, 7376 causal snapshots (StatsBomb open data; 2026 World Cup EXCLUDED).
- Auxiliary club snapshots train ONLY the e8 transfer representation (never intl test rows).

## Protocol
- W/D/L: forward-chaining (kickoff order) + leave-one-competition-out (LOCO); e2 = parameter-free
  remaining-time Poisson reference. Candidates e3..e9 must beat e2 out-of-sample on pooled RPS,
  in a majority of folds, with a match-level paired-bootstrap 95% CI upper bound < 0, and without
  degrading draw-channel calibration.
- Binary families: LOCO; base-rate head is the reference; discipline hazards gated on >=150 positives.
- Match-level bootstrap only; no row-level resampling. No 2026 data in any fit/selection.

## Headline finding
- LOCO W/D/L RPS (lower better): e2=0.1496, e4=0.15121, e6=0.15834, e3=0.15982, e9=0.16567, e5=0.16982
- **No model met the promotion bar.** On this international sample, the richer
  event-process representations did NOT beat the parameter-free remaining-time
  reference out-of-sample. This is an honest negative, not a tuning failure.

## Verdict summary
- reference_only: 20 | rejected: 0 | research_candidate_for_future_shadow_review: 0 | data_insufficient: 2

## Limitations
- Small international event-corpus (58 matches / 5 competitions) → wide bootstrap CIs; a true
  in-play edge below the reference's noise floor cannot be ruled in OR out here.
- Sending-off is rare (<150 positives) → discipline hazard heads are honestly gated off.
- StatsBomb open-data international coverage is the binding constraint; expanding the exact-bridge
  population is the highest-value next step before any of these models could be reconsidered.

_All numbers above are produced by EPJOB9–15 in this run; see the decision ledger for per-model
evidence._