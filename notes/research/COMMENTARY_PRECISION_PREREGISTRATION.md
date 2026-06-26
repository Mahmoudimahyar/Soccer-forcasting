# Commentary Precision V2 — PREREGISTRATION (frozen before any model fitting; 2026-06-26)

## 1. Allowed data
- PRIMARY eval: SoccerNet-Echoes **whisper_v1_en** (English translation) only.
- Original-language ASR (whisper_v1): ONLY for the language-dependence audit (Phase 6), never primary.
- Official SoccerNet Labels-v2.json: retrospective TRUTH only (no publication time -> historical only).

## 2. Allowed event classes (evaluate each separately)
goal, corner, yellow_card, foul, offside, substitution, kickoff; plus shot/shot_on_target/penalty_awarded/
red_card/second_yellow ONLY if >= the count thresholds below; otherwise reported as insufficient_coverage.

## 3. Prohibited claims
No live capability; no player-level event claims; no original-language generalization claim; no predictive
performance claim; no market-edge claim.

## 4. Evaluation protocol
- Leave-one-competition-out (LOCO) outer evaluation (6 competitions).
- ALL threshold choice / calibration / vocabulary / feature selection on TRAINING competitions only.
- No random row-level splits. No test-competition tuning. Match-level grouping (no segment from a test
  match in train).

## 5. Model ladder (fixed)
- R0: current time-only candidate alignment (any within-window segment "witnesses" the event).
- R1: deterministic preregistered rule-based classifier (keyword/phrase families + negation/correction).
- R2: local TF-IDF (word+char n-grams) + regularized logistic regression, per class; calibration on train only.
- R3: hybrid = event-time proximity + R1 rule score + R2 probability -> combined confidence (no test-match calibration).
- R4: abstention/high-confidence policy = emit a silver label only when confidence > train-selected threshold;
  "no label" is an allowed/preferred outcome.

## 6. Silver-label success thresholds (FROZEN — do not change after seeing results)
A class is `silver_label_approved_for_historical_research` ONLY IF ALL hold (on held-out folds, R4 policy):
- T1 count: >= 50 held-out PREDICTED (emitted) labels for the class across outer folds.
- T2 precision: Wilson 95% LOWER confidence bound on precision >= 0.80.
- T3 timing median: median |t_pred - t_event| <= 15 s.
- T4 timing p90: 90th-percentile |t_pred - t_event| <= 35 s.
- T5 stability: meets T2 (Wilson LB >= 0.80) in >= 4 held-out competition folds that each have >= 5 predictions.
- T6 no-single-competition: a class may NOT pass if its emitted labels come from only one competition.

## 7. Release-gate class labels (exactly one per class)
silver_label_approved_for_historical_research / usable_only_with_low_confidence_flag /
taxonomy_research_only / insufficient_precision / insufficient_coverage / language_limited / unsupported_by_source.

## Precision definition
A predicted silver label (segment time t_pred, class C) is CORRECT iff a real SoccerNet event of class C
occurs within the alignment window (45 s, half-relative) of t_pred. Timing error = |t_pred - nearest such event|.
