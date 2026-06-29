"""Phase 2 — deterministic synthetic tests for result reconciliation / outcome semantics."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "prospective_harvest"))

from refresh_prospective_final_results import (  # noqa: E402
    build_result_records, normalize_status, outcome_home_orientation,
    record_from_fd_match, resolve_identity_and_outcome,
)

FT = pd.DataFrame([
    {"match_id": "2026_A_0625_CzeMex", "team_a": "Czechia", "team_b": "Mexico"},
    {"match_id": "2026_B_0624_SwiCan", "team_a": "Canada", "team_b": "Switzerland"},
])
PAIR2MID = {frozenset(("Czechia", "Mexico")): "2026_A_0625_CzeMex",
            frozenset(("Canada", "Switzerland")): "2026_B_0624_SwiCan"}
MID2A = {"2026_A_0625_CzeMex": {"team_a": "Czechia", "team_b": "Mexico"},
         "2026_B_0624_SwiCan": {"team_a": "Canada", "team_b": "Switzerland"}}


def _fd(home, away, hg, ag, status="FINISHED", duration="REGULAR", pen=None, mid=1):
    score = {"duration": duration, "fullTime": {"home": hg, "away": ag}}
    if pen:
        score["penalties"] = {"home": pen[0], "away": pen[1]}
    return {"id": mid, "stage": "GROUP_STAGE", "status": status, "matchday": 3,
            "utcDate": "2026-06-25T17:00:00Z", "homeTeam": {"name": home}, "awayTeam": {"name": away},
            "score": score}


def _resolve(m):
    return resolve_identity_and_outcome(record_from_fd_match(m), PAIR2MID, MID2A)


def test_normal_home_win():
    r = _resolve(_fd("Czechia", "Mexico", 2, 0))  # team_a=Czechia=home
    assert r["reconciliation_status"] == "verified_final"
    assert r["final_1x2_outcome_home_orientation"] == "HOME"
    assert r["final_1x2_outcome_team_a_orientation"] == "A"


def test_normal_draw():
    r = _resolve(_fd("Czechia", "Mexico", 1, 1))
    assert r["final_1x2_outcome_team_a_orientation"] == "D"


def test_normal_away_win():
    r = _resolve(_fd("Czechia", "Mexico", 0, 2))
    assert r["final_1x2_outcome_team_a_orientation"] == "B"


def test_team_a_is_away_orientation_flips():
    # provider home=Switzerland, away=Canada; team_a=Canada. Home win => team_a (Canada) LOSES => B
    r = _resolve(_fd("Switzerland", "Canada", 3, 1))
    assert r["final_1x2_outcome_home_orientation"] == "HOME"
    assert r["final_1x2_outcome_team_a_orientation"] == "B"


def test_extra_time_result_verified():
    r = _resolve(_fd("Czechia", "Mexico", 2, 1, status="AET", duration="EXTRA_TIME"))
    assert r["reconciliation_status"] == "verified_final"
    assert r["final_1x2_outcome_team_a_orientation"] == "A"


def test_shootout_does_not_convert_regulation_draw():
    # 1-1 after regulation/ET, decided on penalties; the regulation 1X2 target stays a DRAW
    r = _resolve(_fd("Czechia", "Mexico", 1, 1, status="PEN", duration="PENALTY_SHOOTOUT", pen=(4, 3)))
    assert r["reconciliation_status"] == "verified_final"
    assert r["final_1x2_outcome_team_a_orientation"] == "D"
    assert r["shootout_home"] == 4 and r["shootout_away"] == 3


def test_cancelled_fixture_excluded():
    r = _resolve(_fd("Czechia", "Mexico", None, None, status="CANCELLED"))
    assert r["reconciliation_status"] == "fixture_cancelled"
    assert r["final_1x2_outcome_team_a_orientation"] is None


def test_postponed_fixture_excluded():
    r = _resolve(_fd("Czechia", "Mexico", None, None, status="POSTPONED"))
    assert r["reconciliation_status"] == "fixture_postponed"


def test_stale_timed_status_excluded_even_if_in_universe():
    r = _resolve(_fd("Czechia", "Mexico", None, None, status="TIMED"))
    assert r["reconciliation_status"] == "awaiting_final"
    assert r["final_1x2_outcome_team_a_orientation"] is None


def test_fixture_id_mismatch_resolved_by_canonical_pair():
    # different numeric provider id, but canonical team pair resolves the ledger fixture id
    r = _resolve(_fd("Mexico", "Czechia", 0, 0, mid=999999))
    assert r["canonical_fixture_id"] == "2026_A_0625_CzeMex"


def test_utc_date_shift_still_resolves_by_pair():
    m = _fd("Czechia", "Mexico", 2, 0)
    m["utcDate"] = "2026-06-24T23:30:00Z"  # shifted vs ledger date; pair match still resolves
    r = _resolve(m)
    assert r["canonical_fixture_id"] == "2026_A_0625_CzeMex"


def test_unresolved_identity_when_not_in_universe():
    r = _resolve(_fd("Brazil", "Scotland", 3, 0))
    assert r["reconciliation_status"] == "unresolved_identity"
    assert r["canonical_fixture_id"] is None


def test_deterministic_normalization():
    recs1 = build_result_records([_fd("Czechia", "Mexico", 2, 0)], FT, "t0", "h0")
    recs2 = build_result_records([_fd("Czechia", "Mexico", 2, 0)], FT, "t0", "h0")
    pd.testing.assert_frame_equal(recs1, recs2)


def test_status_and_outcome_helpers():
    assert normalize_status("finished") == "FINISHED"
    assert outcome_home_orientation(2, 0) == "HOME"
    assert outcome_home_orientation(1, 1) == "DRAW"
    assert outcome_home_orientation(None, 1) is None
