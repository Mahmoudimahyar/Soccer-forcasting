# Licensed Event Provider — Acceptance Protocol

research_only / not_runtime_approved / not_trade_eligible / not_live_eligible. A provider must PASS every
gating category below (on a sample export + written terms) before the project stores or trains on its data.
Runner: `scripts/run_provider_acceptance_tests.py`. Result schema: `schemas/provider_acceptance_result_v1.yaml`.
**Fail-closed**: any unknown right or unknown timing semantic FAILS until confirmed in writing.

## Gating categories
1. **Rights** (all must be confirmed in writing): local retention; historical research use; model training on
   DERIVED features; derived-label (aggregate) publication; raw redistribution prohibited/conditional;
   historical export. Unknown -> fail (conditional_pending_vendor_confirmation).
2. **Coverage** (adopted thresholds): >=500 complete lineup/substitution matches; >=500 timestamped-event
   matches; >=150 direct-red OR second-yellow examples; known competition IDs; sufficient historical seasons.
3. **Schema**: unique match IDs; unique/stable player IDs; per-event timestamps; event-correction support;
   substitution + lineup (incl. bench) semantics; card semantics (Y/2Y/red distinct); shot + shot-location +
   xG semantics; position/formation fields.
4. **Causal availability**: source publication time + provider update time present; published latency;
   historical vs live clearly distinguished; NO retrospectively-corrected event ever relabeled as live.
5. **Quality**: score reconciliation; event ordering; duplicate rate; missingness; correction rate;
   cross-source reconciliation feasible.
6. **Operational**: rate limits; historical backfill practicality; append-only raw storage; resumability;
   quota budgeting; documented retry behavior.

## Decision
- `accept_for_storage_and_research` only if ALL six categories pass.
- `conditional_pending_vendor_confirmation` if the only failures are unknowns the vendor can confirm.
- `reject` if a category fails on a confirmed negative (e.g., no model-training right, or coverage below threshold).

## Demonstrated
The runner has been exercised end-to-end on the MOCK provider (no real vendor), correctly returning
`conditional_pending_vendor_confirmation` with the unconfirmed rights/operational fields listed as
blocking_unknowns — proving the gate is fail-closed before any real data is ever ingested.
