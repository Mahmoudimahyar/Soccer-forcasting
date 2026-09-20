"""Registry of the T0..T7 ladder — factories, eligibility, and the promotion policy.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

A single place that maps the short ladder ids ("T0".."T7") to:
  * a zero-arg FACTORY producing an unfitted model object (each exposes ``fit(train_rows)`` and
    ``predict_wdl(row)->{H,D,A}``);
  * the canonical ``research.transfer.*`` id;
  * promotion metadata: whether the model is the REFERENCE, DIAGNOSTIC-ONLY (never promoted), or a
    promotable candidate.

The promotion rule (``research_candidate_for_future_shadow_review``) is enforced in ``eval.py`` against
the T0 reference. The registry only declares *which* models are even eligible to be considered (T2 is
hard-blocked as diagnostic-only; T0 is the reference and cannot be its own candidate).
"""
from __future__ import annotations

from typing import Callable, Dict

from . import (
    DIAGNOSTIC_ONLY,
    LADDER,
    LADDER_TO_CANONICAL,
    PRIMARY_CANDIDATE,
    REFERENCE_MODEL,
)
from .domain_baselines import T0Reference, T1InternationalOnly, T2NaiveClubPool
from .partial_pooling import T3SharedStableFeatures, T4PartialPooling, T5DomainWeighted
from .selective_transfer import T6SelectiveTransfer, T7CalibratedSimulation

# short id -> zero-arg factory
FACTORIES: Dict[str, Callable[[], object]] = {
    "T0": T0Reference,
    "T1": T1InternationalOnly,
    "T2": T2NaiveClubPool,
    "T3": T3SharedStableFeatures,
    "T4": T4PartialPooling,
    "T5": T5DomainWeighted,
    "T6": T6SelectiveTransfer,
    "T7": T7CalibratedSimulation,
}


def build(short_id: str):
    """Instantiate (unfitted) the model for a short ladder id."""
    if short_id not in FACTORIES:
        raise KeyError(f"unknown ladder model '{short_id}' (expected one of {LADDER})")
    return FACTORIES[short_id]()


def fit_all(train_rows, ids=LADDER) -> Dict[str, object]:
    """Fit every requested ladder model on the SAME train rows. Returns {short_id: fitted_model}."""
    out: Dict[str, object] = {}
    for sid in ids:
        out[sid] = build(sid).fit(list(train_rows))
    return out


def wdl_predictor_factory(ids=LADDER) -> Callable:
    """Return a predictor_factory(train_rows)->{short_id: predict(row)->{H,D,A}} compatible with the eval
    drivers. Fits all requested ladder models on train_rows and exposes their W/D/L heads."""
    def _factory(train_rows):
        fitted = fit_all(train_rows, ids=ids)
        return {sid: m.predict_wdl for sid, m in fitted.items()}
    return _factory


def is_reference(short_id: str) -> bool:
    return short_id == "T0"


def is_diagnostic_only(short_id: str) -> bool:
    return short_id in DIAGNOSTIC_ONLY


def is_promotable(short_id: str) -> bool:
    """A model may be CONSIDERED for promotion iff it is not the reference and not diagnostic-only."""
    return (not is_reference(short_id)) and (not is_diagnostic_only(short_id))


def canonical_id(short_id: str) -> str:
    return LADDER_TO_CANONICAL[short_id]


def registry_summary() -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for sid in LADDER:
        out[sid] = {
            "canonical_id": LADDER_TO_CANONICAL[sid],
            "is_reference": is_reference(sid),
            "is_diagnostic_only": is_diagnostic_only(sid),
            "is_promotable": is_promotable(sid),
            "is_primary_candidate": (sid == PRIMARY_CANDIDATE),
        }
    return out


REFERENCE_SHORT_ID = "T0"
assert LADDER_TO_CANONICAL["T0"] == REFERENCE_MODEL

__all__ = [
    "FACTORIES", "build", "fit_all", "wdl_predictor_factory",
    "is_reference", "is_diagnostic_only", "is_promotable", "canonical_id",
    "registry_summary", "REFERENCE_SHORT_ID",
]
