# Paid Source Activation — Current Truth (Phase 0, 2026-06-26)

## Authorized paid sources (already paid; not procurement blockers this sprint)
- API-Football / API-Sports Pro (direct). Prior V1.5: 2026 WC fixtures/events/subs/cards/lineups returned 2xx.
  Read-only adapter exists: src/wcdrawlab/operations/api_football_adapter.py (rate-limited, key never logged).
- The Odds API. Owned LIVE by the active collector (budget guard OddsBudget, 15/500 used). This sprint uses
  ONLY bounded HISTORICAL endpoints (<=30 credits), never a second live loop.

## What prior sprints established (do not redo)
- Commentary path exhausted for structured events (no player IDs / 0 silver classes).
- Provider-neutral licensed-event contracts + acceptance protocol + adapter framework already built
  (structured-event-procurement-readiness-v1). This sprint feeds REAL API-Football samples through that gate.
- Missing for player/sub/next-goal/card models: real historical event/lineup data at thresholds
  (500 lineup-sub / 500 timestamped / 150 red-2y). API-Football is the configured candidate to test now.

## This sprint goal
Empirically measure API-Football coverage/quality, run the acceptance gate on REAL samples, build a bounded
append-only historical pilot, a capped diagnostic odds pilot, and compute ACTUAL model-readiness counts —
all research-only, collector untouched, budgets reserved.

## Hard boundaries
No purchase/account/NDA/trial/scrape/browser/bypass. Keys via read-only config only; never printed. Raw
responses append-only + gitignored. Nothing trains/tunes M1-M5 or touches B1/runtime/trading.
