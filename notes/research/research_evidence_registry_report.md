# Research Evidence Registry — Report

`research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible`

Built 2026-06-28T02:27:09.405627+00:00. 10 artifact records across the prior programs. Every count traces to a real local manifest/file; no fabricated numbers. The active collector checkout is never read.

## claim_status summary

- **contradicted**: 1
- **incomplete**: 1
- **verified_current**: 2
- **verified_historical**: 6

## Headline reconciliation (the 258 vs 58 question)

- The exact `api<->statsbomb` bridge defines **258** international matches (`bridge.api_statsbomb_exact_v1`, re-counted from the CSV present on disk).
- `statsbomb.cache_audit` *claims* 258 valid cached event files — but the read-only StatsBomb events directory currently holds far fewer JSONs, so that headline is **contradicted** by live disk state (prior larger pull, since pruned).
- `residual.decision_ledger` evaluated **58** matches — the intersection of the 258 bridge with the event JSONs physically on disk. Independently re-derived here and **agrees**.
- Conclusion: the 258→58 reduction is a **missing-StatsBomb-events** drop at the event-process snapshot stage, not a modeling or population-definition error.

## Records

| id | program | claim_status | result |
|---|---|---|---|
| `corpus.research_truth_registry` | api_football_historical_corpus | **verified_historical** | 900-fixture corpus reconciled exact; 900-vs-1120 + 123-vs-176 sendings-off claims resolved by scope |
| `corpus.canonical_counts_ledger` | api_football_historical_corpus | **verified_historical** | 960 reconciled fixtures, regulation-exact rate 1.0 |
| `corpus.coverage_ledger` | api_football_player_history | **verified_historical** | player-history corpus done=2000, gate_95pct_raw_backed=True |
| `bridge.api_statsbomb_exact_v1` | statsbomb_xg_bridge | **verified_current** | 258 exact international api<->statsbomb match bridge rows (all comp_type=international) |
| `statsbomb.cache_audit` | statsbomb_xg_bridge | **contradicted** | audit asserts 258 valid cached; on disk NOW: 60 StatsBomb event JSONs |
| `xg.snapshot_join_audit` | dynamic_xg_state | **verified_historical** | 258 distinct xG-eligible matches, 4386 intl snapshots |
| `event_process.decision_ledger` | event_process_intelligence_v1 | **verified_historical** | event-process intelligence: 0 promoted candidates (honest negative) per prior completion |
| `residual.decision_ledger` | residual_goal_intensity_v1 | **verified_current** | W2 reference R0 best (pooled FC RPS 0.15263); 0 research candidates; honest NEGATIVE |
| `residual.snapshot_dataset` | residual_goal_intensity_v1 | **incomplete** | 7,376 international residual snapshot rows across 58 matches (per data card) |
| `baseline.model_decision_ledger` | baseline_gate | **verified_historical** | pre-match baseline B0-B7 gate decisions |

## Notes (per record)

### `corpus.research_truth_registry`
- manifest: `data/reference/research_truth_registry.json`
- counts: `{"corpus_900_reconciled_exact": 900, "player_history_60_reconciled": 60, "union_distinct_event_files": 1180}`
- next_action: treat as resolved provenance record; raw lives in separate gitignored worktree
- note: registry reconciles the 900-vs-1120 fixture and 123-vs-176 sendings-off discrepancies as scope differences; raw corpus is gitignored and not in this worktree, so counts are verified_historical (from the manifest, not re-counted from raw here)

### `corpus.canonical_counts_ledger`
- manifest: `data/reference/canonical_counts_ledger.json`
- counts: `{"reconciled_fixtures": 960, "regulation_exact": 960, "exact_rate": 1.0, "canonical_sendings_off_total": 128}`
- next_action: none; union-across-roots count, raw gitignored
- note: union across resolved roots; raw not present in this worktree -> verified_historical

### `corpus.coverage_ledger`
- manifest: `data/reference/corpus_coverage_ledger.json`
- counts: `{"done": 2000, "copied_from_prior_no_api": 120}`
- next_action: none; coverage measured by raw across registered roots (raw gitignored here)
- note: player-history plane; raw gitignored -> verified_historical

### `bridge.api_statsbomb_exact_v1`
- manifest: `C:/Users/Mahyar/worldcup-player-impact-xg/data/processed/api_statsbomb_match_bridge_v1.csv`
- counts: `{"exact_bridge_rows_recounted": 258, "total_accepted_audit": 258, "total_rejected_audit": 266, "per_competition": {"FIFA World Cup 2018": {"api_fixtures": 64, "sb_matches": 64, "accepted": 64, "rejected": 0}, "FIFA World Cup 2022": {"api_fixtures": 64, "sb_matches": 64, "accepted": 64, "rejected": 0}, "UEFA Euro 2020": {"api_fixtures": 313, "sb_matches": 51, "accepted": 51, "rejected": 262}, "UEFA Euro 2024": {"api_fixtures": 51, "sb_matches": 51, "accepted": 51, "rejected": 0}, "Copa America 2024": {"api_fixtures": 32, "sb_matches": 32, "accepted": 28, "rejected": 4}}}`
- next_action: none; canonical international population definition
- note: bridge CSV present and re-counted: 258 exact intl rows. Per-competition (from audit): WC2018=64, WC2022=64, Euro2020=51, Euro2024=51, Copa2024=28. This is the international population root for every downstream in-play cohort.

### `statsbomb.cache_audit`
- manifest: `data/reference/statsbomb_cache_audit.json`
- counts: `{"audit_valid_cached": 258, "audit_xg_field_available": 258, "on_disk_event_json_now": 60}`
- next_action: re-acquire the full StatsBomb event pull to lift the residual cohort from 58 back toward 258
- note: audit claims valid_cached=258 (xg_field_available=258), but the on-disk read-only StatsBomb events dir currently holds 60 event JSONs. The audit reflects a PRIOR larger pull since pruned. This is exactly why the residual eval used 58, not 258: only event files PHYSICALLY ON DISK can produce snapshots. Treat the 258 cache claim as historical; the live truth is 60 on disk.

### `xg.snapshot_join_audit`
- manifest: `data/reference/xg_snapshot_join_audit.json`
- counts: `{"xg_eligible_international_snapshots": 4386, "distinct_matches": 258, "rows_nonzero_xg": 4323}`
- next_action: recompute against current on-disk events; the 258 here predate the prune
- note: distinct_matches=258 reflects the SAME larger pull as the cache audit; under current local data the joinable population is the 58 on-disk matches. Marked verified_historical: the audit is internally valid but describes the pre-prune state.

### `event_process.decision_ledger`
- manifest: `data/reference/event_process_model_decision_ledger.json`
- counts: `{"n_models": 22}`
- next_action: none; superseded as the in-play modeling substrate by residual goal-intensity v1
- note: prior in-play family; the residual phase is built on its verified terminal commit 8447f34

### `residual.decision_ledger`
- manifest: `data/reference/residual_goal_intensity_decision_ledger.json`
- counts: `{"n_models": 16, "n_matches": 58, "n_test_rows_wdl": 7376, "present_matches_rederived": 58, "exact_intl_bridge": 258}`
- next_action: the 58-match cohort is the live ceiling until the full StatsBomb pull is re-acquired
- note: ledger records n_matches=58; independently re-derived present matches (on-disk StatsBomb events INTERSECT exact intl bridge) = 58. They agree: the 58 is the live, reproducible cohort. 0 candidates promoted (honest negative).

### `residual.snapshot_dataset`
- manifest: `data/processed/residual_goal_intensity/residual_goal_intensity_snapshots.csv`
- counts: `{"n_snapshot_rows_on_disk": null, "documented_rows": 7376, "documented_matches": 58}`
- next_action: rebuild via build_event_process_snapshots.py + build_residual_goal_intensity_dataset.py if the snapshot CSV is not materialised in this worktree
- note: the materialised residual snapshot CSV is gitignored / not in a clean checkout; documented counts come from the data card + decision-ledger evidence

### `baseline.model_decision_ledger`
- manifest: `data/reference/model_decision_ledger.json`
- counts: `{"present": true}`
- next_action: none; separate pre-match plane, orthogonal to the in-play residual cohort
- note: pre-match baseline plane; recorded for cross-program completeness
