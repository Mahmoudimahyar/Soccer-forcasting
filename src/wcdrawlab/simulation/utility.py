from __future__ import annotations

import pandas as pd
import numpy as np

from wcdrawlab.simulation.group_simulator import simulate_group_stage, force_match_outcome


def match_advance_utilities(
    fixtures: pd.DataFrame,
    probs: np.ndarray,
    match_id,
    team_a: str,
    team_b: str,
    n_sims: int = 5000,
    third_place_slots: int = 8,
    seed: int = 42,
) -> dict[str, float]:
    """Compute P(advance | A win/draw/B win) and derived draw/must-win utilities."""
    results = {}
    for outcome in ["A", "D", "B"]:
        forced = force_match_outcome(fixtures, match_id, outcome)
        sim = simulate_group_stage(forced, probs, n_sims=n_sims, third_place_slots=third_place_slots, seed=seed)
        mp = dict(zip(sim["team"], sim["p_advance"]))
        results[outcome] = {team_a: mp.get(team_a, 0.0), team_b: mp.get(team_b, 0.0)}

    a_win = results["A"][team_a]
    a_draw = results["D"][team_a]
    a_loss = results["B"][team_a]
    b_win = results["B"][team_b]
    b_draw = results["D"][team_b]
    b_loss = results["A"][team_b]

    draw_utility_a = a_draw - a_loss
    draw_utility_b = b_draw - b_loss
    must_win_pressure_a = a_win - a_draw
    must_win_pressure_b = b_win - b_draw

    return {
        "p_adv_a_if_win": a_win,
        "p_adv_a_if_draw": a_draw,
        "p_adv_a_if_loss": a_loss,
        "p_adv_b_if_win": b_win,
        "p_adv_b_if_draw": b_draw,
        "p_adv_b_if_loss": b_loss,
        "draw_utility_a": draw_utility_a,
        "draw_utility_b": draw_utility_b,
        "mutual_draw_utility": min(draw_utility_a, draw_utility_b),
        "must_win_pressure_a": must_win_pressure_a,
        "must_win_pressure_b": must_win_pressure_b,
        "must_win_pressure_max": max(must_win_pressure_a, must_win_pressure_b),
    }
