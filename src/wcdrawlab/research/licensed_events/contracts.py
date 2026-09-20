"""Canonical dataclasses + enums for the provider-neutral licensed-event contract (mirrors schemas/)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

PERIODS = {"first_half", "second_half", "et_first", "et_second", "shootout", "pre", "post", "unknown"}
EVENT_TYPES = {"goal", "own_goal", "penalty_scored", "penalty_missed", "penalty_awarded", "shot",
               "shot_on_target", "assist", "yellow_card", "second_yellow", "red_card", "substitution",
               "lineup", "formation", "var_event", "var_goal_cancelled", "corner", "foul", "offside",
               "kickoff", "halftime", "fulltime", "other", "unknown"}
CAUSAL = {"historical_only", "delayed_live_eligible", "live_eligible", "unknown_fail_closed"}
CORRECTION = {"original", "corrected", "retracted", "unknown"}


@dataclass
class LicensedEvent:
    provider_name: str
    provider_match_id: str
    canonical_match_id: str
    competition: str
    season: str
    home_team_id: str
    away_team_id: str
    event_type: str
    source_snapshot_hash: str
    rights_classification: str
    retrieval_time_utc: str
    causal_eligibility: str = "unknown_fail_closed"
    period: str = "unknown"
    team_id: Optional[str] = None
    player_id: Optional[str] = None
    referee_id: Optional[str] = None
    event_time_utc: Optional[str] = None
    match_clock_s: Optional[float] = None
    source_publication_time_utc: Optional[str] = None
    provider_update_time_utc: Optional[str] = None
    correction_time_utc: Optional[str] = None
    shot_location: Optional[dict] = None
    shot_outcome: Optional[str] = None
    xg: Optional[float] = None
    assist_player_id: Optional[str] = None
    sub_in_player_id: Optional[str] = None
    sub_out_player_id: Optional[str] = None
    position: Optional[str] = None
    formation: Optional[str] = None
    event_confidence: Optional[float] = None
    correction_status: str = "original"
    duplicate_status: str = "unique"
    reconciliation_status: str = "unreconciled"
    availability_status: str = "unknown"
    source_support: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type {self.event_type}")
        if self.period not in PERIODS:
            raise ValueError(f"unknown period {self.period}")
        if self.causal_eligibility not in CAUSAL:
            raise ValueError(f"unknown causal_eligibility {self.causal_eligibility}")
        if self.correction_status not in CORRECTION:
            raise ValueError(f"unknown correction_status {self.correction_status}")


@dataclass
class LicensedLineup:
    provider_name: str
    provider_match_id: str
    canonical_match_id: str
    team_id: str
    source_snapshot_hash: str
    rights_classification: str
    retrieval_time_utc: str
    formation: Optional[str] = None
    starters: list = field(default_factory=list)   # [{player_id, position, shirt_number}]
    bench: list = field(default_factory=list)
    captain_player_id: Optional[str] = None
    lineup_confirmed: str = "unknown"
    source_publication_time_utc: Optional[str] = None
    causal_eligibility: str = "unknown_fail_closed"
    source_support: dict = field(default_factory=dict)


@dataclass
class ProviderCapabilities:
    """Which contract fields a provider/feed populates. Unknown -> treated as unsupported."""
    provider_name: str
    supports: dict = field(default_factory=dict)   # field_name -> bool

    def has(self, field_name: str) -> bool:
        return bool(self.supports.get(field_name, False))
