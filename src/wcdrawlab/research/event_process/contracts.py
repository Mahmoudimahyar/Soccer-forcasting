"""Provider-neutral contracts for the event-process intelligence engine.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This module defines the vocabulary and lightweight dataclasses shared across the engine. It is
deliberately provider-neutral: the canonical event model is what every downstream extractor consumes,
and a *source-quality* flag accompanies every derived field so that consumers never silently treat a
missing/unsupported source field as zero.

SOURCE-QUALITY FLAGS (never imputed-as-zero):
  available_verified  -- the source provides the underlying field directly and unambiguously.
  available_partial   -- the source provides a usable proxy or only covers part of the population
                         (e.g. xG present on newer events only; counterpress proxied from `counterpress`).
  unavailable         -- the source schema does not carry the field at all (e.g. shot freeze-frames
                         absent for a provider that ships no defensive positions).
  unknown             -- the field could not be determined for this row (e.g. a NULL where the source
                         normally populates), distinct from a structural `unavailable`.

LEAKAGE CONTRACT (enforced by snapshots.py, restated here for traceability):
  * Features at snapshot minute t use ONLY events with match-clock minute <= t.
  * Regulation only: period in (1, 2) and minute <= 90. No extra-time, no shootout.
  * No final score / totals / later-substitution information leaks into a snapshot.
  * Club rows are NEVER emitted as international test rows (governed by registry/eval, not here).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

SCHEMA_VERSION = "event_process_v1"

# --- source-quality vocabulary -------------------------------------------------------------------
AVAILABLE_VERIFIED = "available_verified"
AVAILABLE_PARTIAL = "available_partial"
UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"
QUALITY_FLAGS = (AVAILABLE_VERIFIED, AVAILABLE_PARTIAL, UNAVAILABLE, UNKNOWN)

# --- canonical pitch frame -----------------------------------------------------------------------
# StatsBomb open-data convention; the engine normalizes every provider into this frame.
PITCH_LENGTH = 120.0   # x-axis: own goal-line (0) -> opponent goal-line (120)
PITCH_WIDTH = 80.0     # y-axis: left touchline (0) -> right touchline (80)
GOAL_CENTER_Y = 40.0
OPP_GOAL_X = 120.0
# attacking-third / box geometry (canonical frame, attacking towards x=120)
FINAL_THIRD_X = 80.0
BOX_X = 102.0
BOX_Y_LOW = 18.0
BOX_Y_HIGH = 62.0
# channels (lateral thirds of the pitch width)
LEFT_CHANNEL_Y = 80.0 / 3.0          # 0 .. 26.67
RIGHT_CHANNEL_Y = 2.0 * 80.0 / 3.0   # 53.33 .. 80


# --- canonical attack-phase vocabulary -----------------------------------------------------------
PHASE_OPEN_PLAY = "open_play"
PHASE_SET_PIECE = "set_piece"
PHASE_CORNER = "corner"
PHASE_FREE_KICK = "free_kick"
PHASE_THROW_IN = "throw_in"
PHASE_PENALTY = "penalty"
PHASE_GOAL_KICK = "goal_kick"
PHASE_KICK_OFF = "kick_off"
PHASE_KEEPER = "from_keeper"
PHASE_COUNTER = "counter"
PHASE_OTHER = "other"
PHASE_UNKNOWN = "unknown"


@dataclass
class FieldQuality:
    """A single derived field's value paired with its source-quality flag and an optional note."""
    value: Any
    quality: str
    note: Optional[str] = None

    def __post_init__(self):
        if self.quality not in QUALITY_FLAGS:
            raise ValueError(f"invalid source-quality flag {self.quality!r}; must be one of {QUALITY_FLAGS}")


@dataclass
class SourceTrace:
    """Traceability for a derived artifact back to its raw source, without embedding raw JSON."""
    provider: str                 # e.g. 'statsbomb_open'
    source_match_id: str          # provider-native match id
    source_sha256: str            # hash of the raw source bytes (raw never tracked)
    n_source_events: int
    bridge_id: Optional[str] = None         # api<->statsbomb bridge id when known
    api_fixture_id: Optional[str] = None
    competition_label: Optional[str] = None
    comp_type: Optional[str] = None         # 'international' | 'club'
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SourceQualityReport:
    """Per-match roll-up of which canonical capabilities the source actually supported."""
    provider: str
    source_match_id: str
    capabilities: dict = field(default_factory=dict)   # capability_name -> quality flag

    def set(self, capability: str, quality: str, note: Optional[str] = None):
        if quality not in QUALITY_FLAGS:
            raise ValueError(f"invalid quality {quality!r}")
        self.capabilities[capability] = {"quality": quality, "note": note}

    def to_dict(self) -> dict:
        return {"provider": self.provider, "source_match_id": self.source_match_id,
                "capabilities": self.capabilities}


# Canonical capability names tracked in every SourceQualityReport. Keeping this list explicit makes
# cross-provider coverage auditable and prevents a missing capability from being read as "supported".
CAPABILITIES = (
    "possession_structure",
    "territory_thirds",
    "box_entries",
    "channels",
    "deep_progression",
    "field_tilt",
    "attack_phase",
    "counter_proxy",
    "possession_to_shot_chain",
    "pressure",
    "counterpress_proxy",
    "recoveries",
    "turnovers",
    "blocks_clearances",
    "shot_events",
    "shot_xg",
    "shot_location",
    "shot_freeze_frame",
    "big_chance_proxy",
    "match_state",
    "cards",
)
