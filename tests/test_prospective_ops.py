"""Tests for the V1.5 prospective-operations plane. Fixtures/mocks only; no network, no real APIs."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.operations.ledger import ImmutableLedger  # noqa: E402
from wcdrawlab.operations.windows import capture_plan, due_windows  # noqa: E402
from wcdrawlab.operations import prospective as PRO  # noqa: E402
from wcdrawlab.operations.session import (  # noqa: E402
    SessionManifest, reconcile_critical, is_stale, CriticalSourceDisagreement)
from wcdrawlab.research.final_holdout import FrozenInPlayModel  # noqa: E402

MODEL = FrozenInPlayModel(1.35, 0.20, 1.0, model_id="m2_frozen")


# ---- ledger ----
def test_ledger_first_write_wins(tmp_path):
    led = ImmutableLedger(tmp_path / "l.jsonl")
    assert led.record("m1:T-90", {"p_home_win": 0.5})["wrote"] is True
    # second write of the SAME key is a no-op; original preserved
    assert led.record("m1:T-90", {"p_home_win": 0.9})["wrote"] is False
    recs = led.records()
    assert len(recs) == 1 and recs[0]["p_home_win"] == 0.5
    assert led.record("m1:T-15", {"p_home_win": 0.4})["wrote"] is True
    assert led.keys() == {"m1:T-90", "m1:T-15"}


# ---- windows ----
def test_capture_plan_pending_due_missed():
    ko = "2026-07-01T18:00:00+00:00"
    # 2h before kickoff: T-90 pending (target 16:30, now 16:00)
    p_early = {w["window"]: w["status"] for w in capture_plan(ko, "2026-07-01T16:00:00+00:00")}
    assert p_early["T-90"] == "pending"
    # exactly at T-90 target -> due
    assert {w["window"]: w["status"] for w in capture_plan(ko, "2026-07-01T16:30:00+00:00")}["T-90"] == "due"
    # long after a checkpoint -> missed
    p_late = {w["window"]: w["status"] for w in capture_plan(ko, "2026-07-01T23:00:00+00:00")}
    assert p_late["T-90"] == "missed" and p_late["m85"] == "missed"
    # no windows due far in the future
    assert due_windows(ko, "2026-06-01T00:00:00+00:00") == []


# ---- prediction record ----
def test_build_record_is_research_only_and_complete():
    rec = PRO.build_prediction_record(
        match_id="X", kickoff_utc="2026-07-01T18:00:00+00:00", phase="pre_match", capture_window="T-90",
        decision_minute=0, decision_timestamp="2026-07-01T16:30:00+00:00",
        retrieval_timestamp="2026-07-01T16:30:00+00:00", event_source_timestamp="2026-07-01T16:30:00+00:00",
        state={"elo_delta_home": 120, "decision_minute": 0, "score_home": 0, "score_away": 0,
               "red_home": 0, "red_away": 0},
        frozen_model=MODEL, anchor_probs=(0.5, 0.3, 0.2), source_hashes={"q": "X"})
    assert rec["approval_status"] == "research_only" and rec["not_runtime_approved"] is True
    assert abs(rec["p_home_win"] + rec["p_draw"] + rec["p_away_win"] - 1.0) < 1e-9
    assert rec["data_completeness"] == 1.0 and rec["model_id"] == "m2_frozen"


def test_build_record_blocks_leakage():
    with pytest.raises(PRO.LeakageError):
        PRO.build_prediction_record(
            match_id="X", kickoff_utc="k", phase="in_play", capture_window="m60", decision_minute=60,
            decision_timestamp="2026-07-01T19:00:00+00:00",
            retrieval_timestamp="2026-07-01T19:00:00+00:00",
            event_source_timestamp="2026-07-01T19:05:00+00:00",  # AFTER decision -> leak
            state={"elo_delta_home": 0, "decision_minute": 60, "score_home": 1, "score_away": 0,
                   "red_home": 0, "red_away": 0},
            frozen_model=MODEL, anchor_probs=(0.4, 0.3, 0.3), source_hashes={})


def test_score_record_metrics():
    rec = {"ledger_key": "k", "match_id": "X", "phase": "pre_match", "capture_window": "T-90",
           "decision_minute": 0, "model_id": "m2_frozen", "model_version": "v2",
           "p_home_win": 1.0, "p_draw": 0.0, "p_away_win": 0.0,
           "anchor_p_home": 0.34, "anchor_p_draw": 0.33, "anchor_p_away": 0.33}
    s = PRO.score_record(rec, final_wld="H", final_score_home=2, final_score_away=0,
                         result_event_time="t1", result_retrieval_time="t2")
    assert s["rps_model"] == 0.0 and s["log_loss_model"] < 1e-6  # perfect home prediction
    assert s["rps_anchor"] > 0 and s["approval_status"] == "research_only"


def test_state_from_apifootball_counts_reds():
    fixture = {"teams": {"home": {"id": 1}, "away": {"id": 2}}, "goals": {"home": 1, "away": 2}}
    events = [{"type": "Card", "detail": "Red Card", "team": {"id": 1}},
              {"type": "Card", "detail": "Yellow Card", "team": {"id": 2}}]
    st = PRO.state_from_apifootball(fixture, events, elo_delta_home=-50.0, decision_minute=75)
    assert st["score_home"] == 1 and st["score_away"] == 2 and st["red_home"] == 1 and st["red_away"] == 0


# ---- session integrity ----
def test_reconcile_critical_fails_closed():
    assert reconcile_critical("score", [{"h": 1}, {"h": 1}]) == {"h": 1}
    with pytest.raises(CriticalSourceDisagreement):
        reconcile_critical("score", [{"h": 1}, {"h": 2}])


def test_is_stale():
    assert is_stale("2026-07-01T18:00:00+00:00", "2026-07-01T18:20:00+00:00", max_minutes=10) is True
    assert is_stale("2026-07-01T18:00:00+00:00", "2026-07-01T18:05:00+00:00", max_minutes=10) is False


def test_session_manifest_idempotent_and_missed(tmp_path):
    s = SessionManifest(tmp_path, "s1", clock=lambda: "T")
    assert s.log("captured", "cap:1", match_id="m1") is True
    assert s.log("captured", "cap:1", match_id="m1") is False   # duplicate event_key -> no-op
    assert s.mark_missed("m2", "m60") is True
    summ = s.shutdown_summary()
    assert summ["captured"] == 1 and summ["missed"] == 1 and summ["status"] == "clean_shutdown"
    assert (tmp_path / "heartbeat_s1.json").exists()
