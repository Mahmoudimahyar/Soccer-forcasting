# Prospective Review Gate (Phase 4, 2026-06-23)

The review gate that governs when (and how weakly) the live shadow results may be interpreted.

## What exists
- A deterministic scorecard (`scripts/prospective_market_scorecard.py`) that scores the frozen prematch
  models (`prematch.b1_elo`, `prematch.market_novig`, `prematch.elo_market_blend_*`) on one primary
  snapshot per finalized match (T-15 > T-90 > baseline), with RPS / log-loss / draw-Brier / ECE /
  match-level bootstrap, and a Tier A/B/C gate. Canonical model IDs come from the Phase-0 registry;
  immutable ledger rows are never modified.
- Sanitized-fixture tests (4) covering snapshot selection, canonical IDs, perfect-prediction RPS=0, and
  the tier boundaries.

## Current gate status
- **Clean prospective pool finalized eligible matches: 0** (the 28 queued group matches had not finished
  at sprint time; the 41 already-finished 2026 matches are exploratory/seen, not clean prospective).
- Therefore: **Tier A (informational only)**. No comparative claim, no model selection, no promotion.

## Gate rules (do not violate until reached)
- Tier A (<10): informational only.
- Tier B (10–19): descriptive only — **no model-selection claims**.
- Tier C (≥20): exploratory comparative analysis — **still no runtime promotion, no trading, no edge claim**.
- The frozen M1–M5 (prematch) definitions/weights, B1 runtime, and trading flags remain unchanged
  regardless of tier.

## What happens automatically
As the live collector finalizes group matches, re-running the scorecard moves the count toward Tier B/C.
The first genuine out-of-sample read (B1 Elo vs market no-vig vs blends) becomes available at Tier C —
as exploratory evidence only.
