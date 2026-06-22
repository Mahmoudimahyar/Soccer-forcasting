# Tier 4 Research Sprint 1 — Plan

Event Replay → In-Play State Dataset → Baselines → Honest Evaluation. **Research-only.** B1/Elo stays
the sole approved pre-match runtime model; nothing here is promoted, influences forecasts/decisions,
or touches trading/risk/Kalshi/.env/credentials. All in-play models are
`research_only / experimental / not_runtime_approved`.

## Completed prerequisites
- 2022 WC group-stage event replay **validated 48/48** (`event-replay-2022-validated`).
- Provider-aware `event_semantics.py` (own goals correct, fail-closed) + `inplay_replay.state_from_events`.
- Transparent in-play engine (`inplay/engine.py`, remaining-time Poisson).
- B1 Elo + `market_features_2022.csv` (timestamp-safe pre-kickoff no-vig consensus).

## Available event-level data (2022 group, 48 matches)
Goals (120, own-goal-correct), cards (170 yellow/red/second-yellow via detail), substitutions (430),
VAR (24), event minute. Pre-match: B1 Elo (`elo_delta`), market no-vig probs.

## Unavailable event-level data (→ unavailable flags, not imputed)
Shots, shots-on-target, xG, corners, free-kicks/set-pieces, starting XI / on-pitch player IDs,
formations. (API-Football events on this plan carry none; lineups not bulk-cached.)

## Train / validation / test strategy
- **Leave-groups-out CV** across the 12 groups (no match in both train and test). Primary.
- Time-bucket, match-state, and event-triggered breakdowns (Phase 2).
- **Match-level paired bootstrap** for significance — never row-level (rows within a match are
  highly correlated).
- **2022 alone is NOT sufficient for production generalization**: one tournament, 48 matches, sparse
  features. This is a foundation + honesty exercise, not a deployable model.

## Model families (research-only; no neural nets — data far too small)
M0 static B1 (no live info control) · M1 time+score logistic · M2 remaining-time Poisson · M3
event-history hazard (next goal ≤5 min) · M4 competing-risk (home/away/no next goal) · M5 calibrated
ensemble (cross-fitted; calibrator never fit on test fold).

## Hard leakage controls
At decision minute t, features use only events with minute ≤ t (enforced by `state_from_events` +
tests). Targets may use future events (they are labels). No final score/stats/xG/possession/later
odds/later lineups in features. Match-level splits. Calibration train-fold-only / cross-fitted.

## Promotion rules
None. A model is only a "research leader" if it beats **M1 (time+score)** robustly (match-level
bootstrap CI excluding 0) across leave-groups-out folds. Even then it stays research-only and is NOT
runtime-eligible without a multi-tournament dataset + separate human-approved promotion.

## Known limitations
Single tournament; no shots/xG/lineups; 48 matches → underpowered for next-event horizons; class
imbalance for red-card targets (only 2 reds in 48 group matches).

## Ordered work queue
P1 canonical state dataset + tests → P2 eval protocol + split audit → P3 baselines M0–M5 →
P4 evaluation/calibration/failure analysis → P5 data-gap backlog + requests → P6 completion + commit + tag.
