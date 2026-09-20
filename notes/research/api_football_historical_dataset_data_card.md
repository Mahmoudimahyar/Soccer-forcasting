# API-Football Historical Datasets — Data Card (Phase 4)
research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. No model trained.

## Source & provenance
API-Football Pro (already-paid), corpus backfill (events + lineups). Raw append-only + gitignored
(data/raw/api_football_historical_corpus/); derived tables gitignored (data/processed/api_football_corpus/);
tracked manifest = counts only. Every row carries source_hash + provider_semantics_version
(api_football_result_v1). Builder: scripts/build_api_football_historical_datasets.py (deterministic rebuild).

## Tables (11 logical)
match metadata; event timeline; lineup+bench; player-on-pitch state; substitution; card/discipline;
regulation-only score-state; extra-time/shootout exception; competition coverage; source completeness;
reconciliation exception.

## Causal guarantees (tested, 11 cases)
- in-play state at minute t uses ONLY events with elapsed <= t (no future goal/sub/card leak);
- regulation targets use regulation goals only (elapsed <= 90); extra-time + shootout SEPARATED;
- player-on-pitch uses starting XI + subs with minute <= t only;
- own goals credited to `team` (beneficiary); duplicates flagged; deterministic rebuild;
- club and international rows partitioned (never mixed without labels).

## Release rule
A fixture must reconcile exactly for its relevant result type OR be classified + EXCLUDED from affected target
datasets (cards/subs/goals counted only from resolved fixtures). Unresolved fixtures are never silently dropped.

## Known limits
No xG / shot locations (API-Football gap). No per-event publication time -> historical only. Final score /
post-match stats never enter in-play features.
