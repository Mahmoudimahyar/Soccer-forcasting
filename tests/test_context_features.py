"""Leakage tests for travel/rest/weather context features. No network."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wcdrawlab.research.context_features import (  # noqa: E402
    haversine_km, weather_forecast_eligible, build_context_features,
)

VENUES = pd.read_csv(Path(__file__).resolve().parents[1] / "data/reference/venues_2026.csv")


def test_haversine_basic():
    assert haversine_km(0, 0, 0, 0) == 0.0
    d = haversine_km(40.814, -74.074, 33.953, -118.339)   # MetLife -> SoFi (~NY to LA)
    assert 3700 < d < 4100


def test_weather_eligibility_is_decision_gated():
    assert weather_forecast_eligible("2026-06-21T10:00:00Z", "2026-06-21T12:00:00Z") is True
    assert weather_forecast_eligible("2026-06-21T13:00:00Z", "2026-06-21T12:00:00Z") is False


def _matches():
    return pd.DataFrame([
        {"match_id": "g1", "kickoff_utc": "2026-06-12T18:00:00Z", "team_a": "X", "team_b": "Y", "venue": "MetLife Stadium"},
        {"match_id": "g2", "kickoff_utc": "2026-06-17T18:00:00Z", "team_a": "X", "team_b": "Z", "venue": "SoFi Stadium"},
        {"match_id": "g3", "kickoff_utc": "2026-06-22T18:00:00Z", "team_a": "X", "team_b": "W", "venue": "Lumen Field"},
    ])


def test_rest_and_travel_use_only_previous_match():
    feats = build_context_features(_matches(), VENUES)
    x = feats[feats.team_id == "X"].set_index("match_id")
    assert pd.isna(x.loc["g1", "rest_days"])            # first match: no prior
    assert abs(x.loc["g2", "rest_days"] - 5.0) < 1e-6   # Jun 12 -> Jun 17
    assert x.loc["g2", "travel_km"] > 3000              # MetLife -> SoFi
    # every feature's source (prev match) is strictly before this kickoff
    j = feats.merge(_matches()[["match_id", "kickoff_utc"]], on="match_id")
    j["kickoff_utc"] = pd.to_datetime(j["kickoff_utc"], utc=True)
    j["prev_match_kickoff_utc"] = pd.to_datetime(j["prev_match_kickoff_utc"], utc=True)
    have_prev = j.prev_match_kickoff_utc.notna()
    assert (j.loc[have_prev, "prev_match_kickoff_utc"] < j.loc[have_prev, "kickoff_utc"]).all()


def test_future_match_does_not_change_earlier_features():
    full = build_context_features(_matches(), VENUES)
    partial = build_context_features(_matches().iloc[:2], VENUES)   # drop g3 (future)
    a = full[(full.team_id == "X") & (full.match_id == "g2")].iloc[0]
    b = partial[(partial.team_id == "X") & (partial.match_id == "g2")].iloc[0]
    assert abs(a.rest_days - b.rest_days) < 1e-9 and abs(a.travel_km - b.travel_km) < 1e-9
