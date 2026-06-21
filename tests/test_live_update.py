from pathlib import Path
import pandas as pd

from wcdrawlab.live import LivePredictionConfig, update_match_result, run_after_match_update, run_live_prediction_refresh, make_live_predictions
from wcdrawlab.pipeline import build_features


def test_update_match_result_marks_result(seed_root: Path):
    matches = pd.read_csv(seed_root / "data" / "seed" / "worldcup_2026_seed_matches.csv")
    updated = update_match_result(matches, "2026_A_03", 1, 1, source="test")
    row = updated.loc[updated["match_id"] == "2026_A_03"].iloc[0]
    assert row["goals_a"] == 1
    assert row["goals_b"] == 1
    assert "test" in row["data_source"]


def test_make_live_predictions_has_risk_columns(seed_root: Path):
    matches = pd.read_csv(seed_root / "data" / "seed" / "worldcup_2026_seed_matches.csv", parse_dates=["kickoff_utc"])
    elo = pd.read_csv(seed_root / "data" / "seed" / "seed_ratings_2026.csv", parse_dates=["rating_date"])
    odds = pd.read_csv(seed_root / "data" / "seed" / "sample_odds_2026.csv", parse_dates=["snapshot_time"])
    features = build_features(matches, elo=elo, odds=odds)
    pred, adv, edges = make_live_predictions(features, LivePredictionConfig(n_sims=10, utility_sims=5, random_seed=1))
    assert not pred.empty
    assert {"p_a_model", "p_draw_model", "p_b_model", "outcome_sd_draw", "prob_se_draw", "risk_band"}.issubset(pred.columns)
    assert not adv.empty


def test_run_after_match_update_writes_outputs(tmp_path: Path, seed_root: Path):
    current = tmp_path / "current_matches.csv"
    current.write_text((seed_root / "data" / "seed" / "worldcup_2026_seed_matches.csv").read_text(), encoding="utf-8")
    out = tmp_path / "live"
    result = run_after_match_update(
        matches_path=current,
        match_id="2026_A_03",
        goals_a=1,
        goals_b=1,
        elo_path=seed_root / "data" / "seed" / "seed_ratings_2026.csv",
        odds_path=seed_root / "data" / "seed" / "sample_odds_2026.csv",
        output_dir=out,
        current_matches_path=current,
        config=LivePredictionConfig(n_sims=10, utility_sims=5, random_seed=2),
    )
    assert (out / "predictions_remaining.csv").exists()
    assert (out / "advancement_probabilities.csv").exists()
    assert (out / "update_log.csv").exists()
    current_after = pd.read_csv(current)
    row = current_after.loc[current_after["match_id"] == "2026_A_03"].iloc[0]
    assert row["goals_a"] == 1 and row["goals_b"] == 1
    assert not result.predictions.empty
