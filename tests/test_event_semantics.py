"""Deterministic tests for provider-aware own-goal event semantics. Sanitized fixtures + one real
cached fixture (855767). No network."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.event_semantics import interpret_event, score_from_events  # noqa: E402
from wcdrawlab.research.inplay_replay import state_from_events  # noqa: E402

H, A = "Canada", "Morocco"


def _goal(team, minute, detail="Normal Goal"):
    return {"type": "Goal", "detail": detail, "team": {"name": team}, "time": {"elapsed": minute}}


# 1. standard goal: provider event team == scoring team
def test_standard_goal_scoring_team_is_reported():
    c = interpret_event(_goal("Morocco", 4), H, A, "api_football")
    assert c["is_goal"] and c["scoring_team_id"] == "Morocco" and c["own_goal_flag"] is False


# 2. API-Football own goal: reported team is beneficiary; scoring team stays beneficiary (NO inversion)
def test_api_football_own_goal_no_inversion():
    c = interpret_event(_goal("Canada", 40, "Own Goal"), H, A, "api_football")
    assert c["own_goal_flag"] is True
    assert c["beneficiary_team_id"] == "Canada" and c["scoring_team_id"] == "Canada"
    assert c["player_team_id_if_known"] == "Morocco"   # scorer belongs to the opponent
    assert c["derived_state_quality_status"] == "ok"


# 3. alternative provider that encodes the scorer's team -> scoring team is the opponent
def test_scorer_encoding_provider_inverts():
    c = interpret_event(_goal("Morocco", 40, "Own Goal"), H, A, "example_scorer_provider")
    assert c["own_goal_flag"] is True
    assert c["scoring_team_id"] == "Canada"           # opponent of the scorer's team
    assert c["beneficiary_team_id"] == "Canada"


def test_unknown_provider_own_goal_fails_closed():
    c = interpret_event(_goal("Canada", 40, "Own Goal"), H, A, "some_unmapped_provider")
    assert c["derived_state_quality_status"] == "unknown_own_goal_semantics"
    assert c["is_goal"] is False and c["scoring_team_id"] is None   # excluded, not guessed


# 4. card events must not affect score state
def test_card_does_not_score():
    ev = [_goal("Morocco", 4), {"type": "Card", "detail": "Red Card", "team": {"name": "Canada"}, "time": {"elapsed": 50}}]
    s = score_from_events(ev, H, A, "api_football")
    assert s == {"home": 0, "away": 1, "quality_status": "ok"}    # only Morocco's goal


# 5. VAR-cancelled goal must not enter score state
def test_var_cancelled_goal_excluded():
    ev = [{"type": "Var", "detail": "Goal cancelled", "team": {"name": "Canada"}, "time": {"elapsed": 5}},
          _goal("Morocco", 23)]
    s = score_from_events(ev, H, A, "api_football")
    assert s == {"home": 0, "away": 1, "quality_status": "ok"}


# 6. real fixture 855767 must reconstruct Canada 1-2 Morocco
def test_fixture_855767_reconciles():
    C = ROOT / "data/raw/api_football_2022_worldcup"
    ev = json.loads((C / "events_855767.json").read_text(encoding="utf-8"))["response"]
    s = score_from_events(ev, "Canada", "Morocco", "api_football")
    assert (s["home"], s["away"]) == (1, 2), s
    assert s["quality_status"] == "ok"


# 7. event-time causality: state at minute t excludes later events
def test_causality_excludes_future_events():
    ev = [_goal("Morocco", 4), _goal("Morocco", 23), _goal("Canada", 40, "Own Goal")]
    assert score_from_events(ev, H, A, "api_football", up_to_minute=30) == {"home": 0, "away": 2, "quality_status": "ok"}
    assert score_from_events(ev, H, A, "api_football", up_to_minute=45) == {"home": 1, "away": 2, "quality_status": "ok"}
    # via the replay state builder (team_a oriented), minute 30 sees no own goal yet
    st = state_from_events(ev, 30, team_a="Canada", home_team=H, away_team=A)
    assert st["goals_a"] == 0 and st["goals_b"] == 2


# 8. idempotency: scoring the same feed twice does not double-count
def test_idempotent_replay():
    ev = [_goal("Morocco", 4), _goal("Canada", 40, "Own Goal")]
    s1 = score_from_events(ev, H, A, "api_football")
    s2 = score_from_events(ev, H, A, "api_football")
    assert s1 == s2 == {"home": 1, "away": 1, "quality_status": "ok"}
