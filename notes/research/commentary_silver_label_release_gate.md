# Commentary Silver-Label Release Gate (Phase 4)
historical_weak_supervision_only / not_live_eligible / not_runtime_approved / not_trade_eligible.
Gate JSON: notes/research/commentary_silver_label_gate.json. Reproduce: `python scripts/apply_commentary_silver_gate.py`.

## Preregistered bar (FROZEN)
>=50 emitted labels; Wilson 95% LB on precision >=0.80; median |dt|<=15 s; p90 |dt|<=35 s; Wilson LB>=0.80 in
>=4 folds (>=5 preds each); not from a single competition.

## Decision per class
| class | decision | Wilson LB | n | median t | stable folds |
|---|---|---|---|---|---|
| corner | usable_only_with_low_confidence_flag | 0.768 | 2129 | 14.5 | 1 |
| foul | usable_only_with_low_confidence_flag | 0.768 | 1737 | 7.0 | 0 |
| yellow_card | usable_only_with_low_confidence_flag | 0.729 | 217 | 5.2 | 0 |
| goal | insufficient_precision | 0.559 | 76 | 2.0 | 0 |
| shot | insufficient_precision | 0.508 | 108 | 2.1 | 0 |
| shot_on_target | insufficient_precision | 0.459 | 81 | 4.0 | 0 |
| penalty_awarded | insufficient_precision | 0.081 | 114 | 25.0 | 0 |
| offside | insufficient_coverage | 0.468 | 42 | 2.0 | 0 |
| substitution | insufficient_coverage | 0.525 | 43 | 11.5 | 0 |
| kickoff | insufficient_coverage | 0.388 | 24 | 0.0 | 0 |
| red_card | insufficient_coverage | 0.142 | 30 | 8.7 | 0 |
| second_yellow | insufficient_coverage | 0.085 | 19 | 14.8 | 0 |

## Result: **0 classes approved** -> the silver-label dataset is EMPTY.
This is an honest negative result under a preregistered bar. The closest classes (corner/foul/yellow_card)
are retained only as LOW-CONFIDENCE historical signals, never as high-precision silver labels, never live.
