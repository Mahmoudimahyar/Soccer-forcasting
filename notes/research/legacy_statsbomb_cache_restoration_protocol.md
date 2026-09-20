# Legacy StatsBomb Cache Restoration Protocol

run_id: `legacy_restoration_20260628T071033Z`  built_ts: 2026-06-28T07:10:35Z

## Purpose
Restore the durable event lake for the legacy exact international bridge (258 rows) without
re-downloading any file that already exists locally as valid + hash-verified. External retrieval is
**official StatsBomb Open Data only** (`raw.githubusercontent.com/statsbomb/open-data`).

## Decision rule (per bridge row)
1. **copy_verified_local** — already in the lake (hash-verified) OR a valid local event file exists
   under a prior cache root. Copy bytes into the lake atomically (tmp -> validate -> sha256 ->
   atomic rename -> immutable manifest append). Never re-download.
2. **retrieve_official** — no valid local file. Fetch `events/<sb_match_id>.json` from the official
   open-data path (<=4 concurrent, <=2 retries, exponential backoff, atomic, sha256).
3. **quarantine_invalid** — a local file exists but fails validation (empty / HTML / invalid JSON /
   non-event-list). Quarantine it and treat the match as retrieve_official.
4. **blocked_official** — reserved for the case where the official source cannot serve the match
   (permanent 404). Such rows never enter evaluation.
5. **excluded_with_reason** — the row lacks a canonical/StatsBomb id and cannot be bridged. It never
   enters any cohort, fit, calibration, or selection.

## Integrity (fail-closed)
Every written object is content-addressed and re-verifiable. The sentinel fails closed on
manifest-present-but-absent, hash mismatch, empty file, HTML/error body, invalid JSON,
non-event-list, ambiguous id, filename/hash disagreement, or an object under an unregistered root.

## Current state
- legacy bridge rows: **258**
- objects already in lake (hash-verified): **258**
- decisions: {"copy_verified_local": 258}

## Cohort discipline
Senior men's international only; historical cutoff before the 2026 World Cup; no completed-2026-WC
match in any cohort/fit/calibration/selection. Match-level bootstrap only (independent unit = MATCH).
Ambiguous rows never enter evaluation.
