"""Canonical, provider-neutral commentary record + enums (Phase 3). research_only."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

SCHEMA_VERSION = "commentary_record_v1"

CAUSAL_ELIGIBILITY = {
    "live_eligible", "delayed_live_eligible", "historical_weak_supervision_only",
    "historical_alignment_only", "source_time_unknown", "rights_restricted", "rejected",
}
EVENT_TAXONOMY = {
    "goal", "own_goal", "penalty_scored", "penalty_missed", "penalty_awarded", "yellow_card",
    "second_yellow", "red_card", "substitution", "VAR_review", "VAR_goal_cancelled", "shot",
    "shot_on_target", "corner", "foul", "offside", "kickoff", "halftime", "fulltime", "other", "unknown",
}


@dataclass
class CommentaryRecord:
    # identity
    canonical_commentary_id: str
    source_id: str
    canonical_match_id: str | None = None
    provider_match_id: str | None = None
    competition_id: str | None = None
    competition_name: str | None = None
    season_id: str | None = None
    home_team_id: str | None = None
    away_team_id: str | None = None
    language: str | None = None
    source_url_or_reference: str | None = None
    source_content_hash: str | None = None
    rights_classification: str | None = None
    source_provenance_version: str = "v1"
    # timing
    period: int | None = None
    match_clock_minute: int | None = None
    match_clock_second: int | None = None
    event_time_utc_if_known: str | None = None
    commentary_time_as_reported: str | None = None
    publication_time_utc_if_known: str | None = None
    retrieval_time_utc: str | None = None
    source_latency_seconds_if_measured: float | None = None
    safety_lag_seconds: float = 0.0
    causal_eligibility_status: str = "source_time_unknown"
    # text + structure (raw text NEVER stored in canonical rows committed to git)
    raw_text_reference_only: str | None = None
    normalized_text: str | None = None
    language_confidence: float | None = None
    text_quality_status: str | None = None
    linked_event_type: str = "unknown"
    linked_event_team_id: str | None = None
    linked_player_id: str | None = None
    linked_player_name_raw: str | None = None
    linked_assistant_player_id: str | None = None
    linked_event_id: str | None = None
    event_link_confidence: float | None = None
    entity_resolution_confidence: float | None = None
    event_alignment_confidence: float | None = None
    # audit
    is_duplicate: bool = False
    is_correction: bool = False
    correction_target_id: str | None = None
    source_order_index: int | None = None
    raw_snapshot_hash: str | None = None
    parser_version: str = "commentary_parser_v1"
    schema_version: str = SCHEMA_VERSION
    notes: str = ""

    def __post_init__(self):
        if self.causal_eligibility_status not in CAUSAL_ELIGIBILITY:
            raise ValueError(f"bad causal_eligibility_status {self.causal_eligibility_status!r}")
        if self.linked_event_type not in EVENT_TAXONOMY:
            raise ValueError(f"bad linked_event_type {self.linked_event_type!r}")

    def to_dict(self):
        return asdict(self)
