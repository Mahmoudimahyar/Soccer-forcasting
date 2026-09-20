"""Phase 2 / 7C tournament-simulator validation — deterministic synthetic cases for the OFFICIAL 2026
standings + tiebreak engine and the group-stage simulator. No randomness in the assertions."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.simulation.official_standings import (  # noqa: E402
    OfficialGroupTable, rank_third_place_official, simulate_group_stage_official,
    force_match_outcome_official)


def _round_robin(group, results):
    t = OfficialGroupTable(group)
    for (a, b, ga, gb) in results:
        t.add_result(a, b, ga, gb)
    return t


def test_points_then_gd_ordering():
    t = _round_robin("G", [("A", "B", 1, 0), ("A", "C", 1, 0), ("A", "D", 1, 0),
                            ("B", "C", 1, 0), ("B", "D", 1, 0), ("C", "D", 1, 0)])
    assert t.ranked() == ["A", "B", "C", "D"]


def test_head_to_head_breaks_equal_points_and_gd():
    # A and B both 6 pts, both GD +3, both GF 4 -> H2H (A beat B) ranks A above B
    t = _round_robin("G", [("A", "B", 1, 0), ("A", "C", 0, 1), ("A", "D", 3, 0),
                            ("B", "C", 2, 0), ("B", "D", 2, 0), ("C", "D", 0, 1)])
    order = t.ranked()
    assert order.index("A") < order.index("B")


def test_overall_gd_fallback_when_h2h_drawn():
    # A and B both 7 pts, drew head-to-head -> overall GD decides (A +4 > B +2)
    t = _round_robin("G", [("A", "B", 1, 1), ("A", "C", 3, 0), ("A", "D", 1, 0),
                            ("B", "C", 1, 0), ("B", "D", 1, 0), ("C", "D", 0, 0)])
    order = t.ranked()
    assert order.index("A") < order.index("B")


def test_conduct_tiebreak_when_all_equal():
    t = _round_robin("G", [("A", "B", 0, 0), ("A", "C", 1, 0), ("A", "D", 1, 0),
                            ("B", "C", 1, 0), ("B", "D", 1, 0), ("C", "D", 0, 0)])
    # A and B identical (7 pts, GD+2, GF2, H2H 0-0). Better conduct (higher) wins.
    t.set_conduct("A", 0.0); t.set_conduct("B", -2.0)
    order = t.ranked()
    assert order.index("A") < order.index("B")


def test_best_third_place_ranking():
    thirds = pd.DataFrame([
        {"group": "A", "team": "T1", "points": 4, "gd": 1, "gf": 3},
        {"group": "B", "team": "T2", "points": 4, "gd": 2, "gf": 4},  # better GD -> ranks first
        {"group": "C", "team": "T3", "points": 3, "gd": 5, "gf": 9},
    ])
    out = rank_third_place_official(thirds)
    assert list(out.team) == ["T2", "T1", "T3"]


def _fixtures_all_played():
    rows = []
    teams = ["A", "B", "C", "D"]
    res = {("A", "B"): (1, 0), ("A", "C"): (1, 0), ("A", "D"): (1, 0),
           ("B", "C"): (1, 0), ("B", "D"): (1, 0), ("C", "D"): (1, 0)}
    for i, ((a, b), (ga, gb)) in enumerate(res.items()):
        rows.append({"match_id": f"G{i}", "group": "G", "team_a": a, "team_b": b,
                     "goals_a": ga, "goals_b": gb})
    return pd.DataFrame(rows)


def test_simulator_deterministic_when_all_played_and_idempotent():
    fx = _fixtures_all_played()
    probs = np.tile([1 / 3, 1 / 3, 1 / 3], (len(fx), 1))
    r1 = simulate_group_stage_official(fx, probs, n_sims=50, seed=1).sort_values("team").reset_index(drop=True)
    r2 = simulate_group_stage_official(fx, probs, n_sims=50, seed=999).sort_values("team").reset_index(drop=True)
    # fully-played -> deterministic regardless of seed/n_sims
    assert np.allclose(r1["p_advance"].to_numpy(), r2["p_advance"].to_numpy())
    adv = dict(zip(r1.team, r1.p_advance)); first = dict(zip(r1.team, r1.p_first))
    # top two always advance; the 4th-place team never advances. (In a single-group test the 3rd-place
    # team also advances as a "best third" because slots(8) exceed the one competing third — expected.)
    assert adv["A"] == 1.0 and adv["B"] == 1.0 and adv["D"] == 0.0
    assert first["A"] == 1.0 and first["B"] == 0.0


def test_force_outcome_changes_standings_idempotently():
    fx = pd.DataFrame([{"match_id": "M1", "group": "G", "team_a": "A", "team_b": "B",
                        "goals_a": np.nan, "goals_b": np.nan}])
    f1 = force_match_outcome_official(fx, "M1", "A")
    f2 = force_match_outcome_official(f1, "M1", "A")  # re-applying same forced result is idempotent
    assert (f1.iloc[0]["goals_a"] > f1.iloc[0]["goals_b"])
    assert f1.iloc[0]["goals_a"] == f2.iloc[0]["goals_a"] and f1.iloc[0]["goals_b"] == f2.iloc[0]["goals_b"]
