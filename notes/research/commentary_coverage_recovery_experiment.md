# Commentary Coverage-Recovery (Masking) Experiment (Phase 5)
historical_weak_supervision_only / not_live_eligible. Reproduce: `python scripts/evaluate_commentary_coverage_recovery.py`.

## Design
Question tested: can high-confidence silver labels expand historical event coverage where structured labels
are masked? For each APPROVED class, on each held-out competition (models fit on the OTHER competitions),
mask the true events and reconstruct from silver emissions; measure recovered coverage, false-positive
burden, timing. NO outcome model is trained or tuned (per spec).

## Result
The Phase-4 release gate APPROVED **0 classes** (no class meets the frozen Wilson-LB>=0.80 + 4-fold-stability
bar). With no approved high-precision class, there is nothing to reconstruct masked structured labels WITH
at the required confidence. The experiment therefore returns no recoverable class.

- approved_classes: [] ; per_class: {} ; verdict input = empty.
- Note: the closest classes (corner/foul/yellow_card) carry ~30% false positives at their best operating
  point -> using them to "recover" masked labels would inject a large false-positive burden, defeating the
  purpose of high-precision coverage recovery.
