# Provider Gap Recommendation (Phase 6)
research_only.

## Closeable on API-Football (already paid; bounded backfill)
player/substitution, yellow-card, next-goal (regulation), in-play regulation W/D/L — clean, reconciled,
causal datasets. Scale backfill to thresholds; red/2Y needs club volume.

## NOT closeable on API-Football
- xG / shot-locations / shot-quality: hard provider gap (no per-shot xy; partial xG). -> richer provider
  (Opta/StatsBomb) or a historical xG add-on is the only route for that model class.
- Per-event publication time / measured live latency: needed for any future live-shadow use (engineering + a
  feed that timestamps publication). Out of scope here.

## Recommendation
Do NOT buy a new provider for player/sub/card/next-goal/in-play W/D/L work. Reconsider a richer provider ONLY
if xG/shot-quality becomes a priority. Confirm API-Sports retention/model-training/redistribution rights in
writing before any productization (currently unknown_requires_vendor_confirmation).
