"""Tests for the competition-agnostic in-play state builder (guards the elo-lookup itertuples bug)."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.inplay_dataset import _elo_lookup_from_history, build_state_for_competition  # noqa: E402


def test_elo_lookup_builds_without_itertuples_error():
    e = pd.DataFrame({"date": ["2024-06-14", "2022-11-20"], "team_a": ["Germany", "Qatar"],
                      "team_b": ["Scotland", "Ecuador"], "elo_a_pre": [1900.0, 1500.0],
                      "elo_b_pre": [1800.0, 1700.0], "elo_a_post": [1, 1], "elo_b_post": [1, 1]})
    lut = _elo_lookup_from_history(e)
    assert len(lut) == 2
    from wcdrawlab.ingest import canonical_team_name as c
    assert (("2024-06-14", frozenset((c("Germany"), c("Scotland")))) in lut)


def test_build_state_for_competition_euro2024_if_cached():
    cache = ROOT / "data/raw/api_football_euro2024"
    if not (cache / "fixtures.json").exists() or not list(cache.glob("events_*.json")):
        import pytest; pytest.skip("euro2024 cache not present")
    elo = pd.read_csv(ROOT / "data/processed/elo_history.csv")
    df = build_state_for_competition(cache, "EURO2024", elo)
    assert len(df) > 0 and (df.tournament == "EURO2024").all()
    # valid probabilities + leakage-safe score (<= final)
    assert ((df.p_home_elo + df.p_draw_elo + df.p_away_elo).round(6) == 1.0).all()
    assert (df.score_home <= df.final_score_home).all() and (df.score_away <= df.final_score_away).all()
    assert df.source_snapshot_sha256.str.fullmatch(r"[0-9a-f]{16}").all()
