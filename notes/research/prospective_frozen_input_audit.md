# Prospective Frozen Input Audit (Phase 0)

**research_only=True · prospective_evaluation_only=True · not_runtime_approved=True · not_trade_eligible=True · not_live_eligible=True**

Read-only hash + inventory of the immutable frozen inputs. Nothing mutated, repaired, or deleted.

## Input hashes
- prediction_ledger sha256 `f6835caf35b8886863e247d9323249e2e73abfeb7ba299f85eeb46b5d4af8f8e`
- forecast_targets sha256 `3f4f1d78b5f5969d7d59ee5bd69815d0c3fb53331e876ad3f736b347ec0b19eb`
- queue sha256 `f61e30547303fa51e2303fc26041cdc89df9aa8d34c1c696bd0982cce2c57628`
- raw odds snapshots: 56 files, combined sha256 `68263bc735eeaa942738cc37706edecf955f1a4bf345cdc77ff76469cde2589a`

## Counts
- prediction_rows: 680
- unique_fixture_ids: 35
- unique_match_keys_pairs: 35
- models_represented: ['M1_B1', 'M2_market', 'M3_75_25', 'M4_50_50', 'M5_25_75']
- snapshot_types_represented: ['baseline', 'T-15', 'final_pre_kickoff', 'T-90']
- approved_rows: 384
- shadow_rows: 296
- rows_before_kickoff: 680
- rows_after_kickoff: 0
- rows_missing_timestamps: 0
- rows_malformed_probabilities: 0
- rows_unresolved_identity: 0
- rows_missing_provenance: 0
- pending_queue_rows: 72
- stale_queue_rows: 29
- existing_scored_rows: 0
- existing_metrics_rows: 0
- existing_calibration_rows: 0
- valid_predictions: 680
- invalid_predictions: 0

## Validity
- valid predictions: 680 / 680
- invalid predictions: 0 (classified, not deleted)
