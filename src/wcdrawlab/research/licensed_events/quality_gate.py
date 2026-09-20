"""Data-completeness scoring + threshold gating (Phase 3). Mirrors the adopted project thresholds."""
from __future__ import annotations

# adopted project thresholds (also in STRUCTURED_EVENT_REQUIREMENTS.md)
MIN_LINEUP_SUB_MATCHES = 500
MIN_TIMESTAMPED_MATCHES = 500
MIN_RED_OR_SECOND_YELLOW = 150

KEY_EVENT_FIELDS = ["event_time_utc", "match_clock_s", "period", "player_id", "source_snapshot_hash"]


def completeness_score(event, fields=None) -> float:
    fields = fields or KEY_EVENT_FIELDS
    present = sum(1 for f in fields if getattr(event, f, None) not in (None, "", "unknown"))
    return round(present / len(fields), 4)


def match_completeness(events) -> float:
    if not events:
        return 0.0
    return round(sum(completeness_score(e) for e in events) / len(events), 4)


def coverage_summary(matches_with_lineups, timestamped_matches, red_or_2y_examples):
    """Return per-threshold pass/fail against the adopted minimums."""
    return {
        "lineup_sub_matches": {"value": matches_with_lineups, "min": MIN_LINEUP_SUB_MATCHES,
                               "pass": matches_with_lineups >= MIN_LINEUP_SUB_MATCHES},
        "timestamped_matches": {"value": timestamped_matches, "min": MIN_TIMESTAMPED_MATCHES,
                                "pass": timestamped_matches >= MIN_TIMESTAMPED_MATCHES},
        "red_or_second_yellow": {"value": red_or_2y_examples, "min": MIN_RED_OR_SECOND_YELLOW,
                                 "pass": red_or_2y_examples >= MIN_RED_OR_SECOND_YELLOW},
    }


def meets_all_thresholds(summary) -> bool:
    return all(v["pass"] for v in summary.values())
