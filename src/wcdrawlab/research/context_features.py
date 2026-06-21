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
