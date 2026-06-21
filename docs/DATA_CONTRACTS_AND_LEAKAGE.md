# Data Contracts and Leakage Rules

## Prime directive

No feature may use information unavailable before kickoff.

```text
feature_timestamp <= match_kickoff
```

## Required schemas

Schemas live in:

```text
schemas/matches.yaml
schemas/ratings.yaml
schemas/odds.yaml
```

Minimum match columns:

```text
match_id
kickoff_utc
tournament
stage
group
matchday
team_a
team_b
goals_a
goals_b
venue
neutral
```

Minimum Elo columns:

```text
team
rating_date
elo
```

Minimum FIFA columns:

```text
team
release_date
fifa_rank
fifa_points
```

Minimum odds columns:

```text
match_id
snapshot_time
book
odds_a
odds_draw
odds_b
```

## As-of joins

Ratings and odds are joined using as-of logic:

```text
last rating snapshot before kickoff
last FIFA release before kickoff
last odds snapshot before kickoff
```

Never use end-of-tournament rankings. Never use closing odds if the prediction is supposed to be made earlier than the closing timestamp.

## FIFA normalization

Raw FIFA points cannot safely be pooled across ranking eras. The project standardizes FIFA points inside each release:

\[
FIFA_Z = \frac{points - mean(points\ in\ release)}{sd(points\ in\ release)}
\]

It also supports rank percentile.

## Match-type weighting

If you add non-World-Cup matches, do not treat all matches equally. A suggested training weight hierarchy is:

```text
World Cup group/knockout > continental tournaments > qualifiers > friendlies
```

Friendlies can help estimate team strength, but they are not the same behavioral environment as a World Cup Round 3 match.

## Seed data warning

The included 2026 seed files are pipeline-test data. They prove the code path runs. They are not betting-grade.

Replace them with live timestamped sources before trusting any probability.
