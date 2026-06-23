"""Leakage-safe travel / rest / weather-eligibility context features (research-only).

All features for a match use ONLY information available before its kickoff:
  - rest_days / travel_km come from the team's PREVIOUS match (strictly earlier kickoff);
  - venue altitude is known pre-tournament;
  - weather is eligible only if the forecast was ISSUED at/before the decision time.

These are research features; they are NOT added to the approved B1 runtime model. Adding any of them
to a candidate requires the frozen promotion protocol (out-of-sample, no-regression).
"""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

import pandas as pd


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return float(2 * r * asin(sqrt(a)))


def weather_forecast_eligible(issued_at_utc, decision_timestamp_utc) -> bool:
    """A weather forecast may inform a prediction only if it was issued at/before the decision time."""
    return pd.Timestamp(issued_at_utc) <= pd.Timestamp(decision_timestamp_utc)


def build_context_features(matches: pd.DataFrame, venues: pd.DataFrame | None = None) -> pd.DataFrame:
    """For each match row (match_id, kickoff_utc, team_a, team_b, optional venue), compute per-team
    rest_days and travel_km from each team's PREVIOUS match only. Returns long form
    [match_id, team_id, prev_match_kickoff_utc, rest_days, prev_venue, travel_km, altitude_m]."""
    m = matches.copy()
    m["kickoff_utc"] = pd.to_datetime(m["kickoff_utc"], utc=True)
    vcoord = {}
    if venues is not None:
        for r in venues.itertuples():
            vcoord[r.venue] = (r.lat, r.lon, getattr(r, "altitude_m", None))
    # long form: one row per (match, team)
    longs = []
    for r in m.itertuples():
        for team in (r.team_a, r.team_b):
            longs.append({"match_id": r.match_id, "team_id": team, "kickoff_utc": r.kickoff_utc,
                          "venue": getattr(r, "venue", None)})
    L = pd.DataFrame(longs).sort_values(["team_id", "kickoff_utc"]).reset_index(drop=True)

    out = []
    for team, grp in L.groupby("team_id", sort=False):
        prev_ko = None
        prev_venue = None
        for row in grp.itertuples():
            rest = (row.kickoff_utc - prev_ko).total_seconds() / 86400.0 if prev_ko is not None else None
            travel = None
            if prev_venue and row.venue and prev_venue in vcoord and row.venue in vcoord:
                la1, lo1, _ = vcoord[prev_venue]
                la2, lo2, _ = vcoord[row.venue]
                travel = haversine_km(la1, lo1, la2, lo2)
            alt = vcoord.get(row.venue, (None, None, None))[2] if row.venue else None
            out.append({"match_id": row.match_id, "team_id": team,
                        "prev_match_kickoff_utc": prev_ko, "rest_days": rest,
                        "prev_venue": prev_venue, "travel_km": travel, "altitude_m": alt})
            prev_ko, prev_venue = row.kickoff_utc, row.venue
    return pd.DataFrame(out)


# ---- Phase 3 / 7D additions: standalone helpers + availability contract ----
def rest_days(prev_kickoff_iso, this_kickoff_iso) -> float:
    if not prev_kickoff_iso or not this_kickoff_iso:
        return float("nan")
    return (pd.Timestamp(this_kickoff_iso) - pd.Timestamp(prev_kickoff_iso)).total_seconds() / 86400.0


def timezone_displacement_hours(home_utc_offset_h, venue_utc_offset_h) -> float:
    if home_utc_offset_h is None or venue_utc_offset_h is None:
        return float("nan")
    return abs(float(venue_utc_offset_h) - float(home_utc_offset_h))


def travel_distance_km(team_home_lat, team_home_lon, venue_lat, venue_lon) -> float:
    """Distance a team travels to the venue. Neutral-site tournaments -> compute for BOTH teams."""
    if None in (team_home_lat, team_home_lon, venue_lat, venue_lon):
        return float("nan")
    return haversine_km(team_home_lat, team_home_lon, venue_lat, venue_lon)


def weather_feature_eligible(kind: str, issued_at_utc, decision_timestamp_utc) -> bool:
    """forecast issued at/before decision -> eligible; observed (post-hoc) -> NEVER a pre-match feature."""
    if kind == "observed":
        return False
    if kind != "forecast" or issued_at_utc is None or decision_timestamp_utc is None:
        return False
    return weather_forecast_eligible(issued_at_utc, decision_timestamp_utc)


# plane in {pre_match, in_play, retrospective, neither}; leakage_risk in {none, low, medium, high}
CONTEXT_FEATURE_CONTRACT = {
    "venue_lat":               {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "venue_lon":               {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "venue_altitude_m":        {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "roof_indoor":             {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "kickoff_utc":             {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "kickoff_local":           {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "home_travel_km":          {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "away_travel_km":          {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "timezone_displacement_h": {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "rest_days":               {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "travel_days":             {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "low"},
    "match_location_sequence": {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "none"},
    "weather_forecast":        {"plane": "pre_match", "known_before_kickoff": True,  "leakage_risk": "medium",
                                "rule": "use only a forecast issued at/before the decision time"},
    "weather_observed":        {"plane": "retrospective", "known_before_kickoff": False, "leakage_risk": "high",
                                "rule": "never a pre-match/in-play feature"},
}


def feature_plane(name: str) -> str:
    return CONTEXT_FEATURE_CONTRACT.get(name, {}).get("plane", "neither")
