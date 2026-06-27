"""DETERMINISTIC INTEGRITY TESTS for the event-process intelligence stack.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Exercises the leakage-safety, regulation/ET separation, shootout exclusion, club/international separation,
possession/territory/transition correctness, source-availability classification, deterministic rebuild,
source-hash traceability, and the canonical model registry of:

  * src/wcdrawlab/research/event_process/snapshot_features.py   (causal snapshot engine)
  * src/wcdrawlab/research/event_process/canonical_events.py    (provider-neutral adapter)
  * src/wcdrawlab/research/event_process/contracts.py           (source-quality vocabulary)
  * src/wcdrawlab/research/event_process/registry.py            (canonical model IDs)
  * src/wcdrawlab/research/event_process/models.py              (e0-e9 / q0-q4 / h0-h3 / y0-y2 families)
  * src/wcdrawlab/research/event_process/eval.py                (leakage-safe loader + protocols)

Everything is built from SMALL, fully deterministic, in-memory synthetic StatsBomb-shaped fixtures — NO
network, NO disk reads, NO API/StatsBomb downloads. If a symbol a test needs is absent, that single test
SKIPs with an explicit reason rather than crashing collection. >=50 tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# ---- import modules under test; missing modules SKIP (never crash collection) -------------------
try:
    from wcdrawlab.research.event_process import snapshot_features as SF
except Exception as _e:                                   # pragma: no cover
    SF = None
    _SF_ERR = repr(_e)
else:
    _SF_ERR = ""

try:
    from wcdrawlab.research.event_process import canonical_events as CE
except Exception as _e:                                   # pragma: no cover
    CE = None
    _CE_ERR = repr(_e)
else:
    _CE_ERR = ""

try:
    from wcdrawlab.research.event_process import contracts as C
except Exception as _e:                                   # pragma: no cover
    C = None
    _C_ERR = repr(_e)
else:
    _C_ERR = ""

try:
    from wcdrawlab.research.event_process import registry as REG
except Exception as _e:                                   # pragma: no cover
    REG = None
    _REG_ERR = repr(_e)
else:
    _REG_ERR = ""

try:
    from wcdrawlab.research.event_process import models as M
except Exception as _e:                                   # pragma: no cover
    M = None
    _M_ERR = repr(_e)
else:
    _M_ERR = ""

try:
    from wcdrawlab.research.event_process import eval as EV
except Exception as _e:                                   # pragma: no cover
    EV = None
    _EV_ERR = repr(_e)
else:
    _EV_ERR = ""

req_sf = pytest.mark.skipif(SF is None, reason=f"snapshot_features unavailable: {_SF_ERR}")
req_ce = pytest.mark.skipif(CE is None, reason=f"canonical_events unavailable: {_CE_ERR}")
req_c = pytest.mark.skipif(C is None, reason=f"contracts unavailable: {_C_ERR}")
req_reg = pytest.mark.skipif(REG is None, reason=f"registry unavailable: {_REG_ERR}")
req_m = pytest.mark.skipif(M is None, reason=f"models unavailable: {_M_ERR}")
req_ev = pytest.mark.skipif(EV is None, reason=f"eval unavailable: {_EV_ERR}")


# =================================================================================================
# deterministic synthetic StatsBomb-shaped fixtures
# =================================================================================================
def _xi(idx, tid, name):
    return {"index": idx, "period": 1, "minute": 0, "second": 0,
            "type": {"name": "Starting XI"}, "team": {"id": tid, "name": name}}


def _shot(idx, minute, second, tid, xg, outcome="Saved", loc=(110.0, 40.0)):
    return {"index": idx, "period": 1 if minute < 45 else 2, "minute": minute, "second": second,
            "type": {"name": "Shot"}, "team": {"id": tid}, "location": list(loc),
            "shot": {"statsbomb_xg": xg, "outcome": {"name": outcome}}}


def _pass(idx, minute, tid, loc, end, ptype=None, outcome=None):
    p = {"end_location": list(end)}
    if ptype:
        p["type"] = {"name": ptype}
    if outcome:
        p["outcome"] = {"name": outcome}
    return {"index": idx, "period": 1 if minute < 45 else 2, "minute": minute, "second": 0,
            "type": {"name": "Pass"}, "team": {"id": tid}, "location": list(loc), "pass": p}


def _carry(idx, minute, tid, loc, end):
    return {"index": idx, "period": 1 if minute < 45 else 2, "minute": minute, "second": 0,
            "type": {"name": "Carry"}, "team": {"id": tid}, "location": list(loc),
            "carry": {"end_location": list(end)}}


def _ev(idx, minute, tid, tname, loc=None):
    e = {"index": idx, "period": 1 if minute < 45 else 2, "minute": minute, "second": 0,
         "type": {"name": tname}, "team": {"id": tid}}
    if loc:
        e["location"] = list(loc)
    return e


def _card(idx, minute, tid, card_name):
    return {"index": idx, "period": 1 if minute < 45 else 2, "minute": minute, "second": 0,
            "type": {"name": "Foul Committed"}, "team": {"id": tid},
            "foul_committed": {"card": {"name": card_name}}}


def _sub(idx, minute, tid):
    return {"index": idx, "period": 1 if minute < 45 else 2, "minute": minute, "second": 0,
            "type": {"name": "Substitution"}, "team": {"id": tid}}


def base_match():
    """Home(1) scores @10; Away(2) scores @70 (level); plenty of process events; ET shot + shootout
    must be excluded from regulation. Deterministic and self-contained."""
    return [
        _xi(1, 1, "Home"), _xi(2, 2, "Away"),
        # home build-up: completed passes, a carry, a final-third action, a box entry, a corner
        _pass(5, 8, 1, (60, 40), (90, 40)),                              # completed pass (home)
        _carry(6, 8, 1, (90, 40), (100, 40)),                            # carry (home) final third
        _pass(7, 9, 1, (100, 40), (110, 40)),                            # box entry (home)
        _pass(8, 9, 1, (120, 0.5), (110, 40), ptype="Corner"),           # corner (home)
        _shot(10, 10, 0, 1, 0.30, outcome="Goal"),                       # HOME GOAL @10
        _ev(11, 12, 1, "Ball Recovery", (60, 40)),                       # recovery (home)
        _ev(12, 13, 2, "Dispossessed", (50, 40)),                        # turnover (away)
        _pass(13, 20, 2, (40, 40), (70, 40), outcome="Incomplete"),      # INCOMPLETE pass (away) -> not poss
        _shot(20, 30, 0, 2, 0.10, outcome="Saved"),                      # away shot @30
        _card(21, 35, 2, "Yellow Card"),                                 # away yellow @35
        _sub(22, 60, 1),                                                 # home sub @60
        _shot(30, 70, 0, 2, 0.40, outcome="Goal"),                       # AWAY GOAL @70 (level 1-1)
        # extra time (period 3) + shootout (period 5) -> excluded from regulation
        {"index": 40, "period": 3, "minute": 95, "second": 0, "type": {"name": "Shot"},
         "team": {"id": 1}, "location": [110, 40], "shot": {"statsbomb_xg": 0.5, "outcome": {"name": "Goal"}}},
        {"index": 50, "period": 5, "minute": 120, "second": 0, "type": {"name": "Shot"},
         "team": {"id": 2}, "location": [108, 40], "shot": {"statsbomb_xg": 0.7, "outcome": {"name": "Goal"}}},
    ]


def sendoff_match():
    """Away(2) gets a straight red @50; home(1) up a man for the rest."""
    return [
        _xi(1, 1, "Home"), _xi(2, 2, "Away"),
        _shot(10, 20, 0, 1, 0.2, outcome="Saved"),
        _card(20, 50, 2, "Red Card"),
        _shot(30, 80, 0, 1, 0.3, outcome="Goal"),  # home goal @80 -> H win 1-0
    ]


@pytest.fixture
def ctx_base():
    return SF.prepare_match(base_match(), "synthetic_base")


@pytest.fixture
def ctx_sendoff():
    return SF.prepare_match(sendoff_match(), "synthetic_sendoff")


# =================================================================================================
# 1) leakage gate: events_up_to + snapshot truncation
# =================================================================================================
@req_sf
def test_events_up_to_excludes_future(ctx_base):
    ev = base_match()
    sliced = SF.events_up_to(ev, 30.0)
    assert all(SF.event_clock(e) <= 30.0 + 1e-9 for e in sliced)


@req_sf
def test_events_up_to_excludes_extra_time(ctx_base):
    ev = base_match()
    sliced = SF.events_up_to(ev, 90.0)
    assert all(e.get("period") in (1, 2) for e in sliced)
    assert not any(e.get("period", 0) >= 3 for e in sliced)


@req_sf
def test_snapshot_score_no_future_goal_leak(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 30.0, "clock")
    assert snap["goals_home"] == 1 and snap["goals_away"] == 0  # away goal @70 invisible


@req_sf
def test_snapshot_at_5_sees_no_goal(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 5.0, "clock")
    assert snap["goals_home"] == 0 and snap["goals_away"] == 0  # home goal @10 invisible at t=5


@req_sf
def test_snapshot_shot_count_truncated(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 30.0, "clock")
    assert snap["shots_home"] == 1 and snap["shots_away"] == 1  # away goal-shot @70 excluded


@req_sf
def test_snapshot_xg_no_future(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 30.0, "clock")
    assert abs(snap["cum_xg_home"] - 0.30) < 1e-6
    assert abs(snap["cum_xg_away"] - 0.10) < 1e-6  # the 0.40 @70 must not leak


@req_sf
def test_snapshot_monotone_goals_in_minute(ctx_base):
    ev = base_match()
    prev = -1
    for t in (5, 10, 30, 45, 60, 75):
        g = SF.snapshot_features(ev, ctx_base, float(t), "clock")["goals_home"]
        assert g >= prev
        prev = g


@req_sf
def test_no_xg_leak_window(ctx_base):
    # at t=30 there is no shot in the last 5 minutes (shots @10 and @30 only)
    snap = SF.snapshot_features(base_match(), ctx_base, 30.0, "clock")
    # last-5m window from 25..30 includes the @30 away shot
    assert snap["shots_last5m_away"] == 1
    assert snap["shots_last5m_home"] == 0


# =================================================================================================
# 2) regulation / extra-time / shootout separation in targets
# =================================================================================================
@req_sf
def test_regulation_final_excludes_et(ctx_base):
    fin = SF.regulation_final(base_match(), ctx_base)
    assert fin["target_wdl"] == "D"  # 1-1 in regulation; ET/shootout goals excluded
    assert fin["reg_home_goals"] == 1 and fin["reg_away_goals"] == 1


@req_sf
def test_regulation_event_flag():
    assert SF.is_regulation_event({"period": 1})
    assert SF.is_regulation_event({"period": 2})
    assert not SF.is_regulation_event({"period": 3})
    assert not SF.is_regulation_event({"period": 5})


@req_sf
def test_next_goal_after_excludes_et(ctx_base):
    ng = SF.next_goal_after(base_match(), ctx_base, 30.0)
    assert ng["next_goal_side"] == "away"  # the @70 regulation goal, not the @95 ET goal


@req_sf
def test_next_goal_none_when_no_future_goal(ctx_base):
    ng = SF.next_goal_after(base_match(), ctx_base, 75.0)
    assert ng["next_goal_side"] == "none"  # both regulation goals are before 75


@req_sf
def test_scoring_window_horizon(ctx_base):
    sw = SF.scoring_in_window(base_match(), ctx_base, 30.0, 45)
    assert sw["away_scores_next45m"] == 1 and sw["home_scores_next45m"] == 0


@req_sf
def test_scoring_window_excludes_et(ctx_base):
    # window beyond 90 is clamped; ET goal @95 never counts
    sw = SF.scoring_in_window(base_match(), ctx_base, 85.0, 15)
    assert sw["home_scores_next15m"] == 0 and sw["away_scores_next15m"] == 0


@req_sf
def test_pre_extra_time_snapshot_only_when_et():
    ev = base_match()
    ctx = SF.prepare_match(ev, "m")
    sched = SF.snapshot_schedule(ev, ctx)
    assert ctx.has_extra_time is True
    # no scheduled snapshot exceeds regulation 90
    assert all(s["minute"] <= 90.0 + 1e-9 for s in sched)


# =================================================================================================
# 3) possession / territory / transition / set-piece correctness
# =================================================================================================
@req_sf
def test_possession_counts_completed_only(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    # away incomplete pass @20 must NOT add to away possession actions
    assert snap["poss_actions_home"] >= 1
    # the only away pass is incomplete -> away possession action count from passes is 0 (carry none)
    assert snap["poss_actions_away"] == 0


@req_sf
def test_territory_final_third(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    assert snap["final_third_actions_home"] >= 1


@req_sf
def test_box_entry_extracted(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    assert snap["box_entries_home"] >= 1


@req_sf
def test_corner_extracted(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    assert snap["corners_home"] >= 1


@req_sf
def test_transition_recovery_turnover(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    assert snap["recoveries_home"] >= 1
    assert snap["turnovers_away"] >= 1


@req_sf
def test_field_tilt_in_unit_interval(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    ft = snap.get("field_tilt_home")
    assert ft is None or (0.0 <= ft <= 1.0)


@req_sf
def test_poss_share_in_unit_interval(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    ps = snap.get("poss_share_home")
    assert ps is None or (0.0 <= ps <= 1.0)


@req_sf
def test_diff_equals_home_minus_away(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    assert snap["shots_diff"] == snap["shots_home"] - snap["shots_away"]
    assert snap["box_entries_diff"] == snap["box_entries_home"] - snap["box_entries_away"]


# =================================================================================================
# 4) cards / personnel / sending-off
# =================================================================================================
@req_sf
def test_yellow_card_counted(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    assert snap["yellow_away"] == 1 and snap["yellow_home"] == 0


@req_sf
def test_card_not_leaked_before_minute(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 30.0, "clock")
    assert snap["yellow_away"] == 0  # yellow is @35


@req_sf
def test_sendoff_reduces_players(ctx_sendoff):
    snap = SF.snapshot_features(sendoff_match(), ctx_sendoff, 60.0, "clock")
    assert snap["sendoff_away"] == 1
    assert snap["players_away"] == 10 and snap["players_home"] == 11
    assert snap["players_diff"] == 1


@req_sf
def test_sendoff_not_before_minute(ctx_sendoff):
    snap = SF.snapshot_features(sendoff_match(), ctx_sendoff, 45.0, "clock")
    assert snap["sendoff_away"] == 0 and snap["players_away"] == 11


@req_sf
def test_sub_counted(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 65.0, "clock")
    assert snap["subs_used_home"] == 1


@req_sf
def test_sub_not_before_minute(ctx_base):
    snap = SF.snapshot_features(base_match(), ctx_base, 45.0, "clock")
    assert snap["subs_used_home"] == 0  # sub is @60


# =================================================================================================
# 5) deterministic rebuild + source-hash traceability
# =================================================================================================
@req_sf
def test_deterministic_rebuild(ctx_base):
    ev = base_match()
    a = SF.snapshot_features(ev, ctx_base, 45.0, "clock")
    b = SF.snapshot_features(ev, ctx_base, 45.0, "clock")
    assert a == b


@req_sf
def test_snapshot_independent_of_event_order(ctx_base):
    ev = base_match()
    a = SF.snapshot_features(ev, ctx_base, 45.0, "clock")
    shuffled = list(reversed(ev))
    b = SF.snapshot_features(shuffled, ctx_base, 45.0, "clock")
    # the engine sorts by clock+index, so result must be identical
    for k in ("goals_home", "goals_away", "shots_home", "shots_away", "cum_xg_home"):
        assert a[k] == b[k]


@req_ce
def test_source_hash_traceability():
    raw = b'[{"index":1,"type":{"name":"Pass"}}]'
    h1 = CE.sha256_bytes(raw)
    h2 = CE.sha256_bytes(raw)
    assert h1 == h2 and len(h1) == 64
    assert CE.sha256_bytes(raw + b"x") != h1


@req_ce
def test_canonical_adapter_team_resolution():
    ev = base_match()
    canon, trace, (h, a) = CE.from_statsbomb(ev, "m", "deadbeef")
    assert h == 1 and a == 2
    assert trace.source_sha256 == "deadbeef"
    assert trace.n_source_events == len(ev)


@req_ce
def test_attacking_direction_inference():
    ev = base_match()
    d = CE.attacking_direction.__call__  # callable
    canon, trace, (h, a) = CE.from_statsbomb(ev, "m", "x")
    dh = CE.attacking_direction(canon, 1)
    assert dh in (1, -1, None)


# =================================================================================================
# 6) club / international separation + no cross-match leakage
# =================================================================================================
@req_sf
def test_no_cross_match_state_leak():
    # two independent matches must produce independent snapshots
    m1 = base_match()
    m2 = sendoff_match()
    c1 = SF.prepare_match(m1, "m1")
    c2 = SF.prepare_match(m2, "m2")
    s1 = SF.snapshot_features(m1, c1, 45.0, "clock")
    s2 = SF.snapshot_features(m2, c2, 45.0, "clock")
    # m1 has a yellow, m2 has none at 45; independence check
    assert s1["yellow_away"] == 1 and s2["yellow_away"] == 0


@req_ev
def test_club_rows_never_intl_population():
    # the international loader, if data present, must only return comp_type=='international'
    try:
        data = EV.load_eval_rows()
    except EV.DataInsufficient:
        pytest.skip("intl eval product absent in clean worktree")
    assert all(r.get("comp_type") == "international" for r in data["snapshot_rows"])


@req_ev
def test_no_2026_in_eval_population():
    rows = [{"competition_label": "FIFA World Cup 2026", "kickoff_date": "2026-06-15"}]
    with pytest.raises(AssertionError):
        EV.assert_no_2026(rows)


@req_ev
def test_assert_no_2026_passes_pre2026():
    rows = [{"competition_label": "FIFA World Cup 2022", "kickoff_date": "2022-11-20"}]
    EV.assert_no_2026(rows)  # must not raise


@req_ev
def test_2026_detector_handles_none():
    assert EV._is_2026_wc(None, None) is False


# =================================================================================================
# 7) source-availability classification (never imputed as 0)
# =================================================================================================
@req_sf
def test_source_quality_flags_valid(ctx_base):
    rep = SF.source_quality_report(base_match(), ctx_base)
    assert all(info["quality"] in C.QUALITY_FLAGS for info in rep.capabilities.values())


@req_sf
def test_source_quality_shot_xg_partial():
    # one shot with xG, one without -> xG capability should be partial
    ev = [_xi(1, 1, "H"), _xi(2, 2, "A"),
          _shot(10, 10, 0, 1, 0.2),
          {"index": 11, "period": 1, "minute": 20, "second": 0, "type": {"name": "Shot"},
           "team": {"id": 2}, "location": [110, 40], "shot": {"outcome": {"name": "Saved"}}}]
    ctx = SF.prepare_match(ev, "m")
    rep = SF.source_quality_report(ev, ctx)
    assert rep.capabilities["shot_xg"]["quality"] == C.AVAILABLE_PARTIAL


@req_sf
def test_source_quality_unavailable_when_absent():
    # no pressure events at all -> pressure capability unavailable
    ev = [_xi(1, 1, "H"), _xi(2, 2, "A"), _shot(10, 10, 0, 1, 0.2)]
    ctx = SF.prepare_match(ev, "m")
    rep = SF.source_quality_report(ev, ctx)
    assert rep.capabilities["pressure"]["quality"] == C.UNAVAILABLE


@req_sf
def test_time_since_last_shot_none_when_no_shot():
    ev = [_xi(1, 1, "H"), _xi(2, 2, "A"), _pass(5, 10, 1, (60, 40), (70, 40))]
    ctx = SF.prepare_match(ev, "m")
    snap = SF.snapshot_features(ev, ctx, 20.0, "clock")
    assert snap["min_since_last_shot_any"] is None  # None, NOT 0


@req_c
def test_field_quality_rejects_bad_flag():
    with pytest.raises(ValueError):
        C.FieldQuality(value=1, quality="totally_made_up")


@req_c
def test_quality_flags_constant():
    assert set(C.QUALITY_FLAGS) == {"available_verified", "available_partial", "unavailable", "unknown"}


# =================================================================================================
# 8) canonical model registry
# =================================================================================================
@req_reg
def test_registry_has_22_models():
    assert len(REG.ALL_MODELS) == 22


@req_reg
def test_registry_families_present():
    assert len(REG.EVENT_PROCESS_MODELS) == 10
    assert len(REG.NEXT_GOAL_MODELS) == 5
    assert len(REG.SCORING_MODELS) == 4
    assert len(REG.DISCIPLINE_MODELS) == 3


@req_reg
def test_registry_canonical_ids():
    assert REG.is_canonical("research.event_process.e2")
    assert REG.is_canonical("research.next_goal.q0")
    assert not REG.is_canonical("research.event_process.e99")
    assert not REG.is_canonical("M2")  # frozen M-models are NOT EP models


@req_reg
def test_registry_assert_raises_on_noncanonical():
    with pytest.raises(ValueError):
        REG.assert_canonical("not.a.model")


# =================================================================================================
# 9) model families (e0-e9 / q0-q4 / h0-h3 / y0-y2) behavior
# =================================================================================================
def _intl_rows(n_comp=2, per_comp=4):
    """Tiny deterministic intl-shaped eval rows for the model factories. Two competitions."""
    rows = []
    comps = [("CompA", "2018-06-01"), ("CompB", "2020-06-01")]
    mid = 0
    for ci in range(n_comp):
        cname, ko = comps[ci]
        for m in range(per_comp):
            mid += 1
            wdl = ["H", "D", "A"][(m) % 3]
            for t in (15, 30, 45, 60, 75):
                rows.append({
                    "match_id": f"{cname}_{mid}", "competition": cname, "competition_label": cname,
                    "kickoff_date": ko, "comp_type": "international",
                    "snapshot_minute": float(t), "remaining_regulation_min": float(90 - t),
                    "goals_diff": (1 if wdl == "H" else (-1 if wdl == "A" else 0)),
                    "goals_home": 1 if wdl == "H" else 0, "goals_away": 1 if wdl == "A" else 0,
                    "cum_xg_home": 0.3, "cum_xg_away": 0.2, "cum_xg_diff": 0.1, "cum_xg_total": 0.5,
                    "shots_home": 3, "shots_away": 2, "shots_diff": 1,
                    "shots_on_target_home": 1, "shots_on_target_away": 1, "shots_on_target_diff": 0,
                    "poss_share_home": 0.55, "poss_share_diff": 0.1, "field_tilt_home": 0.6,
                    "box_entries_diff": 1, "recoveries_diff": 0, "turnovers_diff": 0,
                    "corners_diff": 1, "att_free_kicks_diff": 0, "yellow_diff": 0, "sendoff_diff": 0,
                    "players_diff": 0, "subs_used_diff": 0,
                    "xg_last5m_diff": 0.0, "xg_last10m_diff": 0.0, "xg_momentum_diff_10m": 0.0,
                    "xg_acceleration_diff": 0.0, "xg_current_half_diff": 0.0,
                    "min_since_last_shot_any": 3.0,
                    "final_third_actions_diff": 1,
                    "rem_goals_home": 0.5, "rem_goals_away": 0.5,
                    "target_wdl": wdl,
                    "next_goal_any_15": (m % 2), "any_goal_next10m": (m % 2),
                    "any_goal_next5m": 0, "any_goal_next15m": (m % 2),
                    "sendoff_after": 0,
                })
    return rows


@req_m
def test_wdl_e2_is_probability_distribution():
    p = M.e2_reference({"remaining_regulation_min": 45.0, "goals_diff": 0})
    assert abs(sum(p.values()) - 1.0) < 1e-6
    assert all(0 <= v <= 1 for v in p.values())


@req_m
def test_wdl_e2_leading_team_favored():
    p = M.e2_reference({"remaining_regulation_min": 5.0, "goals_diff": 2})
    assert p["H"] > p["A"]  # 2-goal lead with 5 min left


@req_m
def test_wdl_intensity_convolution_sums_to_one():
    p = M.wdl_from_intensities(1.0, 1.0, 0)
    assert abs(sum(p.values()) - 1.0) < 1e-6


@req_m
def test_event_process_predictors_returns_all_e():
    preds = M.event_process_predictors(_intl_rows())
    for i in range(10):
        assert f"research.event_process.e{i}" in preds
    # every predictor returns a normalized distribution
    row = _intl_rows()[0]
    for mid, fn in preds.items():
        p = fn(row)
        assert abs(sum(p.values()) - 1.0) < 1e-6


@req_m
def test_next_goal_predictors_return_probabilities():
    preds = M.next_goal_predictors(_intl_rows())
    for i in range(5):
        assert f"research.next_goal.q{i}" in preds
    row = _intl_rows()[0]
    for fn in preds.values():
        p = fn(row)
        assert 0.0 <= p <= 1.0


@req_m
def test_scoring_predictors_return_probabilities():
    preds = M.scoring_predictors(_intl_rows())
    for i in range(4):
        assert f"research.scoring.h{i}" in preds
    row = _intl_rows()[0]
    for fn in preds.values():
        assert 0.0 <= fn(row) <= 1.0


@req_m
def test_discipline_gate_below_threshold():
    res = M.discipline_predictors(_intl_rows())  # 0 positives -> gate closed
    assert res["gate_open"] is False
    assert "research.discipline.y0" in res["predictors"]
    assert "research.discipline.y1" not in res["predictors"]  # honestly not fit


@req_m
def test_discipline_y0_base_rate():
    rows = _intl_rows()
    res = M.discipline_predictors(rows)
    y0 = res["predictors"]["research.discipline.y0"]
    assert 0.0 <= y0(rows[0]) <= 1.0


@req_m
def test_models_target_never_a_feature():
    # the e7 column set must not contain any target column
    targets = {"target_wdl", "next_goal_any_15", "any_goal_next5m", "any_goal_next10m",
               "any_goal_next15m", "sendoff_after", "rem_goals_home", "rem_goals_away"}
    assert not (set(M.FULL_STATE_COLS) & targets)
    assert not (set(M.NEXTGOAL_COLS) & targets)
    assert not (set(M.SCORING_COLS) & targets)
    assert not (set(M.DISCIPLINE_COLS) & targets)


@req_m
def test_club_aux_rep_zero_without_club_rows():
    rep = M.ClubAuxRep().fit([])  # no club rows
    assert rep.trained_on_club_rows == 0
    assert rep.value(_intl_rows()[0]) == 0.0


# =================================================================================================
# 10) eval protocols (deterministic, on synthetic intl rows)
# =================================================================================================
@req_ev
def test_forward_chain_runs_two_comps():
    rows = _intl_rows(n_comp=2, per_comp=4)
    res = EV.forward_chain_wdl(rows, predictor_factory=M.event_process_predictors)
    assert res["n_folds"] >= 1
    assert "research.event_process.e2" in res["pooled"]


@req_ev
def test_loco_runs_two_comps():
    rows = _intl_rows(n_comp=2, per_comp=4)
    res = EV.loco_wdl(rows, predictor_factory=M.event_process_predictors)
    assert res["n_folds"] == 2
    assert "research.event_process.e2" in res["per_model_match_rps"]


@req_ev
def test_loco_binary_next_goal():
    rows = _intl_rows(n_comp=2, per_comp=4)
    res = EV.loco_binary(rows, M.next_goal_predictors, "next_goal_any_15")
    assert res["n_folds"] == 2
    assert "research.next_goal.q0" in res["pooled"]


@req_ev
def test_paired_bootstrap_shape():
    pm = {"cand": {"m1": 0.2, "m2": 0.3, "m3": 0.25}, "ref": {"m1": 0.25, "m2": 0.35, "m3": 0.30}}
    res = EV.paired_bootstrap_delta(pm, "cand", "ref", n=200)
    assert res["n_matches"] == 3
    assert res["mean_delta"] < 0  # candidate strictly better on every match
    assert res["favors_candidate"] in (True, False)


@req_ev
def test_paired_bootstrap_empty():
    res = EV.paired_bootstrap_delta({"a": {}, "b": {}}, "a", "b")
    assert res["n_matches"] == 0 and res["favors_candidate"] is None


@req_ev
def test_score_wdl_perfect_prediction():
    rows = [{"match_id": "m", "target_wdl": "H"}]
    res = EV._score_wdl(lambda r: {"H": 1.0, "D": 0.0, "A": 0.0}, rows)
    assert res["rps"] == 0.0


@req_ev
def test_score_binary_perfect():
    rows = [{"match_id": "m", "next_goal_any_15": 1}]
    res = EV._score_binary(lambda r: 1.0 - 1e-9, rows, "next_goal_any_15")
    assert res["brier"] < 1e-12


# =================================================================================================
# 11) misc invariants
# =================================================================================================
@req_sf
def test_remaining_regulation_nonnegative(ctx_base):
    for t in (15, 45, 75, 90):
        snap = SF.snapshot_features(base_match(), ctx_base, float(t), "clock")
        assert snap["remaining_regulation_min"] >= 0


@req_sf
def test_engine_version_string():
    assert isinstance(SF.ENGINE_VERSION, str) and SF.ENGINE_VERSION


@req_sf
def test_match_completeness_flags(ctx_base):
    mc = SF.match_completeness(base_match(), ctx_base)
    assert mc["xg_coverage"] in C.QUALITY_FLAGS
    assert mc["has_extra_time"] is True


@req_sf
def test_period_label_from_minute(ctx_base):
    s1 = SF.snapshot_features(base_match(), ctx_base, 30.0, "clock")
    s2 = SF.snapshot_features(base_match(), ctx_base, 60.0, "clock")
    assert s1["period"] == 1 and s2["period"] == 2


@req_c
def test_pitch_geometry_constants():
    assert C.PITCH_LENGTH == 120.0 and C.PITCH_WIDTH == 80.0
    assert C.BOX_X < C.PITCH_LENGTH


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
