# Commentary Precision V2 — Outer-Fold Results (Phase 3)

research_only=true · historical_weak_supervision_only=true · not_runtime_approved=true ·
not_trade_eligible=true · not_live_eligible=true

Leave-one-competition-out (6 folds); all fitting + threshold selection on TRAIN competitions only.
Models: R1 deterministic rules (+ class negation), R2 TF-IDF+logreg, R4 = R3 hybrid + train-selected
abstention. Precision = emitted segment has a real event of that class within 45 s (half-relative).
Reproduce: `python scripts/evaluate_commentary_precision_models.py`. No raw text in tracked outputs.

## The ladder works as designed (aggregate precision, emitted count)
| class | R1 prec (n) | R2 prec (n) | R4 prec (n) | R4 Wilson LB |
|---|---|---|---|---|
| corner | 0.758 (2754) | 0.185 (97631) | **0.786 (2129)** | 0.768 |
| foul | 0.738 (2665) | 0.365 (130536) | **0.788 (1737)** | 0.768 |
| yellow_card | 0.625 (981) | 0.092 (64900) | **0.788 (217)** | 0.729 |
| goal | 0.152 (9860) | 0.089 (61141) | 0.671 (76) | 0.559 |
| offside | 0.485 | 0.081 | 0.619 (42) | 0.468 |
| substitution | 0.430 | 0.124 | 0.674 (43) | 0.525 |
| shot / shot_on_target | 0.4–0.5 | 0.08–0.1 | 0.57–0.60 | 0.46–0.51 |
| kickoff | 0.512 | 0.104 | 0.583 (24) | 0.388 |
| penalty_awarded | — | — | 0.132 (114) | 0.081 |
| red_card / second_yellow | — | — | 0.21–0.27 (≤30) | ≤0.14 |
- R2 alone (prob≥0.5) is NOT precision-oriented — the dense proximity target makes it fire everywhere.
- R4 (rule-gated + abstention) is the useful operating point; it lifts goal 0.15→0.67 and yellow 0.63→0.79,
  always at a large coverage cost.

## corner — the borderline near-miss (R4 per fold)
| held-out | n | precision | Wilson LB | median t | p90 t |
|---|---|---|---|---|---|
| england_epl | 101 | 0.812 | 0.725 | 15.6 | 29.7 |
| uefa-champions-league | 378 | 0.820 | 0.778 | 14.5 | 31.3 |
| france_ligue-1 | 271 | 0.830 | 0.781 | 14.0 | 31.1 |
| germany_bundesliga | 168 | 0.857 | 0.796 | 15.2 | 30.8 |
| **italy_serie-a** | 707 | **0.668** | 0.632 | 15.3 | 32.7 |
| spain_laliga | 504 | 0.873 | 0.841 | 14.3 | 29.7 |
Point precision ≥0.80 in **5/6** folds, but the conservative **Wilson LB ≥0.80 holds in only 1 fold**, and
Serie-A collapses to 0.67 → aggregate Wilson LB 0.768. foul (0.71–0.86/fold) and yellow_card (small per-fold
n, 0.56–0.88) are similar: good point precision, not confidently ≥0.80.

## Timing
- corner median ~14–15 s (right at the 15 s bar), p90 ~30–33 s; foul median 4–12 s; yellow 2.5–11 s.
  goal median ~2 s (when narrated, immediate). No class fails purely on timing among the near-misses.
