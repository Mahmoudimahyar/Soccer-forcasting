# Complete xG Snapshot Join — Report (research_only)
Previously 0 joined (cache-path bug). Now REAL and NONZERO over the complete cache.
- xG-eligible international regulation snapshots: 4,386 across 258 exact-bridged matches (17 decision minutes
  10..90 step 5). 4,323 rows carry nonzero cumulative xG.
- Per snapshot (causal, events at match-clock minute <= cutoff only): cumulative xG for/against, xG diff,
  rolling 5/10-min xG diff, xG momentum, shot-count diff, shot-on-target diff, time-since-last-shot,
  time-since-last-major-chance, xG completeness, source event-order quality, StatsBomb source hash, canonical
  match id, snapshot/source-cutoff minute, regulation eligibility.
- Leakage rules enforced + tested (tests/test_xg_snapshot_join_leakage.py): no future xG; no cross-match leakage;
  deterministic aggregation; regulation/extra-time separation; shootout excluded; StatsBomb minutes = match-clock
  not publication time; own goals credit beneficiary with no xG. Paths via canonical registry (both roots).
- Audit: data/reference/xg_snapshot_join_audit.json (all structural checks pass). xG remains historical research
  only; not runtime / not trade / not live eligible. Output data/processed/xg_snapshot_join_v1.csv (derived; raw gitignored).
