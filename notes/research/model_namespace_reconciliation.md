# Model Namespace Reconciliation (Offline Hardening Phase 0, 2026-06-23)

Generic `M1..M6` labels are ambiguous across contexts and unfit as durable audit IDs. This phase adds a
namespaced canonical registry + an append-only alias map, resolving legacy labels **without rewriting
any immutable historical prediction row**.

## The collision (now resolved)
`M2` meant two different models:
- **prematch `M2`** = market no-vig consensus → `prematch.market_novig`
- **inplay `M2`** = remaining-time Poisson → `inplay.remaining_time_poisson_m2`
Resolution requires the **namespace/context**; the alias registry is keyed on `(context, legacy_alias)`.

## Artifacts
- `schemas/model_identity_v1.yaml` — 12 canonical models with `model_namespace, model_family,
  canonical_model_id, canonical_model_version, legacy_model_alias, approval_status, research_status,
  runtime_eligible, trade_eligible`.
- `configs/model_alias_registry.yaml` — append-only `(context, legacy_alias) -> canonical_model_id` (22 entries).
- `src/wcdrawlab/research/model_identity.py` — `resolve()`, `model_info()`, `check_invariants()`,
  and `annotate()` (ADDS canonical columns; never overwrites legacy rows).
- `scripts/validate_model_identity.py` — fails closed on any violation.

## Invariants enforced (validator + tests green)
- **Exactly one** model is `runtime_eligible: true` → `prematch.b1_elo` (B1). All others false.
- **No** model is `trade_eligible` (paper-only).
- No `research_only` model is runtime-eligible.
- Every alias resolves to a defined canonical model; unknown alias/context raises.
- `M2` prematch ≠ `M2` inplay (explicitly tested).

## Immutability
Historical immutable rows (e.g. `outputs/research/live_2026_shadow_predictions.csv` in the live
checkout) are **not modified**. Tools resolve legacy labels at read time via `annotate()`, which returns
a COPY with canonical columns added — proven by `test_annotate_adds_canonical_without_mutating_rows`.
Scorecards should call `annotate(df, context)` to surface canonical IDs.

## Tests (`tests/test_model_identity.py`, 7 passed)
market-M2 ≠ inplay-M2 · invariants hold · no research model runtime/trade-eligible · every alias
resolves · unknown alias raises · annotate adds-not-mutates · in-play scorecard shows canonical IDs.
