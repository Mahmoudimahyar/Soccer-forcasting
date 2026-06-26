# API-Football — Acceptance Result (Phase 2)

research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. Applies the provider acceptance
protocol to OBSERVED Phase-1 samples (no invented vendor confirmation). Machine-readable (gitignored):
`data/processed/api_football_acceptance_result.json`.

## Classification: **accepted_for_limited_historical_research**

### Coverage — PASS (capacity)
- International finished matches sampled: **224** (WC22 59 + Euro24 46 + Copa24 27 + AFCON23 46 + AsianCup23 46).
- Total finished matches available (intl + club leagues): **2,180** -> ample capacity for the adopted
  >=500 lineup/sub and >=500 timestamped thresholds.
- lineups / substitutions / player IDs / cards / events / positions / formation: **available_verified**.
- **red / second-yellow COUNT vs the >=150 threshold: unverified until the Phase-3 backfill** (rare per fixture).

### Quality — PASS (observed)
final-score reconciliation, event ordering (time.elapsed), own-goal + card semantics, lineup/sub consistency
all observed-good. Duplicate rate + correction behavior require the backfill / repeated snapshots.

### Causal readiness — adequate for HISTORICAL
Retrieval timestamps (adapter provenance) + per-event elapsed minute + FT-vs-live status are present.
**No per-event PUBLICATION timestamp** -> any future LIVE-shadow use needs a MEASURED safety lag (not done here).

### Rights — partially local only
Plan = Pro, 7,500/day (from /status). Research use of self-pulled data under the paid subscription is in
scope. **Model-training-on-derived / redistribution / commercial-future-use remain
unknown_requires_vendor_confirmation** (API-Sports ToS not adjudicated here).

## Documented limits
xG partial (newer tournaments only); shot-locations unavailable (team-level stats only); red/2Y counts
pending backfill; redistribution/commercial/training rights unconfirmed in writing.

## Meaning
API-Football Pro is **accepted for limited historical research** on player/substitution/card/next-goal using
self-pulled data — sufficient to build the Phase-3 pilot corpus and compute real readiness counts. It is NOT
accepted for xG/shot-quality research (data gap) and NOT for any live/trading path (out of scope + frozen).
