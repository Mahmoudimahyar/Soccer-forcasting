# Residual Goal-Intensity — Feature Catalog

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Package: `wcdrawlab.research.residual_intensity` (Phase 2). Built off tag
`event-process-intelligence-v1`. Worktree: `C:/Users/Mahyar/worldcup-residual-goal-intensity`.

This catalog documents the six interpretable feature families consumed by the residual-intensity model
families. Every feature is a column of the already-built, already-leakage-truncated event-process
snapshot table `data/processed/event_process_snapshots/intl_event_process_snapshots.csv` (built by
`scripts/build_event_process_snapshots.py` from StatsBomb open-data only; no network, no API, no Odds).
Each snapshot column at decision minute `t` uses only events with match-clock minute `<= t` (regulation
only, period `<= 2`, minute `<= 90`). **Nothing here recomputes from raw events and nothing here reads a
target.**

## Reference: W2 is an intensity, not a classifier
W2 = the remaining-time Poisson model. We treat it as a **reference intensity**: expected REMAINING
regulation goals for home and away. In this package:
- `features.w2_reference_intensities(row)` → `w2_lam_home`, `w2_lam_away` (= `R2_BASE * remaining_fraction`
  per team, `R2_BASE = 1.35`, identical to the locked `event_process.e2` / `dynamic_models.R2_BASE`).
- `intensity.w2_home_away_i0` returns these side-specific intensities.
- `residual.w2_reference_r0` convolves them (exact independent-Poisson) with the current score diff to
  give `P(final H/D/A)`.
Every residual / correction model is expressed RELATIVE to this reference (it either reproduces W2 or
adds an event-process correction blended onto W2 by a selectively-chosen weight `alpha ∈ [0,1]`).

## The six feature families
Columns map verbatim to the snapshot schema. Family availability coverage measured on the real
international panel (7,376 snapshots, 58 matches, 5 competitions: WC2018, WC2022, Euro2020, Euro2024,
Copa2024).

| # | Family | Module symbol | Coverage* | Representative columns |
|---|--------|---------------|-----------|------------------------|
| 1 | reference_state | `REFERENCE_STATE_COLS` | 1.000 | `goals_diff`, `remaining_regulation_min`, `snapshot_minute`, `period`, `players_diff` |
| 2 | recent_chance | `RECENT_CHANCE_COLS` | 0.948 | `cum_xg_home/away/diff`, `xg_last{1,2,5,10,15}m_diff`, `xg_momentum_diff_10m`, `shots_diff`, `min_since_last_shot_any`, `min_since_major_chance` |
| 3 | possession_territory | `POSSESSION_TERRITORY_COLS` | 0.998 | `poss_share_home/diff`, `field_tilt_home`, `final_third_actions_diff`, `box_entries_*` |
| 4 | transition | `TRANSITION_COLS` | 1.000 | `recoveries_diff`, `turnovers_diff`, `recoveries_*`, `turnovers_*` |
| 5 | set_pieces | `SET_PIECE_COLS` | 1.000 | `corners_*`, `att_free_kicks_*` |
| 6 | quality_availability | `QUALITY_AVAILABILITY_COLS` | 1.000 | `yellow_diff`, `sendoff_diff`, `subs_used_diff`, `n_events_observed` |

\* mean per-family availability fraction across the 7,376 real rows (`quality.availability_audit`).

### xG sub-coverage (family 2)
The xG-derived columns have **94.98%** availability — exactly the 7,006 / 7,376 rows whose source carries
xG. The remaining 370 rows (`xg_present == False`) are NOT zero-filled: the availability gate marks every
`cum_xg*` / `xg_last*` / `xg_*` column **unavailable** for those rows (see `availability._XG_GATED_*`), so
a missing-xG source can never masquerade as "no xG happened". Shot-count columns (`shots_diff`,
`shots_last5m_*`) are 100% available because shot events exist even where xG values do not.

`min_since_major_chance` is the lowest-coverage column (0.729) — it is null early in matches before any
major chance, which is genuine missingness, preserved (not imputed as a large/zero sentinel).

## Missingness contract (no silent zeros)
- `features.fnum()` returns `None` for an absent/blank/unparseable cell — it never returns `0` for
  missing data.
- The availability gate (`availability.py`) decides usability per `(row, column)` and **preserves
  missingness**. xG columns are additionally gated on the row's `xg_present` flag.
- Downstream, the reused `dynamic_models.FeatureSpace` imputes a **TRAIN-mean** for an absent cell and
  sets a companion `<col>__unknown` indicator, so the model sees an explicit "was missing" signal rather
  than a spurious zero. Imputation means are learned on TRAIN only and frozen for predict.
- `availability.gate_columns()` drops any column that is unavailable in **every** training row, so a
  model can never be handed an everywhere-unavailable feature. On the real panel,
  `everywhere_unavailable_cols == []` (every declared feature is observed at least sometimes).

## What is deliberately NOT a feature (leakage)
`quality.TARGET_KEYS` and `quality.FORBIDDEN_FEATURE_COLS` enumerate the label/future columns that must
never enter a feature space: `target_wdl`, `rem_goals_home/away`, `reg_home/away_goals`,
`next_goal_*`, `any_goal_next{5,10,15}m`, `home/away_scores_next*`, `sendoff_after`, and any final-score
columns. `quality.leakage_audit` re-asserts (a) none of these are in the chosen feature set, (b) no
forbidden column present, (c) regulation-only `period <= 2` / `minute <= 90`. The audit passes on the real
panel (`ok: true`, `leaked_targets: []`).

## Reuse provenance
- Fitters / `FeatureSpace` / `IsotonicCalibrator` / Poisson convolution: `dynamic_models`.
- Side-specific intensity heads (`IntensityWDL`), exact convolution, W2/e2 reference, `ClubAuxRep`:
  `event_process.models`.
- Leakage-safe joined snapshot/target loader + `assert_no_2026`: `event_process.eval`.
- Metrics (RPS / log-loss / Brier / calibration / LOCO / match bootstrap): `scripts/research_jobs/_common.py`.

No completed-2026-World-Cup data is in any fit/calibration/selection path: `event_process.eval` and
`quality.no_2026_audit` enforce no-2026; the real panel contains WC2018/WC2022/Euro2020/Euro2024/Copa2024
only.
