"""Deterministic tests for the 2026 48-team / 12-group / best-third-place simulator.

Construct a fully-PLAYED synthetic tournament (12 groups x 6 matches = 72) where every group
ranks cleanly 1>2>3>4 and the 12 third-placed teams have DISTINCT goal differences, so the 8
best thirds are unambiguous. With all matches played, simulate_group_stage is deterministic
(no Monte-Carlo sampling), so advancement must be exact.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wcdrawlab.simulation.group_simulator import simulate_group_stage
from wcdrawlab.simulation.standings import GroupTable, rank_third_place_teams

GROUPS = list("ABCDEFGHIJKL")  # 12 groups


def build_played_tournament() -> tuple[pd.DataFrame, dict]:
    """Each group g has teams g1..g4. Forced results -> 1:9pts, 2:6, 3:3, 4:0.
    Third team's GD = X-2 where X is the g3-vs-g4 winning margin, distinct per group."""
    rows = []
    third_gd = {}
    for i, g in enumerate(GROUPS):
        t1, t2, t3, t4 = f"{g}1", f"{g}2", f"{g}3", f"{g}4"
        X = 12 - i  # distinct margins 12..1 -> third GD 10..-1; top 8 (groups A..H) advance
        third_gd[g] = X - 2
        fixtures = [
            (t1, t2, 1, 0), (t1, t3, 1, 0), (t1, t4, 1, 0),
            (t2, t3, 1, 0), (t2, t4, 1, 0),
            (t3, t4, X, 0),
        ]
        for j, (a, b, ga, gb) in enumerate(fixtures):
            rows.append({"match_id": f"{g}_{j}", "group": g, "team_a": a, "team_b": b,
                         "goals_a": ga, "goals_b": gb})
    return pd.DataFrame(rows), third_gd


def test_group_table_ranks_within_group():
    gt = GroupTable("A")
    gt.add_result("A1", "A2", 1, 0)
    gt.add_result("A1", "A3", 1, 0)
    gt.add_result("A1", "A4", 1, 0)
    gt.add_result("A2", "A3", 1, 0)
    gt.add_result("A2", "A4", 1, 0)
    gt.add_result("A3", "A4", 5, 0)
    order = list(gt.dataframe()["team"])
    assert order == ["A1", "A2", "A3", "A4"]


def test_simulator_advances_exactly_32_deterministically():
    fixtures, third_gd = build_played_tournament()
    assert fixtures["group"].nunique() == 12
    assert len(fixtures) == 72
    teams = set(fixtures["team_a"]) | set(fixtures["team_b"])
    assert len(teams) == 48
    probs = np.full((len(fixtures), 3), 1 / 3)  # ignored: all matches are played
    adv = simulate_group_stage(fixtures, probs, n_sims=25, third_place_slots=8, seed=1)

    assert len(adv) == 48
    # fully played -> deterministic: every p is exactly 0 or 1
    for col in ["p_advance", "p_first", "p_second", "p_third_advance"]:
        assert set(np.unique(np.round(adv[col], 6))) <= {0.0, 1.0}, f"{col} not deterministic"
    assert int(adv["p_advance"].sum()) == 32, "exactly 32 teams must advance (12+12+8)"
    assert int(adv["p_first"].sum()) == 12
    assert int(adv["p_second"].sum()) == 12
    assert int(adv["p_third_advance"].sum()) == 8


def test_best_eight_thirds_are_the_correct_groups():
    fixtures, third_gd = build_played_tournament()
    probs = np.full((len(fixtures), 3), 1 / 3)
    adv = simulate_group_stage(fixtures, probs, n_sims=15, third_place_slots=8, seed=2)
    advancing_thirds = set(adv[adv["p_third_advance"] > 0.5]["team"])
    # groups ranked by third GD desc; top 8 = groups A..H (X=12..5)
    expected = {f"{g}3" for g in GROUPS[:8]}
    assert advancing_thirds == expected, f"got {sorted(advancing_thirds)}"


def test_determinism_across_seeds_when_all_played():
    fixtures, _ = build_played_tournament()
    probs = np.full((len(fixtures), 3), 1 / 3)
    a1 = simulate_group_stage(fixtures, probs, n_sims=10, third_place_slots=8, seed=1)
    a2 = simulate_group_stage(fixtures, probs, n_sims=10, third_place_slots=8, seed=999)
    m = a1.merge(a2, on="team", suffixes=("_1", "_2"))
    assert (m["p_advance_1"] == m["p_advance_2"]).all()


def test_rank_third_place_picks_top_by_gd():
    rows = [{"group": g, "team": f"{g}3", "points": 3, "gd": gd, "gf": gd + 2,
             "fairplay": 0, "fifa_rank": 50} for g, gd in zip(GROUPS, range(11, -1, -1))]
    ranked = rank_third_place_teams(pd.DataFrame(rows))
    top8 = list(ranked.head(8)["team"])
    assert top8 == [f"{g}3" for g in GROUPS[:8]]
