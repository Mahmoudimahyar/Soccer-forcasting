# Red-Threshold Extension Protocol (Phase 2) — predeclared BEFORE event/lineup retrieval
research_only. Purpose: determine whether sendings-off reach 150 with UNBIASED additional data (current 123).

## Selection (metadata-only; NO results/cards/goals/players used)
The next **220** fixtures by the existing committed corpus manifest order (included[900:1120]). The first 900
fixtures (all 627 international Cohort A + 273 club) are already pulled; international priority is therefore
preserved and the extension continues the deterministic Cohort-B league-rotation + date order.

## Constraints (enforced by JOB2)
- API-Football only (no Odds API); events + lineups only; NO statistics; NO players endpoint unless resolving a
  missing lineup identity.
- <= 500 API-Football requests; respects the active-collector reserve (controller-level api budget 600 cap).
- Stop on auth/entitlement/persistent-rate-limit; stop if collector heartbeat goes stale.
- Append-only, gitignored raw (data/raw/api_football_historical_corpus/); no duplicate writes (ext_progress.json).

## Use rule
Not used for model tuning until the full selected slice is collected AND reconciled (JOB3). Manifest:
data/reference/api_football_red_threshold_extension_manifest.csv.
