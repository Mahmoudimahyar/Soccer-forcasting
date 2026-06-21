from pathlib import Path

import pandas as pd

from wcdrawlab.elo import (
    EloUpdateConfig,
    compute_post_match_elo,
    goal_difference_multiplier,
    update_elo_after_match_table,
)
from wcdrawlab.live import LivePredictionConfig, run_after_match_update


def test_goal_difference_multiplier():
    assert goal_difference_multiplier(0) == 1.0
    assert goal_difference_multiplier(1) == 1.0
    assert goal_difference_multiplier(2) == 1.5
    assert goal_difference_multiplier(3) == 1.75
    assert goal_difference_multiplier(-4) == 1.875


def test_compute_post_match_elo_zero_sum():
    out = compute_post_match_elo(1600, 1500, 2, 0, EloUpdateConfig(k=60, round_change=True))
    assert out["elo_change_a"] == -out["elo_change_b"]
    assert out["elo_a_post"] + out["elo_b_post"] == 3100
    assert out["elo_a_post"] > 1600


def test_update_elo_after_match_table_appends_two_rows(seed_root: Path):
    matches = pd.read_csv(seed_root / "data" / "seed" / "worldcup_2026_seed_matches.csv", parse_dates=["kickoff_utc"])
    ratings = pd.read_csv(seed_root / "data" / "seed" / "seed_ratings_2026.csv", parse_dates=["rating_date"])
    updated, audit = update_elo_after_match_table(ratings, matches, "2026_A_03", 1, 1)
    assert len(updated) == len(ratings) + 2
    assert len(audit) == 1
    assert {"Czechia", "South Africa"}.issubset(set(updated.tail(2)["team"]))
    assert "elo_change_a" in audit.columns


def test_after_match_update_writes_current_elo_and_uses_it_next_time(tmp_path: Path, seed_root: Path):
    current_matches = tmp_path / "current_matches.csv"
    current_matches.write_text((seed_root / "data" / "seed" / "worldcup_2026_seed_matches.csv").read_text(), encoding="utf-8")
    current_elo = tmp_path / "current_elo.csv"
    out = tmp_path / "live"

    first = run_after_match_update(
        matches_path=current_matches,
        match_id="2026_A_03",
        goals_a=1,
        goals_b=1,
        elo_path=seed_root / "data" / "seed" / "seed_ratings_2026.csv",
        odds_path=seed_root / "data" / "seed" / "sample_odds_2026.csv",
        output_dir=out,
        current_matches_path=current_matches,
        current_elo_path=current_elo,
        config=LivePredictionConfig(n_sims=8, utility_sims=4, random_seed=3),
    )
    assert current_elo.exists()
    rows_after_first = len(pd.read_csv(current_elo))
    assert rows_after_first > len(pd.read_csv(seed_root / "data" / "seed" / "seed_ratings_2026.csv"))

    # Second update should read current_elo rather than resetting back to seed ratings.
    second = run_after_match_update(
        matches_path=current_matches,
        match_id="2026_A_04",
        goals_a=0,
        goals_b=0,
        elo_path=seed_root / "data" / "seed" / "seed_ratings_2026.csv",
        odds_path=seed_root / "data" / "seed" / "sample_odds_2026.csv",
        output_dir=out,
        current_matches_path=current_matches,
        current_elo_path=current_elo,
        config=LivePredictionConfig(n_sims=8, utility_sims=4, random_seed=4),
    )
    assert len(pd.read_csv(current_elo)) == rows_after_first + 2
    assert second.updated_elo is not None
