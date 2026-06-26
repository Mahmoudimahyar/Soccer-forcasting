# Provider Acceptance Test Plan (Phase 4)
research_only. Maps each acceptance category to a concrete, deterministic check run by
`scripts/run_provider_acceptance_tests.py` against a vendor's SAMPLE export + written terms (no live calls).

| category | how tested | pass condition |
|---|---|---|
| rights | parse vendor's written answers into licensed_provider_rights_v1 | retention+research+training+derived-pub = yes/conditional; raw redistribution prohibited/conditional |
| coverage | counts from sample/answers vs quality_gate thresholds | >=500 lineup-sub, >=500 timestamped, >=150 red/2y |
| schema | inspect normalized sample events | unique match+player IDs, timestamps, correction support, sub/card/shot/xG/position fields |
| causal | availability.causal_eligibility on declared timing | eligibility != unknown_fail_closed; live requires publication time |
| quality | reconcile_score + dedupe + completeness on sample | reconciles; dup_rate<=0.5; completeness>=0.6 |
| operational | parse declared ops terms | rate limit / backfill / append-only / resumable / quota / retry all declared |

## Procedure when access is granted
1. Vendor returns the questionnaire (data_requests/pending/structured_event_vendor_questionnaire.*) + a 20-match
   historical sample + 5 event timelines + corrections + timing metadata.
2. Drop the sample behind a NEW real adapter (subclass of ProviderAdapter) — gitignored raw; source hashes preserved.
3. Run run_provider_acceptance_tests.py -> provider_acceptance_result_v1.
4. Only on `accept_for_storage_and_research` does storage/training begin; otherwise resolve blocking_unknowns
   with the vendor first.
