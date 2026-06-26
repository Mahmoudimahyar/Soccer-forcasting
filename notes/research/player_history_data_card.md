# Player-History Feature System — Data Card (Phase 2)

`research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`

Causal rolling PLAYER-IMPACT feature system. Turns API-Football **events + lineups** into leakage-safe
**pre-match player priors**, **starting-XI / bench aggregates**, and **per-substitution deltas**.
Transparent models only (regularized means / shrinkage; **no neural nets**, no learned embeddings).

## Provenance & lineage
- **Source**: API-Football `/fixtures`, `/fixtures/events`, `/fixtures/lineups` (cached raw, **gitignored**).
  Raw lives in `data/raw/player_history_corpus` (this worktree) and the inherited
  `api_football_historical_corpus` (corpus worktree + this worktree). No raw external data is committed.
- **Cohort (predeclared)**: club seasons 2020–21..2023–24 (EPL/LaLiga/SerieA/Bundesliga/Ligue1), 100
  hash-stratified fixtures per league-season (2,000 selected; see `player_history_sampling_protocol.md`),
  plus the inherited international corpus (WC/Euro/Copa/AFCON/AsianCup). Selection is metadata-only.
- **Reuses (never re-implemented)**: `paid_source/result_semantics.py` (own-goal beneficiary, regulation =
  `elapsed<=90`, ET/shootout separation, reconciliation), `paid_source/historical_datasets.py`
  (`parse_lineup`, `substitutions`, `players_on_pitch`).
- **Versioning**: every derived row carries `prior_model_version = player_history_prior_v1` and the parser
  version `player_history_parser_v1`; every appearance carries a `source_hash` over its raw events+lineups.

## What an appearance is (within-match, fully causal)
For each fixture whose **regulation reconciles EXACTLY** (event-derived regulation == official `score.fulltime`)
we derive one `Appearance` per player who was on the pitch:
- `minutes_on` — causal on-pitch **regulation** minutes (starter from 0; sub from entry minute; clamped 0–90;
  goes off at the sub-off minute). Uses ONLY subs with `minute <= off`.
- `goals_for_on` / `goals_against_on` / `gd_on` — regulation team goals scored / conceded **while the player
  was on the pitch**, beneficiary-credited (own goals to the `team` field, per `result_semantics`). A player
  subbed off at 60' is never charged with an 80' goal.
- `team_result` — regulation W/D/L (ET and shootout excluded).
Unreconciled fixtures yield **no** appearances (attribution would be untrustworthy).

## Rolling priors (cross-match; the only place histories combine)
`prior(player_id, before_date, comp_type)` aggregates ONLY appearances with `match_date < before_date`
(**STRICT**; equal-date excluded) within the **same `comp_type`** (club and international never pooled):
- `gd_contribution_per90`, `off_contribution_per90`, `def_contribution_per90` — minute-weighted per-90 rates,
  **shrunk** toward date/comp-filtered global means with pseudo-exposure `SHRINK_MINUTES = 270`.
- `wdl_contribution` — W=1/D=0.5/L=0 share, shrunk with `SHRINK_APPEARANCES = 3` pseudo-appearances.
- `exposure = minutes/(minutes+270)` ∈ [0,1]; `uncertainty = 3/(apps+3)` ∈ (0,1].
- `position_state` — dominant START position (G/D/M/F), `sub`, or `unknown`.
- `unknown_player` / `insufficient_history` — explicit cold-start flags. Unknown players (no strictly-earlier
  appearance) receive the **shrinkage prior only** — never a future-derived value.

## Lineup aggregates (`player_history_state_v1`) — one row per team per match
`xi_mean_prior_gd90`, `xi_weighted_prior_gd90` (exposure-weighted), `xi_top3_prior_gd90` (star concentration),
`xi_off_balance_per90` / `xi_def_balance_per90`, `bench_strength_prior_gd90`, `history_completeness`
(= 1 − unknown share), `n_unknown_players`, `continuity_with_prior_xi` (fraction of today's XI that started
the team's **immediately-prior** XI — a past fixture, so legal pre-match), `mean_exposure`, `mean_uncertainty`.

## Substitution delta (`player_substitution_delta_v1`)
`incoming prior − outgoing prior` (per contract; direction never reversed) on gd/off/def/wdl/exposure, plus
`in_unknown` / `out_unknown`. Positive `gd_delta_per90` ⇒ the incoming player has the stronger prior.

## Causal guarantees (enforced in `tests/test_player_history.py`, all deterministic synthetic)
1. no future player-appearance leakage · 2. no future national-team-appearance leakage · 3. no post-match use
in a pre-match prior (incl. equal-date exclusion + on-pitch window) · 4. exact integer player.id linkage only
(no name fuzz; unknown is its own category) · 5. substitution-delta direction (and sign-flip on reverse) ·
6. unknown-player behavior · 7. position-specific aggregation · 8. deterministic rebuild (full dict equality,
incl. hashes) · 9. club/international separation · 10. source-hash traceability (recompute matches). Plus
regulation/ET separation and reconciliation gating. **17 tests pass.**

## Build & audit
- `python scripts/build_player_history_features.py` → gitignored derived tables under
  `data/processed/player_history/` (`player_priors.csv`, `lineup_aggregates.csv`, `substitution_deltas.csv`)
  + a tracked **counts-only** manifest `notes/research/player_history_feature_manifest.json`.
- `python scripts/audit_player_history_coverage.py` → `player_history_coverage_report.md` (coverage,
  reconciliation rate, cold-start curve, and a **leakage self-check** that found 0 violations).

## Known limitations
- Events/lineups currently exist for the **inherited** fixtures (273 club + 627 international reconciled-exact);
  the 2,000-fixture club player-history backfill is bounded/resumable and not yet pulled — coverage will grow.
- Cold-start share is high for the earliest matches of each cohort (≈22–27%) and falls as the rolling window
  fills; this is exposed via `history_completeness` / `unknown_player`, never hidden.
- `def_contribution` is a team-level on-pitch signal attributed to all on-pitch players, not a per-player
  defensive-action metric (no event-level defensive actions in this source).
- Provider `rating`/post-match xG are deliberately **NOT** used as priors (post-match aggregates).
