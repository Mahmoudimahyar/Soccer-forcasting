# Model Card

## Intended use

The World Cup Draw Model Lab is intended to:

- test draw-prediction hypotheses,
- build calibrated match probabilities,
- simulate 2026-style group-stage incentives,
- compare model probabilities against market odds,
- report uncertainty and risk for each prediction.

## Not intended for

- guaranteed betting profit,
- automated wagering without human review,
- predictions from stale or post-match data,
- use with unverified seed data,
- replacing lineup/injury/weather analysis.

## Core assumptions

1. Team strength is partially captured by Elo/FIFA/market/squad features.
2. Goal counts can be approximated with Poisson-style models, with low-score corrections tested empirically.
3. Draw probability depends on strength parity, expected total goals, and tournament state.
4. Market odds are a strong baseline but may have residual miscalibration in specific buckets.
5. 2026 third-place qualification changes group-stage incentives and must be simulated.

## Main outputs

Prediction outputs include:

```text
p_a
p_draw
p_b
outcome_sd_a
outcome_sd_draw
outcome_sd_b
prob_se_a
prob_se_draw
prob_se_b
prob_ci_low_a / draw / b
prob_ci_high_a / draw / b
prediction_entropy
confidence_score
risk_band
```

Edge-scan outputs include:

```text
edge_draw
fair_odds_draw
bet_draw
draw_bet_ev_per_unit
draw_bet_sd_per_unit
draw_bet_sharpe_like
```

## Known limitations

- Historical World Cup samples are small.
- Draws are intrinsically noisy.
- Market odds data must be timestamped correctly.
- Team news and starting XI data can dominate final probabilities.
- The current simulator uses simple representative score generation unless replaced with score-matrix sampling.
- Risk intervals are approximate and based on effective sample size, not a full Bayesian posterior.

## Recommended governance

Before trusting a new module:

1. run walk-forward validation,
2. check calibration by draw-probability bucket,
3. compare against market probabilities,
4. inspect prediction intervals,
5. verify no leakage,
6. run ablation with and without the module.
