"""Leakage / data-quality guards for the research modeling table and candidate inputs.

These tests FAIL if forbidden post-match information could ever reach a candidate model,
and if the time-safe group-state / Elo construction is violated. They use synthetic data
so they always run; a separate module validates the real generated table when present.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wcdrawlab.research.runner import leakage_safe_feature_frame, TARGET_COLUMNS
from wcdrawlab.research.candidate import FEATURES, CandidateModel
from wcdrawlab.features import build_pre_match_group_state


CONFIG = {
    "leakage_guard": {
        "forbidden_columns": [
            "goals_a", "goals_b", "outcome", "is_draw", "final_score",
            "post_match_xg", "closing_odds_after_kickoff", "result",
        ]
    }
}

FORBIDDEN = set(CONFIG["leakage_guard"]["forbidden_columns"]) | TARGET_COLUMNS


def _frame_with_everything() -> pd.DataFrame:
    n = 20
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "match_id": [f"m{i}" for i in range(n)],
        "kickoff_utc": pd.date_range("2018-06-14", periods=n, freq="D", tz="UTC"),
        "elo_delta": rng.normal(0, 200, n),
        "abs_elo_delta": rng.uniform(0, 400, n),
        "matchday": rng.integers(1, 4, n),
        "prior_group_draws": rng.integers(0, 3, n),
        # forbidden post-match columns that MUST be stripped:
        "goals_a": rng.integers(0, 5, n),
        "goals_b": rng.integers(0, 5, n),
        "outcome": rng.choice(list("ADB"), n),
        "is_draw": rng.integers(0, 2, n),
        "final_score": rng.integers(0, 9, n),
        "post_match_xg": rng.normal(1.2, 0.5, n),
        "closing_odds_after_kickoff": rng.uniform(1.5, 5, n),
        "result": rng.choice(list("ADB"), n),
    })
    return df


def test_leakage_guard_strips_every_forbidden_column():
    df = _frame_with_everything()
    safe = leakage_safe_feature_frame(df, CONFIG)
    leaked = FORBIDDEN & set(safe.columns)
    assert not leaked, f"forbidden columns leaked into candidate features: {sorted(leaked)}"
    # legitimate pre-match features survive
    assert {"elo_delta", "abs_elo_delta", "matchday", "prior_group_draws"} <= set(safe.columns)


def test_candidate_feature_list_contains_no_forbidden_names():
    leaked = FORBIDDEN & set(FEATURES)
    assert not leaked, f"CandidateModel.FEATURES references forbidden columns: {sorted(leaked)}"


def test_candidate_never_consumes_a_leaked_column():
    """Even if a forbidden column is numerically predictive, the fitted candidate must not use it."""
    df = _frame_with_everything()
    # make is_draw perfectly encode the label to tempt leakage
    y = pd.Series(np.where(df["is_draw"] == 1, "D", np.where(df["elo_delta"] > 0, "A", "B")))
    safe = leakage_safe_feature_frame(df, CONFIG)
    model = CandidateModel().fit(safe, y)
    assert all(c not in FORBIDDEN for c in model.columns)


def _round_robin_group() -> pd.DataFrame:
    """One 4-team group, 6 matches, chronological, with known results."""
    teams = ["W", "X", "Y", "Z"]
    # distinct kickoff times so chronological ordering is unambiguous
    fixtures = [
        ("2018-06-10T12:00", "W", "X", 1, 1),  # MD1 draw (first kickoff overall)
        ("2018-06-10T15:00", "Y", "Z", 2, 0),  # MD1
        ("2018-06-14T12:00", "W", "Y", 0, 0),  # MD2 draw
        ("2018-06-14T15:00", "X", "Z", 3, 1),  # MD2
        ("2018-06-18T12:00", "W", "Z", 1, 2),  # MD3
        ("2018-06-18T15:00", "X", "Y", 0, 0),  # MD3 draw
    ]
    df = pd.DataFrame(fixtures, columns=["kickoff_utc", "team_a", "team_b", "goals_a", "goals_b"])
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    df["group"] = "G"
    df["match_id"] = [f"g{i}" for i in range(len(df))]
    return df


def test_group_state_is_strictly_pre_match():
    df = build_pre_match_group_state(_round_robin_group()).sort_values("kickoff_utc").reset_index(drop=True)
    # the very first kickoff in the group must carry zero accumulated state and zero prior draws
    first = df.iloc[0]
    assert first["points_a_pre"] == 0 and first["points_b_pre"] == 0
    assert first["prior_group_draws"] == 0 and first["prior_group_matches"] == 0
    # a team's pre-match played count can never exceed 2 in a 3-match group (no future games)
    assert (df["played_a_pre"] <= 2).all() and (df["played_b_pre"] <= 2).all()
    # points can never exceed 3 * games already played (no future points injected)
    assert (df["points_a_pre"] <= 3 * df["played_a_pre"]).all()
    assert (df["points_b_pre"] <= 3 * df["played_b_pre"]).all()


def test_group_state_excludes_the_current_match():
    df = build_pre_match_group_state(_round_robin_group()).sort_values("kickoff_utc")
    # the final match's prior_group_matches must be < total played in the group (5, not 6)
    last = df.iloc[-1]
    assert last["prior_group_matches"] < 6
    # by the last MD, three group draws happened earlier (WX, WY) before XY -> prior draws >= 2
    assert last["prior_group_draws"] >= 2


def test_prior_group_draws_never_counts_the_present_draw():
    df = build_pre_match_group_state(_round_robin_group()).sort_values("kickoff_utc")
    # first match is itself a draw; its prior_group_draws must still be 0
    assert df.iloc[0]["prior_group_draws"] == 0


def test_strict_prior_aggregates_exclude_simultaneous_final_matchday():
    """Always-on guard for the simultaneity fix used in the table build: two final-matchday
    matches sharing an identical kickoff timestamp must NOT see each other in group aggregates."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from build_research_table import _strict_prior_group_aggregates

    fixtures = [
        ("2018-06-10T12:00", "W", "X", 1, 1),  # MD1 draw
        ("2018-06-10T15:00", "Y", "Z", 2, 0),  # MD1
        ("2018-06-14T12:00", "W", "Y", 0, 0),  # MD2 draw
        ("2018-06-14T15:00", "X", "Z", 3, 1),  # MD2
        ("2018-06-18T18:00", "W", "Z", 1, 0),  # MD3  <-- identical timestamp
        ("2018-06-18T18:00", "X", "Y", 2, 2),  # MD3  <-- identical timestamp (simultaneous)
    ]
    df = pd.DataFrame(fixtures, columns=["kickoff_utc", "team_a", "team_b", "goals_a", "goals_b"])
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True)
    df["group_uid"] = "2018_G"
    df["match_id"] = [f"g{i}" for i in range(len(df))]
    out = _strict_prior_group_aggregates(df)
    md3 = out[out["kickoff_utc"] == pd.Timestamp("2018-06-18T18:00", tz="UTC")]
    # each MD3 match sees exactly the 4 earlier matches, NOT its 5th (simultaneous) sibling
    assert (md3["prior_group_matches"] == 4).all(), "simultaneous MD3 match leaked into aggregates"
    # 2 earlier draws (W-X, W-Y); the simultaneous X-Y draw must be excluded
    assert (md3["prior_group_draws"] == 2).all()
