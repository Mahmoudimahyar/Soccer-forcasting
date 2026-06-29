# Prospective Score Harvest — Primary Snapshot Selection Preregistration (LOCKED)

**research_only=true · prospective_evaluation_only=true · not_runtime_approved=true · not_trade_eligible=true · not_live_eligible=true**

Locked 2026-06-29 **before any model-vs-outcome metric was computed.** The rule below depends only on
timestamps and model/market coverage — never on realized outcomes or scores.

## Why a selection rule is needed
The frozen ledger contains multiple correlated forecast rows per fixture (re-freezes at baseline / T-90 /
T-15 / final-pre-kickoff). Scoring every snapshot as independent evidence would double-count fixtures and
understate uncertainty. The primary analysis therefore uses **exactly one snapshot per fixture**.

## Compared model families (canonical identities)
- `prematch.b1_elo`  = `M1_B1` (approved B1 ternary-Elo, r=0.4) — Elo-only
- `prematch.market_novig` = `M2_market` (no-vig consensus) — **read-only market benchmark**
- `prematch.blend_75_25` = `M3_75_25`
- `prematch.blend_50_50` = `M4_50_50`
- `prematch.blend_25_75` = `M5_25_75`

## Primary selection rule (LOCKED)
For each fixture, the primary snapshot is the **latest common valid pre-kickoff snapshot available for all
five compared models and the no-vig market reference**, by this preference:
1. **T-15** if all five models + market are present and pre-kickoff;
2. else **T-90** if all five are present and pre-kickoff;
3. else **baseline** if all five are present and pre-kickoff;
4. else **exclude** the fixture from the primary comparison, with explicit reason `no_common_market_snapshot`.

Operationalization (deterministic): among the fixture's `source_snapshot_timestamp` values where all five
model rows exist, every probability vector is a valid simplex, the market columns are non-null, and
`prediction_timestamp < kickoff_utc`, choose the snapshot with the **latest `source_snapshot_timestamp`**
(closest to kickoff = most informative). The window preference T-15→T-90→baseline is monotone in time, so
"latest qualifying timestamp" realizes it. The chosen snapshot is identical across all five models for a
fixture (same snapshot window), guaranteeing a fair same-information comparison.

## Units & uncertainty
- Primary unit of analysis = **fixture** (one snapshot per fixture per model).
- Uncertainty = fixture-level paired deltas + match-level bootstrap. No row-level pseudo-replication.

## Secondary (descriptive only)
All valid snapshot windows may be reported descriptively, match-clustered, explicitly labeled descriptive.
Secondary results never drive model selection or promotion.

## Hard constraints
- No outcome-based snapshot selection. No selecting the best snapshot after the result is known.
- Market is a read-only comparator; it is never used to fit/calibrate/select any model.
- No 2026 outcome enters any model fit, calibration, or selection.
