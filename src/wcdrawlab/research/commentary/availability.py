"""Causal availability + live-eligibility logic (Phase 3 core). NON-NEGOTIABLE RULE:

  live use requires   publication_time <= decision_time
  delayed-live use    publication_time + safety_lag <= decision_time

A source with event_time but no trustworthy publication_time may be used for historical labeling /
weak supervision / alignment ONLY — never as a live feature, never relabeled as point-in-time live.
"""
from __future__ import annotations


def _ts(x):
    return None if x is None else str(x)


def live_publication_safe(publication_time, decision_time, safety_lag_seconds: float = 0.0) -> bool:
    """True only if the line was published (plus a safety lag) at/before the decision time.
    Unknown publication_time -> NEVER safe for live use."""
    if publication_time is None or decision_time is None:
        return False
    if safety_lag_seconds and safety_lag_seconds > 0:
        import datetime as _dt
        try:
            pub = _dt.datetime.fromisoformat(str(publication_time).replace("Z", "+00:00"))
            dec = _dt.datetime.fromisoformat(str(decision_time).replace("Z", "+00:00"))
        except Exception:
            return False
        return (pub + _dt.timedelta(seconds=safety_lag_seconds)) <= dec
    return _ts(publication_time) <= _ts(decision_time)


def classify_source_eligibility(*, rights_ok: bool, has_publication_time: bool,
                                has_event_time: bool) -> str:
    """Best-possible plane for a SOURCE (Phase 6 gate may downgrade further, never upgrade)."""
    if not rights_ok:
        return "rights_restricted"
    if has_publication_time:
        return "delayed_live_eligible"   # 'live_eligible' only after the Phase-6 gate verifies lag+quality
    if has_event_time:
        return "historical_weak_supervision_only"
    return "source_time_unknown"


def attach_eligibility(record, *, rights_ok: bool) -> str:
    """Set record.causal_eligibility_status from its timing fields + rights. Returns the status."""
    status = classify_source_eligibility(
        rights_ok=rights_ok,
        has_publication_time=record.publication_time_utc_if_known is not None,
        has_event_time=record.event_time_utc_if_known is not None,
    )
    record.causal_eligibility_status = status
    return status
