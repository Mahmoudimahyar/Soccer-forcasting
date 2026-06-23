# SoccerNet Historical Weak-Supervision Readiness (Phase 5 decision)
research_only=true / historical_weak_supervision_only=true / not_live_eligible=true

## Decision: **ready_for_historical_weak_supervision_only**  (option 2 of 5)
Rationale: deterministic keyword+time alignment yields usable NOISY labels for SALIENT events
(goal recall 0.63-0.88; corner recall 0.40-0.75 at precision 0.64-0.82; yellow/foul precision 0.70-0.75),
reproducibly across 6 leave-one-competition-out folds. This is sufficient for **historical weak
supervision** (noisy distant labels for model pre-training / data augmentation), but NOT clean enough for
**event_enrichment as ground truth** (option 1) without per-type precision filtering, because several
classes (goal precision 0.16, substitution recall 0.09, kickoff recall 0.006) are weak, and rare events
(red/2nd-yellow, n<=6) are statistically unreliable.

## NOT chosen
- option 1 (ready_for_historical_event_enrichment): rejected — precision too variable for clean enrichment.
- option 3 (taxonomy-only): too weak a claim — we have real, reproducible recall/precision.
- option 4 (insufficient overlap): rejected — 254 matched games >> 20 threshold.
- option 5 (blocked_by_action_label_source): rejected — labels openly acquired (no NDA).

## Hard constraint
No publication_time exists -> **never live-eligible**. Usable only for retrospective/offline weak
supervision, parser/taxonomy research, and commentary-event timing studies. Never a live feature, never
into the active collector, never trading/paper-trading.
