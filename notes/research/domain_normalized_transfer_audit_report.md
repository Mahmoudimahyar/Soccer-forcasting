# Domain-Normalized Transfer Dataset Audit (Phase 3)

_research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible_

Generated: 2026-06-28T17:10:13Z
Row source: **materialised_real_dataset**  (reference model: `research.transfer.w2_reference_t0`)

## Summary

- rows: **93940**  |  folds: **4** (Copa America 2024, FIFA World Cup 2022, UEFA Euro 2020, UEFA Euro 2024)
- row roles: {'intl_train': 69850, 'intl_test': 24090}
- international test matches: **194**  |  club train matches: **0**
- stable-feature subset size(s): **[19]**
- all invariants OK: **True**

## Invariant checks

| check | ok | detail |
|---|---|---|
| no_2026_world_cup_row | PASS | {"n_violations": 0} |
| train_rows_strictly_before_fold_cutoff | PASS | {"n_violations": 0, "examples": []} |
| club_row_never_intl_test | PASS | {"n_violations": 0} |
| each_fold_test_is_single_intl_tournament | PASS | {"n_folds_with_test": 4, "multi_comp_folds": {}, "mismatched_folds": {}} |
| intl_train_never_contains_held_tournament | PASS | {"n_folds": 4, "n_violations": 0, "examples": []} |
| excluded_columns_never_feat | PASS | {"violations": []} |
| transfer_residual_equals_obs_minus_domain_baseline | PASS | {"n_checked": 93940, "n_violations": 0, "examples": []} |
| match_level_grouping_consistent_per_fold | PASS | {"n_keys": 749, "n_violations": 0} |
| every_row_has_source_sha_and_engine_version | PASS | {"n_rows": 93940, "n_missing": 0} |
| eligibility_labels_present_on_every_row | PASS | {"want": "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible", "n_rows": 93940, "n_bad": 0} |
| deterministic_fold_recreation | PASS | {"rows_identical": true, "subsets_identical": true} |
