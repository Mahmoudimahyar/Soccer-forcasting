"""Authoritative runtime model registry + hard governance safeguards.

Single source of truth = configs/approved_models.yaml. Rules enforced here:
  - B1_ELO is the ONLY approved runtime model.
  - Any other registered model is SHADOW (no runtime authority).
  - Unknown model ids FAIL CLOSED (raise), never silently fall back.
  - The prediction-mode envelope is DERIVED from the registry, so it is impossible to label a
    shadow model (V8 / market blend) as 'approved'.
  - Decision/paper-trade paths must call require_decision_model(), which rejects shadow predictions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_REGISTRY_PATH = Path(__file__).resolve().parents[3] / "configs" / "approved_models.yaml"


class UnknownModelError(RuntimeError):
    """Raised when a model id is not in the registry (fail closed)."""


class ModelNotApprovedError(RuntimeError):
    """Raised when an approved-only operation is attempted with a non-approved model."""


class ShadowDecisionError(RuntimeError):
    """Raised when a shadow/experimental prediction is used for a decision/paper-trade/risk path."""


@lru_cache(maxsize=1)
def registry() -> dict[str, Any]:
    with _REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        reg = yaml.safe_load(fh)
    # minimal integrity checks
    assert reg["approved_model"]["approved_model_id"] == "B1_ELO", "approved model must be B1_ELO"
    return reg


def get_approved_model_id() -> str:
    return registry()["approved_model"]["approved_model_id"]


APPROVED_MODEL_ID = "B1_ELO"


def _shadow_ids() -> set[str]:
    return {m["model_id"] for m in registry().get("experimental_models", [])}


def is_approved(model_id: str) -> bool:
    return model_id == get_approved_model_id()


def classify(model_id: str) -> str:
    """Return 'approved' or 'shadow'. Unknown ids FAIL CLOSED (raise)."""
    if model_id == get_approved_model_id():
        return "approved"
    if model_id in _shadow_ids():
        return "shadow"
    raise UnknownModelError(
        f"Model id {model_id!r} is not in the approved-model registry. Fail closed: "
        f"refusing to run an unregistered model. Approved={get_approved_model_id()!r}; "
        f"shadow={sorted(_shadow_ids())}."
    )


def require_approved(model_id: str) -> str:
    """Gate for runtime forecast/decision use. Raises unless model_id is the approved model."""
    cls = classify(model_id)  # raises UnknownModelError for unknown (fail closed)
    if cls != "approved":
        raise ModelNotApprovedError(
            f"Model {model_id!r} is {cls} and has no runtime authority. Only "
            f"{get_approved_model_id()!r} may produce approved runtime output."
        )
    return model_id


def _shadow_meta(model_id: str) -> dict[str, Any]:
    for m in registry().get("experimental_models", []):
        if m["model_id"] == model_id:
            return m
    raise UnknownModelError(model_id)


def make_envelope(model_id: str, decision_timestamp: str | None = None) -> dict[str, Any]:
    """Build the governance envelope for a prediction. The prediction_mode is DERIVED from the
    registry — callers cannot mark a shadow model as approved."""
    cls = classify(model_id)  # fail closed on unknown
    ts = decision_timestamp or datetime.now(timezone.utc).isoformat()
    if cls == "approved":
        a = registry()["approved_model"]
        return {
            "model_id": a["approved_model_id"],
            "model_version": a["model_version"],
            "approval_status": "approved",
            "prediction_mode": "approved",
            "decision_timestamp": ts,
            "source_manifest_id": a["data_snapshot_ref"],
            "feature_schema_version": a["feature_schema_version"],
            "commit_hash": a["commit_hash"],
            "experimental_status": False,
            "no_runtime_authority": False,
        }
    meta = _shadow_meta(model_id)
    return {
        "model_id": model_id,
        "model_version": "experimental",
        "approval_status": "experimental",
        "prediction_mode": "shadow",
        "decision_timestamp": ts,
        "experimental_status": True,
        "no_runtime_authority": True,
        "reason_not_approved": meta.get("reason_not_approved", "experimental; not promoted"),
    }


def require_decision_model(envelope_or_mode) -> None:
    """Hard guard for paper-trade / decision / risk / Kalshi paths: reject shadow predictions.
    Accepts an envelope dict or a prediction_mode string."""
    mode = envelope_or_mode.get("prediction_mode") if isinstance(envelope_or_mode, dict) else envelope_or_mode
    if mode != "approved":
        raise ShadowDecisionError(
            f"Refusing to use a {mode!r} prediction for a decision/paper-trade/risk path. "
            f"Only approved ({get_approved_model_id()}) predictions may drive decisions."
        )
