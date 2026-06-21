# Elo Update System

## Decision

The project now keeps a **live internal Elo table** and updates it immediately after each final score. This is the only way to have ratings available right after a match. Third-party Elo sites can be used as external reconciliation snapshots, but they may lag, may not expose a stable API, and may use slightly different formulas.

The live workflow is therefore:

1. Start with a seed Elo table, ideally scraped/imported from World Football Elo or another chosen rating source before the tournament.
2. After a match is final, insert the score into `current_matches.csv`.
3. Compute a post-match Elo update for both teams.
4. Append two new rows to `current_elo.csv`, one for each team.
5. Rebuild features using the latest rating whose `rating_date <= kickoff_utc` for every remaining match.
6. Recompute match probabilities, advancement probabilities, draw utilities, risks, and betting edges.

## Formula

For team A:

```text
E_A = 1 / (1 + 10^(-(R_A + H - R_B) / scale))
S_A = 1 for win, 0.5 for draw, 0 for loss
R_A_new = R_A + K * G * (S_A - E_A)
R_B_new = R_B - K * G * (S_A - E_A)
```

The default update is zero-sum and World-Football-Elo-like:

```text
K = 60.0
scale = 400.0
home_advantage = 0.0 by default for neutral-site matches
round_change = true
```

Goal-difference multiplier:

```text
G = 1                 for draws or one-goal wins
G = 1.5               for two-goal wins
G = (11 + N) / 8      for wins by N >= 3
```

These defaults can be changed from the CLI. For example, if you want a FIFA-SUM-like lower group-stage weight, run with `--elo-k 50`.

## Why internal Elo rather than only fetching external Elo?

There is no single official football Elo. World Football Elo is a widely used public implementation, while FIFA uses its own modified Elo-style ranking system. Public sources may update later than final whistle. For a live prediction engine, waiting for external ratings defeats the purpose.

So the model uses two layers:

- **External seed/reconciliation layer:** import the latest trusted external Elo snapshot before the tournament or periodically during the tournament.
- **Internal live layer:** update immediately after each final score using a documented formula.

The current file of record is:

```text
data/live/current_elo.csv
```

The audit file is:

```text
outputs/live/elo_update_log.csv
```

## Commands

Initialize live Elo:

```bash
mkdir -p data/live
cp data/seed/seed_ratings_2026.csv data/live/current_elo.csv
```

After each completed game, run:

```bash
wcdrawlab update-after-match \
  --matches data/live/current_matches.csv \
  --match-id 2026_A_03 \
  --goals-a 1 \
  --goals-b 1 \
  --elo data/seed/seed_ratings_2026.csv \
  --current-elo data/live/current_elo.csv \
  --current-matches data/live/current_matches.csv \
  --output outputs/live
```

The command prefers `data/live/current_elo.csv` when it exists and falls back to the seed Elo file only on the first update.

Elo-only update without refreshing predictions:

```bash
wcdrawlab update-elo \
  --matches data/live/current_matches.csv \
  --elo data/live/current_elo.csv \
  --match-id 2026_A_03 \
  --goals-a 1 \
  --goals-b 1
```

## Caveat

Internal Elo is not guaranteed to match World Football Elo point-for-point unless you exactly replicate its fixture classification, home advantage handling, rounding, and source data. This project deliberately makes these settings explicit and auditable instead of silently pretending that one Elo number is canonical.
