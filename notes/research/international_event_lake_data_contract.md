# International Event Lake — Data Contract (v1)

Persistent, content-addressed, fail-closed store for **official StatsBomb Open Data** senior men's
international event JSON. Built for the WC forecasting lab's preregistered model families. research_only.

## Scope

- **Source (external retrieval):** OFFICIAL StatsBomb Open Data ONLY
  (`raw.githubusercontent.com/statsbomb/open-data/master/data/events/<sb_match_id>.json`).
  No API-Football / Odds / paid / scrape / mirror / browser / 360 / video.
- **Cohort:** senior MEN'S INTERNATIONAL only — FIFA World Cup, UEFA Euro, Copa America,
  African Cup of Nations (from the official catalog). Historical cutoff strictly **before the 2026
  World Cup**; no completed-2026-WC match in any cohort / fit / calibration / selection.
- **Bridge:** strict **EXACT** international rows only
  (`api_statsbomb_match_bridge_v1.csv`, `bridge_confidence == exact`, `comp_type == international`).
  No fuzzy / forced bridge. Ambiguous ids never enter evaluation.
- **Bootstrap unit:** independent unit = **MATCH** (not snapshot).

## Lake location (external to every git worktree)

```
C:/Users/Mahyar/worldcup_data_lake/statsbomb_open/international_event_lake_v1/
  objects/<aa>/<sha256>.json   # content-addressed raw event JSON (immutable, sharded by sha[:2])
  indexes/                     # international_event_lake_index_v1.{json,jsonl}
  manifests/                   # international_event_lake_manifest_v1.jsonl (append-only, immutable)
  quarantine/                  # rejected / corrupt / ambiguous payloads (never indexed)
  integrity/                   # sentinel_report.json
  logs/                        # init / restore / audit / retention run logs
```

Raw event JSON lives **only** in the lake (gitignored/external). Nothing resolves into the active
collector checkout `worldcup_draw_model_lab_FINAL` (fail-closed in `Lake.resolve`).

## Index / manifest record

`sb_match_id -> { local_path, sha256, event_count, xg_available, possession_available,
location_available, source_url, retrieval_ts, validation_status, source_schema_version }`
plus provenance (`bridge_id`, `competition_label`, `kickoff_date`, `norm_home/away`,
`ingestion_mode` ∈ {copied_local, downloaded_official}, `ingestion_run_id`, `copied_from`).

Schema: `schemas/international_event_lake_manifest_v1.yaml`.

## Write protocol (atomic, first-write-wins, immutable)

`tmp -> JSON-validate -> sha256 -> atomic rename -> immutable manifest append`. An existing
content-addressed object is **never** overwritten; identical bytes are idempotent. Object filename
== sha256 of its bytes. External downloads: ≤4 concurrent, exp backoff, ≤2 retries, source-url +
retrieval-ts recorded.

## Restore (no re-download)

`restore_international_event_lake.py` COPIES locally-valid + hash-verified StatsBomb event files
from the read-only source roots (`statsbomb_raw`, `statsbomb_raw_prior` — the ~60 surviving files)
into the lake. It NEVER re-downloads a file that is already locally valid. Invalid / ambiguous /
non-exact-bridge payloads go to `quarantine/`, never the index.

**Real-data restore result:** 60 local event files → 58 stored (exact-bridge-gated; ids
`3939978`, `3939980` were not in the exact international bridge). Idempotent on re-run
(0 copied, 58 already present).

## Fail-closed sentinel (`audit_international_event_lake.py`)

Verifies EVERY indexed object and FAILS CLOSED (exit ≠ 0) on ANY of:

| condition | reason code |
|---|---|
| manifest says present but object absent | `manifest_present_but_object_absent` |
| on-disk bytes ≠ recorded sha256 | `hash_mismatch` |
| object filename ≠ sha256 of bytes | `filename_hash_disagreement` |
| zero-byte object | `empty_file` |
| HTML / provider-error body | `html_or_error_body` |
| not parseable JSON | `invalid_json` |
| not a non-empty event list | `not_event_list` |
| id not in exactly one exact bridge row | `not_in_exact_bridge` |
| duplicate id in index | `ambiguous_match_id_duplicate_index_key` |
| object outside registered objects/ tree | `object_under_unregistered_root` |
| object on disk at non-canonical path / not indexed | `object_under_unregistered_root` / `orphan_object_not_in_index` |

The sentinel **never deletes** a valid object and **never git-cleans** the lake.

## Retention (`verify_international_event_lake_retention.py`)

Asserts (read-only): every manifest-recorded object still exists with its recorded sha; every index
entry has a manifest record and an on-disk object; the lake root is external to all worktrees. No
valid object is ever dropped.

## Self-test (`tests/test_international_event_lake.py`)

15 tests, all passing: sentinel PASSES on valid objects and FAILS CLOSED on each synthetic
corruption (hash mismatch, empty, HTML, invalid JSON, non-event-list, absent, unregistered-root,
not-in-bridge); store is idempotent; quarantine never enters the index. Runs against an isolated
temporary lake.

## Operational sequence

```
python scripts/init_international_event_lake.py              # validate structure + manifest skeleton
python scripts/restore_international_event_lake.py           # COPY valid local files in (no re-download)
python scripts/audit_international_event_lake.py             # fail-closed sentinel (exit 0 = all_ok)
python scripts/verify_international_event_lake_retention.py  # retention guarantees
```
