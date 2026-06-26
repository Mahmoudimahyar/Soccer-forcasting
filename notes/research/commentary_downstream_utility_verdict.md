# Commentary Downstream Utility Verdict (Phase 5)
historical_weak_supervision_only / not_live_eligible / not predictive / no market-edge.

## Verdict: **insufficient_quality_or_coverage**
No event class passed the preregistered high-precision silver gate, so commentary-derived labels cannot
safely expand historical event coverage where structured labels are absent. The best classes
(corner/foul/yellow_card) reach ~0.73-0.77 Wilson-LB precision — usable only as flagged LOW-CONFIDENCE
historical signals, not as silver ground truth, and not for coverage recovery.

Explicitly NOT claimed: that commentary labels improve W/D/L, next-goal, or any prediction. This phase did
not train or tune any outcome model, by design.
