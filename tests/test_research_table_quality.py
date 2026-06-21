"""Validate the generated research modeling table when it exists.

Skips cleanly if the table has not been built (so CI without the data step still passes).
Build it with: python scripts/build_research_table.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from wcdrawlab.research.runner import leakage_safe_feature_frame, TARGET_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "data" / "processed" / "research_modeling_table.csv"
TARGETS = ROOT / "data" / "processed" / "forecast_targets_2026.csv"

REQUIRED = [
    "match_id", "kickoff_utc", "tournament", "stage", "group", "matchday",
    "team_a", "team_b", "goals_a", "goals_b", "elo_a", "elo_b", "elo_delta",
    "abs_elo_delta", "prior_group_draws", "points_a_pre", "outcome",
]


@pytest.fixture(scope="module")
def table() -> pd.DataFrame:
    if not TABLE.exists():
        pytest.skip("research_modeling_table.csv not built; run scripts/build_research_table.py")
    return pd.read_csv(TABLE, parse_dates=["kickoff_utc"])


def test_required_columns_present(table):
    missing = [c for c in REQUIRED if c not in table.columns]
    assert not missing, f"missing required columns: {missing}"


def test_unique_match_ids(table):
    assert table["match_id"].is_unique


def test_all_group_stage_and_valid_matchday(table):
    assert (table["stage"].str.lower() == "group").all()
    assert set(table["matchday"].dropna().unique()) <= {1, 2, 3}


def test_no_nan_in_core_features(table):
    core = ["elo_a", "elo_b", "elo_delta", "abs_elo_delta", "prior_group_draws", "points_a_pre"]
    nulls = table[core].isna().sum()
    assert nulls.sum() == 0, f"NaNs in core features:\n{nulls}"


def test_only_played_matches_in_modeling_table(table):
    assert table["goals_a"].notna().all() and table["goals_b"].notna().all()
    assert set(table["outcome"].unique()) <= {"A", "D", "B"}


def test_leakage_guard_strips_results_from_real_table(table):
    config = {"leakage_guard": {"forbidden_columns": ["goals_a", "goals_b", "outcome", "is_draw"]}}
    safe = leakage_safe_feature_frame(table, config)
    forbidden = set(config["leakage_guard"]["forbidden_columns"]) | TARGET_COLUMNS
    assert not (forbidden & set(safe.columns))
    assert "elo_delta" in safe.columns  # a real feature survived


def test_group_state_pre_match_invariants_on_real_data(table):
    # a team's pre-match played count must be < matchday (MD1->0, MD2-><=1, MD3-><=2)
    for col in ("played_a_pre", "played_b_pre"):
        assert (table[col] <= table["matchday"] - 1).all(), f"{col} exceeds matchday-1 (future leak)"
    assert (table["points_a_pre"] <= 3 * table["played_a_pre"]).all()
    assert (table["points_b_pre"] <= 3 * table["played_b_pre"]).all()
    # MD1 rows: a team has played 0 games in the group, so per-team state is zero
    md1 = table[table["matchday"] == 1]
    assert (md1["points_a_pre"] == 0).all() and (md1["played_a_pre"] == 0).all()
    assert (table["prior_group_draws"] <= table["prior_group_matches"]).all()
    # no match may ever see a same-day group match (final-matchday pair is simultaneous):
    assert (table["prior_group_matches"] <= 4).all(), "saw a 5th (same-day) group match"
    md3 = table[table["matchday"] == 3]
    assert (md3["prior_group_matches"] == 4).all(), "MD3 must see exactly the 4 earlier matches"


def test_group_aggregates_use_strictly_earlier_kickoff(table):
    """Independently recompute prior_group_matches with strict-before-date and compare.
    Guards against any regression to processing-order (<=) group aggregation."""
    t = table.copy()
    t["guid"] = t["tournament"].astype(str) + "|" + t["group"].astype(str)
    exp = pd.Series(0, index=t.index, dtype=int)
    for _, g in t.groupby("guid"):
        for idx, row in g.iterrows():
            exp.loc[idx] = int((g["kickoff_utc"] < row["kickoff_utc"]).sum())
    assert (t["prior_group_matches"] == exp).all(), "prior_group_matches not strictly pre-kickoff"


def test_first_group_match_has_zero_group_state(table):
    # the earliest-kickoff match in every (tournament, group) carries no prior info
    idx = table.groupby([table["tournament"], table["group"]])["kickoff_utc"].idxmin()
    first = table.loc[idx]
    assert (first["prior_group_matches"] == 0).all()
    assert (first["prior_group_draws"] == 0).all()
    assert (first["points_a_pre"] == 0).all() and (first["points_b_pre"] == 0).all()


def test_draw_rate_is_plausible(table):
    rate = (table["outcome"] == "D").mean()
    assert 0.15 <= rate <= 0.40, f"implausible overall draw rate {rate:.3f}"


def test_2026_structure(table):
    wc26 = table[table["tournament"].str.contains("2026", na=False)]
    if wc26.empty:
        pytest.skip("no 2026 rows")
    assert wc26["group"].nunique() == 12, "2026 must have 12 groups"


def test_forecast_targets_are_unplayed_and_2026(table):
    if not TARGETS.exists():
        pytest.skip("forecast_targets_2026.csv not built")
    tgt = pd.read_csv(TARGETS)
    assert (tgt["goals_a"].isna() | tgt["goals_b"].isna()).all()
    assert (tgt["matchday"].dropna().isin([2, 3])).all()
    # no overlap with the played modeling table
    assert not set(tgt["match_id"]) & set(table["match_id"])
