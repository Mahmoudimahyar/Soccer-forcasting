# Player-History Sampling Protocol (Phase 1) — predeclared BEFORE event retrieval
research_only. Selection is metadata-only; NO results/goals/cards/players/teams/event-volume used.

## Cohort
Completed club seasons 2020-21..2023-24, leagues EPL/LaLiga/SerieA/Bundesliga/Ligue1. Target 100 fixtures per
league-season (5 leagues x 4 seasons = 20 strata) -> **2,000 selected** with equal representation (400/league).

## Deterministic stratified selection
Within each league-season, fixtures sorted by sha256("player_impact_v1_fixed_seed:<fixture_id>") and the first
100 taken -> reproducible, content-independent. Manifest: data/reference/player_history_corpus_manifest.{csv,json}.

## Budget (observed)
remaining 4,977; reserve max(1500,0.25*rem)=1,500; research_budget min(4200,rem-reserve)=3,477;
fixture_target min(2000, floor((3477-50)/2))=**1,713** (JOB3 backfills up to this within budget; resumable).
API-Football only; events+lineups only; NO statistics; NO Odds API; >=1s/request; <=2 retries; append-only gitignored raw.
