"""Governance tests for the runtime model-routing layer.

Enforces: B1/Elo is the sole approved runtime model; V8 and the market blend are shadow-only with
no runtime authority; unknown models fail closed; approved output carries the model identity +
approval envelope; shadow predictions cannot drive decisions and cannot be relabelled approved.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.runtime import (  # noqa: E402
    get_approved_model_id, classify, require_approved, require_decision_model, make_envelope,
    ModelNotApprovedError, UnknownModelError, ShadowDecisionError,
)
from wcdrawlab.runtime.forecaster import (  # noqa: E402
    runtime_forecast, approved_forecast, label_shadow,
)

V8 = "V8_ELO_BLEND_LOGIT"
MKT = "MARKET_ELO_BLEND"


def _matches():
    return pd.DataFrame({
        "match_id": ["m1", "m2", "m3"],
        "team_a": ["A", "C", "E"], "team_b": ["B", "D", "F"],
        "elo_delta": [120.0, -50.0, 0.0],
    })


def test_b1_is_default_when_no_model_requested():
    out = runtime_forecast(_matches())  # no model_id -> default
    assert get_approved_model_id() == "B1_ELO"
    assert set(out["model_id"]) == {"B1_ELO"}
    assert set(out["prediction_mode"]) == {"approved"}
    assert set(out["approval_status"]) == {"approved"}
    # probabilities are valid
    assert (out[["p_a", "p_draw", "p_b"]].sum(axis=1).round(6) == 1.0).all()


def test_v8_cannot_produce_approved_runtime_output():
    with pytest.raises(ModelNotApprovedError):
        runtime_forecast(_matches(), model_id=V8)
    with pytest.raises(ModelNotApprovedError):
        require_approved(V8)
    env = make_envelope(V8)  # registry forces shadow
    assert env["prediction_mode"] == "shadow"
    assert env["no_runtime_authority"] is True
    assert env["approval_status"] != "approved"


def test_market_blend_cannot_drive_paper_trade_decisions():
    shadow_pred = make_envelope(MKT)
    assert shadow_pred["prediction_mode"] == "shadow"
    with pytest.raises(ShadowDecisionError):
        require_decision_model(shadow_pred)
    with pytest.raises(ShadowDecisionError):
        require_decision_model("shadow")
    # the approved model is accepted by the decision guard
    require_decision_model(make_envelope(get_approved_model_id()))  # no raise


def test_unknown_model_fails_closed():
    with pytest.raises(UnknownModelError):
        classify("NOT_A_REAL_MODEL")
    with pytest.raises(UnknownModelError):
        require_approved("NOT_A_REAL_MODEL")
    with pytest.raises(UnknownModelError):
        runtime_forecast(_matches(), model_id="NOT_A_REAL_MODEL")
    with pytest.raises(UnknownModelError):
        make_envelope("NOT_A_REAL_MODEL")


def test_approved_output_records_model_identity_and_approval():
    out = approved_forecast(_matches(), decision_timestamp="2026-06-21T00:00:00Z")
    for col in ["model_id", "model_version", "approval_status", "prediction_mode",
                "decision_timestamp", "source_manifest_id", "feature_schema_version", "commit_hash"]:
        assert col in out.columns, f"approved ledger row missing {col}"
    assert (out["model_id"] == "B1_ELO").all()
    assert (out["approval_status"] == "approved").all()
    assert (out["decision_timestamp"] == "2026-06-21T00:00:00Z").all()
    assert out["commit_hash"].iloc[0].startswith("e78cde4")


def test_shadow_artifacts_retain_experimental_provenance():
    df = _matches().assign(p_a=0.4, p_draw=0.3, p_b=0.3)
    for mid in (V8, MKT):
        tagged = label_shadow(mid, df)
        assert (tagged["prediction_mode"] == "shadow").all()
        assert bool(tagged["experimental_status"].iloc[0]) is True
        assert bool(tagged["no_runtime_authority"].iloc[0]) is True
        assert tagged["reason_not_approved"].iloc[0]
    # cannot relabel the approved model via the shadow path
    with pytest.raises(ValueError):
        label_shadow(get_approved_model_id(), df)


def test_registry_lists_shadow_models_with_no_authority():
    assert classify(V8) == "shadow"
    assert classify(MKT) == "shadow"
    assert classify("B1_ELO") == "approved"


def test_fail_closed_when_approved_model_inputs_missing():
    # approved model requires elo_delta; missing -> fail closed, never fall back to shadow
    bad = _matches().drop(columns=["elo_delta"])
    with pytest.raises(RuntimeError):
        approved_forecast(bad)
