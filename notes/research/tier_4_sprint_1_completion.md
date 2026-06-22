# Tier 4 Research Sprint 1 — Completion Report

Event Replay → In-Play State Dataset → Baselines → Honest Evaluation. **Research-only.** B1/Elo
remains the sole approved pre-match runtime model; no in-play model influences forecasts, advancement,
paper decisions, risk, or Kalshi. `pytest -q` → **151 passed**. No protected files changed
(candidate.py, approved_models.yaml, trading/, provider adapters, .env all unchanged vs
`approved-b1-runtime`); raw payloads + large datasets gitignored.

## What was completed (Phases 0–5)
- **Canonical in-play state dataset** from the validated 2022 replay: builder + data card + 6 leakage
  tests. `data/processed/inplay_state_2022_group_stage.parquet`.
- **Leakage-safe eval protocol** (leave-one-group-out + match-level bootstrap + breakdowns) + split audit.
- **Baselines M0–M5** (`src/wcdrawlab/research/inplay_models/`) with full output envelope; 4 model tests.
- **Evaluation + calibration + failure analysis + data-limitations** reports + metrics CSVs.
- **Data-gap backlog** + new `tier4_event_xg_feed.yaml` request (no provider implemented/scraped).

## Could not be completed (honest)
- Next-goal/red-card horizon models are **not viable on 2022** (no xG/shots/lineups; red targets too
  sparse) — documented, not forced.
- No multi-tournament data → no generalizable model (out of scope for a 2022-only foundation).

## Exact data volume
858 decision rows · 48 matches · 8 groups (A–H, 97–118 rows each) · 54 columns. Decision points:
fixed {0,15,30,45,60,75,85} + event-triggered (goal/card/sub/VAR).

## Exact evaluation splits
Leave-one-group-out (8 folds; no match in train+test) · match-level paired bootstrap (2000×) ·
breakdowns by time bucket / score state / event type. Calibration cross-fitted (train-fold only).

## Model comparison (W/D/L, LOGO, lower=better)
| model | RPS | log loss | draw Brier |
|---|---|---|---|
| M0 static B1 (control) | 0.2432 | 1.112 | 0.147 |
| M1 time+score | 0.1748 | 0.864 | 0.142 |
| **M2 remaining-time Poisson** | **0.1552** | 0.819 | **0.123** |
| M5 ensemble (M1+M2) | 0.1614 | 0.819 | 0.126 |

Next-event: `goal_within_5` (M3) Brier 0.1148 vs base 0.1126 → **does not beat base rate**;
`next_goal_team` (M4) log loss 1.032 vs base 1.084 → **modestly beats base rate**.

## Uncertainty / calibration summary
Match-level bootstrap vs M1: M0 **significantly worse** ([+0.011,+0.121]); M2 better but **not
significant** ([−0.042,+0.004]); **M5 significantly better** ([−0.023,−0.004]). Models are
overconfident in volatile mid-game states (85/858 conf>0.7 wrong) and under-weight draws (mean
p(draw)=0.476 on actual draws); sharp late (RPS 0.072 ≥76').

## Research-only leader
**M2 (remaining-time Poisson)** on point estimates; **M5 (ensemble)** is the only model that beats
the honest time+score baseline (M1) with match-level significance. Both `research_only`,
`not_runtime_approved`.

## Does any model beat time-and-score (M1) robustly?
**M5 yes** (match-level CI excludes 0); **M2 no** (CI includes 0, underpowered). M0 is significantly
worse than M1 — static pre-match is not enough once a match is underway.

## Suitable for a future live shadow test?
**No.** One tournament, 48 matches, sparse features, wide CIs, failed next-goal hazard. A live shadow
test needs richer event features (xG/shots/lineups) and many more matches across competitions.

## Top 5 data gaps
1. Event-level xG/shots feed · 2. Confirmed lineups/benches/injuries · 3. Multi-competition historical
event volume · 4. Substitutions with player IDs/positions · 5. Player club minutes/fatigue.
(Full table: `tier_4_data_gap_backlog.md`.)

## Exact next recommended sprint
**Tier 4 Sprint 2 — Event-feature enrichment + multi-competition volume:** on approval, ingest
StatsBomb open historical events (free, xG/shots/lineups) across multiple tournaments into the state
schema, re-run M2–M5 + a richer next-goal hazard with cross-competition leave-one-tournament-out
evaluation. Only then consider whether any in-play model is shadow-test-worthy. Do not start until the
`tier4_event_xg_feed.yaml` source is approved.
