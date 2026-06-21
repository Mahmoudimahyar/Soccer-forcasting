# After-Game Update Workflow

The model should update immediately after every completed group-stage game. This is an event-driven update, not a daily cron job.

## 1. Initialize the live match table

Use the seed table or your own verified fixture table:

```bash
mkdir -p data/live
cp data/seed/worldcup_2026_seed_matches.csv data/live/current_matches.csv
```

## 2. Refresh predictions before making any update

```bash
wcdrawlab predict-live \
  --matches data/live/current_matches.csv \
  --elo data/seed/seed_ratings_2026.csv \
  --odds data/seed/sample_odds_2026.csv \
  --output outputs/live
```

## 3. Insert a final result after a game

Example:

```bash
wcdrawlab update-after-match \
  --matches data/live/current_matches.csv \
  --match-id 2026_A_03 \
  --goals-a 1 \
  --goals-b 1 \
  --source manual_verified \
  --current-matches data/live/current_matches.csv \
  --output outputs/live
```

## 4. Inspect outputs

Main files:

```text
outputs/live/predictions_remaining.csv
outputs/live/advancement_probabilities.csv
outputs/live/draw_edges.csv
outputs/live/features_after_update.csv
data/live/current_matches.csv
outputs/live/update_log.csv
```

## 5. What changes after the update

A single result can change several downstream variables:

- pre-match points before future games;
- goal difference and goals scored before future games;
- prior group draw count;
- prior group goals per match;
- simulated advancement probabilities;
- third-place advancement safety;
- mutual draw utility;
- must-win pressure;
- model draw probability;
- draw fair odds;
- risk interval and edge flags.

## 6. Automation pattern

In production, connect your result source to this command:

```bash
wcdrawlab update-after-match --match-id MATCH_ID --goals-a GA --goals-b GB ...
```

That command should run whenever a match result becomes final. A scheduler alone is inferior because the important event is not a clock time; it is the final score being confirmed.

For polling-based systems, poll your result source every few minutes and call `update-after-match` only when a match status changes to final.


## Elo update after each game

After the latest upgrade, `update-after-match` also updates the live Elo table by default. The command first checks `data/live/current_elo.csv`; if it exists, it uses that as the latest rating source. If it does not exist, it falls back to the seed Elo file passed with `--elo`. After the score is inserted, it appends two post-match Elo rows, writes `data/live/current_elo.csv`, logs the calculation in `outputs/live/elo_update_log.csv`, and then recomputes all remaining predictions from those updated ratings.

See `docs/ELO_UPDATE_SYSTEM.md` for the formula, assumptions, and command examples.
