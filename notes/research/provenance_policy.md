# Data Provenance & Storage Policy (Tier-1)

Defines the per-record provenance envelope, raw-storage rules, source-priority, and
multi-provider disagreement handling required by the scientific rules (Section C).

## 1. Provenance envelope (required on every raw record)
Every ingested raw record (match, odds snapshot, event, valuation, ranking) must carry:

| field | meaning |
|---|---|
| `source_name` | provider id, e.g. `the_odds_api`, `football_data_org`, `martj42`, `jfjelstul`, `dato_futbol_fifa`, `transfermarkt_dcaribou` |
| `source_url_or_endpoint` | exact URL / API endpoint fetched |
| `retrieved_at_utc` | wall-clock UTC of retrieval |
| `published_or_event_time_utc` | provider's event/publish time (kickoff, snapshot_time, release_date) |
| `match_id` | canonical match id (where applicable) |
| `provider_event_id` | provider's own id (game_id, event id) where available |
| `raw_payload_hash` | sha256 of the raw bytes/JSON for reproducibility |
| `schema_version` | normalizer schema version |
| `quality_status` | `ok` / `partial` / `suspect` / `conflict` |

Raw API/JSON pulls are stored verbatim under `data/raw/<source>/...` before normalization, so any
prediction can be reproduced from the exact bytes. CSV open datasets store the source URL + a
content hash in `data/processed/source_provenance.json`.

## 2. Source-priority policy (when providers cover the same fact)
Results / standings / schedule (2026): `football_data_org` (authoritative, live) >
`martj42` (broad, ~2-day lag) > seed snapshot. Group/matchday labels (2026): `football_data_org`
(validated 12/12 vs reconstruction). Group labels (1998–2022): `jfjelstul`. Odds: per-book
no-vig consensus (median across books); `pinnacle` retained separately as the sharp reference.
Ratings: internal Elo (from martj42) is primary; FIFA ranking is a secondary cross-check only.

## 3. Multi-provider disagreement handling
- Preserve ALL raw versions (never overwrite a conflicting value in place).
- Emit a `disagreement_flag` + record both values + `quality_status=conflict`.
- Resolve the *used* value by the source-priority policy above; keep the alternative for audit.
- **Do not emit a high-confidence live forecast (and never a paper/live trade) when critical event
  feeds disagree** — degrade confidence or abstain. (Enforced in the in-play layer, Tier 4.)

## 4. Leakage rules tied to provenance (already enforced by tests)
- Pre-match: every feature's `published_or_event_time_utc <= kickoff_utc`.
- In-play: `published_or_event_time_utc <= decision_timestamp`.
- Odds used pre-match must have `snapshot_time <= kickoff_utc`; closing odds captured after kickoff
  are forbidden for pre-match.
- Ratings must be `elo_before(strict < kickoff)`; never updated with the match being predicted.

## 5. Current coverage vs the envelope (honest status)
- `source_provenance.json` records source_name/url/retrieved_at/hash/coverage for all sources used.
- Per-RECORD hashes are attached for new structured pulls going forward (odds, football-data,
  FIFA, TM). Historical CSV datasets (martj42/jfjelstul) are versioned at the FILE level (URL +
  content hash) rather than per-row — recorded as a known limitation to tighten in Tier 4/5 when
  the live event pipeline is built.
