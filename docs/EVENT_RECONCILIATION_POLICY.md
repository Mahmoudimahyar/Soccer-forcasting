# Event Reconciliation Policy

The system will eventually consume multiple data sources. It must **never silently merge conflicting
events**. This policy is implemented by `wcdrawlab.ingestion.reconcile.reconcile_events` and covered by
`tests/test_event_reconciliation.py` (deterministic, sanitized fixtures only — no real API calls).

## Source priority (highest first)
1. Official competition / federation event feed (`official_feed`, `fifa_official`)
2. Licensed structured provider (`api_football`, `the_odds_api`)
3. Secondary structured provider (`football_data_org`, `secondary_provider`)
4. Approved public official announcement (`approved_announcement`)
5. Open historical dataset (`open_dataset`, `martj42`, `jfjelstul`)

Unknown sources get the lowest priority (9) and can never override a known source.

## Matching across providers
For events reported by multiple providers:
1. **Preserve every raw version** — the canonical record keeps all contributing raw rows
   (`raw_versions`) and never discards a source.
2. **Match by provider ids where possible** — an exact `provider_event_id` match joins rows (e.g. a
   provider re-fetch) regardless of small minute drift.
3. **Otherwise match by** `match_id` + `event_type` + `team_id` + `player_id` + **event-time within
   tolerance** (default ±1 match-minute). Beyond tolerance ⇒ treated as **separate** events.
4. **Retain discrepancies** — minute spreads and any attribute differences are recorded in
   `provider_disagreement`.

## Verdicts (`reconciliation_status`)
- **reconciled** — ≥2 sources agree on identity attributes ⇒ canonical taken from the highest-priority
  source; `source_confidence = high`.
- **single_source** — only one source reports it (uncorroborated, *not* a conflict) ⇒
  `source_confidence = medium` if from priority ≤2 else `low`. Allowed but flagged.
- **unresolved** — sources **disagree** on an identity attribute ⇒ `source_confidence = low`.
- **superseded** — a later corrected record replaces an earlier one (append-only; the old row is kept
  and marked superseded, never deleted).

## Critical events (must be reconciled before approved use)
`goal, penalty, yellow_card, second_yellow, red_card, substitution, match_minute, match_status,
kickoff, final_whistle`.

A **critical** event that is **unresolved** has `approved_feature_eligible = False` and **must not
feed approved in-play features**. The in-play model degrades confidence or abstains rather than
guessing. Non-critical streams (shots, corners, free kicks, team stats) are never hard-blocked:
the highest-priority source wins and disagreement lowers confidence.

## Identity attributes that trigger `unresolved` on disagreement
| event_type | identity attributes checked |
|---|---|
| goal | `player_id`, `goal_type` |
| penalty | `taker_player_id`, `outcome`, `phase` |
| yellow_card / second_yellow | `player_id` |
| red_card | `player_id`, `red_type` |
| substitution | `player_off_id`, `player_on_id` |
| kickoff / final_whistle | the respective timestamp |
| match_status | `status` |
| match_minute | (timing handled via tolerance, not equality) |

## Confidence & disagreement recording
Every canonical event carries `canonical_source`, `contributing_sources`, `source_confidence`, and a
`provider_disagreement` map. Downstream features may use `source_confidence` to weight or gate inputs.

## What this policy does not do
No ingestion runs, no network calls, no scraping. It is a pure-function contract + test suite so that
when real multi-source feeds are approved, conflicts are surfaced and quarantined — never silently
merged into the approved model's inputs.
