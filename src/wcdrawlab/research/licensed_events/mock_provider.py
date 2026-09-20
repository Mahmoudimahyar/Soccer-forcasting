"""Mock provider adapter + synthetic fixtures (Phase 3). NOT a real client: no network, no credentials.
Used only to exercise the contract/normalization/reconciliation/availability logic in tests."""
from __future__ import annotations

from . import contracts as C
from . import provider_interface as PI

FULL_CAPS = {"player_ids": True, "positions": True, "lineups": True, "substitutions": True, "shots": True,
             "shot_locations": True, "xg": True, "cards": True, "publication_time": True, "corrections": True}
EVENTS_ONLY_CAPS = {"player_ids": True, "cards": True, "substitutions": True, "publication_time": False}


class MockProvider(PI.ProviderAdapter):
    provider_name = "mock_provider"
    rights_classification = "mock_research_only"

    def __init__(self, caps=None, availability=None):
        self._caps = caps if caps is not None else dict(FULL_CAPS)
        self._avail = availability if availability is not None else {
            "has_publication_time": True, "has_event_time": True, "historical_available": True, "live_available": True}

    def declare_capabilities(self):
        return C.ProviderCapabilities(self.provider_name, dict(self._caps))

    def declare_availability(self):
        return dict(self._avail)


# ---- synthetic raw fixtures (provider-shaped dicts) ----
def _base(**kw):
    d = {"provider_match_id": "MP1", "canonical_match_id": "wc/2026/2026-06-20/HOME/AWAY",
         "competition": "world_cup", "season": "2026", "home_team_id": "HOME", "away_team_id": "AWAY",
         "retrieval_time_utc": "2026-06-20T20:00:00+00:00", "source_snapshot_hash": "snap1"}
    d.update(kw)
    return d


def fixture_full_event():
    return _base(event_type="goal", team_id="HOME", player_id="P10", match_clock_s=300.0, period="1h",
                 event_time_utc="2026-06-20T19:05:00+00:00", source_publication_time_utc="2026-06-20T19:05:10+00:00",
                 shot_location={"x": 0.9, "y": 0.5}, xg=0.42)


def fixture_events_only():
    return _base(event_type="yellow_card", team_id="AWAY", player_id="P22", match_clock_s=1200.0, period="1h")


def fixture_lineup_sub():
    return _base(event_type="substitution", team_id="HOME", sub_in_player_id="P15", sub_out_player_id="P10",
                 match_clock_s=3600.0, period="2h", source_publication_time_utc="2026-06-20T20:05:00+00:00")


def fixture_card_correction():
    return _base(event_type="yellow_card", team_id="HOME", player_id="P7", match_clock_s=600.0, period="1h",
                 correction_status="corrected", correction_time_utc="2026-06-20T19:20:00+00:00")


def fixture_var_reversal():
    return _base(event_type="var_goal_cancelled", team_id="HOME", player_id="P10", match_clock_s=305.0,
                 period="1h", correction_status="retracted")


def fixture_delayed_event():
    # publication well after event -> still historical/delayed; safe for live only if pub <= decision
    return _base(event_type="goal", team_id="AWAY", player_id="P30", match_clock_s=900.0, period="1h",
                 event_time_utc="2026-06-20T19:15:00+00:00", source_publication_time_utc="2026-06-20T19:18:00+00:00")


def fixture_missing_player_id():
    return _base(event_type="foul", team_id="AWAY", player_id=None, match_clock_s=700.0, period="1h")


def fixture_shot_xg():
    return _base(event_type="shot_on_target", team_id="HOME", player_id="P9", match_clock_s=1500.0, period="1h",
                 shot_location={"x": 0.8, "y": 0.4}, xg=0.18)


def fixture_conflicting_event():
    # same goal, different scorer per provider B
    return _base(event_type="goal", team_id="HOME", player_id="P11", match_clock_s=302.0, period="1h")


def fixture_incomplete_match():
    return _base(event_type="goal", team_id="HOME", player_id=None, match_clock_s=None, period="unknown")


def fixture_historical_only():
    return _base(event_type="goal", team_id="HOME", player_id="P10", match_clock_s=300.0, period="1h",
                 event_time_utc="2018-06-20T19:05:00+00:00")  # no publication time


def fixture_live_eligible():
    return _base(event_type="goal", team_id="HOME", player_id="P10", match_clock_s=300.0, period="1h",
                 event_time_utc="2026-06-20T19:05:00+00:00", source_publication_time_utc="2026-06-20T19:05:05+00:00")
