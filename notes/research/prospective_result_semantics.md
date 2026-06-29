# Prospective Result Semantics & 1X2 Outcome Policy

**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

## Result-source hierarchy (read-only; no Odds API)
1. Refreshed **football-data.org** WC competition endpoint (`/v4/competitions/WC/matches`) — the same
   official-grade source the collector already trusts for FINISHED scoring. Authoritative for the 2026 WC.
2. **API-Football Pro** final fixture result via the existing safe adapter — used only if football-data
   lacks a verified final for a fixture in the locked universe (fallback; bounded; key never printed).
3. (Optional, available) API-Football Pro **cross-check** of football-data finals — not invoked by
   default to avoid unnecessary paid calls; football-data WC finals are treated as `official_single_source`.

**The Odds API is never called for results.** No market data is used to determine an outcome.

## Verified-final requirement
A fixture is scored only when `reconciliation_status == verified_final`: provider status `FINISHED`
(or `AET`/`PEN` for knockouts) **and** both final goals present and numeric. Anything else is classified
(`awaiting_final`, `fixture_cancelled`, `fixture_postponed`, `unresolved_identity`, `provider_conflict`)
and excluded — never scored on a non-final result.

## 1X2 outcome definition
Outcome is expressed in **team_a orientation** (predictions store `p_team_a_win`,`p_draw`,`p_team_b_win`):
- Resolve the fixture's `team_a`/`team_b` from the immutable `forecast_targets_2026.csv` via canonical
  team-name pair match to the provider's home/away teams.
- `A` if team_a final goals > team_b; `D` if equal; `B` otherwise.

### Group-stage / league-style fixtures (the entire current locked universe)
- Outcome = **regulation/final score** (`fullTime`). No extra time, no shootout. A level score is a draw.

### Knockout fixtures (encoded for completeness; none in the current universe)
- Use the score definition declared by the frozen forecast contract. The frozen M1–M5 contract here is a
  **regulation/final-score 1X2** target, so a knockout decided in extra time uses the post-ET score, and a
  shootout does **not** silently convert a regulation draw into a win/loss for the 1X2 target.
- Extra-time goals and shootout results are recorded in separate fields, never folded into the 1X2 target.

## Canonical result record fields
canonical_fixture_id · provider_fixture_id · normalized_home_team · normalized_away_team · kickoff_utc ·
competition · matchday · final_status · home_regulation_goals · away_regulation_goals · extra_time_home ·
extra_time_away · shootout_home · shootout_away · final_1x2_outcome_home_orientation ·
final_1x2_outcome_team_a_orientation · team_a · team_b · source_provider · source_retrieval_timestamp ·
source_payload_hash · reconciliation_status · cross_check_status · discrepancy_reason.
