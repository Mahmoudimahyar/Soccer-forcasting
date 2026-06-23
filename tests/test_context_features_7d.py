"""Phase 3 / 7D context-feature leakage + computation tests. Pure; no network, no model fitting."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research import context_features as CF  # noqa: E402


def test_haversine_known_distance():
    d = CF.haversine_km(51.5074, -0.1278, 48.8566, 2.3522)  # London->Paris ~343 km
    assert 330 < d < 355


def test_missing_venue_travel_is_nan():
    d = CF.travel_distance_km(None, None, 48.0, 2.0)
    assert d != d  # NaN


def test_rest_days():
    assert abs(CF.rest_days("2026-06-20T18:00:00+00:00", "2026-06-24T18:00:00+00:00") - 4.0) < 1e-9
    assert CF.rest_days(None, "2026-06-24T18:00:00+00:00") != 4.0  # NaN


def test_timezone_displacement():
    assert CF.timezone_displacement_hours(1.0, -5.0) == 6.0
    assert CF.timezone_displacement_hours(None, -5.0) != 6.0  # NaN


def test_neutral_site_both_teams_travel():
    venue = (40.7, -74.0)
    home = CF.travel_distance_km(51.5, -0.13, *venue)   # England -> NY
    away = CF.travel_distance_km(52.5, 13.4, *venue)    # Germany -> NY
    assert home > 0 and away > 0


def test_weather_forecast_eligible_before_decision_only():
    assert CF.weather_feature_eligible("forecast", "2026-06-24T10:00:00+00:00", "2026-06-24T16:30:00+00:00") is True
    assert CF.weather_feature_eligible("forecast", "2026-06-24T17:00:00+00:00", "2026-06-24T16:30:00+00:00") is False


def test_observed_weather_never_eligible_as_prematch_feature():
    assert CF.weather_feature_eligible("observed", "2026-06-24T10:00:00+00:00", "2026-06-24T16:30:00+00:00") is False
    assert CF.weather_feature_eligible("observed", "2026-06-24T19:00:00+00:00", "2026-06-24T16:30:00+00:00") is False


def test_contract_planes_and_leakage_present():
    assert CF.feature_plane("weather_observed") == "retrospective"
    assert CF.feature_plane("rest_days") == "pre_match"
    assert CF.feature_plane("nonexistent") == "neither"
    assert all("leakage_risk" in v for v in CF.CONTEXT_FEATURE_CONTRACT.values())
