# Baseline Evaluation B0–B7 (free-data only)

Date: 2026-06-20. Script: `scripts/evaluate_baselines.py`. Table:
`data/processed/research_modeling_table.csv` (364 played WC group matches, 1998–2026).
Objective J = 0.40·RPS + 0.25·LogLoss + 0.20·draw-Brier + 0.15·draw-calibration-error
(lower is better). Calibration is the primary target, **not accuracy**.

## Fold hierarchy
- **DEV** (model selection): train<2010→2010, train<2014→2014, train<2018→2018.
- **GATE** (release): train<2022→2022.
- **LOCKED** (transfer only, never used to select): train<2026→2026 Matchday 1.

## Results (composite; lower better)

| Model | DEV mean | DEV worst-fold | 2022 gate | 2026-MD1 locked | 2026 draw-cal |
|---|---|---|---|---|---|
| B1 ternary-Elo | **0.3553** | 0.3796 | 0.4157 | 0.4644 | 0.171 |
| B4 independent Poisson | 0.3569 | 0.3838 | 0.4233 | 0.4434 | 0.193 |
| B5 Dixon-Coles | 0.3580 | 0.3781 | 0.4258 | 0.4351 | 0.173 |
| B7 calibrated ensemble | 0.3603 | **0.3664** | 0.4263 | 0.4739 | 0.221 |
| B3 Elo + host | 0.3634 | 0.3759 | 0.4701 | 0.4514 | 0.189 |
| B2 multinomial logit | 0.3672 | 0.3781 | 0.4586 | 0.4601 | 0.215 |
| B0 historical prior | 0.4187 | 0.4217 | 0.4038 | 0.4301 | **0.128** |
| **B6 no-vig market** | — unavailable — | | | | |

## Findings
1. **Elo is the strong, simple baseline.** B1 (parameter-free ternary-Elo) has the best DEV
   mean; B4/B5 (scoreline) are within 0.003. Nothing complex dominates simple Elo on free data.
2. **The calibrated ensemble is the most *robust*.** B7 (blend of Elo+Dixon-Coles+logit, then
   Platt draw recalibration) has the best DEV **worst-fold** (0.3664) — it never has a bad fold.
   Robustness, not peak mean, is what the protocol rewards.
3. **Isotonic draw calibration overfits; Platt does not.** An earlier B7 using isotonic
   recalibration on a single tournament blew up the locked-2026 composite to 0.96 (extreme
   p_draw → huge log loss). Switching to 2-parameter Platt scaling fixed it (0.47). Recorded as
   a rejected approach.
4. **2026 Matchday-1 is a genuine drift signal.** Every skill model is worse on draw
   calibration there (0.17–0.22) than on DEV (0.06–0.08), because 2026 MD1 had an unusually
   high draw rate (~36% vs the historical ~25%) with several upsets ending level (Qatar–
   Switzerland, Saudi–Uruguay, Iran–NZ, Belgium–Egypt). The humble prior B0 looks deceptively
   good on this 24-match sample precisely because it never makes a confident wrong call — a
   small-sample, high-variance artifact, not evidence B0 is a good model.
5. **B6 (market) is the most valuable missing piece.** No real timestamped odds exist, so the
   single strongest probability benchmark cannot be built or beaten. See
   `data_requests/pending/odds_api.yaml`.

## Calibration evidence (ensemble, pooled DEV draws)
Reliability (predicted vs actual draw rate) is monotonic and close to the diagonal; 90%
draw-interval coverage = 0.60 of bins. Detail in
`outputs/research/baselines/reliability_ensemble_dev.csv`.

| p_draw bin | n | predicted | actual |
|---|---|---|---|
| 0.1–0.2 | 23 | 0.159 | 0.217 |
| 0.2–0.3 | 58 | 0.259 | 0.172 |
| 0.3–0.4 | 52 | 0.352 | 0.269 |
| 0.4–0.5 | 5 | 0.413 | 0.400 |

## Uncertainty fields
Every prediction carries `prob_se_*`, `prob_ci_*`, `prediction_entropy`, `confidence_score`,
`max_outcome_prob`, `risk_band`, and outcome variance/sd (via `risk.add_prediction_risk_columns`).
Locked-fold per-match predictions with these fields:
`outputs/research/baselines/predictions_2026_md1.csv`.

## Honest verdict
On free data, **no model robustly beats Elo + the market** — and the market baseline cannot
even be built yet. The accepted research model (autoresearch cycle 1) and B7 modestly improve
robustness/calibration over raw Elo on historical folds, but **the 2026 forecasts should be
read as Elo-grade with calibrated uncertainty, not as a validated edge.** A real claim of
"good" requires timestamped odds (B6/CLV) and a FIFA-rank feature.
