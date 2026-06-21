"""Runtime forecast routing. The default (and only approved) path runs B1/Elo and stamps the
approved governance envelope. Shadow models can only be LABELLED (their externally-produced
outputs tagged shadow) — never run as approved here.

Fail-closed: requesting any non-approved model raises; if the approved model implementation is
unavailable, raise rather than fall back to a shadow model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from wcdrawlab.evaluation import normalize_probs
from wcdrawlab.runtime.model_registry import (
    APPROVED_MODEL_ID, get_approved_model_id, make_envelope, require_approved, classify,
)

_ENV_COLS = ["model_id", "model_version", "approval_status", "prediction_mode",
             "decision_timestamp", "source_manifest_id", "feature_schema_version",
             "commit_hash", "experimental_status", "no_runtime_authority", "reason_not_approved"]


def _attach_envelope(df: pd.DataFrame, env: dict) -> pd.DataFrame:
    out = df.copy()
    for k in _ENV_COLS:
        out[k] = env.get(k)
    return out


def _b1_probs(matches: pd.DataFrame) -> np.ndarray:
    """Approved model B1: parameter-free ternary-Elo on elo_delta. Fail closed if unavailable."""
    try:
        from wcdrawlab.models.baselines import TernaryEloModel
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Approved model {APPROVED_MODEL_ID} implementation unavailable: {e}. "
                           f"Failing closed (no shadow fallback).") from e
    if "elo_delta" not in matches.columns:
        raise RuntimeError("Approved model B1 requires 'elo_delta'; failing closed (no fallback).")
    return normalize_probs(TernaryEloModel(r=0.4).predict_proba(matches))


def approved_forecast(matches: pd.DataFrame, decision_timestamp: str | None = None) -> pd.DataFrame:
    """Produce the APPROVED B1/Elo forecast with the approved envelope. This is the runtime
    default and the only path allowed to emit prediction_mode='approved'."""
    require_approved(APPROVED_MODEL_ID)  # sanity: approved model must be the approved id
    P = _b1_probs(matches)
    env = make_envelope(APPROVED_MODEL_ID, decision_timestamp)  # registry-derived -> 'approved'
    cols = [c for c in ["match_id", "matchday", "group", "team_a", "team_b", "kickoff_utc"] if c in matches.columns]
    out = matches[cols].copy().reset_index(drop=True)
    out["p_a"], out["p_draw"], out["p_b"] = P[:, 0], P[:, 1], P[:, 2]
    out["prediction_entropy"] = (-P * np.log(np.clip(P, 1e-12, 1)) / np.log(3)).sum(1)
    return _attach_envelope(out, env)


def runtime_forecast(matches: pd.DataFrame, model_id: str | None = None,
                     decision_timestamp: str | None = None) -> pd.DataFrame:
    """Runtime entry point. Defaults to the approved model when none is requested.
    FAILS CLOSED for any non-approved / unknown model (no shadow may produce runtime output)."""
    model_id = model_id or get_approved_model_id()
    require_approved(model_id)  # raises ModelNotApprovedError / UnknownModelError
    return approved_forecast(matches, decision_timestamp)


def label_shadow(model_id: str, predictions: pd.DataFrame,
                 decision_timestamp: str | None = None) -> pd.DataFrame:
    """Tag externally-produced shadow predictions (must already have p_a/p_draw/p_b) with the
    SHADOW envelope. The registry forces prediction_mode='shadow' for any non-approved model,
    so this cannot mint an 'approved' label."""
    if classify(model_id) == "approved":
        raise ValueError(f"label_shadow is for experimental models only; {model_id} is approved. "
                         f"Use approved_forecast() for the approved model.")
    for c in ("p_a", "p_draw", "p_b"):
        if c not in predictions.columns:
            raise ValueError(f"shadow predictions must include column {c!r}")
    env = make_envelope(model_id, decision_timestamp)  # -> shadow
    return _attach_envelope(predictions, env)
