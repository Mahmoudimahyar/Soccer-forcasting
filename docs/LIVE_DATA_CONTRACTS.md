# Live Data Contracts

Prose companion to `schemas/live_data_contracts.yaml`. Defines the append-only raw provenance
envelope and the normalized schemas A–Q, plus the leakage rules that make every future feed
point-in-time reproducible. **No live feed flows from these yet** — this is the contract that any
ingestion must satisfy before it can touch features. Reconciliation rules live in
`docs/EVENT_RECONCILIATION_POLICY.md`.

## 1. Append-only raw provenance envelope
Every raw record (one per provider response or per extracted event) carries these fields. Raw rows
are **immutable and append-only** — corrections are new rows, never edits.

| field | required | meaning |
|---|---|---|
| `source_name` | ✓ | canonical source id (e.g. `the_odds_api`, `football_data_org`) |
| `provider_endpoint` | ✓ | logical endpoint path |
| `retrieval_timestamp_utc` | ✓ | when *we* fetched it |
| `event_timestamp_utc` | – | real-world event clock time, if supplied |
| `published_timestamp_utc` | – | when the source published/observed it, if supplied |
| `match_id` | ✓ | our canonical match id (schema A) |
| `provider_match_id` | – | provider's native fixture id |
| `provider_event_id` | – | provider's native event id |
| `source_url_or_endpoint` | ✓ | full endpoint/URL |
| `raw_payload_hash` | ✓ | sha256 of the exact raw bytes |
| `schema_version` | ✓ | contract version |
| `ingestion_run_id` | ✓ | uuid grouping one ingestion run |
| `quality_status` | ✓ | `ok` / `partial` / `suspect` / `conflict` |
| `reconciliation_status` | ✓ | `single_source` / `reconciled` / `unresolved` / `superseded` |

Normalized rows always retain `raw_payload_hash`, linking back to the immutable raw snapshot.

## 2. The decision-time rule (leakage guard)
For a prediction made at `decision_timestamp_utc`, a record is eligible **only if**

```
effective_known_time <= decision_timestamp_utc
effective_known_time = coalesce(published_timestamp_utc, event_timestamp_utc, retrieval_timestamp_utc)
```

Post-match aggregates (final score, full-match xG/stats) may **never** inform a prediction about the
same match. Pre-match feeds (lineups, odds, weather forecasts, availability) are eligible only after
their *publication/observation* time, not their real-world effect time.

## 3. Usability classes
Each schema is tagged `pre_match`, `in_play`, `post_match`, or `never`:
- **pre_match** — usable before kickoff once published (A identity, B lineups, N pre-match odds, P weather forecast, Q availability).
- **in_play** — usable during the match at/after the event's known time (C–L, M in-play, O in-play odds).
- **post_match** — full-match aggregates; usable only for *other* matches' history, never the same match (final goals, full-match stats/xG).
- **never** — not modeled (none currently; reserved for unsourced rumor).

## 4. Normalized schemas A–Q (summary)
| key | domain | primary key | usability | critical? (reconciled) |
|---|---|---|---|---|
| A | fixtures / match identity | `match_id` | pre_match (goals post_match) | identity yes |
| B | starting lineups & benches | `match_id, team_id, player_id, role` | pre_match (after release) | no |
| C | substitutions | `match_id, team_id, off, on, minute` | in_play | **yes** |
| D | goals | `match_id, team_id, minute, sequence` | in_play | **yes** |
| E | yellow cards | `match_id, player_id, minute, sequence` | in_play | **yes** |
| F | second yellows | `match_id, player_id, minute` | in_play | **yes** |
| G | red cards | `match_id, player_id, minute` | in_play | **yes** |
| H | penalties | `match_id, team_id, minute, sequence` | in_play | **yes** |
| I | shots / shots on target | `match_id, team_id, minute, sequence` | in_play (totals post_match) | no |
| J | corners | `match_id, team_id, minute, sequence` | in_play | no |
| K | free kicks / set pieces | `match_id, team_id, minute, sequence` | in_play | no |
| L | match status / minute | `match_id, observed_at_utc` | in_play | **yes** (kickoff/final/status) |
| M | team statistics | `match_id, team_id, observed_at_utc` | in_play (full-match post_match) | no |
| N | pre-match odds snapshots | `match_id, bookmaker, market, snapshot_utc` | pre_match (snapshot ≤ kickoff) | no |
| O | in-play odds snapshots | `match_id, bookmaker, market, snapshot_utc` | in_play | no |
| P | weather / venue conditions | `match_id, time, source_name` | pre_match (forecast issued ≤ decision) | no |
| Q | availability / injuries / suspensions | `match_id, player_id, status_published_utc` | pre_match (after announcement) | reconciled vs official |

"Critical" rows are the events whose disagreement across sources blocks approved in-play features
(`reconciliation_status=unresolved`); see the reconciliation policy.

## 5. Source priority (per schema, abbreviated)
Official competition/federation feed → licensed structured provider (e.g. API-Football once keyed)
→ secondary structured provider (e.g. football-data.org) → approved public announcement → open
historical dataset. Each schema's `source_priority` lists the concrete ordering. Odds come from The
Odds API (N/O); results/standings from football-data.org (A/D/L) until a licensed event feed exists;
weather from Open-Meteo (P).

## 6. Missingness and conflict (principles)
- **Absent ≠ zero.** A missing shot/corner/availability is `unknown`, never silently 0.
- **Critical events** (C–H, L) that disagree across sources are kept raw, marked `unresolved`, and
  **excluded** from approved in-play features until reconciled.
- **Non-critical streams** (I/J/K/M) take the highest-priority source; large disagreement lowers
  confidence rather than hard-blocking.
- **Odds** (N/O): every bookmaker's snapshot is retained; no-vig consensus is computed downstream.

## 7. What this does NOT do
No ingestion runs, no scraping, no provider expansion, no model change. The contracts exist so that
when a feed is approved, ingestion is immutable, provenance-complete, leakage-safe, and reconcilable
by construction. Current approved-model (B1/Elo) inputs are unchanged.
