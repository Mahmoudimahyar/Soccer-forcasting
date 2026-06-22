# In-Play Evaluation Protocol (research-only)

In-play state rows within one match are **highly correlated** (consecutive minutes share score, cards,
strength). Random row splits leak. This protocol fixes leakage-safe splits + reporting for the 2022
foundation. Nothing here is runtime-approved.

## Split policy (NEVER split rows randomly)
- **Leave-groups-out (primary):** the 8 groups (A–H) are the fold unit. Leave-one-group-out → 8 folds;
  train on 7 groups' matches, evaluate on the held-out group's matches. **No match contributes rows to
  both train and test** (a match belongs to exactly one group).
- **Match-level paired bootstrap** for significance: resample whole matches (not rows), 2000×.
  Row-level bootstrap is forbidden (anti-conservative).
- Calibration is **train-fold-only or cross-fitted** — a calibrator is never fit on its test fold.

## Reporting breakdowns (computed on held-out predictions)
- **Time buckets:** 0–15, 16–30, 31–45+, 46–60, 61–75, 76–90+.
- **Match-state:** level score, 1-goal diff, 2+-goal diff; equal player count vs red-card imbalance;
  late-game (≥76').
- **Event-triggered:** immediately after goal / red card / substitution / penalty vs ordinary fixed
  snapshots.

## Metrics
- W/D/L: RPS, 3-way log loss, draw Brier, calibration slope/intercept, reliability, interval coverage,
  entropy.
- Next-goal / horizon targets: Brier, log loss, PR-AUC (where class balance permits), calibration
  curve, ECE; broken down by minute / score / red state / post-event vs ordinary.

## Why 2022 alone is insufficient for production generalization
One tournament, 48 matches, 858 decision rows, **sparse features** (no shots/xG/lineups), and severe
class imbalance for rare targets (only ~4 red-imbalance rows; 7 `red_within_10` positives → red-card
horizons are effectively unlearnable here). Leave-groups-out on 8 small groups gives wide CIs. This
supports **honest baseline comparison and calibration study only** — not a deployable in-play model.
A credible in-play model needs many tournaments/competitions of event data (multi-season feeds).
