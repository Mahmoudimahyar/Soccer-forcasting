# Evidence-Power Consolidation v1 -- Completion Report

`research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible`

Built 2026-06-28T02:32:45.855055+00:00. Local-artifact-only consolidation: registry -> lineage -> 58-match audit -> reproducibility -> bug-detect/repair -> power -> live-readiness -> decision memo -> consistency -> integrity. No network/API/Odds/StatsBomb/scrape; the active collector (`dc73318`) is read-only.

## The WHY-58 funnel (match-level, independent unit = match)

- exact-international bridge population: **258**
- dropped `missing_statsbomb_events`: **200** (no StatsBomb event JSON on disk -- a preregistered DATA-AVAILABILITY boundary, not a defect)
- residual / event-process evaluable: **58**
- forward-chain test set: **46** (earliest competition `FIFA World Cup 2018` train-only)
- LOCO test set: **58**

## Independent reproduction (cold recompute, no package import)

- forward-chain pooled R0 RPS: recomputed **0.15263** vs reported **0.15263** -> match=**True**
- LOCO pooled R0 RPS: recomputed **0.14906** vs reported **0.14906** -> match=**True**

## Verdict on 58

The 58-match cohort is **preregistered_valid_data_availability_boundary**: the intersection of the 258 exact-international bridge matches with the StatsBomb event JSONs physically on disk. It is a data boundary, not a bug. The honest-negative residual conclusion (no in-play correction beats the W2 reference out-of-sample) is calibrated and match-level-bootstrapped on the 58 it had.

## Bug detection / repair

- verified defects: **0**; no_repair_required=**True**
- affected-eval rerun: []

## Statistical power (match-clustered)

- unit of independence: **match (snapshots of a match are one cluster)**
- power@58 by target absolute-RPS improvement: {'0.0005': 0.102, '0.0010': 0.1355, '0.0020': 0.1955, '0.0030': 0.2845, '0.0050': 0.49, '0.0100': 0.8985}
- more snapshots on the same 58 matches does NOT raise power (clustering ceiling).

## Live readiness

- families classified: **21**; classes {'potentially_live_with_verified_provider': 6, 'blocked_by_missing_provider_contract': 5, 'blocked_by_latency': 3, 'blocked_by_no_point_in_time_history': 6, 'historical_research_ready': 1}; live-eligible today **0** (no source carries an event-publication timestamp).

## Cross-artifact consistency

- checks: **5**, inconsistent: **0**, all_consistent=**True**.

## Evidence registry

- rows: **10**; claim_status {'verified_historical': 6, 'verified_current': 2, 'contradicted': 1, 'incomplete': 1}.

## Integrity audit

- violations: **none**; integrity_ok=**True**
- collector commit `dc73318` unchanged=**True**; raw not git-tracked; no canonical root resolves into the collector; no forbidden network/provider import.

All artifacts are labelled `research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible`.