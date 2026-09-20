"""Deterministic integrity tests for the event-process MODEL FAMILIES + EVAL.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Exercises src/wcdrawlab/research/event_process/{models,eval}.py on SMALL, fully deterministic, in-memory
synthetic fixtures -- NO network, NO disk reads, NO API/StatsBomb downloads. Asserts REAL behaviour:
  * the e2 remaining-time Poisson reference yields finite, normalized W/D/L on any causal state;
  * the goal-intensity convolution is monotone in the leading side's remaining intensity;
  * all e0..e9 / q0..q4 / h0..h3 predict valid probabilities;
  * the discipline family GATES below 150 positives (preregistered);
  * a 2-fold forward chain returns numbers and the candidate rule emits a sanctioned verdict;
  * CLUB rows train the e8 aux rep but never appear as international test rows;
  * the harness REFUSES a 2026-World-Cup eval population (never fit/select on 2026).
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/research_jobs"))

from wcdrawlab.research.event_process import models as M  # noqa: E402
from wcdrawlab.research.event_process import eval as E  # noqa: E402
import _common as CM  # noqa: E402


def _row(comp, mid, t, cur_h, cur_a, fin_h, fin_a, kickoff, comp_type="international", **extra):
    base = {
        "match_id": mid, "competition": comp, "comp_type": comp_type, "kickoff_date": kickoff,
        "snapshot_minute": float(t), "remaining_regulation_min": 90.0 - float(t),
        "goals_home": cur_h, "goals_away": cur_a, "goals_diff": cur_h - cur_a,
        "target_wdl": "H" if fin_h > fin_a else ("A" if fin_a > fin_h else "D"),
        "rem_goals_home": fin_h - cur_h, "rem_goals_away": fin_a - cur_a,
        "cum_xg_home": 0.02 * t, "cum_xg_away": 0.02 * t, "cum_xg_diff": 0.0, "cum_xg_total": 0.04 * t,
        "xg_last5m_home": 0.05, "xg_last5m_away": 0.05, "xg_last10m_home": 0.1, "xg_last10m_away": 0.1,
        "xg_last5m_diff": 0.0, "xg_last10m_diff": 0.0, "xg_momentum_diff_10m": 0.0, "xg_acceleration_diff": 0.0,
        "shots_home": int(0.1 * t), "shots_away": int(0.1 * t),
        "shots_on_target_home": int(0.04 * t), "shots_on_target_away": int(0.04 * t),
        "shots_diff": 0, "shots_on_target_diff": 0,
        "poss_share_home": 0.5, "poss_share_diff": 0.0, "field_tilt_home": 0.5,
        "final_third_actions_home": 30, "final_third_actions_away": 30, "final_third_actions_diff": 0,
        "box_entries_home": 5, "box_entries_away": 5, "box_entries_diff": 0,
        "recoveries_home": 20, "recoveries_away": 20, "recoveries_diff": 0,
        "turnovers_home": 10, "turnovers_away": 10, "turnovers_diff": 0,
        "min_since_last_shot_home": 2.0, "min_since_last_shot_away": 2.0,
        "min_since_last_shot_any": 1.5, "min_since_major_chance": 10.0,
        "corners_home": 3, "corners_away": 3, "corners_diff": 0,
        "att_free_kicks_home": 4, "att_free_kicks_away": 4, "att_free_kicks_diff": 0,
        "yellow_home": 1, "yellow_away": 1, "yellow_diff": 0,
        "sendoff_diff": 0, "players_diff": 0, "subs_used_diff": 0, "xg_present": "1",
        "next_goal_any_15": 0, "any_goal_next10m": 0, "sendoff_after": 0,
    }
    base.update(extra)
    return base


def _synth_competition(comp, n_matches, kickoff, seed):
    rng = random.Random(seed)
    rows = []
    for mi in range(n_matches):
        mid = f"{comp}_{mi}"
        sh = rng.gauss(0.3, 0.5)
        fh = max(0, int(round(rng.gauss(1.3 + sh, 1.0))))
        fa = max(0, int(round(rng.gauss(1.3 - sh, 1.0))))
        for t in (15.0, 30.0, 45.0, 60.0, 75.0):
            frac = t / 90.0
            ch = min(fh, int(fh * frac + rng.random()))
            ca = min(fa, int(fa * frac + rng.random()))
            r = _row(comp, mid, t, ch, ca, fh, fa, kickoff,
                     next_goal_any_15=1 if rng.random() < 0.3 else 0,
                     any_goal_next10m=1 if rng.random() < 0.25 else 0,
                     sendoff_after=1 if rng.random() < 0.02 else 0)
            rows.append(r)
    return rows


@pytest.fixture(scope="module")
def corpus():
    rows = (_synth_competition("WC2018", 16, "2018-06-14", 1)
            + _synth_competition("Euro2020", 16, "2021-06-11", 2)
            + _synth_competition("WC2022", 16, "2022-11-20", 3))
    club = []
    for r in _synth_competition("ClubLeagueX", 14, "2019-08-01", 9):
        r["comp_type"] = "club"
        club.append(r)
    return {"rows": rows, "club": club}


# ----------------------------------------------------------------------------------------------------
# e2 remaining-time Poisson reference
# ----------------------------------------------------------------------------------------------------
def test_e2_reference_finite_and_normalized():
    for diff, t in [(0, 15.0), (1, 60.0), (-2, 80.0), (3, 89.0), (0, 0.0)]:
        row = {"goals_diff": diff, "remaining_regulation_min": 90.0 - t, "snapshot_minute": t}
        p = M.e2_reference(row)
        assert set(p) == {"H", "D", "A"}
        assert abs(sum(p.values()) - 1.0) < 1e-9
        for v in p.values():
            assert math.isfinite(v) and 0.0 <= v <= 1.0
        assert math.isfinite(CM.rps(p, "D"))


def test_e2_lead_increases_win_prob():
    late = {"remaining_regulation_min": 5.0, "snapshot_minute": 85.0}
    level = M.e2_reference({**late, "goals_diff": 0})
    lead = M.e2_reference({**late, "goals_diff": 2})
    assert lead["H"] > level["H"]  # a 2-goal lead late => much higher P(home win)
    assert lead["A"] < level["A"]


def test_intensity_convolution_monotone():
    # more remaining home intensity strictly raises P(home win) at level score
    p_lo = M.wdl_from_intensities(0.5, 0.5, 0)
    p_hi = M.wdl_from_intensities(1.5, 0.5, 0)
    assert p_hi["H"] > p_lo["H"]
    assert p_hi["A"] < p_lo["A"]


# ----------------------------------------------------------------------------------------------------
# e0..e9 family
# ----------------------------------------------------------------------------------------------------
def test_all_event_process_models_predict_valid(corpus):
    preds = M.event_process_predictors(corpus["rows"], club_rows=corpus["club"], include_club_transfer=True)
    assert set(preds) == set(M.REG.EVENT_PROCESS_MODELS)
    for mid, fn in preds.items():
        p = fn(corpus["rows"][0])
        assert set(p) == {"H", "D", "A"}
        assert abs(sum(p.values()) - 1.0) < 1e-6
        for v in p.values():
            assert 0.0 <= v <= 1.0


def test_e2_is_parameter_free_reference():
    # e2 must be identical regardless of training data (parameter-free); it never reads train rows.
    rows_a = _synth_competition("A", 4, "2018-01-01", 11)
    rows_b = _synth_competition("B", 4, "2019-01-01", 22)
    pa = M.event_process_predictors(rows_a)["research.event_process.e2"]
    pb = M.event_process_predictors(rows_b)["research.event_process.e2"]
    probe = {"goals_diff": 1, "remaining_regulation_min": 30.0, "snapshot_minute": 60.0}
    assert pa(probe) == pb(probe) == M.e2_reference(probe)


# ----------------------------------------------------------------------------------------------------
# binary families + discipline gate
# ----------------------------------------------------------------------------------------------------
def test_next_goal_and_scoring_predict_probabilities(corpus):
    q = M.next_goal_predictors(corpus["rows"])
    h = M.scoring_predictors(corpus["rows"])
    assert set(q) == set(M.REG.NEXT_GOAL_MODELS)
    assert set(h) == set(M.REG.SCORING_MODELS)
    for fn in list(q.values()) + list(h.values()):
        v = float(fn(corpus["rows"][0]))
        assert 0.0 <= v <= 1.0


def test_discipline_gate_below_threshold(corpus):
    out = M.discipline_predictors(corpus["rows"])
    # the synthetic corpus has < 150 sending-off positives, so the hazard models must be SKIPPED.
    assert out["n_positives"] < M.DISCIPLINE_POSITIVE_GATE
    assert out["gate_open"] is False
    assert out["gated_status"] == "SKIPPED_below_gate"
    assert set(out["predictors"]) == {"research.discipline.y0"}  # only the base rate survives the gate


def test_discipline_gate_opens_with_enough_positives():
    rows = _synth_competition("Disc", 40, "2018-01-01", 7)  # 40 matches x 5 snaps = 200 rows
    for r in rows:
        r["sendoff_after"] = 1  # force >= 150 positives
    out = M.discipline_predictors(rows)
    assert out["gate_open"] is True
    assert {"research.discipline.y1", "research.discipline.y2"} <= set(out["predictors"])


# ----------------------------------------------------------------------------------------------------
# eval harness: forward chain, LOCO, candidate rule, club transfer
# ----------------------------------------------------------------------------------------------------
def test_forward_chain_returns_numbers(corpus):
    fwd = E.forward_chain_wdl(corpus["rows"],
                              predictor_factory=E.make_wdl_factory(None, include_club_transfer=False))
    assert fwd["n_folds"] >= 2
    for mid in ("research.event_process.e2", "research.event_process.e7"):
        assert fwd["pooled"][mid]["rps"] is not None
        assert math.isfinite(fwd["pooled"][mid]["rps"])


def test_candidate_rule_emits_sanctioned_verdict(corpus):
    loco = E.loco_wdl(corpus["rows"], predictor_factory=E.make_wdl_factory(corpus["club"]))
    v = E.evaluate_candidate_rule(loco, "research.event_process.e9",
                                  rows_for_completeness=corpus["rows"])
    assert v["verdict"] in E.CANDIDATE_VERDICTS
    assert v["reference"] == "research.event_process.e2"


def test_club_transfer_comparison_runs(corpus):
    cmp = E.club_transfer_comparison(corpus["rows"], corpus["club"])
    assert cmp["model_id"] == "research.event_process.e8"
    assert cmp["rps_with_club"] is not None and cmp["rps_without_club"] is not None
    assert math.isfinite(cmp["rps_with_club"]) and math.isfinite(cmp["rps_without_club"])


def test_club_rows_never_test_rows(corpus):
    # LOCO folds are built from international rows only; a club competition must never become a test fold.
    loco = E.loco_wdl(corpus["rows"], predictor_factory=E.make_wdl_factory(corpus["club"]))
    held = {f["held_competition"] for f in loco["folds"]}
    assert "ClubLeagueX" not in held
    assert held <= {"WC2018", "Euro2020", "WC2022"}


def test_harness_refuses_2026(corpus):
    rows_2026 = _synth_competition("FIFA World Cup 2026", 4, "2026-06-11", 99)
    for r in rows_2026:
        r["competition_label"] = "FIFA World Cup 2026"
    with pytest.raises(AssertionError):
        E.assert_no_2026(rows_2026)
