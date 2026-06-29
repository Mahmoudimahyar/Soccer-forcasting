# Domain-Normalized Transfer Dataset — Data Card (Phase 3)

_research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible_

Reference model for every candidate comparison: `research.transfer.w2_reference_t0` (the parameter-free
remaining-time Poisson anchor; never a weaker baseline).

## What this dataset is

The **causal domain-normalized transfer dataset** is the leakage-safe row population the hierarchical
partial-pooling transfer ladder (`research.transfer.{international_only_t1… calibrated_transfer_simulation_t7}`)
consumes. One row per leakage-safe event-process snapshot (decision minute `t`, period ∈ {1,2},
clock-minute ≤ 90). Each row belongs to exactly **one outer temporal fold** (one held-out international
tournament) and carries:

- the **T0 reference** intensity (`t0_lam_*`) and final-H/D/A probabilities (`t0_prob_*`) — the common,
  domain-agnostic anchor;
- the **per-domain baseline** (`domain_baseline_*`) — the residual baseline, fit on this fold's TRAIN
  rows only (a function of score-state / time / remaining / orientation / numerical-state + a per-domain
  intercept);
- the **transfer target** (`transfer_residual_*`) — observed remaining goals **minus that domain's own
  baseline** (the residual contribution the transfer ladder models, NOT relative to T0);
- the **kept stable-feature subset** (`feat_*`) — the filter is fit on TRAIN rows only.

Schemas: `schemas/domain_normalized_intensity_snapshot_v1.yaml` (the row) and
`schemas/domain_transfer_feature_contract_v1.yaml` (the feature/gate contract).

## Real-data build (this worktree)

Built by `python scripts/build_domain_normalized_transfer_dataset.py` →
`data/processed/domain_normalized_transfer/transfer_dataset_v1.csv` + `build_manifest.json`
(mirrored under `outputs/research_runs/<run_id>/hierarchical_transfer/`).

| quantity | value |
|---|---:|
| rows (snapshots) | **93,940** |
| outer temporal folds | **4** |
| international test matches (total) | **194** |
| club training matches | **0** (see below) |
| stable-feature subset size (per fold) | **19** |
| columns | 61 |

### Folds (held-out international tournament → training before its first kickoff)

| held-out tournament | cutoff (first kickoff) | intl_train rows | club_train rows | test rows | test matches | kept features |
|---|---|---:|---:|---:|---:|---:|
| UEFA Euro 2020 | 2021-06-11 | 8,269 | 0 | 6,412 | 51 | 19 |
| FIFA World Cup 2022 | 2022-11-20 | 14,681 | 0 | 7,614 | 64 | 19 |
| UEFA Euro 2024 | 2024-06-14 | 22,295 | 0 | 6,612 | 51 | 19 |
| Copa America 2024 | 2024-06-21 | 24,605 | 0 | 3,452 | 28 | 19 |

`FIFA World Cup 2018` (the earliest tournament in the lake, first kickoff 2018-06-14) is **correctly
skipped**: it has no earlier international training data, so no fold can be fit. This is the honest,
leakage-safe behaviour — not a failure.

### Kept stable-feature subset (19)

`goals_diff, players_diff, yellow_diff, sendoff_diff, subs_used_diff, poss_share_diff, field_tilt_home,
final_third_actions_diff, box_entries_diff, recoveries_diff, turnovers_diff, corners_diff,
att_free_kicks_diff, shots_diff, shots_on_target_diff, cum_xg_diff, cum_xg_total, xg_last5m_diff,
xg_last10m_diff`.

Always excluded from the model space (domain-shifted / source-incompatible): `poss_actions_home`,
`poss_actions_away` (raw action counts scale with a league's event-logging density), `n_events_observed`
(leakage-budget provenance, not a feature).

## Sources

- **INTERNATIONAL (primary test population)** — the persistent international event lake
  (`statsbomb_open/international_event_lake_v1`): 258 hash-verified official StatsBomb international event
  objects across 5 tournaments (WC 2018, Euro 2020, WC 2022, Euro 2024, Copa America 2024), resolved via
  the lake index + the exact api↔statsbomb bridge. Leakage-safe snapshots are produced by the canonical
  `event_process` engine (`snapshot_features`), carrying side-specific remaining-goal labels.
- **CLUB (auxiliary training only)** — the event-process auxiliary corpus (669 club matches; manifest at
  `data/reference/event_process_auxiliary_manifest.csv`). **Club raw event JSON is not materialized in
  this worktree**, so the club training rows = 0 for this build. This is reported honestly in the build
  manifest (`club.status = no_local_club_events`) and is **not fabricated**. When the 669 club event
  objects are materialized under the statsbomb_raw aux root, the same engine path produces club training
  rows and the cross-domain stable-feature shift gate becomes active (its synthetic two-domain behaviour
  is exercised by the test suite).

## Leakage / honesty guarantees (re-asserted by the audit + tests)

- **No 2026 World Cup** material in any domain or fold (`assert_no_2026`; the lake is 2018–2024 only).
- **Temporal cutoff** — `intl_train` + `club_train` kickoff strictly before `fold_cutoff_kickoff`.
- **Club rows are auxiliary-only** — a club row is NEVER `row_role=intl_test`; the primary test
  population is international-only.
- **Fit-on-train-only** — the per-domain baseline and the stable-feature filter are fit on the fold's
  TRAIN rows only; the held-out tournament's rows are passed only for APPLICATION.
- **No competition-label leak** — a fold's `intl_train` never contains the held-out tournament label.
- **Targets are never features** — `rem_goals_*`, `target_wdl`, and `transfer_residual_*` are separate
  keys; no `feat_<target>` column exists. `n_events_observed` is provenance, never a feature.
- **Match-level grouping** — a `(match_id, fold)` carries exactly one role (bootstrap unit = match).
- **Source traceability** — every row carries `source_sha256` + `engine_version`.
- **Deterministic** — identical inputs → byte-identical rows / folds / kept subset (no RNG in the path).

## Verification

- `python scripts/audit_domain_normalized_transfer_dataset.py` → `all_invariants_ok: true` on the
  materialised 93,940-row real dataset (4 folds, 194 intl test matches, 0 club train matches, subset 19).
  Writes `data/reference/domain_normalized_transfer_audit.json` +
  `notes/research/domain_normalized_transfer_audit_report.md`.
- `pytest tests/test_domain_normalized_transfer_dataset.py -q` → **38 passed** (32 always-run synthetic +
  6 integration on the real CSV; integration tests SKIP cleanly when the CSV is absent).

## Reported metrics (build contract)

- international test match count: **194**
- club training match count: **0** (club raw events not materialized locally — honest, never fabricated)
- stable-feature subset size: **19** (per fold)
