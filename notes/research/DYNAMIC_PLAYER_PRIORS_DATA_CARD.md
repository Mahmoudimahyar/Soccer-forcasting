# Dynamic Temporal Player Priors — Data Card (Component 2 / Phase 2)

`research_only` · `experimental` · `not_runtime_approved` · `not_trade_eligible` · `not_live_eligible`

Model id family served: `research.wdl.player_starting_xi_p1`, `research.wdl.player_on_pitch_p2`,
`research.wdl.player_substitution_delta_p3`, `research.wdl.player_composition_p4`,
`research.wdl.player_team_state_p5`, `research.next_goal.{player_on_pitch_n2,substitution_delta_n3}`,
`research.wdl.{xg_player_state_x2,xg_calibrated_hybrid_x3}`.

Version: `dynamic_player_prior_v1` (`DPP.DYNAMIC_PRIOR_MODEL_VERSION`).
Parser: `player_history_parser_v1` (inherited; minutes / on-pitch goal-diff / WDL semantics unchanged).

## What this is
A leakage-safe **temporal** player-prior feature system. For every international snapshot it converts the
API-Football events+lineups corpus into four feature categories that a downstream transparent regularized
model can consume. Every player feature for a snapshot at time `T` uses **only** appearances dated strictly
before `T` (`appearance_date < T`). EXACT integer `player_id` linkage only — no fuzzy name matching, no
guessed national identity.

## Source data (all resolved through the canonical registry; raw stays gitignored)
- `api_football_player_history` (canonical, this worktree): club events/lineups that thicken per-player
  PRIOR history.
- `api_football_player_history_prior` (read-only prior pull): additional club history + fixture metadata.
- `api_football_corpus` / inherited corpus worktree: the reconciled international fixtures (the TEST
  population) + their events/lineups.
- The active collector checkout `worldcup_draw_model_lab_FINAL` is **never** read (registry fails closed).

Appearance corpus actually built (real numbers, this run):
- **62,357** leakage-safe appearances total = **13,931 international** + **48,426 club**.
- Club appearances feed per-player priors ONLY; they are NEVER test rows. The test population is
  international fixtures.

## Feature categories
**(A) Exposure / recency** — `player_exposure_priors.csv` (29,186 rows). prior appearances / starts /
minutes, `minutes_last5/10`, `apps_last5/10`, `starts_last5/10`, days-since-last, national/club/intl
appearance counters, per-position start share, `lineup_uncertainty`, `unknown_player` flag, dominant
position.

**(B) Regularized contribution priors** — `player_contribution_priors.csv` (29,186 rows; 16,521 known).
Per-90 team-adjusted goal-diff (`gd_contribution_per90`), offensive (`off`), defensive concession (`def`),
WDL contribution, availability prior (recent start propensity), exposure, uncertainty. **Nested shrinkage**:
`player_raw → player_team → position → competition → global`, each tier blended by its real sample weight
against a fixed pseudo-count (`SHRINK_MINUTES=270`, `SHRINK_APPEARANCES=3`, `SHRINK_TEAM=6`,
`SHRINK_POSITION=12`, `SHRINK_COMPETITION=24`). A player with no strictly-earlier appearance returns the
nested shrinkage mean only and is flagged `unknown_player` with 0 prior appearances.
*Honesty note:* `discipline_per90` is emitted as a constant 0.0 — `Appearance` carries no per-player card
linkage, so a real per-player discipline rate cannot be computed from this corpus without re-reading events.
It is left as an explicit absent signal rather than a fabricated rate (the discipline `c2` family will source
this elsewhere).

**(C) Current team composition** — `team_composition_features.csv` (6,270 rows = 627 matches × 2 teams ×
5 decision minutes). On-pitch evolves with substitutions `minute ≤ t` (no future-sub leak). weighted/mean
on-pitch & XI prior gd90, top3/bottom3, attack/mid/def group balance, bench strength, `familiarity_continuity`
(vs prior XI), `national_continuity` (vs prior NATIONAL XI), `coverage_aggregate`, `n_unknown_players`,
`low_coverage_flag`.

**(D) Substitution delta** — `substitution_delta_features.csv` (4,687 rows). incoming-minus-outgoing prior
(gd/off/def/wdl), `position_consistent`, `gd_delta_context_adjusted` (fixed-form score/minute/fatigue
scaling, no fitting), `uncertainty_delta`, `low_history_flag`, `tactical_imbalance_flag`.

## Leakage guarantees (proven, not asserted)
`scripts/audit_dynamic_player_priors.py` — **19/19 checks pass, self_test=pass**:
- *No future-appearance leakage*: a prior at `T` ignores an appearance dated exactly `T` and any later
  appearance; advancing `T` past a later appearance demonstrably moves the prior. The same strictly-before
  priors drive the substitution-delta features.
- *Correct shrinkage*: an unknown player returns exactly the nested shrinkage mean (finite, flagged,
  0 appearances); a thin-history extreme value lies strictly between its raw value and the shrinkage target;
  more same-signed exposure moves the prior toward the raw value, raises exposure, and lowers uncertainty.
- *Real-output audit*: every unknown row has 0 prior appearances, every known row ≥1; exposure/uncertainty
  in [0,1]; all contributions finite; manifest coverage matches an independent recount.

## Modeling constraints honored
Transparent regularized form only (fixed-pseudo-count shrinkage means). No neural nets / transformers / LLM,
no unrestricted hyper-parameter search, no test-time fitting. All aggregation is deterministic. Primary
population = senior men's international fixtures; club rows are auxiliary prior history only. No completed
2026 World Cup result is used (the corpus international fixtures here predate / exclude the locked 2026
tournament; this build does not read any 2026 result for fitting/selection/calibration).

## Reproduce
```
python scripts/build_dynamic_temporal_player_priors.py     # builds the 4 tables + manifest
python scripts/audit_dynamic_player_priors.py              # 19/19 leakage + shrinkage + real-output checks
```
Outputs: `data/processed/dynamic_player_priors/*.csv` (gitignored derived) +
`notes/research/dynamic_player_priors_manifest.json` (tracked, counts only).
