# Structured Event Data Procurement & Integration Readiness V1 — Completion

research_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true ·
KALSHI_ENABLE_LIVE_TRADING=false · TRADING_MODE=paper

Worktree `C:/Users/Mahyar/worldcup-structured-event-readiness`, branch `structured-event-procurement-readiness-v1`.

## Active-collector isolation result (verified)
Collector untouched: main checkout `worldcup_draw_model_lab_FINAL`, `v1-5-prospective-operations` @ **dc73318**,
tracked-clean, task **Ready**, heartbeat advancing (…05:33Z), flags `false/paper`. `git diff dc73318..HEAD`
= **39 Added, 0 Modified** — no pre-existing collector file changed. 13 tests pass. No purchase/trial/form/
scrape/credential/provider-API/Odds/API-Football call. No real provider client activated. No raw commercial
data and no secret tracked (the only env-var-name mentions are pre-existing baseline docs/placeholders).
licensed-event modules are non-importable by runtime/trading/Kalshi (enforced by test).

## Current project data gaps (why this sprint exists)
Player IDs, lineups/benches, substitutions, positions, distinct card classes, timestamped events, shots/
shot-locations/xG, and live publication timestamps for men's-senior-international + WC coverage. The commentary
path cannot fill these (see below). A licensed STRUCTURED provider is required.

## Provider catalogue result (official sources only)
Five paths evaluated — `data/reference/structured_event_provider_catalog.{json,csv}` + due-diligence report.
- **Verified publicly**: stable player IDs (all 5); World Cup coverage (all 5; Opta holds FIFA-official WC2026
  rights); published pricing for **Sportmonks** (EUR29/99/249 + add-ons) and **API-Football** (Free / Pro $19 /
  higher); Opta/StatsBomb/Sportradar are **quote-only**; xG/shot-location strongest for Opta + StatsBomb.
- **Requires vendor confirmation** (marked `unknown_requires_vendor_confirmation`, counts Opta 18 / StatsBomb 15
  / Sportmonks 12 / API-Football 14 / Sportradar 10): historical men's-international event DEPTH at the adopted
  thresholds; model-training / retention / aggregate-publication / redistribution RIGHTS; live publication-time
  semantics + latency. **Rights + depth — not coverage — are the binding gate.**

## Generic adapter readiness
`src/wcdrawlab/research/licensed_events/` — 6 provider-neutral schemas + contracts/interface/normalization/
reconciliation/availability/quality_gate/mock_provider/registry + 12 synthetic fixtures + **13 deterministic
tests** (capability gating, fail-closed causal eligibility, no-invented-IDs, source-hash traceability,
correction idempotency, own-goal/shootout score reconciliation, cross-provider reconciliation, runtime/trading
import isolation). Adapters fail closed on unknown timing and never invent player IDs.

## Acceptance-test readiness
`docs/LICENSED_EVENT_PROVIDER_ACCEPTANCE_PROTOCOL.md` + `schemas/provider_acceptance_result_v1.yaml` +
`scripts/run_provider_acceptance_tests.py` (fail-closed; demoed on the mock provider ->
`conditional_pending_vendor_confirmation`). Gates: rights / coverage / schema / causal / quality / operational.

## Procurement packet readiness
`structured_event_vendor_outreach_packet.md` + `structured_event_vendor_email_templates.md` +
`data_requests/pending/structured_event_vendor_questionnaire.{yaml,md}` +
`structured_event_acceptance_criteria.yaml`. NOTHING sent; no credentials; no trials.

## Exact external action the user must take next
1) Choose ONE provider (budget + priority: cheap player/sub/card/next-goal via API-Football/Sportmonks, vs
premium xG/shot-quality via Opta/StatsBomb; Opta if FIFA-official WC2026 live is required). 2) Send the
outreach packet + questionnaire. 3) Get written rights confirmation. 4) Get a 20-match + 5-timeline sample.
5) Approve budget / sign / subscribe and place the key in `.env` out of band. (Details:
`structured_event_external_actions.md`.)

## What begins immediately after access is granted
Day-one plan (`structured_event_day_one_integration_plan.md`): new real adapter (subclass of ProviderAdapter)
-> gitignored append-only raw + source manifest -> normalize to `licensed_event_record_v1` -> reconcile +
quality gate -> `run_provider_acceptance_tests.py` -> on `accept_for_storage_and_research`, build leakage-safe
historical player/lineup/sub/card/timestamped-event research datasets. Enables **player/substitution, next-goal,
card/red-card, and WC in-play** model classes; xG/shot-quality depends on the chosen provider's depth.

## Why commentary is no longer the primary path
The commentary precision V2 gate approved **0 high-precision silver classes**; SoccerNet v2 labels have no
player IDs / no own-goal / no VAR; the English pipeline fails on original-language ASR. Commentary remains a
flagged LOW-CONFIDENCE historical signal only — it cannot supply player/sub/next-goal/card structured data.

## Why live trading remains disabled
Out of scope and unchanged: `KALSHI_ENABLE_LIVE_TRADING=false`, `TRADING_MODE=paper`. This sprint is research
prep only; licensed-event modules are walled off from runtime/trading/Kalshi/risk by test. Any future live use
additionally requires a provider with verified publication timestamps passing the causal gate.
