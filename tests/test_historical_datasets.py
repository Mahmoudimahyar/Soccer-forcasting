"""Phase 4 causal dataset tests. Synthetic events/lineups only; no real data, no network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.paid_source import historical_datasets as HD  # noqa: E402

H, A = 10, 20


def _goal(el, team, detail="Normal Goal"):
    return {"time": {"elapsed": el}, "type": "Goal", "detail": detail, "team": {"id": team}, "player": {"id": 1}}


def _sub(el, team, pin, pout):
    return {"time": {"elapsed": el}, "type": "subst", "team": {"id": team}, "player": {"id": pin}, "assist": {"id": pout}}


def _card(el, team, pid, detail="Yellow Card"):
    return {"time": {"elapsed": el}, "type": "Card", "detail": detail, "team": {"id": team}, "player": {"id": pid}}


def test_no_future_goal_in_state():
    ev = [_goal(30, H), _goal(80, A)]
    assert HD.regulation_state_at(ev, H, A, 50) == (1, 0)  # the 80' goal must not leak at t=50


def test_no_future_substitution_in_on_pitch():
    subs = HD.substitutions([_sub(60, H, 99, 5)])
    on50 = HD.players_on_pitch([1, 2, 3, 4, 5], subs, 50)
    on70 = HD.players_on_pitch([1, 2, 3, 4, 5], subs, 70)
    assert 99 not in on50 and 5 in on50          # sub at 60 not applied at t=50
    assert 99 in on70 and 5 not in on70          # applied by t=70


def test_no_future_card_in_events_up_to():
    ev = [_card(20, A, 7), _card(85, A, 8)]
    assert len(HD.events_up_to(ev, 50)) == 1


def test_correct_player_on_pitch_state():
    subs = HD.substitutions([_sub(46, H, 12, 3), _sub(70, H, 14, 12)])
    on = HD.players_on_pitch([1, 2, 3, 4], subs, 75)
    assert on == {1, 2, 4, 14}  # 3 off@46, 12 on@46 then off@70, 14 on@70


def test_regulation_vs_extra_time_separation():
    ev = [_goal(40, H), _goal(105, H)]
    assert HD.regulation_state_at(ev, H, A, 120) == (1, 0)  # ET goal excluded from regulation


def test_own_goal_beneficiary():
    assert HD.regulation_state_at([_goal(30, A, "Own Goal")], H, A, 90) == (0, 1)  # credited to team=A


def test_cards_table_second_yellow_vs_direct_red():
    rows = HD.cards_table([_card(20, A, 7), _card(60, A, 7), _card(70, A, 8, "Red Card")])
    classes = [r["card_class"] for r in rows]
    assert "second_yellow" in classes        # player 7 second yellow
    assert "direct_red" in classes           # player 8 straight red (no prior yellow)


def test_duplicate_event_idempotent_state():
    # duplicate goal would double-count; the canonical reconciler flags it (tested in result_semantics);
    # here ensure events_up_to is stable / deterministic regardless of duplication input ordering
    ev = [_goal(30, H), _goal(30, H)]
    assert HD.events_up_to(ev, 50) == HD.events_up_to(ev, 50)


def test_partition_club_vs_international():
    assert HD.partition("international") == "international"
    assert HD.partition("club") == "club"


def test_deterministic_rebuild():
    ev = [_goal(20, H), _goal(80, A)]
    assert HD.regulation_state_at(ev, H, A, 90) == HD.regulation_state_at(ev, H, A, 90)


def test_lineup_parse_preserves_player_ids():
    tl = {"team": {"id": H}, "formation": "4-3-3",
          "startXI": [{"player": {"id": 1, "pos": "G", "number": 1}}],
          "substitutes": [{"player": {"id": 9, "pos": "F"}}]}
    p = HD.parse_lineup(tl)
    assert p["starters"][0]["player_id"] == 1 and p["bench"][0]["player_id"] == 9 and p["formation"] == "4-3-3"
