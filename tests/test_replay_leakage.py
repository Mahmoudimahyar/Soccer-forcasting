"""Leakage guards for in-play replay + pre-match snapshot timing. No network.

Covers: event-time, substitution-time, lineup-time, market-snapshot timing, standings/tournament-
state timing. (Simultaneous final-matchday group leakage is additionally covered by
tests/test_research_leakage.py.)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.research.inplay_replay import (  # noqa: E402
    state_from_events, event_known_by, pre_match_odds_eligible, lineup_eligible,
)

EVENTS = [
    {"time": {"elapsed": 10}, "team": {"name": "A"}, "type": "Goal", "detail": "Normal Goal"},
    {"time": {"elapsed": 55}, "team": {"name": "B"}, "type": "Card", "detail": "Yellow Card"},
    {"time": {"elapsed": 70}, "team": {"name": "B"}, "type": "subst", "detail": "Substitution 1"},
    {"time": {"elapsed": 80}, "team": {"name": "B"}, "type": "Goal", "detail": "Normal Goal"},
    {"time": {"elapsed": 85}, "team": {"name": "A"}, "type": "Card", "detail": "Red Card"},
]


def test_event_time_leakage_excludes_future_goals():
    s60 = state_from_events(EVENTS, 60, team_a="A", home_team="A", away_team="B")
    assert s60 == {"goals_a": 1, "goals_b": 0, "red_cards_a": 0, "red_cards_b": 0}  # 80' goal & 85' red excluded
    s90 = state_from_events(EVENTS, 90, team_a="A", home_team="A", away_team="B")
    assert s90 == {"goals_a": 1, "goals_b": 1, "red_cards_a": 1, "red_cards_b": 0}  # all known by 90'


def test_substitution_time_leakage():
    # the 70' substitution / 80' goal must not be reflected before they occur
    assert event_known_by(70, 60) is False
    assert event_known_by(70, 75) is True


def test_own_goal_credits_beneficiary_and_missed_penalty_ignored():
    # CORRECTED (own-goal remediation): API-Football's Own Goal `team` is the BENEFICIARY (the team
    # credited the goal), NOT the scorer's team -> no inversion. (Was previously asserted backwards.)
    ev = [
        {"time": {"elapsed": 20}, "team": {"name": "A"}, "type": "Goal", "detail": "Own Goal"},   # credits A (beneficiary)
        {"time": {"elapsed": 30}, "team": {"name": "A"}, "type": "Goal", "detail": "Missed Penalty"},  # ignored
    ]
    s = state_from_events(ev, 90, team_a="A", home_team="A", away_team="B")
    assert s["goals_a"] == 1 and s["goals_b"] == 0


def test_lineup_time_leakage():
    assert lineup_eligible("2026-06-21T17:00:00Z", "2026-06-21T18:00:00Z") is True   # published before decision
    assert lineup_eligible("2026-06-21T18:30:00Z", "2026-06-21T18:00:00Z") is False  # published after decision


def test_market_snapshot_timing():
    assert pre_match_odds_eligible("2022-11-20T14:25:00Z", "2022-11-20T16:00:00Z") is True   # pre-kickoff
    assert pre_match_odds_eligible("2022-11-20T16:00:00Z", "2022-11-20T16:00:00Z") is False  # at/after kickoff


def test_standings_tournament_state_timing():
    # a prior-matchday result (earlier kickoff) is eligible; a same-or-later one is not
    assert lineup_eligible("2026-06-17T18:00:00Z", "2026-06-22T18:00:00Z") is True
    assert lineup_eligible("2026-06-22T18:00:00Z", "2026-06-22T17:00:00Z") is False
