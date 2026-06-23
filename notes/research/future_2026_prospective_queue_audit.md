# Future-2026 Prospective Queue Audit (Phase 4, 2026-06-23)

Queue: `data/reference/future_2026_prospective_queue.csv` (built from authoritative API-Football
fixtures, read-only). Operative model `m2_frozen@v2`. Ledger: `data/processed/prospective/ledger.jsonl`.

## Composition (72 WC2026 fixtures returned)
- **eligible (clean prospective pool): 28** — NOT-STARTED matches with a resolvable Elo anchor.
- skipped: 44 — completed (`FT`, 43) or in-progress (`1H`, 1) → **excluded from the clean pool** with
  reason `completed_not_clean_prospective` / `in_progress_or_other_status`.
- blocked: 0 (after aliasing "Bosnia & Herzegovina"→Bosnia, "Cape Verde Islands"→Cape Verde).

Each eligible row carries: match_id, teams, kickoff_utc, stage (group/knockout), round, **precomputed
elo_delta_home + Elo anchor probs** (so pre-match capture needs no live call), scheduled windows
(T-90;T-15;m0..m85), source dependencies, frozen model version, ledger path, scoring_status=pending.

## Dry-run verification (no writes, no fetch)
- **No request before its window:** at real `now` (2026-06-23T03:04Z) all 28 matches' windows are
  `pending` → planned=0, captured=0. The earliest kickoff is 2026-06-23T17:00Z.
- **Window fires correctly:** at `--now 2026-06-23T15:35Z`, exactly the Portugal–Uzbekistan **T-90**
  pre-match window is `due` → planned=1 (phase `pre_match`), produced deterministically with no API call.
- **No future result read:** pre-match prediction uses only the pre-stored Elo anchor; dry-run performs
  no fetch; in-play windows require `--execute` + a verified live source.
- **No completed match in the clean pool:** all 43 `FT` + 1 `1H` are `skipped` with explicit reasons.
- **Missed windows marked explicitly:** windows past `[target+grace]` are logged
  `MISSED_UNRECOVERABLE` (no silent backfill).
- **Deterministic paths:** ledger + session paths are fixed; `ledger_key = "{match_id}:{window}"`.

## Notes
- The eligible pool will grow as knockout fixtures are scheduled and their teams are determined (they
  currently don't exist as fixtures yet). Re-running the builder refreshes the queue idempotently.
- 2 group teams needed a name alias (handled locally; shared `ingest.canonical_team_name` untouched).
