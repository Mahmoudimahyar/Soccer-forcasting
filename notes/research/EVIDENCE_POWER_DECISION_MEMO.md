# Evidence-Power Consolidation -- Next-Investment Decision Memo

`research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible`

Synthesized from local consolidated evidence only. No purchase recommendation, no market claim, no 2026 WC claim.

## Binding constraint

The residual in-play evaluation cohort is bounded by **data availability**, not modeling. Of 258 exact-international bridge matches, **200** drop with reason `missing_statsbomb_events` (no StatsBomb event JSON on disk), leaving **58** evaluable matches. This is a preregistered data boundary, not a defect.

## Power levers

| option | lever | raises power? |
|---|---|---|
| acquire full StatsBomb event pull | more independent international matches | **yes (primary)** |
| more snapshots per match | clustering ceiling | no (non-lever) |
| pursue live eligibility | separate live gate | n/a (latency/rights/schema) |

Match-level power at M=58 (by target absolute-RPS improvement): {'0.0005': 0.102, '0.0010': 0.1355, '0.0020': 0.1955, '0.0030': 0.2845, '0.0050': 0.49, '0.0100': 0.8985}

## What each option requires

- **acquire_full_statsbomb_event_pull** (more_independent_international_matches (primary power lever)): restores the cohort from 58 toward 258 exact-international matches (the 200 dropped for missing_statsbomb_events); a DATA-ACQUISITION step, not a modeling change _Evidence required:_ the StatsBomb open events for the 200 bridge-exact matches on disk
- **add_more_snapshots_per_match** (rejected_non_lever): does NOT raise power -- the independent unit is the match; the clustering ceiling demonstration shows power is invariant to snapshot inflation on the same 58 matches _Evidence required:_ none would help; recorded as a non-lever
- **pursue_live_eligibility** (separate_live_gate): blocked until a provider's real event-publication latency is measured and causally gated; offline match-clock replay is not live eligibility _Evidence required:_ measured per-event provider latency + data rights + schema parity