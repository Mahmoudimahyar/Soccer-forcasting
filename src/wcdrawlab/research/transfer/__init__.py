"""Hierarchical cross-domain transfer research package.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This package hosts the canonical ``research.transfer.*`` model identifiers and the leakage-safe,
domain-normalized transfer DATASETS (Phase 3) that the hierarchical partial-pooling models (T0..T7)
consume. Nothing here is runtime-approved, trade-eligible, or live-eligible.

Canonical model identifiers (frozen names; the T0..T7 ladder):
  * research.transfer.w2_reference_t0              -- remaining-time Poisson REFERENCE (parameter-free)
  * research.transfer.international_only_t1         -- intl-only residual model (no club transfer)
  * research.transfer.naive_club_pool_t2           -- naive pooled intl+club (no domain correction)
  * research.transfer.shared_stable_features_t3     -- shared coeff on the stable-feature subset only
  * research.transfer.partial_pooling_t4           -- hierarchical partial-pooling GLM (domain intercepts)
  * research.transfer.domain_weighted_t5           -- domain-overlap weighted transfer
  * research.transfer.selective_transfer_t6        -- selective (gated) transfer
  * research.transfer.calibrated_transfer_simulation_t7 -- calibrated MC simulation of the selected model

The REFERENCE for every candidate comparison is ``w2_reference_t0`` (never a weaker anchor).
"""
from __future__ import annotations

# ---- canonical ids (single source of truth; imported by datasets / schemas / tests) --------------
T0_REFERENCE = "research.transfer.w2_reference_t0"
T1_INTERNATIONAL_ONLY = "research.transfer.international_only_t1"
T2_NAIVE_CLUB_POOL = "research.transfer.naive_club_pool_t2"
T3_SHARED_STABLE_FEATURES = "research.transfer.shared_stable_features_t3"
T4_PARTIAL_POOLING = "research.transfer.partial_pooling_t4"
T5_DOMAIN_WEIGHTED = "research.transfer.domain_weighted_t5"
T6_SELECTIVE_TRANSFER = "research.transfer.selective_transfer_t6"
T7_CALIBRATED_SIMULATION = "research.transfer.calibrated_transfer_simulation_t7"

TRANSFER_MODELS = (
    T0_REFERENCE,
    T1_INTERNATIONAL_ONLY,
    T2_NAIVE_CLUB_POOL,
    T3_SHARED_STABLE_FEATURES,
    T4_PARTIAL_POOLING,
    T5_DOMAIN_WEIGHTED,
    T6_SELECTIVE_TRANSFER,
    T7_CALIBRATED_SIMULATION,
)

REFERENCE_MODEL = T0_REFERENCE

# domain labels used throughout the transfer plane
DOMAIN_INTERNATIONAL = "international"
DOMAIN_CLUB = "club"
DOMAINS = (DOMAIN_INTERNATIONAL, DOMAIN_CLUB)

# eligibility labels stamped on every produced row/artifact
ELIGIBILITY_LABELS = (
    "research_only",
    "experimental",
    "not_runtime_approved",
    "not_trade_eligible",
    "not_live_eligible",
)

PACKAGE_VERSION = "hierarchical_transfer_v1"
