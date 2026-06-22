"""Leakage-safety tests for live in-play xG (StatsBomb). Synthetic shots only; no network."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wcdrawlab.research.xg_inplay import live_xg, attach_live_xg, map_sb_matches  # noqa: E402


def _shots():
    return pd.DataFrame([
        {"sb_match_id": 1, "home_team": "Alpha", "away_team": "Beta", "match_date": "2022-12-01",
         "minute": 10, "team": "Alpha", "xg": 0.3, "is_goal": 0},
        {"sb_match_id": 1, "home_team": "Alpha", "away_team": "Beta", "match_date": "2022-12-01",
         "minute": 20, "team": "Beta", "xg": 0.2, "is_goal": 0},
        {"sb_match_id": 1, "home_team": "Alpha", "away_team": "Beta", "match_date": "2022-12-01",
         "minute": 30, "team": "Alpha", "xg": 0.5, "is_goal": 1},
    ])


def test_live_xg_uses_only_shots_strictly_before_decision_minute():
    s = _shots()
    # before any shot -> 0,0
    assert live_xg(s, "Alpha", 5) == (0.0, 0.0)
    # at minute 25: Alpha's min-10 (0.3) + Beta's min-20 (0.2); min-30 excluded
    h, a = live_xg(s, "Alpha", 25)
    assert abs(h - 0.3) < 1e-9 and abs(a - 0.2) < 1e-9
    # at minute 30 the 30' shot must NOT count (strictly-before) -> no look-ahead on a goal
    h2, a2 = live_xg(s, "Alpha", 30)
    assert abs(h2 - 0.3) < 1e-9 and abs(a2 - 0.2) < 1e-9
    # full match
    h3, a3 = live_xg(s, "Alpha", 200)
    assert abs(h3 - 0.8) < 1e-9 and abs(a3 - 0.2) < 1e-9


def test_attach_live_xg_maps_and_flags_unmapped():
    inplay = pd.DataFrame([
        {"match_id": "M1", "home_team": "Alpha", "away_team": "Beta",
         "kickoff_utc": "2022-12-01T18:00:00+00:00", "decision_minute": 25, "score_diff": 0},
        {"match_id": "M2", "home_team": "Gamma", "away_team": "Delta",   # no StatsBomb match -> unmapped
         "kickoff_utc": "2022-12-02T18:00:00+00:00", "decision_minute": 25, "score_diff": 0},
    ])
    out = attach_live_xg(inplay, _shots())
    r1 = out[out.match_id == "M1"].iloc[0]
    assert r1.has_xg and abs(r1.live_xg_diff - 0.1) < 1e-9  # 0.3 - 0.2
    assert abs(r1.xg_surprise - 0.1) < 1e-9                 # diff(0.1) - score_diff(0)
    assert not out[out.match_id == "M2"].iloc[0].has_xg     # unmapped -> NaN/False


def test_map_sb_matches_joins_on_pair_and_date():
    inplay = pd.DataFrame([{"match_id": "M1", "home_team": "Alpha", "away_team": "Beta",
                            "kickoff_utc": "2022-12-01T20:00:00+00:00", "decision_minute": 1, "score_diff": 0}])
    assert map_sb_matches(inplay, _shots()) == {"M1": 1}
