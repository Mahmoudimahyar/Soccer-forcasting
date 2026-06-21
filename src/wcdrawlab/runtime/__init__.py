"""Runtime model governance: route all approved forecasts through the single approved model
(B1/Elo) and treat every other model as shadow-only with no runtime authority.

Public API:
    from wcdrawlab.runtime import (
        APPROVED_MODEL_ID, get_approved_model_id, is_approved, classify,
        require_approved, require_decision_model, make_envelope, registry,
    )
"""
from wcdrawlab.runtime.model_registry import (  # noqa: F401
    APPROVED_MODEL_ID, get_approved_model_id, is_approved, classify,
    require_approved, require_decision_model, make_envelope, registry,
    ModelNotApprovedError, UnknownModelError, ShadowDecisionError,
)
