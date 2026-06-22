# In-Play 2022 Data Limitations (research-only)

Why the 2022 in-play foundation cannot support a deployable model.

## Sample size
- 1 tournament, **48 matches, 858 decision rows**, 8 groups. Leave-one-group-out folds = 5–6 matches
  each → wide CIs (e.g. M2's match-level dRPS-vs-M1 CI includes 0 despite the best point estimate).

## Feature sparsity (the binding constraint)
Available: goals, cards (yellow/red/second-yellow), substitutions (counts only), VAR, minute, score,
pre-match Elo + market. **Absent:** shots, shots-on-target, **xG**, corners, set-pieces, **starting
XI / on-pitch player IDs**, formations, possession. Consequences:
- next-goal hazard (M3) cannot beat the base rate;
- substitution *impact* is unmodelable (no player quality/position);
- momentum/territory unobserved → mid-game overconfidence.

## Class imbalance for rare targets
- `red_within_10`: 7/858 positives; red-imbalance states: 4 rows → red-card targets **unlearnable**.

## Single-competition generalization risk
2022 is one men's World Cup. Tactical/era/style differences across competitions are unrepresented; a
model tuned here would not transfer. Production in-play modeling needs **multi-season, multi-
competition event feeds with shots/xG/lineups** (see `tier_4_data_gap_backlog.md`).

## Honest conclusion
This foundation is suitable for **method/calibration study and baseline comparison only**. No in-play
model here is a candidate for live shadow testing until (a) richer event features and (b) many more
matches are available. B1/Elo remains the sole approved pre-match model; no in-play model is promoted.
