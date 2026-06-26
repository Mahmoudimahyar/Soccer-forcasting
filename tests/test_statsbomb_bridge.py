"""Synthetic, network-free tests for the StatsBomb OPEN-DATA xG bridge (Phase 3).

Covers the required invariants:
  - exact-match requirement (comp+normalized teams+date+score all agree -> accepted)
  - ambiguous-match rejection (two StatsBomb candidates on same date+team-pair -> rejected, never guessed)
  - date-mismatch rejection (team pair exists but on a different calendar date)
  - score-mismatch rejection (comp+date+teams agree but final 90+ET score disagrees)
  - no future xG event leaks into the causal in-play state at minute t
  - no raw external data is tracked by git (StatsBomb raw + processed outputs gitignored)
  - deterministic bridge rebuild (same inputs -> identical accepted rows + digest)

All inputs are synthetic dicts; no download, no corpus dependency.
"""
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load(modname, relpath):
    spec = importlib.util.spec_from_file_location(modname, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BR = _load("bridge_mod", "scripts/build_api_statsbomb_match_bridge.py")
XG = _load("xg_mod", "scripts/build_xg_event_state_features.py")


# ----------------------------- helpers to build synthetic inputs -----------------------------
def api_fixture(fid, home, away, date, ft_home, ft_away, et_home=None, et_away=None, pen=None):
    score = {"fulltime": {"home": ft_home, "away": ft_away}}
    if et_home is not None:
        score["extratime"] = {"home": et_home, "away": et_away}
    if pen is not None:
        score["penalty"] = {"home": pen[0], "away": pen[1]}
    return {
        "fixture": {"id": fid, "date": f"{date}T18:00:00+00:00"},
        "teams": {"home": {"name": home, "id": 1}, "away": {"name": away, "id": 2}},
        "score": score,
        "league": {"id": 1, "season": 2022},
    }


def sb_match(mid, home, away, date, hs, as_):
    return {"match_id": mid, "match_date": date,
            "home_team": {"home_team_name": home}, "away_team": {"away_team_name": away},
            "home_score": hs, "away_score": as_}


def goal_events(reg_goals, home, away):
    """Build minimal API-Football regulation goal events so canonical_result reconciles exactly."""
    evs = []
    el = 10
    for _ in range(reg_goals[0]):
        evs.append({"type": "Goal", "team": {"name": home, "id": 1}, "time": {"elapsed": el}}); el += 5
    for _ in range(reg_goals[1]):
        evs.append({"type": "Goal", "team": {"name": away, "id": 2}, "time": {"elapsed": el}}); el += 5
    return evs


def run_match(fid, fx, ev, sb_rows_raw, label="FIFA World Cup 2022", api_key=(1, 2022), sb_key=(43, 106)):
    sb_rows = [BR.sb_row_view(m) for m in sb_rows_raw]
    return BR.match_one_fixture(fid, fx, {fid: ev}, sb_rows, label, api_key, sb_key, "deadbeef")


# ----------------------------- exact-match requirement -----------------------------
def test_exact_match_accepted():
    fx = api_fixture(100, "Argentina", "Mexico", "2022-11-26", 2, 0)
    ev = goal_events((2, 0), "Argentina", "Mexico")
    sb = [sb_match(900, "Argentina", "Mexico", "2022-11-26", 2, 0)]
    row, rej = run_match(100, fx, ev, sb)
    assert rej is None, rej
    assert row is not None
    assert row["bridge_confidence"] == "exact"
    assert row["sb_match_id"] == 900
    assert (row["final_home_goals"], row["final_away_goals"]) == (2, 0)
    assert row["orientation"] == "same"


def test_exact_match_after_extra_time_uses_cumulative_score():
    # API regulation 2-2, ET increment 1-1 -> after-ET 3-3 must equal StatsBomb 3-3.
    fx = api_fixture(101, "Argentina", "France", "2022-12-18", 2, 2, et_home=1, et_away=1, pen=(4, 2))
    ev = goal_events((2, 2), "Argentina", "France")
    sb = [sb_match(901, "Argentina", "France", "2022-12-18", 3, 3)]
    row, rej = run_match(101, fx, ev, sb)
    assert rej is None, rej
    assert (row["final_home_goals"], row["final_away_goals"]) == (3, 3)
    assert row["api_result_type"] == "penalty_shootout"


def test_swapped_orientation_with_swapped_score_accepted():
    # StatsBomb lists teams in opposite order; score must swap too.
    fx = api_fixture(102, "Brazil", "Serbia", "2022-11-24", 2, 0)
    ev = goal_events((2, 0), "Brazil", "Serbia")
    sb = [sb_match(902, "Serbia", "Brazil", "2022-11-24", 0, 2)]
    row, rej = run_match(102, fx, ev, sb)
    assert rej is None, rej
    assert row["orientation"] == "swapped"
    # reported in API orientation
    assert (row["final_home_goals"], row["final_away_goals"]) == (2, 0)


def test_normalized_team_names_match():
    # API 'USA' / StatsBomb 'United States' must fold to the same canonical token.
    fx = api_fixture(103, "USA", "Iran", "2022-11-29", 1, 0)
    ev = goal_events((1, 0), "USA", "Iran")
    sb = [sb_match(903, "United States", "Iran", "2022-11-29", 1, 0)]
    row, rej = run_match(103, fx, ev, sb)
    assert rej is None, rej
    assert row["norm_home"] == "United States"


# ----------------------------- ambiguous-match rejection -----------------------------
def test_ambiguous_multiple_candidates_rejected():
    fx = api_fixture(110, "Argentina", "Mexico", "2022-11-26", 2, 0)
    ev = goal_events((2, 0), "Argentina", "Mexico")
    sb = [sb_match(910, "Argentina", "Mexico", "2022-11-26", 2, 0),
          sb_match(911, "Argentina", "Mexico", "2022-11-26", 2, 0)]  # duplicate identity -> ambiguous
    row, rej = run_match(110, fx, ev, sb)
    assert row is None
    assert rej["reason"] == "ambiguous_multiple_candidates"
    assert set(rej["candidate_sb_ids"]) == {910, 911}


# ----------------------------- date-mismatch rejection -----------------------------
def test_date_mismatch_rejected():
    fx = api_fixture(120, "Peru", "Canada", "2024-06-26", 0, 1)
    ev = goal_events((0, 1), "Peru", "Canada")
    # same team pair exists in the comp-season but on a different calendar date
    sb = [sb_match(920, "Peru", "Canada", "2024-06-25", 0, 1)]
    row, rej = run_match(120, fx, ev, sb)
    assert row is None
    assert rej["reason"] == "date_mismatch"


# ----------------------------- score-mismatch rejection -----------------------------
def test_score_mismatch_rejected():
    fx = api_fixture(130, "Spain", "Germany", "2022-11-27", 1, 1)
    ev = goal_events((1, 1), "Spain", "Germany")
    sb = [sb_match(930, "Spain", "Germany", "2022-11-27", 2, 1)]  # final score disagrees
    row, rej = run_match(130, fx, ev, sb)
    assert row is None
    assert rej["reason"] == "score_mismatch"


def test_no_candidate_when_absent():
    fx = api_fixture(140, "Wales", "Iran", "2022-11-25", 0, 2)
    ev = goal_events((0, 2), "Wales", "Iran")
    sb = [sb_match(940, "Qatar", "Senegal", "2022-11-25", 1, 3)]
    row, rej = run_match(140, fx, ev, sb)
    assert row is None
    assert rej["reason"] == "no_statsbomb_candidate"


# ----------------------------- no future xG event in causal state -----------------------------
def _shot(team, minute, second, xg, goal=False):
    return {"type": {"name": "Shot"}, "team": {"name": team}, "minute": minute, "second": second,
            "period": 1 if minute <= 45 else 2,
            "shot": {"statsbomb_xg": xg, "outcome": {"name": "Goal" if goal else "Saved"}}}


def test_no_future_xg_leaks_into_state():
    events = [
        _shot("Alpha", 10, 0, 0.10),
        _shot("Beta", 20, 0, 0.20),
        _shot("Alpha", 40, 0, 0.50, goal=True),
        _shot("Beta", 70, 0, 0.40),   # FUTURE relative to t=30/45/60
    ]
    shots, goals, et = XG.extract_shots_goals(events, "Alpha", "Beta")
    # at t=30: only the 10' (0.10 H) and 20' (0.20 A) shots may appear
    f30 = XG.features_at(shots, goals, 30)
    assert abs(f30["cum_xg_home"] - 0.10) < 1e-9
    assert abs(f30["cum_xg_away"] - 0.20) < 1e-9
    assert f30["shot_count_home"] == 1 and f30["shot_count_away"] == 1
    assert f30["score_home_to_t"] == 0  # the 40' goal is in the future
    # at t=45: home goal at 40' is now included; the 70' Beta shot must NOT be
    f45 = XG.features_at(shots, goals, 45)
    assert abs(f45["cum_xg_home"] - 0.60) < 1e-9    # 0.10 + 0.50
    assert abs(f45["cum_xg_away"] - 0.20) < 1e-9    # 70' shot excluded
    assert f45["score_home_to_t"] == 1
    # monotonic non-decreasing cumulative xG across the grid
    prev_h = prev_a = -1.0
    for t in XG.DECISION_GRID:
        f = XG.features_at(shots, goals, t)
        assert f["cum_xg_home"] + 1e-9 >= prev_h
        assert f["cum_xg_away"] + 1e-9 >= prev_a
        prev_h, prev_a = f["cum_xg_home"], f["cum_xg_away"]
    # the 70' future shot is fully captured by the final state but never earlier
    f90 = XG.features_at(shots, goals, 90)
    assert f90["shot_count_away"] == 2


def test_extra_time_excluded_from_regulation_state():
    events = [
        _shot("Alpha", 30, 0, 0.30),
        {"type": {"name": "Shot"}, "team": {"name": "Alpha"}, "minute": 100, "second": 0, "period": 3,
         "shot": {"statsbomb_xg": 0.9, "outcome": {"name": "Goal"}}},  # extra time
    ]
    shots, goals, et = XG.extract_shots_goals(events, "Alpha", "Beta")
    assert et == 1  # flagged
    f90 = XG.features_at(shots, goals, 90)
    assert abs(f90["cum_xg_home"] - 0.30) < 1e-9  # ET shot excluded from regulation xG


def test_own_goal_credited_to_beneficiary_no_xg():
    events = [
        {"type": {"name": "Own Goal For"}, "team": {"name": "Alpha"}, "minute": 25, "second": 0, "period": 1},
    ]
    shots, goals, et = XG.extract_shots_goals(events, "Alpha", "Beta")
    f30 = XG.features_at(shots, goals, 30)
    assert f30["score_home_to_t"] == 1     # beneficiary credited
    assert abs(f30["cum_xg_home"]) < 1e-9  # own goal carries no xG


# ----------------------------- deterministic bridge rebuild -----------------------------
def test_deterministic_rebuild_same_inputs():
    fx = api_fixture(150, "Argentina", "Mexico", "2022-11-26", 2, 0)
    ev = goal_events((2, 0), "Argentina", "Mexico")
    sb = [sb_match(950, "Argentina", "Mexico", "2022-11-26", 2, 0)]
    row1, _ = run_match(150, fx, ev, sb)
    row2, _ = run_match(150, fx, ev, sb)
    assert row1 == row2
    # bridge_id is a pure function of (api_fixture_id, sb_match_id)
    expected = hashlib.sha256(b"150|950").hexdigest()[:16]
    assert row1["bridge_id"] == expected


def test_features_deterministic():
    events = [_shot("Alpha", 10, 0, 0.10), _shot("Beta", 20, 0, 0.20), _shot("Alpha", 40, 0, 0.50, goal=True)]
    s1, g1, _ = XG.extract_shots_goals(events, "Alpha", "Beta")
    s2, g2, _ = XG.extract_shots_goals(events, "Alpha", "Beta")
    assert [XG.features_at(s1, g1, t) for t in XG.DECISION_GRID] == [XG.features_at(s2, g2, t) for t in XG.DECISION_GRID]


# ----------------------------- no raw external data tracked -----------------------------
def test_no_raw_external_data_tracked_by_git():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    offenders = [p for p in tracked if p.startswith("data/raw/")]
    assert not offenders, f"raw external data must not be tracked: {offenders}"
    # StatsBomb raw + processed bridge outputs must be gitignored
    chk = subprocess.run(["git", "check-ignore", "data/raw/statsbomb_open/x.json",
                          "data/processed/api_statsbomb_match_bridge_v1.csv"],
                         cwd=ROOT, capture_output=True, text=True)
    ignored = set(chk.stdout.split())
    assert "data/raw/statsbomb_open/x.json" in ignored
    assert "data/processed/api_statsbomb_match_bridge_v1.csv" in ignored


def test_api_final_after_et_helper():
    assert BR.api_final_after_et({"fulltime": {"home": 2, "away": 2}, "extratime": {"home": 1, "away": 1}}) == (3, 3)
    assert BR.api_final_after_et({"fulltime": {"home": 1, "away": 0}}) == (1, 0)
    assert BR.api_final_after_et({"fulltime": {"home": None, "away": None}}) is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
