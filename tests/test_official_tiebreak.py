"""Deterministic tests for the OFFICIAL 2026 tiebreak engine (official_standings.py):
head-to-head BEFORE overall GD, recursive H2H, third-place ranking, exactly 8 advance,
simultaneous final-matchday determinism, and seed reproducibility.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from wcdrawlab.simulation.official_standings import (
    OfficialGroupTable, rank_third_place_official, simulate_group_stage_official,
)

GROUPS = list("ABCDEFGHIJKL")


def table_from(results, conduct=None, fifa=None) -> OfficialGroupTable:
    t = OfficialGroupTable("G")
    for a, b, ga, gb in results:
        t.add_result(a, b, ga, gb)
    for team, c in (conduct or {}).items():
        t.set_conduct(team, c)
    for team, r in (fifa or {}).items():
        t.ensure(team, r)
    return t


def test_a_two_team_tie_resolved_by_head_to_head():
    # A&B tie at 6 (A beat B); C&D tie at 3 (C beat D) -> both ties broken by H2H
    res = [("A", "B", 1, 0), ("A", "C", 1, 0), ("A", "D", 0, 1),
           ("B", "C", 1, 0), ("B", "D", 1, 0), ("C", "D", 1, 0)]
    assert table_from(res).ranked() == ["A", "B", "C", "D"]


def test_b_three_team_tie_resolved_by_h2h_goal_difference():
    # A,B,C cycle (each beats D); H2H points equal -> H2H GD separates: A(+2),C(0),B(-2)
    res = [("A", "B", 3, 0), ("B", "C", 1, 0), ("C", "A", 1, 0),
           ("A", "D", 1, 0), ("B", "D", 1, 0), ("C", "D", 1, 0)]
    assert table_from(res).ranked() == ["A", "C", "B", "D"]


def test_c_h2h_tie_resolved_by_goals_when_gd_equal():
    # cycle with H2H points equal AND H2H GD all 0; separated by H2H goals scored: B(4),A(3),C(2)
    res = [("A", "B", 3, 2), ("B", "C", 2, 1), ("C", "A", 1, 0),
           ("A", "D", 1, 0), ("B", "D", 1, 0), ("C", "D", 1, 0)]
    t = table_from(res)
    assert t.ranked() == ["B", "A", "C", "D"]


def test_d_conduct_fallback_when_all_else_equal():
    # A & B identical on points/H2H(draw)/overall GD/goals -> team conduct decides (higher=better)
    res = [("A", "B", 1, 1), ("A", "C", 1, 0), ("A", "D", 1, 0),
           ("B", "C", 1, 0), ("B", "D", 1, 0), ("C", "D", 1, 0)]
    t = table_from(res, conduct={"A": 0, "B": -1})  # B has a card -> worse conduct
    order = t.ranked()
    assert order[:2] == ["A", "B"], order
    # flip conduct -> B should now rank above A, proving conduct is actually used
    t2 = table_from(res, conduct={"A": -1, "B": 0})
    assert t2.ranked()[:2] == ["B", "A"]


def test_f_rank_twelve_third_place_teams():
    rows = [{"group": g, "team": f"{g}3", "points": 3, "gd": gd, "gf": gd + 2,
             "conduct": 0, "fifa_rank": 50} for g, gd in zip(GROUPS, range(11, -1, -1))]
    ranked = rank_third_place_official(pd.DataFrame(rows))
    assert list(ranked["team"]) == [f"{g}3" for g in GROUPS]  # full 12-team order by GD desc


def _played_tournament():
    rows = []
    for i, g in enumerate(GROUPS):
        t1, t2, t3, t4 = f"{g}1", f"{g}2", f"{g}3", f"{g}4"
        X = 12 - i  # distinct third-place GD 10..-1 -> top 8 thirds = groups A..H
        fx = [(t1, t2, 1, 0), (t1, t3, 1, 0), (t1, t4, 1, 0),
              (t2, t3, 1, 0), (t2, t4, 1, 0), (t3, t4, X, 0)]
        for j, (a, b, ga, gb) in enumerate(fx):
            rows.append({"match_id": f"{g}_{j}", "group": g, "team_a": a, "team_b": b,
                         "goals_a": ga, "goals_b": gb})
    return pd.DataFrame(rows)


def test_e_g_exactly_eight_thirds_and_32_advance_deterministic():
    fx = _played_tournament()
    assert fx["group"].nunique() == 12 and len(fx) == 72
    probs = np.full((len(fx), 3), 1 / 3)  # ignored: all played -> deterministic
    adv = simulate_group_stage_official(fx, probs, n_sims=20, third_place_slots=8, seed=7)
    assert len(adv) == 48
    for c in ["p_advance", "p_first", "p_second", "p_third_advance"]:
        assert set(np.unique(np.round(adv[c], 6))) <= {0.0, 1.0}, f"{c} not deterministic (leak?)"
    assert int(adv["p_advance"].sum()) == 32      # 12 + 12 + 8
    assert int(adv["p_third_advance"].sum()) == 8  # exactly eight third-place teams
    # correct 8 thirds = groups A..H
    thirds = set(adv[adv["p_third_advance"] > 0.5]["team"])
    assert thirds == {f"{g}3" for g in GROUPS[:8]}


def test_seed_reproducibility_with_unplayed_matches():
    fx = _played_tournament()
    # leave one group's last match unplayed -> sampling occurs
    fx.loc[fx["match_id"] == "L_5", ["goals_a", "goals_b"]] = np.nan
    probs = np.full((len(fx), 3), 1 / 3)
    a1 = simulate_group_stage_official(fx, probs, n_sims=200, seed=123)
    a2 = simulate_group_stage_official(fx, probs, n_sims=200, seed=123)
    m = a1.merge(a2, on="team", suffixes=("_1", "_2"))
    assert (m["p_advance_1"] == m["p_advance_2"]).all()  # same seed -> identical
