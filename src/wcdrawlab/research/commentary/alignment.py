"""Commentary-to-structured-event alignment with explicit confidence (research_only; NOT a live model)."""
from __future__ import annotations


def align_confidence(comm_event_type, comm_team_id, comm_minute,
                     ev_event_type, ev_team_id, ev_minute, clock_tol_min: float = 2.0) -> float:
    """Weighted match of (event type, team, match-clock). Returns confidence in [0,1]."""
    score = 0.0
    if comm_event_type and ev_event_type and comm_event_type == ev_event_type:
        score += 0.4
    if comm_team_id is not None and ev_team_id is not None and comm_team_id == ev_team_id:
        score += 0.3
    if comm_minute is not None and ev_minute is not None:
        d = abs(float(comm_minute) - float(ev_minute))
        if d <= clock_tol_min:
            score += 0.3 * (1.0 - d / clock_tol_min) if clock_tol_min else 0.3
    return round(min(1.0, score), 3)


def classify_alignment(confidence: float, *, is_correction_or_duplicate: bool = False,
                       timing_safe_for_live: bool = True) -> str:
    if is_correction_or_duplicate:
        return "correction_or_duplicate"
    if not timing_safe_for_live:
        return "timing_not_safe_for_live_use"
    if confidence >= 0.75:
        return "high_confidence_event_alignment"
    if confidence >= 0.5:
        return "medium_confidence_event_alignment"
    if confidence > 0.0:
        return "low_confidence_event_alignment"
    return "unaligned"
