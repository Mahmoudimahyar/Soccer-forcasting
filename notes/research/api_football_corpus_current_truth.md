# API-Football Corpus — Current Truth (Phase 0, 2026-06-26)

## Inherited from paid-source-activation-v1 (prior sprint)
- API-Football Pro verified: 7,500/day; lineups+benches+player-IDs+positions+events+timestamps
  available_verified; xG partial (newer tournaments only); shot-locations UNAVAILABLE (team-level only).
- 120-match international pilot pulled: 100% lineup/player-ID, dup 0.0005, **90% score-exact reconciliation**
  (12 mismatches flagged "ET/shootout/VAR boundary" — NOT yet classified). Raw lives (gitignored) in the
  paid-source worktree: C:/Users/Mahyar/worldcup-paid-source-activation/data/raw/api_football_historical.
- Acceptance: accepted_for_limited_historical_research. Odds API historical pilot was diagnostic (this sprint
  does NOT use the Odds API at all).

## This sprint
1. FIX reconciliation FIRST (Phase 1): classify each mismatch; build a provider-aware canonical result repr
   that SEPARATES regulation / extra-time / penalty-shootout; never count shootout/ET as regulation/next-goal.
2. Predeclare a balanced corpus (Cohort A internationals incl WC2018/Euro2020 not in the pilot + Cohort B five
   major leagues 2023-24) BEFORE retrieval; selection independent of results.
3. Bounded resumable backfill (events+lineups only) under research_budget = min(4200, remaining - reserve).
4. Build 11 causal, provenance-preserving research datasets (regulation/ET/shootout separated; no future leak).
5. Measure REAL readiness vs 500/500/150 thresholds; write next-model plan; audit + tag.

## Hard boundaries
API-Football only (no Odds API). Key via read-only loader; never printed. Raw append-only + gitignored.
Nothing trains/promotes models or touches the collector / frozen M1-M5 / M2 / B1 / trading / Kalshi.
