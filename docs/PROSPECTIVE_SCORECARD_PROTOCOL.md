# Prospective Scorecard Protocol (Phase 4)

Deterministic scoring of the frozen prematch shadow models against finalized 2026 results. Reads ONLY
immutable ledgers + finalized results. Tool: `scripts/prospective_market_scorecard.py`; tests:
`tests/test_prospective_market_scorecard.py` (sanitized fixtures only).

## Inputs
- Immutable ledger (e.g. the live collector's `live_2026_shadow_predictions.csv`) — never modified.
- Finalized results: `{match_id: {status, final_wld, ...}}`; only `status == FINISHED` is scored.

## Method (deterministic)
1. **One primary snapshot per match:** T-15 preferred → T-90 → baseline → else **unscorable**.
2. **One independent unit per match.**
3. **Models compared (canonical IDs):** `prematch.b1_elo`, `prematch.market_novig`,
   `prematch.elo_market_blend_{75_25,50_50,25_75}` — resolved from legacy labels via the Phase-0 alias
   registry (immutable rows never rewritten).
4. **Metrics:** RPS, three-way log loss, draw Brier, calibration / ECE, match-level paired bootstrap,
   coverage report, snapshot-quality, provenance completeness, missing-window report.

## Evidence tiers (gate)
- **Tier A** (<10 finalized eligible): informational only.
- **Tier B** (10–19): descriptive only, **no model-selection claims**.
- **Tier C** (≥20): exploratory comparative analysis, **still no runtime promotion**.

## Hard rules (stated by the tool)
No model selection · no recalibration · no blend-weight change · no paper-trading · no live-trading ·
no market-edge claim. The frozen models and B1 runtime are untouched; this is observation only.

## Current status
The live clean prospective pool has **0 finalized eligible matches** so far → Tier A / empty. Do NOT run
against the live ledger for claims until it has naturally finalized matches; sanitized fixtures cover the
logic deterministically meanwhile.
