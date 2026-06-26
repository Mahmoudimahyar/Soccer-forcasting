# API-Football Corpus Sampling Protocol (Phase 2) — committed BEFORE event/lineup retrieval
research_only. Selection is purely fixture-metadata based (cohort + date order + league rotation); NEVER uses
results/events/cards/goals/players. Manifest: data/reference/api_football_corpus_fixture_manifest.{csv,json}.

## Budget (observed from /status)
remaining_daily = 7,229; reserve = max(1500, ceil(0.25*remaining)) = 1,808; research_budget =
min(4200, remaining - reserve) = 4,200; fixture_budget = research_budget // 2 (events+lineups) = 2,100.

## Cohorts
- COHORT A (international priority, ALL completed): FIFA WC 2018 + 2022, UEFA Euro 2020 + 2024, Copa America
  2024, AFCON 2023, AFC Asian Cup 2023. -> 627 completed fixtures (incl. associated qualifier fixtures the
  league IDs return).
- COHORT B (major-league volume, 2023-24, rotation EPL->LaLiga->SerieA->Bundesliga->Ligue1): 1,756 completed.

## Truncation rule (predeclared)
Include ALL Cohort A; then Cohort B by **league-rotation + date order** until fixture_budget is reached.
Result: included = 2,100 (627 A + 1,473 B); excluded_truncated = 283 (tail of Cohort B). No event/result data
used for inclusion. Backfill (Phase 3) is resumable + bounded by research_budget; partial coverage is allowed.

## Per-fixture manifest fields
canonical_match_id, provider_fixture_id, competition(label), cohort, comp_type(international/club), region,
league, season, kickoff_utc, status, eligibility(included/excluded_truncated), inclusion_rule,
expected_endpoints(events,lineups), raw_status, reconciliation_status.
