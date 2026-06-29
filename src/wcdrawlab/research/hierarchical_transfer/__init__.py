"""Hierarchical cross-domain transfer MODELS (Phase 4-6) — the T0..T7 ladder + intl-only eval.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This package fits and evaluates the hierarchical partial-pooling transfer ladder on the leakage-safe,
domain-normalized transfer DATASET produced by ``research.transfer.domain_normalized_dataset`` (Phase 3).
Nothing here is runtime-approved, trade-eligible, or live-eligible. The frozen runtime M2 is never
touched; the REFERENCE for every comparison is the parameter-free remaining-time Poisson
``research.transfer.w2_reference_t0`` (never a weaker anchor).

The ladder (canonical ids re-exported from ``research.transfer``):
  * T0  w2_reference_t0                  — remaining-time Poisson REFERENCE (parameter-free, no fit)
  * T1  international_only_t1            — intl-only residual model on the stable-feature subset
  * T2  naive_club_pool_t2              — naive pooled intl+club, NO domain correction (DIAGNOSTIC ONLY,
                                          never promoted; exposes the cost of ignoring domain shift)
  * T3  shared_stable_features_t3        — shared coeff on the stable subset, domain-normalized targets
  * T4  partial_pooling_t4              — hierarchical: shared coeff + intl-specific deviations,
                                          shrinkage chosen in-train
  * T5  domain_weighted_t5             — partial-pooling with club rows weighted by training-estimated
                                          domain overlap + feature stability
  * T6  selective_transfer_t6           — selective: falls back to T1 (then T0) when coverage / overlap /
                                          support / quality inadequate (alpha=0 fallback)
  * T7  calibrated_transfer_simulation_t7 — T6 remaining-goal intensity -> H/D/A via Monte-Carlo
                                          simulation + in-train monotone calibration

HONESTY invariants (re-asserted by eval + tests):
  * the international population is the ONLY primary test population; club rows are auxiliary TRAINING
    only and NEVER appear as a primary international test row;
  * every model is fit on TRAINING folds only; held-out international tournaments are scored, never fit;
  * candidate vs T0 ONLY (never a weaker anchor);
  * no completed-2026-World-Cup match in any domain / fold;
  * match-level paired bootstrap (unit = match);
  * domain-shifted / source-incompatible features are excluded from the transfer model space (the
    Phase-3 stable-feature subset is the only feature space the residual models read);
  * honest ``data_insufficient`` (with reason) wherever a quantity is not derivable — no fabrication.
"""
from __future__ import annotations

# Re-export the canonical transfer ids so callers import them from one place.
from wcdrawlab.research.transfer import (  # noqa: F401
    T0_REFERENCE,
    T1_INTERNATIONAL_ONLY,
    T2_NAIVE_CLUB_POOL,
    T3_SHARED_STABLE_FEATURES,
    T4_PARTIAL_POOLING,
    T5_DOMAIN_WEIGHTED,
    T6_SELECTIVE_TRANSFER,
    T7_CALIBRATED_SIMULATION,
    TRANSFER_MODELS,
    REFERENCE_MODEL,
    DOMAIN_INTERNATIONAL,
    DOMAIN_CLUB,
    DOMAINS,
    ELIGIBILITY_LABELS,
)

PACKAGE_VERSION = "hierarchical_transfer_models_v1"

# Short ladder ids (the "T#" labels used in eval tables / reports).
LADDER = ("T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7")

# Map short id -> canonical research.transfer.* id.
LADDER_TO_CANONICAL = {
    "T0": T0_REFERENCE,
    "T1": T1_INTERNATIONAL_ONLY,
    "T2": T2_NAIVE_CLUB_POOL,
    "T3": T3_SHARED_STABLE_FEATURES,
    "T4": T4_PARTIAL_POOLING,
    "T5": T5_DOMAIN_WEIGHTED,
    "T6": T6_SELECTIVE_TRANSFER,
    "T7": T7_CALIBRATED_SIMULATION,
}

# T2 is a DIAGNOSTIC anchor only — it must never be promoted to a shadow candidate.
DIAGNOSTIC_ONLY = ("T2",)

# The only model that may ever become a research candidate is the SELECTIVE one expressed as W/D/L
# (T7), judged against the T0 reference. (T6 is the intensity model; T7 is its calibrated W/D/L view.)
PRIMARY_CANDIDATE = "T7"

__all__ = [
    "PACKAGE_VERSION", "LADDER", "LADDER_TO_CANONICAL", "DIAGNOSTIC_ONLY", "PRIMARY_CANDIDATE",
    "T0_REFERENCE", "T1_INTERNATIONAL_ONLY", "T2_NAIVE_CLUB_POOL", "T3_SHARED_STABLE_FEATURES",
    "T4_PARTIAL_POOLING", "T5_DOMAIN_WEIGHTED", "T6_SELECTIVE_TRANSFER", "T7_CALIBRATED_SIMULATION",
    "TRANSFER_MODELS", "REFERENCE_MODEL", "DOMAIN_INTERNATIONAL", "DOMAIN_CLUB", "DOMAINS",
    "ELIGIBILITY_LABELS",
]
