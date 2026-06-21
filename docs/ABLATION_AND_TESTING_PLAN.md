# Ablation and Testing Plan

## Goal

Every idea must earn its place by improving out-of-sample probability quality.

The model is tested in layers:

```text
M0: historical prior
M1: Elo-only
M2: FIFA-normalized only
M3: market-only
M4: scoreline Poisson
M5: scoreline + Dixon-Coles / diagonal inflation
M6: scoreline + draw calibration
M7: + group state
M8: + mutual draw utility
M9: + third-place safety
M10: + schedule-adjusted state
M11: + low-block risk
M12: + travel/fatigue/weather
M13: + squad/player data
M14: + market residual model
```

## Primary metrics

- log loss
- Ranked Probability Score
- draw Brier score
- draw calibration error

## Betting-specific diagnostics

- no-vig edge
- expected value per unit
- standard deviation per unit
- closing-line value
- ROI by edge bucket
- max drawdown

## Pass/fail thresholds

A module survives only if it improves at least one of:

```text
ΔRPS >= 0.002
ΔLogLoss >= 0.005
Draw calibration error improvement >= 0.02
Positive closing-line value across historical tests
Positive ROI after vig under realistic odds timing
```

These thresholds are intentionally modest. In football prediction, large improvements are rare.

## Hypotheses to test

### H1: Elo beats raw FIFA

Expected result: Elo should beat raw FIFA rank/points, but normalized FIFA may add incremental signal.

### H2: Draw probability peaks near strength parity

Expected result:

\[
P(D) \downarrow \text{ as } |EloDelta| \uparrow
\]

### H3: Expected total goals materially affects draws

Expected result: lower total goals increase draw probability after controlling for strength gap.

### H4: Matchday effect exists but is unstable

Do not hard-code `MD3 = higher draw`. Estimate matchday effect after controlling for strength and table state.

### H5: Prior group draws are not a cap

Test whether `prior_group_draws` helps after controlling for group goals, team strength, and incentives. Reject hard caps.

### H6: Mutual draw utility improves Round 3 calibration

Expected result: if both teams gain materially from drawing rather than losing, draw probability should increase.

### H7: Must-win pressure lowers draw probability and increases late chaos

Expected result: if both teams need a win, pre-match draw probability may fall and live over/next-goal probabilities may rise late.

### H8: Travel/fatigue matters in 2026

Expected result unknown. Keep only if it improves calibration.

### H9: Market residual model is necessary for betting

Prediction quality and betting edge are different. The market residual layer tests whether the model finds systematic miscalibration in odds.

## Walk-forward validation

Use temporal splits only:

```text
train on past -> test on future
```

Examples:

```text
train through 2014 -> test 2018
train through 2018 -> test 2022
train through yesterday -> predict today
```

Never train on later group-stage matches to predict earlier group-stage matches.
