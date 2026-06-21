# Model Architecture

## Core principle

The project is a testing lab. Each chatbot idea becomes either:

1. a baseline model,
2. a feature,
3. a calibration layer,
4. a simulator quantity, or
5. a hypothesis to reject.

No football story becomes a hard rule until it improves out-of-sample probability quality.

## Layer 1: time-safe data engine

Inputs:

- match results and fixtures
- Elo ratings by date
- FIFA rankings by release date
- odds snapshots
- optional squad/player data
- optional venue/travel/weather data

Timestamp rule:

```text
feature_available_at <= match_kickoff
```

If this rule is broken, the model is leaking future information.

## Layer 2: strength layer

The strength layer creates team-difference features:

- `elo_delta`
- `abs_elo_delta`
- `fifa_z_delta`
- `fifa_rank_pct_delta`
- `market_ability_delta`
- `squad_value_log_delta`

This layer answers: who is stronger before kickoff?

## Layer 3: scoreline layer

The scoreline layer estimates goals and generates a full score matrix. It currently includes:

- independent Poisson
- Dixon-Coles-style low-score correction
- diagonal inflation

The output is:

```text
p_a_score
p_draw_score
p_b_score
```

The score matrix can also support derivative markets:

- under 2.5
- both teams to score: no
- 0-0 / 1-1 score clusters

## Layer 4: draw calibration layer

The draw calibration layer is trained as draw vs non-draw. It replaces the base scoreline draw probability while preserving the relative split between team A and team B in the non-draw mass.

Base probability:

\[
\mathbf p^{base} = (p_A, p_D, p_B)
\]

Calibrated draw:

\[
\hat p_D = g(p_D^{base}, p_D^{market}, |EloDelta|, \lambda_T, state, fatigue, lowblock)
\]

Non-draw mass is rescaled:

\[
\hat p_A = (1-\hat p_D)\frac{p_A}{p_A+p_B}
\]

\[
\hat p_B = (1-\hat p_D)\frac{p_B}{p_A+p_B}
\]

This avoids destroying the score model's opinion about which team is likelier to win.

## Layer 5: tournament-state simulator

The simulator updates group tables and estimates advancement probabilities. It is especially important for the 2026 format because third-place teams can advance.

For each match, it can force three counterfactual outcomes:

- team A win
- draw
- team B win

Then it estimates:

```text
p_adv_a_if_win
p_adv_a_if_draw
p_adv_a_if_loss
p_adv_b_if_win
p_adv_b_if_draw
p_adv_b_if_loss
mutual_draw_utility
must_win_pressure_max
```

This is where match incentives become probability features.

## Layer 6: context modules

The project includes feature modules for:

- group-state points and goal difference
- prior group draws and prior group goals
- schedule-adjusted state
- low-block risk
- travel/fatigue
- confederation features when added by the user

These modules are not trusted by default. They must survive ablation testing.

## Layer 7: market residual layer

The market layer converts bookmaker odds into no-vig probabilities and computes model-vs-market edge:

\[
Edge_D = p^{model}_D - p^{market}_D
\]

For betting, the model also computes expected value and standard deviation per unit staked.

## Final architecture

```text
Raw Data
  -> Time-Safe Joins
  -> Strength Features
  -> Scoreline Model
  -> Draw Calibration
  -> Tournament Simulator Features
  -> Market Residual / Edge Scan
  -> Risk & Uncertainty Report
```

The system is intentionally modular so that each block can be removed and tested.
