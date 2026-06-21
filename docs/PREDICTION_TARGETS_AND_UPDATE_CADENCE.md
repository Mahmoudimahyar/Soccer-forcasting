# Prediction Targets and After-Game Update Cadence

## What the model predicts

The project is not only a “who wins?” model. It produces a full probability and risk report for each remaining group-stage match.

For each unplayed match, the live pipeline predicts:

1. `p_a_model`: probability that `team_a` wins.
2. `p_draw_model`: probability that the match is a draw.
3. `p_b_model`: probability that `team_b` wins.
4. `fair_odds_draw`: fair decimal draw odds implied by the model, `1 / p_draw_model`.
5. `most_likely_outcome`: team A win, draw, or team B win.
6. `p_advance_a` and `p_advance_b`: current simulated probability that each team advances from the group stage.
7. `p_third_advance_a` and `p_third_advance_b`: simulated probability that each team advances as a third-place team.
8. `draw_utility_a` and `draw_utility_b`: how much a draw improves each team’s advancement probability relative to losing.
9. `mutual_draw_utility`: the minimum of the two draw utilities. This is high when a draw is useful to both teams.
10. `must_win_pressure_max`: the strongest win-over-draw incentive for either team.
11. Risk metrics: event standard deviation, probability standard error, probability intervals, entropy, confidence score, and risk band.
12. Betting diagnostics when odds are available: model edge, fair odds, expected value per unit, bet standard deviation, and whether the draw passes the edge filter.

## What the model does not claim

It does not claim that the highest-probability outcome will always occur. A 30% draw probability means the model expects 70% non-draw outcomes in comparable matches. The risk columns exist because even a good probability forecast has large event-level variance.

It also does not automatically bet every positive edge. A draw is only flagged when the model probability clears the market no-vig probability by more than the required safety margin and the available odds exceed fair odds.

## How often the data should update

The intended deployment cadence is **event-driven after every completed game**.

After each final whistle, run:

```bash
wcdrawlab update-after-match \
  --matches data/live/current_matches.csv \
  --match-id 2026_A_03 \
  --goals-a 1 \
  --goals-b 1 \
  --elo data/seed/seed_ratings_2026.csv \
  --odds data/seed/sample_odds_2026.csv \
  --current-matches data/live/current_matches.csv \
  --output outputs/live
```

The command updates the match result, recomputes group standings, recomputes advancement probabilities, recalculates draw utility and must-win pressure, regenerates probabilities for remaining matches, recomputes uncertainty/risk metrics, and rewrites output files.

## What gets updated after each game

After every result, the system updates:

- `data/live/current_matches.csv`: current canonical match/result table.
- `outputs/live/update_log.csv`: append-only log of result updates.
- `outputs/live/features_after_update.csv`: refreshed feature table.
- `outputs/live/predictions_remaining.csv`: refreshed match probabilities and risk metrics for all remaining matches.
- `outputs/live/advancement_probabilities.csv`: refreshed team-level advancement probabilities.
- `outputs/live/draw_edges.csv`: refreshed draw value scan when odds are available.
- `outputs/live/prediction_targets.json`: machine-readable list of prediction outputs.

## Why after-game updating matters mathematically

Every completed game changes the conditional probability distribution of all remaining games. The base team strength may not change much, but the tournament state changes sharply:

\[
P(advance_i | win),\quad P(advance_i | draw),\quad P(advance_i | loss)
\]

These quantities feed into:

\[
DrawUtility_i = P(advance_i | draw) - P(advance_i | loss)
\]

and:

\[
MustWinPressure_i = P(advance_i | win) - P(advance_i | draw)
\]

So the model is not merely updating a CSV. It is updating the conditional probability space for the remaining tournament.

## Recommended operational cadence

Minimum cadence:

- Update once after every final score.

Better cadence:

- Update after every final score.
- Refresh odds snapshots before the next match starts.
- Refresh ratings if your chosen rating source publishes updated values.
- Refresh lineups/injuries when those data are available.

Live-betting cadence, if implemented later:

- Update every 1–5 minutes during a match using score, minute, cards, xG/shots, and current table state.

The current package implements the after-game workflow. It does not yet implement automated bookmaker scraping or real-time in-play updates.


## Rating cadence

The live model updates Elo immediately after each final score. This is event-driven, not daily. The data source of record is `data/live/current_elo.csv`; external Elo snapshots are treated as seed/reconciliation data, while the internal Elo updater gives the model immediate post-match ratings before a third-party site may have refreshed.
