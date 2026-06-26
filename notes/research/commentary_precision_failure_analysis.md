# Commentary Precision V2 — Failure Analysis (Phase 3)
historical_weak_supervision_only / not_live_eligible. Examples are SYNTHETIC (no raw text quoted).

## Why no class clears the high-precision bar
1. **Keyword polysemy (precision ceiling).** "goal" appears in chances/goal-kick/goalkeeper; "shot" in
   blocked/wide. R1 negation + R4 abstention raise precision (goal 0.15->0.67) but only by discarding most
   coverage, and the residual emitted set still carries ~30% false positives -> Wilson LB stays < 0.80.
2. **Proximity-label noise (precision ceiling, not just keywords).** Truth = "a real event within 45 s".
   Commentary near an event often discusses something else (crowd, replay, build-up) -> a confident,
   on-topic-looking segment can still miss the 45 s window or sit near a different event.
3. **Per-competition instability (the Serie-A effect).** corner point precision is 0.81-0.87 in 5 leagues
   but 0.67 in Serie-A (translation/commentary-style differences) -> fails T5 (>=4 folds with Wilson LB>=0.80)
   and drags the aggregate. This is exactly what the stability threshold is meant to catch.
4. **Conservative interval vs point estimate.** corner point precision ~0.79 (5/6 folds >= 0.80 point) but
   Wilson LB 0.768. The preregistered bar uses the LOWER bound deliberately -> "looks good" is not
   "confidently good".
5. **Coverage starvation for rare classes.** red_card (n=30), second_yellow (19), offside (42),
   substitution (43), kickoff (24) emit < 50 high-confidence labels across all folds -> insufficient_coverage
   regardless of precision. Subs/kickoff are barely narrated; reds are rare events.
6. **penalty_awarded** is a precision sink: "penalty" fires on penalty-box/appeals/no-penalty -> 0.13 precision.

## What this rules in / out
- IN (low-confidence, flagged): corner, foul, yellow_card as ~0.73-0.77 Wilson-LB historical signals.
- OUT (high-precision silver): every class. The deterministic+local-ML ceiling on this source is ~0.79
  aggregate precision for the best classes; the 0.80 Wilson-LB + 4-fold-stability bar is not met.

## Honest non-gaming note
TRAIN_TARGET_PRECISION (0.85) and all success thresholds were FROZEN before evaluation and were NOT changed
after seeing results. A stricter train target would trade more coverage for precision; exploring that is
future work, not a re-decision of this gate.
