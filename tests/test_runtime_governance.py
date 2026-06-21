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


# --- paper-decision (risk gate) is registry-bound: shadow models cannot produce a trade decision ---
from datetime import datetime, timezone  # noqa: E402

from wcdrawlab.trading.models import MarketQuote, TradeIntent  # noqa: E402
from wcdrawlab.trading.risk import PortfolioRiskState, RiskGate, TradingPolicy  # noqa: E402


def _intent(model_id):
    now = datetime.now(timezone.utc)
    return TradeIntent(
        market_ticker="TEST-MKT", book_side="bid", limit_price_cents=45, contracts=2,
        model_probability=0.56, model_probability_lower=0.53, market_probability=0.45,
        prediction_created_at_utc=now, market_observed_at_utc=now,
        model_version="approved-v1", rationale="test", event_key="ev", model_id=model_id,
    )


def _approve_everything_but_model():
    # state/policy that pass every OTHER gate so we isolate the model-identity check
    now = datetime.now(timezone.utc)
    quote = MarketQuote("TEST-MKT", yes_bid_cents=44, yes_ask_cents=46, observed_at_utc=now)
    state = PortfolioRiskState(approved_model_versions=frozenset({"approved-v1"}))
    return quote, state, now


def test_paper_decision_rejects_shadow_model_id():
    quote, state, now = _approve_everything_but_model()
    dec = RiskGate(TradingPolicy()).evaluate(_intent(V8), quote, state, now=now, confidence_score=0.7)
    assert not dec.approved
    assert "model is shadow/experimental: not approved for runtime decisions" in dec.reasons
    # market blend too
    dec2 = RiskGate(TradingPolicy()).evaluate(_intent(MKT), quote, state, now=now, confidence_score=0.7)
    assert not dec2.approved


def test_paper_decision_accepts_approved_model_id():
    quote, state, now = _approve_everything_but_model()
    dec = RiskGate(TradingPolicy()).evaluate(_intent("B1_ELO"), quote, state, now=now, confidence_score=0.7)
    assert dec.approved, dec.reasons
