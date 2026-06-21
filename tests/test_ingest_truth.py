from __future__ import annotations

import pandas as pd
from wcdrawlab.truth import binomial_group_draw_distribution
from wcdrawlab.ingest import canonical_team_name, normalize_international_results


def test_binomial_group_draw_distribution_sums_to_one():
    d = binomial_group_draw_distribution(0.24)
    assert abs(d["probability"].sum() - 1.0) < 1e-12
    p4 = float(d.loc[d["draws"] == 4, "probability"].iloc[0])
    assert 0.02 < p4 < 0.04


def test_team_alias():
    assert canonical_team_name("USA") == "United States"
    assert canonical_team_name("Czech Republic") == "Czechia"


def test_normalize_international_results():
    raw = pd.DataFrame({
        "date": ["2022-11-21"],
        "home_team": ["USA"],
        "away_team": ["Wales"],
        "home_score": [1],
        "away_score": [1],
        "tournament": ["FIFA World Cup"],
        "neutral": [True],
        "city": ["Al Rayyan"],
        "country": ["Qatar"],
    })
    out = normalize_international_results(raw)
    assert out.loc[0, "team_a"] == "United States"
    assert out.loc[0, "goals_a"] == 1
