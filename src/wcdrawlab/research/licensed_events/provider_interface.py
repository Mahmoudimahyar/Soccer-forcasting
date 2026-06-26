"""Abstract provider adapter (Phase 3). Real clients are NOT implemented here; only the contract a future
licensed adapter must satisfy. Adapters fail closed on unknown timing semantics and never invent IDs/fields.
"""
from __future__ import annotations

import abc

from . import availability as AV
from . import contracts as C
from . import normalization as N


class ProviderAdapter(abc.ABC):
    """A licensed-provider adapter MUST declare capabilities, rights, and availability, and normalize raw
    provider payloads into the provider-neutral contract WITHOUT inventing data."""

    provider_name: str = "abstract"
    rights_classification: str = "unknown_requires_vendor_confirmation"
    # marker: these adapters are research-only and may never be used by runtime/trading
    RUNTIME_ELIGIBLE = False
    TRADE_ELIGIBLE = False
    LIVE_ELIGIBLE = False

    @abc.abstractmethod
    def declare_capabilities(self) -> C.ProviderCapabilities: ...

    @abc.abstractmethod
    def declare_availability(self) -> dict:
        """Return dict with has_publication_time/has_event_time/historical_available/live_available."""

    def declare_rights(self) -> str:
        return self.rights_classification

    def _eligibility(self) -> str:
        a = self.declare_availability()
        return AV.causal_eligibility(a.get("has_publication_time", False), a.get("has_event_time", False),
                                     a.get("historical_available", False), a.get("live_available", False))

    def normalize_event(self, raw: dict) -> C.LicensedEvent:
        """Base normalization: preserve provider IDs + source hash, fail-closed eligibility, no invented data.
        Subclasses map provider field names into the canonical kwargs via `field_map`."""
        caps = self.declare_capabilities()
        elig = self._eligibility()
        snap = raw.get("source_snapshot_hash") or N.source_hash(repr(sorted(raw.items())))
        ev = C.LicensedEvent(
            provider_name=self.provider_name,
            provider_match_id=str(raw["provider_match_id"]),
            canonical_match_id=str(raw.get("canonical_match_id") or raw["provider_match_id"]),
            competition=str(raw.get("competition", "unknown")),
            season=str(raw.get("season", "unknown")),
            home_team_id=str(raw.get("home_team_id", "unknown")),
            away_team_id=str(raw.get("away_team_id", "unknown")),
            event_type=str(raw.get("event_type", "unknown")),
            source_snapshot_hash=snap,
            rights_classification=self.rights_classification,
            retrieval_time_utc=str(raw.get("retrieval_time_utc", "unknown")),
            causal_eligibility=elig,
            period=N.normalize_period(raw.get("period", "unknown")),
            team_id=raw.get("team_id"),
            player_id=N.preserve_player_id(raw.get("player_id")) if caps.has("player_ids") else None,
            event_time_utc=raw.get("event_time_utc"),
            match_clock_s=raw.get("match_clock_s"),
            source_publication_time_utc=raw.get("source_publication_time_utc") if caps.has("publication_time") else None,
            provider_update_time_utc=raw.get("provider_update_time_utc"),
            correction_time_utc=raw.get("correction_time_utc"),
            shot_location=raw.get("shot_location") if caps.has("shot_locations") else None,
            xg=raw.get("xg") if caps.has("xg") else None,
            sub_in_player_id=N.preserve_player_id(raw.get("sub_in_player_id")) if caps.has("player_ids") else None,
            sub_out_player_id=N.preserve_player_id(raw.get("sub_out_player_id")) if caps.has("player_ids") else None,
            position=raw.get("position") if caps.has("positions") else None,
            correction_status=str(raw.get("correction_status", "original")),
            source_support=dict(caps.supports),
        )
        return ev
