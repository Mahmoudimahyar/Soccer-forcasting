# API-Football Data Gap Update (Phase 5)
research_only. Updates the project gap picture with REAL observed API-Football coverage.

## CLOSED / closeable via API-Football (bounded backfill)
- Player IDs + lineups + benches + positions + formation: CLOSED (100% on 120 pilot matches; verified).
- Substitutions (on/off + minute + player): CLOSED (1,085 in pilot).
- Timestamped event timelines (goals/cards/subs/VAR): CLOSED (every finished match).
- Yellow cards: CLOSED (abundant). Final-score reconciliation: 90% exact (clean).
- Player/substitution + next-goal + in-play W/D/L THRESHOLDS (500/500): NOT met by pilot but REACHABLE with
  a larger bounded backfill (2,180 finished matches available).

## STILL OPEN
- Red / second-yellow >=150 examples: pilot has 15/120 (~0.125/match) -> needs ~1,200 matches (add major
  leagues where reds are more frequent). Reachable but the largest backfill.
- xG: PARTIAL (newer tournaments only; WC2022 had none) -> not reliable historically on this source.
- Shot locations (xy): UNAVAILABLE on API-Football (team-level shot counts only) -> hard provider gap.
- Injuries / referee depth / event corrections-over-time: not characterized (separate endpoints / repeated snapshots).
- Rights for model-training-on-derived / redistribution / commercial: unknown_requires_vendor_confirmation (external).

## Net
API-Football converts the player/sub/card/next-goal/in-play gaps from "no data" to "reachable with bounded
backfill on an already-paid source" — EXCEPT xG/shot-location, which still require a richer provider. The
red-card volume target is the largest remaining data lift.
