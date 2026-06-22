# 2022 Event-Replay Release Gate (2026-06-21)

Rebuilt with the corrected provider-aware semantics (`event_replay_2022_remediation.md`).
Per-match table: `data/processed/event_replay_2022_quality.csv`.

## Result: PASS — 48/48 group-stage matches reconcile EXACTLY
| metric | value |
|---|---|
| matches | 48 |
| exact final-score reconciliation | **48 / 48** |
| goals-by-team reconciliation | 48 / 48 |
| own-goal matches | 1 (fixture 855767 Canada 1-2 Morocco → now exact) |
| VAR-present matches | 21 (cancelled goals are `Var` events → correctly excluded) |
| missing-minute matches | 0 |
| degraded/unknown-semantics | 0 |

No "47/48 is close enough" — every match reconciles exactly; there are **no remaining discrepancies**
to classify or exclude.

## Classification of the previously-unresolved case
Fixture 855767 (Canada–Morocco): **OWN_GOAL provider-attribution convention**, now corrected. Was the
only discrepancy; resolved.

## Tier 4 / Tier 5 safety status
- Release gate **PASSES** → event replay is marked **RESEARCH-READY only**.
- **Not promoted to runtime.** No in-play (Tier 4) or next-event (Tier 5) model training is started.
- No event-derived probability may affect approved forecasts, paper decisions, or trading.
- B1 remains the sole approved runtime 1X2 model; V8 + market blend remain shadow-only.

## Governance / reproducibility
- `pytest -q`: all pass (incl. the 8 new event-semantics tests).
- No trading/risk/provider/credential/scraping/`.env`/`candidate.py`/approved-routing change.
- Raw event payloads immutable + gitignored; derived quality CSV retains per-match raw payload hashes.
- Tag (gate passed): **`event-replay-2022-validated`**.

## Explicit non-actions (per instruction)
No new shadow session, no historical odds backfill, no player modeling, no provider expansion, no
model training. Stop after this report.
