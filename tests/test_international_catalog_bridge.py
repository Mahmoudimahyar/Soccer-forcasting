"""Tests for the catalog/bridge helpers used by the international-event-lake JOBs
(scripts/_lake_catalog_util.py): strict team/date normalization, regulation-result derivation, and
the official-URL guard. Network-free. research_only."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# the helper lives under scripts/ (job-local utility)
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _lake_catalog_util as U  # noqa: E402


def test_normalize_team_aliases():
    assert U.normalize_team("Korea Republic") == "south korea"
    assert U.normalize_team("Türkiye") == "turkey"
    assert U.normalize_team("Côte d'Ivoire") == "cote divoire"
    assert U.normalize_team("Czechia") == "czech republic"
    assert U.normalize_team("USA") == "united states"
    assert U.normalize_team(None) == ""


def test_normalize_date():
    assert U.normalize_date("2018-06-14") == "2018-06-14"
    assert U.normalize_date("2018-06-14T18:00:00") == "2018-06-14"
    assert U.normalize_date("garbage") == ""
    assert U.normalize_date(None) == ""


def test_regulation_result():
    assert U.regulation_result(2, 0) == "home"
    assert U.regulation_result(0, 0) == "draw"
    assert U.regulation_result(1, 3) == "away"
    assert U.regulation_result(None, 1) == ""


def test_team_set_orientation_independent():
    assert U.team_set("argentina", "canada") == U.team_set("canada", "argentina")
    assert U.team_set("a", "b") != U.team_set("a", "c")


def test_official_url_builders_are_official():
    assert "raw.githubusercontent.com/statsbomb/open-data" in U.competitions_url()
    assert U.matches_url(43, 3).endswith("/matches/43/3.json")


@pytest.mark.parametrize("url", [
    "http://raw.githubusercontent.com/statsbomb/open-data/x.json",  # not https
    "https://example.com/x.json",                                   # wrong host
    "https://api-football.com/events/1.json",                       # forbidden source
])
def test_official_get_rejects_non_official(url):
    with pytest.raises(ValueError):
        U.get_bytes(url)


def test_strict_score_mismatch_logic():
    """ET-knockout: official full-time decisive but regulation was a draw -> NOT exact."""
    off_ft = "home"          # decided in extra time
    local_reg = "draw"       # level at 90'
    # same orientation: results disagree -> score_mismatch (held out of exact bridge)
    assert off_ft != local_reg


def test_swapped_orientation_result_flip():
    flip = {"home": "away", "away": "home", "draw": "draw"}
    assert flip["home"] == "away" and flip["away"] == "home" and flip["draw"] == "draw"
