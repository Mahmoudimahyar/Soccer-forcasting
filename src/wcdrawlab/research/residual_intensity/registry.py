"""Canonical model-ID registry for the residual goal-intensity phase (Phase 2).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

These are the ONLY sanctioned identifiers for this phase, taken verbatim from the build spec. The
package does not invent names; centralizing the IDs here prevents ad-hoc names from leaking into
artifacts. Nothing here is M1-M5, nothing here is runtime/trade/live-approved.

Three canonical families (the spec enumerates each verbatim):

  residual.*    -- residual goal-intensity / correction WDL family. r0 is the W2 remaining-time
                   Poisson REFERENCE (parameter-free); every residual model must beat it or fall back
                   to it. The selective-correction model (r4) MUST permit alpha=0 (pure r0 fallback).
  horizon.*     -- near-term scoring-window family (5/10/15min, right-censored). h0 is the W2-implied
                   horizon baseline; the rest add event-process state under the availability gate.
  intensity.*   -- side-specific (home & away) remaining-goal intensity family. i0 is the W2
                   home/away reference intensity; the rest add event residuals / regime / club transfer.
"""
from __future__ import annotations

# ----- residual goal-intensity / correction WDL family --------------------------------------------
RESIDUAL_MODELS = [
    "research.residual.w2_reference_r0",        # W2 remaining-time Poisson reference (parameter-free)
    "research.residual.intensity_glm_r1",       # regularized Poisson/ridge intensity GLM on event state
    "research.residual.competing_risk_r2",      # regularized discrete-time competing-risk hazard
    "research.residual.event_process_boost_r3", # HistGradientBoosting intensity (small predeclared grid)
    "research.residual.selective_correction_r4",# selective correction of r0 (alpha in-train; alpha=0 ok)
    "research.residual.calibrated_simulation_r5",# Monte-Carlo simulation from intensities + in-train cal
    "research.residual.club_auxiliary_transfer_r6", # frozen club-trained representation transferred in
]

# ----- near-term scoring-window (horizon) family --------------------------------------------------
HORIZON_MODELS = [
    "research.horizon.w2_implied_h0",           # W2-implied near-term scoring baseline
    "research.horizon.xg_residual_h1",          # + cumulative/rolling xG residual
    "research.horizon.possession_transition_h2",# + possession/territory/transition state
    "research.horizon.full_event_process_h3",   # + full event-process state
    "research.horizon.selective_gate_h4",       # selective gate over h0..h3 (training-chosen)
]

# ----- side-specific (home & away) intensity family -----------------------------------------------
INTENSITY_MODELS = [
    "research.intensity.w2_home_away_i0",       # W2 home/away REFERENCE intensities
    "research.intensity.event_residual_home_away_i1", # + event-process residual per side
    "research.intensity.regime_specific_i2",    # regime-conditioned intensities (interpretable regimes)
    "research.intensity.club_transfer_i3",      # + frozen club-transfer scalar
]

ALL_MODELS = RESIDUAL_MODELS + HORIZON_MODELS + INTENSITY_MODELS

# The W2 reference anchors of each family (a candidate must beat its family reference or fall back).
REFERENCE_IDS = {
    "residual": "research.residual.w2_reference_r0",
    "horizon": "research.horizon.w2_implied_h0",
    "intensity": "research.intensity.w2_home_away_i0",
}

ARTIFACT_LABELS = (
    "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"
)


def is_canonical(model_id: str) -> bool:
    return model_id in ALL_MODELS


def assert_canonical(model_id: str) -> str:
    if model_id not in ALL_MODELS:
        raise ValueError(f"non-canonical residual_intensity model id {model_id!r}; allowed: {ALL_MODELS}")
    return model_id
