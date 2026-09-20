# 2022 Replay Full-Tournament Release Gate (Phase 1 / 7B, 2026-06-23)

Reconciles every AVAILABLE 2022 World Cup match from the cached API-Football event feed (read-only from
the active checkout). Tool: `scripts/replay_2022_full_quality.py`; semantics:
`src/wcdrawlab/research/replay_semantics.py`; output: `data/processed/replay_2022_full_tournament_quality.csv`.

## Result
| status | matches | meaning |
|---|---|---|
| ok (reconciles exact) | **48** | regulation+ET score matches the reported final exactly |
| exception (score mismatch) | **0** | none |
| not_cached | **16** | knockout matches whose event files are not in the local cache |
| **total fixtures** | **64** | |

- **All 48 cached matches reconcile exactly** on regulation+ET score (own-goal beneficiary honored, VAR
  cancellations excluded, penalty shootout kept separate).
- 18 of the 48 are flagged **non-chronological (informational only)** — the provider groups events by
  type, so the raw list isn't minute-monotonic; the score still reconciles exactly. This does NOT fail
  the gate (see `replay_2022_event_semantics_exceptions.md`).

## Release rule (satisfied)
- Every **available** match reconciles exactly ✓.
- Every **unavailable** match/category is explicitly classified (16 knockouts = `not_cached`) and is
  excluded from any research target that requires knockout event data — never silently inferred ✓.

## To extend to the 16 knockouts
The knockout event files are not in the offline cache. Fetching them requires the API-Football Pro feed,
which is the **active collector's** provider — out of scope for this offline sprint (no new paid/live
calls). When fetched (read-only) into the cache, re-running the tool will reconcile them with the same
semantics (shootout handling already implemented + tested).

## Provenance + leakage
Each reconciled row carries `source_events_sha256`. Deterministic regression tests
(`tests/test_replay_2022_semantics.py`, 9 cases) cover own goals, standard/penalty goals, VAR-cancelled
goals, ET-vs-regulation separation, penalty shootouts, second-yellow + direct red, duplicate events
(dedup), out-of-order events, and no-future-event leakage.
