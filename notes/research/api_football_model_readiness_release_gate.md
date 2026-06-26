# API-Football Model Readiness Release Gate (Phase 5)
research_only. A class is READY only if actual observed counts meet its threshold. No model trained.

| model class | threshold | actual (900-fixture corpus) | READY? |
|---|---|---|---|
| A. Player / substitution | 500 complete lineup/sub matches | **900** (627 intl + 273 club) | **YES** |
| B. Next-goal (regulation) | 500 clean timestamped event matches | **900** (100% reconciled) | **YES** |
| C. Card / 2nd-yellow / direct-red | 150 relevant positive events | **123 sendings-off** (75 intl + 48 club) | **NO (close; reachable)** |
| D. In-play W/D/L (regulation) | 500 clean regulation event matches | **900** (100% exact reconcile) | **YES** |
| E. xG / shot-quality | per-shot xG + locations | **unavailable** (provider gap) | **NO (blocked)** |

## Notes
- A/B/D READY on the CURRENT corpus (international alone already gives 627 >= 500). All causal + reconciled.
- C (red/2Y) is at 123/150 sendings-off — NOT ready, but reachable: 1,200 included fixtures remain (mostly
  club, where reds are more frequent); a single resume run closes the gap. Yellow cards are abundant (3,419)
  if the target is yellows.
- E (xG) is BLOCKED at the provider level — not a backfill-volume problem.
- Do NOT mark A/B/D as model-validated: these are DATA-readiness counts, not trained/evaluated results.
