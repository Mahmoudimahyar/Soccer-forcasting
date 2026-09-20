# International Event Lake Restoration v1 — Completion Report

_research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible_

- Completed (UTC): 2026-06-28T08:04:31.720085+00:00
- Lake root: `C:\Users\Mahyar\worldcup_data_lake\statsbomb_open\international_event_lake_v1`
- Lake objects (raw-backed + hash-verified): **258**
- Final integrity sentinel all_ok: **True** (checked=258, failures=0)
- Retention verifier ok: **True**
- Isolation ok: **True** (in_collector=False, roots_in_collector=[], lake_external=True, raw_git_tracked=False, lake_git_tracked=False)
- Active collector commit (read-only): `dc73318` (expected `dc73318`)
- pytest gate: passed=601 failed=0 skipped=33 (rc=0)

## Cohort
- Cohort matches: **258**
- Excluded ids: 27
- Total regulation-only causal snapshots: 32359
- Sub-cohort counts: {'official_selected': 258, 'exact_bridged_reconciled': 207, 'xg_eligible': 231, 'event_process_eligible': 231, 'residual_eligible': 231, 'wdl': 231, 'near_term': 231, 'discipline': 231, 'power': 231}
- No-2026-World-Cup guarantee: True
- Leakage self-test (real rows): True

## Statistical power (match-level, clustered)
- Observed M (eligible matches): 231
- Independent unit is the MATCH; adding snapshots to the same matches does not buy power.

## Model decision (preregistered families only; locked rule)
- Verdict: **data_insufficient**
- Reference: `None`
- Reuses ONLY remaining-time Poisson reference + time-score + xG-state + event-process + residual/selective-correction. No new features / search / neural / market.

## Provenance & source quality (raw-backed from the lake index)
- Ingestion modes: {'copied_local': 58, 'retrieved_official': 200}
- Objects with xG / possession / location: 258 / 258 / 258
- Official-source-only: True (host raw.githubusercontent.com/statsbomb/open-data)

## Guarantees
- Raw event JSON lives ONLY in the external content-addressed lake (0 git-tracked in this worktree).
- External retrieval = OFFICIAL StatsBomb Open Data ONLY. No API-Football / Odds / paid / scrape / mirror / browser / 360 / video / credentials.
- Strict EXACT international bridge only; ambiguous never enters evaluation; no completed-2026-WC match in any cohort/fit/calibration/selection.
- Never modifies the active collector (worldcup_draw_model_lab_FINAL / WorldCupShadowCollector), B1, frozen M1-M5, candidate.py, approved_models.yaml, trading/Kalshi/risk, .env.
