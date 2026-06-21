# wcdrawlab building-block map (reference)

Generated from a parallel read of every module. Probability arrays are `(n,3)` in
`OUTCOME_ORDER = ['A','D','B']` (0=A-win, 1=Draw, 2=B-win).

## Metrics & calibration — `wcdrawlab.evaluation`, `wcdrawlab.calibration`
- `metric_report(y_true, probs)->{log_loss, rps, draw_brier, draw_ece}` (normalizes internally).
- `rps_3way`, `log_loss_3way`, `brier_draw(y, p_draw)`, `expected_calibration_error_draw(y, p_draw, bins=10)`,
  `draw_calibration_table(...)`, `normalize_probs`, `outcome_to_index`.
- `DrawLogitCalibrator(features, C=1.0).fit(X, y_is_draw).apply(base_probs, X)->(n,3)`.
- `IsotonicDrawCalibrator().fit(p_draw, y_is_draw).apply(base_probs)->(n,3)`.
  Calibrators MUST be fit on a split distinct from base-model train and from test.

## Feature builders — `wcdrawlab.features`
Order: `add_basic_outcome_columns` (labels, last) → `add_strength_deltas` → `build_pre_match_group_state`
→ `add_schedule_adjusted_state` → `add_low_block_risk` → `add_travel_fatigue`. All leakage-safe; skip if inputs absent.
- `build_pre_match_group_state(matches)` needs group,kickoff_utc,goals_a/b → pre-match cumulative team/group state incl `prior_group_draws`.
- `add_strength_deltas` makes `elo_delta`, `abs_elo_delta`, fifa/market deltas (A−B).

## One-shot — `wcdrawlab.pipeline`
- `build_features(matches, elo=None, fifa=None, odds=None)` asof-joins elo (fill 1500) + fifa(std) + no-vig market
  (snapshot_time<=kickoff), runs all builders. Market default 1/3, total 2.35.
- `run_walkforward_backtest(features, test_start, outdir)` -> PipelineResult(metrics, predictions, edges).
  Trains 6 models: historical_prior, ternary_elo, gaussian_draw, multinomial_logit,
  scoreline_poisson_dc_diag, scoreline_plus_draw_calibrator. (No market row, no ensemble row.)

## Elo — `wcdrawlab.elo`
- `latest_elo(ratings, team, as_of=kickoff, default=1500)` TIME-SAFE (rating_date<=as_of).
- `EloUpdateConfig(k=60, scale=400, home_advantage=0, ...)`, `compute_post_match_elo(elo_a,elo_b,ga,gb,config)`,
  `update_elo_after_match_table(...)`, `append_post_match_elo_rows(...)`, `write_elo_outputs(...)`.

## Ratings → prob — `wcdrawlab.ratings`
- `elo_expected_score(delta, scale=400)`; `ternary_elo_probs(delta, r=0.4, home_advantage=0)->(n,3)` (r UNFITTED);
  `gaussian_draw_prob(delta, draw_base=0.30, draw_width=240)`; `standardize_fifa_release(fifa)`.

## Market — `wcdrawlab.market`
- `no_vig_from_decimal_odds(odds_a, odds_d, odds_b)->(n,3)`  ← **this is B6**.
- `decimal_odds_to_implied`, `remove_overround`, `fair_odds`, `edge_scan(...)`, `kelly_fraction`.

## Baselines — `wcdrawlab.models.baselines`, `wcdrawlab.models.scoreline`
- `HistoricalPriorModel().fit(y).predict_proba(n|df)` ← **B0**.
- `TernaryEloModel(r=0.4, home_advantage=0)` ← **B1** (and **B3** via home_advantage).
- `GaussianDrawEloModel(...)`; `MultinomialLogitModel(features, C, max_iter)` (StandardScaler+LogReg) ← **B2** via FIFA features.
- `IndependentPoissonModel(features, max_goals=8, alpha=1e-4, rho=0, diagonal_inflation=0)`:
  rho=0 → **B4**; rho=-0.05,diag=0.05 → **B5** (Dixon-Coles). `.fit(X, y_goals_a, y_goals_b)`.
- Low-level: `poisson_score_matrix`, `adjusted_score_matrix`, `probs_from_score_matrix`.

## Simulation — `wcdrawlab.simulation.*`
- `standings`: `GroupTable.add_result(...)`, `.dataframe()`, `rank_third_place_teams(third_rows)`.
- `group_simulator.simulate_group_stage(fixtures, probs, n_sims, third_place_slots=8, seed)` (plays only NaN-goal rows).
- `utility.match_advance_utilities(...)` → draw utility, mutual_draw_utility, must_win_pressure.

## Gaps to fill for B0–B7
1. **B6 not wired** into any backtest row (function exists).
2. **B7 not a real ensemble** — only single-model `scoreline+draw_calibrator`. Need a blender of B0–B6 + draw calibration.
3. **B2** = generic logit; needs FIFA features (none free yet) or accept logit-on-available-features.
4. **B3** explicit Elo+host = `TernaryEloModel(home_advantage=...)`.
5. No uniform registry returning all 8 baselines — assemble from callables above.
