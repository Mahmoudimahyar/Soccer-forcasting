# In-Play 2022 Baseline Comparison (research-only)

Leave-one-group-out (8 folds), 858 decision rows, 48 matches. Match-level paired bootstrap (2000×).
Metrics: `outputs/research/inplay_2022_metrics/`. **Nothing promoted; B1 stays the approved pre-match model.**

## W/D/L (HOME-perspective), lower = better
| model | RPS | log loss | draw Brier | mean entropy |
|---|---|---|---|---|
| M0 static B1 (no live info, control) | 0.2432 | 1.112 | 0.147 | 0.814 |
| M1 time+score logit | 0.1748 | 0.864 | 0.142 | 0.709 |
| **M2 remaining-time Poisson** | **0.1552** | 0.819 | **0.123** | 0.571 |
| M5 ensemble (M1+M2, cross-fit calib) | 0.1614 | **0.819** | 0.126 | 0.652 |

## Match-level bootstrap vs M1 (negative = better than M1; significant if CI excludes 0)
| model | dRPS vs M1 | 95% CI | verdict |
|---|---|---|---|
| M0 static B1 | +0.065 | [+0.011, +0.121] | **significantly WORSE** than M1 |
| M2 remaining Poisson | −0.021 | [−0.042, +0.004] | better, **not significant** (underpowered) |
| M5 ensemble | −0.014 | [−0.023, −0.004] | **significantly better** than M1 |

## Next-event targets (LOGO)
- `goal_within_5` (M3 hazard): Brier 0.1148 vs base-rate 0.1126 → **does NOT beat the base rate**. The
  sparse features (no shots/xG/possession) carry too little next-goal signal on 2022.
- `next_goal_team` (M4 competing-risk): log loss 1.032 vs base-rate 1.084 → **modestly beats base rate**.
- `red_within_*`: 7 positives in 858 → not modeled (reported as a gap).

## Read
- **Live state is hugely informative for W/D/L**: M2 (0.155) vs static B1 (0.243). But that mostly
  reflects knowing the current score — the honest bar is M1 (time+score), and only the **ensemble (M5)
  beats M1 with significance**; M2 is best on point estimates but its match-level CI includes 0.
- **Next-goal timing is not learnable from these features on 2022** (M3 fails vs base rate). Richer
  event data (shots/xG/possession) is required.
- Research leader: **M2 / M5** for W/D/L. Still research-only; not remotely runtime-eligible from one
  tournament. See `inplay_2022_failure_analysis.md`, `inplay_2022_data_limitations.md`.
