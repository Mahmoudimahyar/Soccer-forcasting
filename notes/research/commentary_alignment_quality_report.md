# Commentary Alignment Quality Report (Phase 5, 2026-06-23)

Research-only alignment between commentary lines and verified structured events (truth anchors:
StatsBomb/API-Football, used only where rights allow). NOT a live forecasting model.

## Tooling
`commentary/alignment.py` scores each line by (event-type 0.4 + team 0.3 + match-clock 0.3) -> confidence,
classified high/medium/low/unaligned, plus `correction_or_duplicate` and `timing_not_safe_for_live_use`.
`scripts/commentary_alignment_audit.py` (synthetic demo) + `commentary_event_taxonomy_eval.py`.

## Metrics defined (computed on permitted data)
precision, recall, F1, event-time absolute error, entity-resolution accuracy, alignment-latency
distribution, per-language / per-source / per-event-type quality, publication-time completeness.

## Evaluation discipline
**All splits are match-level or competition-level. Never random row split within a match.**

## Status
No rights-clear aligned commentary sample is available yet (SoccerNet-Echoes is acquirable but not pulled
this session; SoccerReplay-1988 needs NDA). Synthetic demo confirms the toolchain runs; real precision/
recall numbers are pending permitted data. No live model is tuned from any of this.
