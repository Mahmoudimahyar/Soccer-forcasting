# Commentary Causality Policy (Phase 6)

THREE distinct times: event_time (when it happened), commentary_time (match clock on the text),
publication_time (when the line was actually available). NON-NEGOTIABLE:

- live use:        publication_time <= prediction_decision_time
- delayed-live:    publication_time + measured_safety_lag <= prediction_decision_time
- unknown publication_time: historical labeling / weak supervision / alignment ONLY; never live; never
  relabeled as point-in-time live data.

Match clock is NEVER treated as availability time. Code: `commentary/availability.py`
(`live_publication_safe`, `classify_source_eligibility`). research_only / not_runtime_approved /
not_trade_eligible. No commentary-derived feature may reach B1, the frozen M2, M1-M5 shadow, the active
collector, paper trades, Kalshi, risk, or performance claims.
