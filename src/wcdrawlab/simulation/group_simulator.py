from __future__ import annotations

import numpy as np
import pandas as pd

from wcdrawlab.evaluation import normalize_probs
from wcdrawlab.simulation.standings import GroupTable, rank_third_place_teams


def outcome_to_score(outcome: str, rng: np.random.Generator) -> tuple[int, int]:
    """Simple score generator for table simulation.

    Replace with score-matrix sampling when available.
    """
    if outcome == "A":
        return int(rng.choice([1, 2, 2, 3])), int(rng.choice([0, 0, 1]))
    if outcome == "B":
        b, a = outcome_to_score("A", rng)
        return a, b
    # Draw: mostly 0-0/1-1/2-2.
    k = int(rng.choice([0, 1, 1, 1, 2], p=[0.2, 0.45, 0.2, 0.1, 0.05]))
    return k, k


def simulate_group_stage(
    fixtures: pd.DataFrame,
    probs: np.ndarray,
    n_sims: int = 10000,
    third_place_slots: int = 8,
    seed: int = 42,
) -> pd.DataFrame:
    """Monte Carlo group stage simulation.

    fixtures must include group, team_a, team_b, match_id, and optionally played goals.
    probs is aligned with fixtures, columns [A,D,B] for unplayed matches.
    """
    rng = np.random.default_rng(seed)
    fixtures = fixtures.reset_index(drop=True).copy()
    probs = normalize_probs(probs)
    teams = sorted(set(fixtures["team_a"]).union(set(fixtures["team_b"])))
    advance_counts = {t: 0 for t in teams}
    first_counts = {t: 0 for t in teams}
    second_counts = {t: 0 for t in teams}
    third_adv_counts = {t: 0 for t in teams}

    for _ in range(n_sims):
        tables: dict[str, GroupTable] = {g: GroupTable(g) for g in sorted(fixtures["group"].dropna().unique())}
        for i, r in fixtures.iterrows():
            table = tables[r["group"]]
            a, b = r["team_a"], r["team_b"]
            table.ensure(a, fifa_rank=int(r.get("fifa_rank_a", 999) if pd.notna(r.get("fifa_rank_a", 999)) else 999))
            table.ensure(b, fifa_rank=int(r.get("fifa_rank_b", 999) if pd.notna(r.get("fifa_rank_b", 999)) else 999))
            if pd.notna(r.get("goals_a", np.nan)) and pd.notna(r.get("goals_b", np.nan)):
                ga, gb = int(r["goals_a"]), int(r["goals_b"])
            else:
                outcome = rng.choice(["A", "D", "B"], p=probs[i])
                ga, gb = outcome_to_score(outcome, rng)
            table.add_result(a, b, ga, gb)

        third_rows = []
        for g, table in tables.items():
            ranked = table.dataframe()
            if len(ranked) >= 1:
                first = ranked.iloc[0]["team"]; first_counts[first] += 1; advance_counts[first] += 1
            if len(ranked) >= 2:
                second = ranked.iloc[1]["team"]; second_counts[second] += 1; advance_counts[second] += 1
            if len(ranked) >= 3:
                third_rows.append(ranked.iloc[2].to_dict())
        third_df = rank_third_place_teams(pd.DataFrame(third_rows))
        for _, row in third_df.head(third_place_slots).iterrows():
            team = row["team"]
            third_adv_counts[team] += 1
            advance_counts[team] += 1

    out = pd.DataFrame({"team": teams})
    out["p_advance"] = out["team"].map(advance_counts) / n_sims
    out["p_first"] = out["team"].map(first_counts) / n_sims
    out["p_second"] = out["team"].map(second_counts) / n_sims
    out["p_third_advance"] = out["team"].map(third_adv_counts) / n_sims
    return out.sort_values("p_advance", ascending=False).reset_index(drop=True)


def force_match_outcome(fixtures: pd.DataFrame, match_id, outcome: str) -> pd.DataFrame:
    """Set one match result to A/D/B with a simple representative score."""
    out = fixtures.copy()
    idx = out.index[out["match_id"] == match_id]
    if len(idx) != 1:
        raise ValueError(f"match_id {match_id} not found uniquely")
    if outcome == "A":
        ga, gb = 1, 0
    elif outcome == "D":
        ga, gb = 1, 1
    elif outcome == "B":
        ga, gb = 0, 1
    else:
        raise ValueError("outcome must be A, D, or B")
    out.loc[idx, "goals_a"] = ga
    out.loc[idx, "goals_b"] = gb
    return out
