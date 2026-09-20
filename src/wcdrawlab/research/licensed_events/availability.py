"""Causal availability + fail-closed eligibility (Phase 3). Mirrors the commentary causal rule:
live use requires publication_time <= decision_time; unknown publication semantics -> never live."""
from __future__ import annotations

from datetime import datetime


def _parse(ts):
    if ts is None:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def causal_eligibility(has_publication_time: bool, has_event_time: bool, historical_available: bool,
                       live_available: bool) -> str:
    """Fail-closed: without publication-time semantics a feed can never be live/delayed-live."""
    if not has_publication_time:
        return "historical_only" if (historical_available and has_event_time) else "unknown_fail_closed"
    if live_available:
        return "live_eligible"
    if historical_available:
        return "delayed_live_eligible"
    return "unknown_fail_closed"


def live_publication_safe(publication_time, decision_time, safety_lag_seconds: float = 0.0) -> bool:
    """True only if publication_time (+lag) <= decision_time. Unknown publication_time -> False (fail closed)."""
    p, d = _parse(publication_time), _parse(decision_time)
    if p is None or d is None:
        return False
    return (p.timestamp() + safety_lag_seconds) <= d.timestamp()


def is_live_eligible(event) -> bool:
    """A LicensedEvent is live-eligible only if its causal_eligibility says so AND it carries a publication time."""
    return getattr(event, "causal_eligibility", "unknown_fail_closed") in ("live_eligible", "delayed_live_eligible") \
        and getattr(event, "source_publication_time_utc", None) is not None
