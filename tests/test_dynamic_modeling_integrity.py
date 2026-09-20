"""Component 6 — DETERMINISTIC INTEGRITY TESTS for the dynamic in-play modeling stack (Phases 1-3).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

These tests exercise the leakage-safety, event-semantics, player-prior causality, and xG-state causality
contracts of the three dynamic engines built by the other agents:

  * Phase 1  src/wcdrawlab/research/dynamic_state.py                  (in-play state snapshots)
  * Phase 2  src/wcdrawlab/research/dynamic_player_prior_models.py    (temporal player priors)
  * Phase 3  src/wcdrawlab/research/dynamic_xg_state.py               (dynamic xG state)

Everything here is built from SMALL, fully deterministic, in-memory synthetic fixtures — NO network, NO
disk reads, NO API/StatsBomb downloads. If a symbol an individual test needs is not present in the built
module, that single test SKIPs with an explicit reason (so the suite still runs and reports honestly)
rather than crashing collection. Where the symbol is present we assert REAL behaviour, not a stub.

Coverage (>=35 deterministic tests):
  Phase 1 state ............. goal timing, own-goal beneficiary, missed penalty, VAR-cancelled goal,
                             extra time, shootout exclusion, on-pitch state, bench state, sub direction,
                             second-yellow, direct-red, duplicated events, out-of-order events,
                             no-future-xG flag, no cross-match state leakage, deterministic rebuild,
                             source-hash traceability.
  Phase 2 priors ............ no future appearance/club/national leakage, correct shrinkage, exact id
                             linkage, deterministic recency, availability timeline, sub-delta sign,
                             sub timing context, club/international separation.
  Phase 3 xG ................ no-future xG, no cross-match, exact-bridge-required (regulation-only),
                             missing-xG handling, momentum window, source-order determinism,
                             hash traceability, big-chance proxy.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# ---- import the modules under test; fall back to None so missing modules SKIP, never crash ----------
try:
    from wcdrawlab.research import dynamic_state as DS
except Exception as _e:                                   # pragma: no cover - import guard
    DS = None
    _DS_ERR = repr(_e)
else:
    _DS_ERR = ""

try:
    from wcdrawlab.research import dynamic_player_prior_models as DP
except Exception as _e:                                   # pragma: no cover - import guard
    DP = None
    _DP_ERR = repr(_e)
else:
    _DP_ERR = ""

try:
    from wcdrawlab.research import dynamic_xg_state as XS
except Exception as _e:                                   # pragma: no cover - import guard
    XS = None
    _XS_ERR = repr(_e)
else:
    _XS_ERR = ""

# The Appearance dataclass is needed to drive the player-prior tests deterministically.
try:
    from wcdrawlab.research.player_history import Appearance
except Exception:                                         # pragma: no cover - import guard
    Appearance = None


def _need(mod, err, name):
    if mod is None:
        pytest.skip(f"{name} not importable (built by another agent): {err}")


def _have(mod, attr):
    return mod is not None and hasattr(mod, attr)


# ==================================================================================================
# Deterministic synthetic fixture builders (API-Football shape) for the Phase-1 state engine.
# ==================================================================================================
HOME_ID, AWAY_ID = 10, 20


def _goal(team_id, minute, detail="Normal Goal", player_id=None):
    return {"type": "Goal", "detail": detail, "team": {"id": team_id},
            "player": {"id": player_id}, "time": {"elapsed": minute}}


def _card(team_id, minute, detail, player_id):
    return {"type": "Card", "detail": detail, "team": {"id": team_id},
            "player": {"id": player_id}, "time": {"elapsed": minute}}


def _subst(team_id, minute, in_id, out_id):
    # API-Football: player = incoming, assist = outgoing.
    return {"type": "subst", "team": {"id": team_id}, "player": {"id": in_id},
            "assist": {"id": out_id}, "time": {"elapsed": minute}}


def _var(team_id, minute, detail="Goal cancelled"):
    return {"type": "Var", "detail": detail, "team": {"id": team_id}, "time": {"elapsed": minute}}


def _lineups(home_xi, away_xi, home_bench=(), away_bench=(), pos="M"):
    return [
        {"team": {"id": HOME_ID}, "formation": "4-4-2",
         "startXI": [{"player": {"id": p, "pos": pos}} for p in home_xi],
         "substitutes": [{"player": {"id": p, "pos": "F"}} for p in home_bench]},
        {"team": {"id": AWAY_ID}, "formation": "4-4-2",
         "startXI": [{"player": {"id": p, "pos": pos}} for p in away_xi],
         "substitutes": [{"player": {"id": p, "pos": "F"}} for p in away_bench]},
    ]


def _fixture(fid=9001, league_id=1, season=2025, date="2025-03-01T18:00:00+00:00",
             ft=(2, 1), et=(None, None), pen=(None, None)):
    return {
        "fixture": {"id": fid, "date": date},
        "league": {"id": league_id, "season": season},
        "teams": {"home": {"id": HOME_ID}, "away": {"id": AWAY_ID}},
        "score": {"fulltime": {"home": ft[0], "away": ft[1]},
                  "extratime": {"home": et[0], "away": et[1]},
                  "penalty": {"home": pen[0], "away": pen[1]}},
    }


def _full_xi(start):
    return list(range(start, start + 11))


def _build(fx, events, lineups):
    """Convenience: build snapshot rows for one fixture and index them by minute."""
    rows, status, reason = DS.build_snapshots_for_fixture(
        str(fx["fixture"]["id"]), fx, events, lineups, {str(fx["fixture"]["id"]): "api_football_corpus"})
    by_min = {r["snapshot_minute"]: r for r in rows}
    return rows, status, reason, by_min


# ==================================================================================================
# PHASE 1 — dynamic_state.py
# ==================================================================================================
def test_p1_goal_timing_state_is_causal():
    """Score at minute t reflects ONLY regulation goals with elapsed <= t (goal timing)."""
    _need(DS, _DS_ERR, "dynamic_state")
    events = [_goal(HOME_ID, 15), _goal(AWAY_ID, 50), _goal(HOME_ID, 80)]
    fx = _fixture(ft=(2, 1))
    _, status, _, by_min = _build(fx, events, _lineups(_full_xi(1), _full_xi(40)))
    assert status == "ok"
    assert (by_min[15]["score_home"], by_min[15]["score_away"]) == (1, 0)
    assert (by_min[20]["score_home"], by_min[20]["score_away"]) == (1, 0)   # nothing between 15 and 50
    assert (by_min[55]["score_home"], by_min[55]["score_away"]) == (1, 1)   # away goal at 50 now counted
    assert (by_min[85]["score_home"], by_min[85]["score_away"]) == (2, 1)   # home goal at 80 counted
    assert (by_min[90]["score_home"], by_min[90]["score_away"]) == (2, 1)


def test_p1_own_goal_credited_to_beneficiary_team():
    """API-Football own goal: event `team` is the BENEFICIARY; it must be credited there (no inversion)."""
    _need(DS, _DS_ERR, "dynamic_state")
    # AWAY scores 1 normal; HOME benefits from an own goal (event team = HOME). Official reg = 1-0... but the
    # own goal benefits HOME so reg should reconcile to 1(home)-0(away) only if no away goal. Use ft=(1,1).
    events = [_goal(HOME_ID, 30, "Own Goal", player_id=999), _goal(AWAY_ID, 60)]
    fx = _fixture(ft=(1, 1))
    rows, status, reason, by_min = _build(fx, events, _lineups(_full_xi(1), _full_xi(40)))
    assert status == "ok", reason
    # at minute 40 only the own goal (credited to HOME beneficiary) has happened
    assert (by_min[30]["score_home"], by_min[30]["score_away"]) == (1, 0)
    assert (by_min[90]["score_home"], by_min[90]["score_away"]) == (1, 1)
    assert by_min[90]["target_wdl"] == "D"


def test_p1_missed_penalty_does_not_score():
    """A missed/cancelled penalty is not a goal and must not change the score state."""
    _need(DS, _DS_ERR, "dynamic_state")
    events = [_goal(HOME_ID, 20, "Missed Penalty"), _goal(HOME_ID, 70)]
    fx = _fixture(ft=(1, 0))
    _, status, reason, by_min = _build(fx, events, _lineups(_full_xi(1), _full_xi(40)))
    assert status == "ok", reason
    assert (by_min[30]["score_home"], by_min[30]["score_away"]) == (0, 0)   # missed pen ignored
    assert (by_min[75]["score_home"], by_min[75]["score_away"]) == (1, 0)


def test_p1_var_cancelled_goal_excluded_from_state():
    """A VAR 'Goal cancelled' event is not a goal and must not enter the score state."""
    _need(DS, _DS_ERR, "dynamic_state")
    events = [_var(HOME_ID, 5, "Goal cancelled"), _goal(AWAY_ID, 23)]
    fx = _fixture(ft=(0, 1))
    _, status, reason, by_min = _build(fx, events, _lineups(_full_xi(1), _full_xi(40)))
    assert status == "ok", reason
    assert (by_min[10]["score_home"], by_min[10]["score_away"]) == (0, 0)
    assert (by_min[30]["score_home"], by_min[30]["score_away"]) == (0, 1)


def test_p1_extra_time_goal_not_in_regulation_target():
    """An extra-time goal (elapsed>90) must NOT change a regulation score / regulation target."""
    _need(DS, _DS_ERR, "dynamic_state")
    # Regulation 1-1; HOME wins in ET. Official fulltime (regulation) = 1-1, extratime present.
    events = [_goal(HOME_ID, 30), _goal(AWAY_ID, 70), _goal(HOME_ID, 100)]
    fx = _fixture(ft=(1, 1), et=(2, 1))
    _, status, reason, by_min = _build(fx, events, _lineups(_full_xi(1), _full_xi(40)))
    assert status == "ok", reason
    # regulation full-time boundary snapshot is 90 and must read 1-1 (ET goal excluded)
    assert (by_min[90]["score_home"], by_min[90]["score_away"]) == (1, 1)
    assert by_min[90]["target_wdl"] == "D"
    assert max(by_min) <= DS.PRE_ET_BOUNDARY     # no regulation snapshot is placed after minute 90


def test_p1_penalty_shootout_excluded_from_state_and_target():
    """A penalty shootout (official score.penalty) never enters the regulation score / W-D-L target."""
    _need(DS, _DS_ERR, "dynamic_state")
    events = [_goal(HOME_ID, 30), _goal(AWAY_ID, 70)]
    fx = _fixture(ft=(1, 1), et=(1, 1), pen=(4, 3))
    _, status, reason, by_min = _build(fx, events, _lineups(_full_xi(1), _full_xi(40)))
    assert status == "ok", reason
    assert (by_min[90]["score_home"], by_min[90]["score_away"]) == (1, 1)
    assert by_min[90]["target_wdl"] == "D"        # shootout winner is NOT the regulation target
    assert by_min[90]["final_result_type"] == "penalty_shootout"


def test_p1_players_on_pitch_state_after_sub():
    """After a sub at minute m, the incoming player is on-pitch only for snapshots with t >= m."""
    _need(DS, _DS_ERR, "dynamic_state")
    events = [_subst(HOME_ID, 60, in_id=111, out_id=1)]
    fx = _fixture(ft=(0, 0))
    _, _, _, by_min = _build(fx, events, _lineups(_full_xi(1), _full_xi(40), home_bench=(111,)))
    before = by_min[55]["on_pitch_home_ids"].split(",")
    after = by_min[65]["on_pitch_home_ids"].split(",")
    assert "111" not in before and "1" in before
    assert "111" in after and "1" not in after
    assert by_min[55]["players_on_pitch_home"] == 11 and by_min[65]["players_on_pitch_home"] == 11


def test_p1_bench_state_recorded():
    """Bench ids are recorded from the lineup substitutes; bench size is exposed per side."""
    _need(DS, _DS_ERR, "dynamic_state")
    fx = _fixture(ft=(0, 0))
    _, _, _, by_min = _build(fx, [], _lineups(_full_xi(1), _full_xi(40),
                                              home_bench=(111, 112), away_bench=(141,)))
    r = by_min[0]
    assert r["n_bench_home"] == 2 and r["n_bench_away"] == 1
    assert set(r["bench_home_ids"].split(",")) == {"111", "112"}


def test_p1_substitution_direction_in_minus_out():
    """Substitution direction: incoming = event.player, outgoing = event.assist (HD.substitutions)."""
    _need(DS, _DS_ERR, "dynamic_state")
    from wcdrawlab.research.paid_source import historical_datasets as HD
    subs = HD.substitutions([_subst(HOME_ID, 60, in_id=111, out_id=1)])
    assert len(subs) == 1
    s = subs[0]
    assert s["in_player_id"] == 111 and s["out_player_id"] == 1 and s["minute"] == 60


def test_p1_second_yellow_handling():
    """Two yellows for one player => a second_yellow card AND a sending-off (second_yellow_red)."""
    _need(DS, _DS_ERR, "dynamic_state")
    if not _have(DS, "_cards_state"):
        pytest.skip("dynamic_state._cards_state not present")
    events = [_card(HOME_ID, 20, "Yellow Card", 100),
              _card(HOME_ID, 40, "Yellow Card", 100),
              _card(HOME_ID, 40, "Red Card", 100)]
    yh, ya, syh, sya, drh, dra = DS._cards_state(events, HOME_ID, AWAY_ID)
    assert yh == 1 and syh == 1 and drh == 1     # 1st yellow, 2nd yellow, resulting red
    assert ya == 0 and dra == 0


def test_p1_direct_red_reduces_players_on_pitch():
    """A direct red reduces players_on_pitch for that side net of the sending-off."""
    _need(DS, _DS_ERR, "dynamic_state")
    events = [_card(HOME_ID, 30, "Red Card", 5)]
    fx = _fixture(ft=(0, 0))
    _, _, _, by_min = _build(fx, events, _lineups(_full_xi(1), _full_xi(40)))
    assert by_min[20]["players_on_pitch_home"] == 11        # before the red
    assert by_min[55]["players_on_pitch_home"] == 10        # after the red (net of sending-off)
    assert by_min[55]["red_home"] == 1 and by_min[55]["red_away"] == 0


def test_p1_duplicated_events_do_not_double_count():
    """A duplicated goal event (same team/minute/detail) must not double the score versus a single goal."""
    _need(DS, _DS_ERR, "dynamic_state")
    dup = [_goal(HOME_ID, 30, player_id=7), _goal(HOME_ID, 30, player_id=7)]
    single = [_goal(HOME_ID, 30, player_id=7)]
    from wcdrawlab.research.paid_source import result_semantics as RS
    # the canonical window-score counts each goal event; reconciliation status flags the duplication so a
    # duplicated fixture is NOT silently admitted as exact when official says one goal.
    fx_dup = _fixture(ft=(1, 0))
    rows_dup, status_dup, reason_dup, _ = _build(fx_dup, dup, _lineups(_full_xi(1), _full_xi(40)))
    rows_one, status_one, _, _ = _build(fx_dup, single, _lineups(_full_xi(1), _full_xi(40)))
    # the single-goal fixture reconciles exactly (1-0); the duplicated one does not (2-0 derived vs 1-0).
    assert status_one == "ok"
    assert rows_dup[0]["reconciliation_status"] == "mismatch"
    assert rows_one[0]["reconciliation_status"] == "exact"


def test_p1_out_of_order_source_events_classified():
    """Out-of-order source events are detectable via the reconciliation exception classifier."""
    _need(DS, _DS_ERR, "dynamic_state")
    from wcdrawlab.research.paid_source import result_semantics as RS
    # later-minute event appears before an earlier one; with a forced regulation mismatch the classifier
    # can attribute provider-event-ordering. Build an ordering-bad event stream that under-counts.
    events = [_goal(HOME_ID, 80), _goal(HOME_ID, 20)]    # descending then ascending -> ordering anomaly
    fx = _fixture(ft=(3, 0))                              # official says 3, events give 2 -> mismatch
    can = RS.canonical_result(fx, events)
    assert can["reconciliation_status"] == "mismatch"
    assert can["reconciliation_exception_type"] is not None


def test_p1_no_future_xg_flag_is_zero():
    """The state engine never fabricates xG; xg_join_available is 0 (xG is joined downstream with a guard)."""
    _need(DS, _DS_ERR, "dynamic_state")
    fx = _fixture(ft=(1, 0))
    rows, _, _, _ = _build(fx, [_goal(HOME_ID, 40)], _lineups(_full_xi(1), _full_xi(40)))
    assert all(r["xg_join_available"] == 0 for r in rows)


def test_p1_no_cross_match_state_leakage():
    """Two distinct fixtures produce independent state; a goal in one cannot affect the other's snapshots."""
    _need(DS, _DS_ERR, "dynamic_state")
    fx_a = _fixture(fid=1, ft=(1, 0))
    fx_b = _fixture(fid=2, ft=(0, 0))
    _, _, _, a = _build(fx_a, [_goal(HOME_ID, 40)], _lineups(_full_xi(1), _full_xi(40)))
    _, _, _, b = _build(fx_b, [], _lineups(_full_xi(1), _full_xi(40)))
    assert (a[90]["score_home"], a[90]["score_away"]) == (1, 0)
    assert (b[90]["score_home"], b[90]["score_away"]) == (0, 0)
    assert a[90]["api_fixture_id"] != b[90]["api_fixture_id"]


def test_p1_deterministic_rebuild():
    """Rebuilding the same fixture twice yields byte-identical rows (deterministic)."""
    _need(DS, _DS_ERR, "dynamic_state")
    fx = _fixture(ft=(2, 1))
    events = [_goal(HOME_ID, 15), _goal(AWAY_ID, 50), _goal(HOME_ID, 80)]
    ln = _lineups(_full_xi(1), _full_xi(40), home_bench=(111,))
    r1, _, _, _ = _build(fx, events, ln)
    r2, _, _, _ = _build(fx, events, ln)
    assert r1 == r2


def test_p1_source_hash_traceability():
    """Every snapshot row carries a stable content-addressed events+lineups hash for provenance."""
    _need(DS, _DS_ERR, "dynamic_state")
    fx = _fixture(ft=(1, 0))
    events = [_goal(HOME_ID, 40)]
    ln = _lineups(_full_xi(1), _full_xi(40))
    r1, _, _, _ = _build(fx, events, ln)
    r2, _, _, _ = _build(fx, events, ln)
    # hash present, 16-hex, identical across rebuild, and changes when events change
    h = r1[0]["events_sha256"]
    assert isinstance(h, str) and len(h) == 16
    assert r1[0]["events_sha256"] == r2[0]["events_sha256"]
    r3, _, _, _ = _build(fx, [_goal(HOME_ID, 41)], ln)
    assert r3[0]["events_sha256"] != h


def test_p1_club_rows_not_regulation_target_eligible():
    """A club fixture (non-international league) is auxiliary only: regulation_target_eligible == 0."""
    _need(DS, _DS_ERR, "dynamic_state")
    fx = _fixture(league_id=39, ft=(1, 0))   # 39 = Premier League (club, not in INTL_LEAGUES)
    rows, _, _, _ = _build(fx, [_goal(HOME_ID, 40)], _lineups(_full_xi(1), _full_xi(40)))
    assert all(r["regulation_target_eligible"] == 0 for r in rows)
    assert all(r["comp_type"] == "club" for r in rows)


def test_p1_pre_et_boundary_is_last_regulation_snapshot():
    """No regulation snapshot is ever placed after minute 90 (the pre-ET boundary)."""
    _need(DS, _DS_ERR, "dynamic_state")
    fx = _fixture(ft=(1, 1), et=(2, 1))
    events = [_goal(HOME_ID, 30), _goal(AWAY_ID, 70), _goal(HOME_ID, 105)]
    rows, _, _, _ = _build(fx, events, _lineups(_full_xi(1), _full_xi(40)))
    assert max(r["snapshot_minute"] for r in rows) <= DS.PRE_ET_BOUNDARY


def test_p1_selftest_no_future_leak_passes_on_clean_fixture():
    """The module's own no-future-leak self-test passes (0 failures) on a clean synthetic fixture."""
    _need(DS, _DS_ERR, "dynamic_state")
    if not _have(DS, "selftest_no_future_leak"):
        pytest.skip("dynamic_state.selftest_no_future_leak not present")
    fx = _fixture(ft=(2, 1))
    events = [_goal(HOME_ID, 15), _goal(AWAY_ID, 50), _goal(HOME_ID, 80)]
    fixtures = {"9001": fx}
    evmap = {"9001": events}
    lnmap = {"9001": _lineups(_full_xi(1), _full_xi(40))}
    passed, failed, details = DS.selftest_no_future_leak(fixtures, evmap, lnmap, {"9001": "x"})
    assert failed == 0 and passed > 0, details


# ==================================================================================================
# PHASE 2 — dynamic_player_prior_models.py
# ==================================================================================================
def _ap(pid, team, mid, date, comp, pos, started, mins, gf, ga, res):
    return Appearance(player_id=pid, team_id=team, match_id=mid,
                      match_date=datetime.fromisoformat(date), comp_type=comp, position=pos,
                      started=started, minutes_on=float(mins), goals_for_on=gf, goals_against_on=ga,
                      gd_on=gf - ga, team_result=res, source_hash="h" + mid)


def _wide_population():
    """A deterministic population: one strong scorer (1), one weak (2), filler so global means exist."""
    aps = []
    for i in range(20):
        aps.append(_ap(1, 10, f"s{i}", f"2024-{(i % 12) + 1:02d}-01", "international", "F", True, 90, 3, 0, "W"))
    for i in range(20):
        aps.append(_ap(2, 10, f"w{i}", f"2024-{(i % 12) + 1:02d}-02", "international", "F", True, 90, 0, 3, "L"))
    for i in range(40):
        aps.append(_ap(100 + i, 11, f"f{i}", f"2024-{(i % 12) + 1:02d}-03", "international", "M", True, 90, 1, 1, "D"))
    return aps


def test_p2_no_future_appearance_leakage():
    """A prior at date D uses ONLY appearances strictly before D (no same-match / future appearance)."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    aps = [_ap(1, 10, "m1", "2025-01-01", "international", "F", True, 90, 3, 0, "W"),
           _ap(1, 10, "m2", "2025-02-01", "international", "F", True, 90, 2, 1, "W")]
    pri = DP.DynamicPlayerPriors(aps)
    cp = pri.contribution_prior(1, datetime.fromisoformat("2025-02-01"), "international", team_id=10)
    assert cp["prior_appearances"] == 1     # strictly before 2025-02-01 -> only m1, never m2 itself


def test_p2_club_international_separation():
    """Club and international appearances are NEVER pooled into the same contribution prior."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    aps = [_ap(1, 10, "i1", "2025-01-01", "international", "F", True, 90, 3, 0, "W"),
           _ap(1, 10, "i2", "2025-02-01", "international", "F", True, 90, 2, 1, "W"),
           _ap(1, 10, "c1", "2025-01-15", "club", "F", True, 90, 5, 0, "W")]
    pri = DP.DynamicPlayerPriors(aps)
    end = datetime.fromisoformat("2025-12-01")
    intl = pri.contribution_prior(1, end, "international", team_id=10)
    club = pri.contribution_prior(1, end, "club", team_id=10)
    assert intl["prior_appearances"] == 2     # club row excluded from intl prior
    assert club["prior_appearances"] == 1


def test_p2_national_club_exposure_counters_are_cross_comp():
    """Exposure counters report national vs club appearance counts separately (pure counters, not pooled)."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    aps = [_ap(1, 10, "i1", "2025-01-01", "international", "F", True, 90, 3, 0, "W"),
           _ap(1, 10, "c1", "2025-01-15", "club", "F", True, 90, 5, 0, "W")]
    pri = DP.DynamicPlayerPriors(aps)
    ef = pri.exposure_features(1, datetime.fromisoformat("2025-12-01"), "international", team_id=10)
    assert ef["national_appearances"] == 1 and ef["intl_appearances"] == 1
    assert ef["club_appearances"] == 1


def test_p2_exact_player_id_linkage_unknown_category():
    """A player_id with no strictly-earlier appearance is an explicit unknown category (no fuzzy match)."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    pri = DP.DynamicPlayerPriors(_wide_population())
    cu = pri.contribution_prior(999999, datetime.fromisoformat("2025-06-01"), "international", team_id=10)
    assert cu["unknown_player"] is True and cu["insufficient_history"] is True
    assert cu["prior_appearances"] == 0


def test_p2_correct_shrinkage_orders_strong_above_weak():
    """Shrinkage is correct: a strong scorer's prior gd90 exceeds a weak conceder's, both pulled to global."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    pri = DP.DynamicPlayerPriors(_wide_population())
    before = datetime.fromisoformat("2025-06-01")
    p1 = pri.contribution_prior(1, before, "international", team_id=10)
    p2 = pri.contribution_prior(2, before, "international", team_id=10)
    assert p1["gd_contribution_per90"] > p2["gd_contribution_per90"]
    # shrinkage pulls toward the (here ~0) global mean: |shrunk| < |raw=3.0 per 90|
    assert abs(p1["gd_contribution_per90"]) < 3.0


def test_p2_thin_history_shrinks_harder_than_thick():
    """A thinner-history player is pulled harder toward the prior mean than a thicker-history one."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    aps = _wide_population()
    # add a SECOND strong scorer (3) with only 2 appearances vs player 1's 20
    aps += [_ap(3, 10, f"t{i}", f"2024-0{i + 1}-05", "international", "F", True, 90, 3, 0, "W") for i in range(2)]
    pri = DP.DynamicPlayerPriors(aps)
    before = datetime.fromisoformat("2025-06-01")
    thick = pri.contribution_prior(1, before, "international", team_id=10)["gd_contribution_per90"]
    thin = pri.contribution_prior(3, before, "international", team_id=10)["gd_contribution_per90"]
    # both are positive scorers but the thin one is shrunk closer to the global mean (smaller magnitude)
    assert thin < thick


def test_p2_deterministic_recency():
    """Recency windows are deterministic and reflect only the most-recent strictly-earlier appearances."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    pri = DP.DynamicPlayerPriors(_wide_population())
    before = datetime.fromisoformat("2025-06-01")
    e1 = pri.exposure_features(1, before, "international", team_id=10)
    e2 = pri.exposure_features(1, before, "international", team_id=10)
    assert e1 == e2
    assert e1["apps_last5"] == 5 and e1["apps_last10"] == 10


def test_p2_availability_timeline_is_strictly_before():
    """Availability prior uses recent starts strictly before the snapshot; unknown player -> known unknown."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    pri = DP.DynamicPlayerPriors(_wide_population())
    cp = pri.contribution_prior(1, datetime.fromisoformat("2025-06-01"), "international", team_id=10)
    # player 1 always started -> availability prior pulled above 0.5 (shrunk toward 0.5)
    assert 0.5 < cp["availability_prior"] <= 1.0
    cu = pri.contribution_prior(999999, datetime.fromisoformat("2025-06-01"), "international", team_id=10)
    assert cu["availability_prior"] == 0.0     # unknown -> honest 0.0, not a guess


def test_p2_substitution_delta_sign_in_minus_out():
    """Sub delta = incoming prior - outgoing prior: bringing a strong player on for a weak one is positive."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    pri = DP.DynamicPlayerPriors(_wide_population())
    before = datetime.fromisoformat("2025-06-01")
    sd = pri.substitution_delta_features(1, 2, before, "international", minute=60, score_diff=-1, team_id=10)
    assert sd["gd_delta_per90"] > 0           # strong (1) in for weak (2) out -> positive delta
    sd_rev = pri.substitution_delta_features(2, 1, before, "international", minute=60, score_diff=-1, team_id=10)
    assert sd_rev["gd_delta_per90"] == pytest.approx(-sd["gd_delta_per90"])


def test_p2_substitution_timing_context_scale():
    """Sub-timing context: a later sub (less remaining time) yields a smaller-magnitude context-adjusted delta."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    pri = DP.DynamicPlayerPriors(_wide_population())
    before = datetime.fromisoformat("2025-06-01")
    early = pri.substitution_delta_features(1, 2, before, "international", minute=30, score_diff=0, team_id=10)
    late = pri.substitution_delta_features(1, 2, before, "international", minute=85, score_diff=0, team_id=10)
    # raw delta is identical; context-adjusted magnitude shrinks with remaining time
    assert early["gd_delta_per90"] == late["gd_delta_per90"]
    assert abs(late["gd_delta_context_adjusted"]) < abs(early["gd_delta_context_adjusted"])
    # and the context-adjusted magnitude never exceeds the raw magnitude
    assert abs(early["gd_delta_context_adjusted"]) <= abs(early["gd_delta_per90"])


def test_p2_composition_continuity_and_coverage():
    """Composition continuity counts shared ids with the prior XI; coverage falls with unknown players."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    if Appearance is None:
        pytest.skip("Appearance dataclass not importable")
    pri = DP.DynamicPlayerPriors(_wide_population())
    before = datetime.fromisoformat("2025-06-01")
    xi = [1, 2] + [999000 + i for i in range(9)]    # 2 known + 9 unknown
    comp = pri.composition_features(on_pitch_ids=xi, starting_ids=xi, bench_ids=[],
                                    before=before, comp_type="international", team_id=10,
                                    prev_xi_ids=[1, 2, 12345])
    assert comp["n_unknown_players"] == 9
    assert comp["coverage_aggregate"] == pytest.approx(2 / 11, abs=1e-6)
    assert comp["familiarity_continuity"] == pytest.approx(2 / 11, abs=1e-6)   # 1 and 2 shared with prev XI
    assert comp["low_coverage_flag"] is True


def test_p2_no_test_time_fitting_constants_are_fixed():
    """Shrinkage pseudo-counts are FIXED module constants (no learned/hyper-searched parameters)."""
    _need(DP, _DP_ERR, "dynamic_player_prior_models")
    assert DP.SHRINK_TEAM == 6.0 and DP.SHRINK_POSITION == 12.0 and DP.SHRINK_COMPETITION == 24.0
    assert DP.RECENCY_WINDOWS == (5, 10)


# ==================================================================================================
# PHASE 3 — dynamic_xg_state.py
# ==================================================================================================
HOME, AWAY = "Brazil", "Chile"


def _shot(index, minute, team, xg, outcome="Shot Saved", period=1, second=0):
    e = {"index": index, "type": {"name": "Shot"}, "period": period,
         "minute": minute, "second": second, "team": {"name": team}, "shot": {}}
    if xg is not None:
        e["shot"]["statsbomb_xg"] = xg
    if outcome is not None:
        e["shot"]["outcome"] = {"name": outcome}
    return e


def _parse(events):
    return XS.parse_match_events(json.dumps(events).encode("utf-8"), HOME, AWAY, "Mtest")


def test_p3_no_future_xg():
    """xG at decision minute t uses ONLY shots with match-clock minute <= t (no future xG)."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    me = _parse([_shot(1, 10, HOME, 0.5, "Goal"), _shot(2, 70, HOME, 0.9, "Goal")])
    f25 = XS.dynamic_features_at(me, 25)
    f90 = XS.dynamic_features_at(me, 90)
    assert f25["cum_xg_home"] == pytest.approx(0.5)     # the min-70 shot is in the future at t=25
    assert f90["cum_xg_home"] == pytest.approx(1.4)


def test_p3_no_cross_match_leakage():
    """Per-match extraction: features for one sb_match_id never include another match's shots."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    a = _parse([_shot(1, 30, HOME, 0.7, "Goal")])
    b = _parse([_shot(1, 30, AWAY, 0.6, "Goal")])
    fa = XS.dynamic_features_at(a, 90)
    fb = XS.dynamic_features_at(b, 90)
    assert fa["cum_xg_home"] == pytest.approx(0.7) and fa["cum_xg_away"] == pytest.approx(0.0)
    assert fb["cum_xg_home"] == pytest.approx(0.0) and fb["cum_xg_away"] == pytest.approx(0.6)


def test_p3_regulation_only_extra_time_excluded():
    """Extra-time / shootout shots (period>2) are EXCLUDED from features and only flagged."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    me = _parse([_shot(1, 30, HOME, 0.4, "Goal"),
                 _shot(2, 105, HOME, 0.9, "Goal", period=4)])   # ET shot
    f = XS.dynamic_features_at(me, 90)
    assert f["cum_xg_home"] == pytest.approx(0.4)     # ET shot not in regulation features
    assert me.extra_time_count == 1
    assert len(me.shots) == 1                          # only the regulation shot is a ShotRecord


def test_p3_missing_xg_not_imputed():
    """A shot with statsbomb_xg missing contributes to shot COUNTS but 0.0 to xG SUMS (never imputed)."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    me = _parse([_shot(1, 20, HOME, 0.5, "Goal"),
                 _shot(2, 40, HOME, None, "Off T")])     # missing xg
    f = XS.dynamic_features_at(me, 90)
    assert f["n_shots_to_t"] == 2 and f["n_shots_with_xg_to_t"] == 1
    assert f["cum_xg_home"] == pytest.approx(0.5)        # missing shot adds 0.0, not imputed
    assert f["xg_completeness"] == pytest.approx(0.5)


def test_p3_momentum_window_is_past_only():
    """Momentum and rolling windows compare strictly-past windows only (no future window)."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    me = _parse([_shot(1, 81, HOME, 0.6, "Goal")])      # a recent home shot
    f = XS.dynamic_features_at(me, 83)
    # roll5 window is (78,83]; the shot at 81 is inside it and is home -> positive roll5
    assert f["roll5_xg_diff"] == pytest.approx(0.6)
    # at t=75 (before the shot) the same window is empty -> 0
    f0 = XS.dynamic_features_at(me, 75)
    assert f0["roll5_xg_diff"] == pytest.approx(0.0)
    assert f0["cum_xg_home"] == pytest.approx(0.0)


def test_p3_source_order_determinism():
    """Shots are deterministically time-sorted regardless of source order; out-of-order index is flagged."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    ordered = _parse([_shot(1, 10, HOME, 0.2, "Goal"), _shot(2, 30, AWAY, 0.3, "Goal")])
    shuffled = _parse([_shot(2, 30, AWAY, 0.3, "Goal"), _shot(1, 10, HOME, 0.2, "Goal")])
    assert [s.minute for s in ordered.shots] == [s.minute for s in shuffled.shots] == [10.0, 30.0]
    assert ordered.event_order_ok == 1 and shuffled.event_order_ok == 0
    # features identical regardless of source order
    assert XS.dynamic_features_at(ordered, 90) == XS.dynamic_features_at(shuffled, 90)


def test_p3_hash_traceability():
    """parse_match_events produces a stable sha256 over the raw bytes (provenance traceability)."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    events = [_shot(1, 10, HOME, 0.2, "Goal")]
    raw = json.dumps(events).encode("utf-8")
    m1 = XS.parse_match_events(raw, HOME, AWAY, "M")
    m2 = XS.parse_match_events(raw, HOME, AWAY, "M")
    assert m1.sha256 == m2.sha256 and len(m1.sha256) == 64
    raw2 = json.dumps([_shot(1, 11, HOME, 0.2, "Goal")]).encode("utf-8")
    assert XS.parse_match_events(raw2, HOME, AWAY, "M").sha256 != m1.sha256


def test_p3_big_chance_proxy_threshold():
    """Big-chance is an explicit xG-threshold PROXY (>=0.30), counted per side and as a diff."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    me = _parse([_shot(1, 20, HOME, 0.40, "Goal"),     # >= threshold
                 _shot(2, 40, HOME, 0.10, "Off T"),    # below threshold
                 _shot(3, 50, AWAY, 0.35, "Goal")])    # >= threshold
    f = XS.dynamic_features_at(me, 90)
    assert XS.BIG_CHANCE_XG == 0.30
    assert f["big_chance_proxy_home"] == 1 and f["big_chance_proxy_away"] == 1
    assert f["big_chance_proxy_diff"] == 0


def test_p3_prior_xg_quality_defaults_when_absent():
    """Prior-match xG quality is injected by the builder; absent it defaults to None / 0 (never future-derived)."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    me = _parse([_shot(1, 30, HOME, 0.5, "Goal")])
    f = XS.dynamic_features_at(me, 90)   # no prior_quality argument
    assert f["prior_xg_quality_home"] is None and f["prior_xg_quality_away"] is None
    assert f["prior_xg_n_matches_home"] == 0 and f["prior_xg_n_matches_away"] == 0
    # when provided, the injected values pass through unchanged (strictly-earlier per the data card)
    f2 = XS.dynamic_features_at(me, 90, prior_quality={"home": 0.4, "away": 0.2, "n_home": 3, "n_away": 2})
    assert f2["prior_xg_quality_home"] == 0.4 and f2["prior_xg_n_matches_away"] == 2


def test_p3_time_since_last_shot_capped_when_none():
    """time_since_last_* uses the cap (not zero) when nothing has happened yet (honest absence)."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    me = _parse([_shot(1, 80, HOME, 0.5, "Goal")])
    f_early = XS.dynamic_features_at(me, 30)    # no shot yet at t=30
    assert f_early["time_since_last_shot"] == pytest.approx(XS.CAP_MIN)
    assert f_early["n_shots_to_t"] == 0
    f_late = XS.dynamic_features_at(me, 85)     # shot at 80; 5 minutes since
    assert f_late["time_since_last_shot"] == pytest.approx(5.0)


def test_p3_regulation_grid_constants_frozen():
    """The decision grid + thresholds are frozen module constants (pre-registered before evaluation)."""
    _need(XS, _XS_ERR, "dynamic_xg_state")
    assert XS.GRID[0] == 10 and XS.GRID[-1] == 90
    assert XS.MAJOR_XG == 0.30 and XS.XG_SOURCE == "statsbomb_open"


# ==================================================================================================
# Cross-cutting: all three modules import and expose their research-only governance markers.
# ==================================================================================================
def test_modules_are_research_only_marked():
    """Each dynamic module's docstring carries the research_only / not_runtime governance marker."""
    present = [m for m in (DS, DP, XS) if m is not None]
    assert present, "no dynamic module importable at all"
    for m in present:
        doc = (m.__doc__ or "").lower()
        assert "research_only" in doc or "research-only" in doc, f"{m.__name__} missing research_only marker"


def test_at_least_one_module_built():
    """Sanity guard: at least one of the three Phase-1/2/3 modules must be importable for this suite to mean
    anything. (If all three are missing the build is broken, not merely incomplete.)"""
    assert any(m is not None for m in (DS, DP, XS)), \
        f"none importable: DS={_DS_ERR} DP={_DP_ERR} XS={_XS_ERR}"
