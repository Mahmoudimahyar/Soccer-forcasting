# In-Play 2022 Split Audit

Dataset: `data/processed/inplay_state_2022_group_stage.parquet` — **858 rows, 48 matches, 8 groups.**
Protocol: `docs/INPLAY_EVALUATION_PROTOCOL.md`. Research-only.

## Rows per group (leave-one-group-out fold sizes)
A 100 · B 108 · C 113 · D 97 · E 113 · F 98 · G 118 · H 111. Balanced enough for 8-fold LOGO; each
held-out fold = 5–6 matches → wide CIs (expected).

## Time-bucket distribution
0–15: 117 · 16–30: 89 · 31–45: 93 · 46–60: 147 · 61–75: 194 · 76–90+: 215. Skewed late (more events
accumulate), so late buckets are better-sampled than early ones.

## Match-state distribution
level score: 399 · 1-goal diff: 284 · 2+-goal diff: 175. **Red-card-imbalance rows: only 4** → any
red-state metric is anecdotal, not estimable.

## Target balance
- final W/D/L rows: home-win 346 · away-win 352 · draw 160.
- next_goal_team: none 348 · home 282 · away 228.
- goal_within_5 positives: **111 / 858 (~13%)** — learnable but imbalanced.
- red_within_10 positives: **7 / 858 (<1%)** → **effectively unlearnable**; report as a known gap, do
  not claim a red-card hazard model from 2022.

## Implications for evaluation
- W/D/L and next-goal(≤5/≤10 min) are the only targets with enough signal for a descriptive
  comparison. Red-card horizons and post-substitution next-goal effects are too sparse for inference.
- All comparisons use leave-one-group-out + match-level bootstrap; no single-row significance.
