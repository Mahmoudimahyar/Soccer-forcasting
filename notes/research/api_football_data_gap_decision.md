# API-Football Data Gap Decision (Phase 5)
research_only.

## Closed on the current corpus (already-paid API-Football)
- Player/substitution, next-goal (regulation), in-play regulation W/D/L: data-ready (>=500 clean reconciled
  matches each), 100% regulation reconciliation, full lineup/player-ID/position/bench coverage, causal datasets.

## Still open
- Red/2nd-yellow sendings-off: 123/150 -> resume the backfill over the remaining 1,200 included fixtures
  (club-heavy) to clear 150. Bounded by daily budget; no new provider needed.
- xG / shot-locations: BLOCKED (provider gap) -> richer provider (Opta/StatsBomb) or xG add-on only.
- Rights (model-training-on-derived / redistribution / commercial): unknown_requires_vendor_confirmation.
- Live publication-time / latency: needed for any future live-shadow; out of scope.

## Decision
No new provider needed for player/sub/next-goal/in-play-WDL. Resume backfill to close the red-card gap. Only
reconsider a richer provider for xG/shot-quality. Confirm API-Sports rights before any productization.
