"""Deterministic multi-source event reconciliation (Data Enrichment Gate 1, section 3).

Never silently merges conflicting events. For each canonical event candidate it:
  - preserves every raw version (contributing_sources keeps them),
  - matches by provider ids where possible, else by (match_id, event_type, team, player, minute±tol),
  - retains discrepancies,
  - sets reconciliation_status = 'unresolved' when sources disagree on identity attributes,
  - records source confidence and provider disagreement.

Critical events that are 'unresolved' must NOT feed approved in-play features
(approved_feature_eligible == False). Pure functions only — no I/O, no network.
"""
from __future__ import annotations

from typing import Any, Iterable

# Priority order (1 = highest). See docs/EVENT_RECONCILIATION_POLICY.md.
SOURCE_PRIORITY: dict[str, int] = {
    "official_feed": 1, "fifa_official": 1,
    "api_football": 2, "the_odds_api": 2,            # licensed structured providers
    "football_data_org": 3, "secondary_provider": 3,  # secondary structured providers
    "approved_announcement": 4,
    "open_dataset": 5, "martj42": 5, "jfjelstul": 5,
}
DEFAULT_PRIORITY = 9

CRITICAL_EVENT_TYPES = {
    "goal", "penalty", "yellow_card", "second_yellow", "red_card", "substitution",
    "match_minute", "match_status", "kickoff", "final_whistle",
}

# Identity attributes whose cross-source disagreement => unresolved, per event type.
_IDENTITY_ATTRS: dict[str, tuple[str, ...]] = {
    "goal": ("player_id", "goal_type"),
    "penalty": ("taker_player_id", "outcome", "phase"),
    "yellow_card": ("player_id",),
    "second_yellow": ("player_id",),
    "red_card": ("player_id", "red_type"),
    "substitution": ("player_off_id", "player_on_id"),
    "kickoff": ("kickoff_utc",),
    "final_whistle": ("final_whistle_utc",),
    "match_status": ("status",),
    "match_minute": (),  # minute handled via tolerance, not identity equality
}


def priority(source_name: str) -> int:
    return SOURCE_PRIORITY.get(source_name, DEFAULT_PRIORITY)


def is_critical(event_type: str) -> bool:
    return event_type in CRITICAL_EVENT_TYPES


def _sort_key(c: dict[str, Any]) -> tuple:
    return (
        str(c.get("match_id")), str(c.get("event_type")), str(c.get("team_id")),
        int(c.get("minute") or 0), priority(str(c.get("source_name"))), str(c.get("source_name")),
    )


def _attr(c: dict[str, Any], key: str):
    if key in c:
        return c.get(key)
    return (c.get("attrs") or {}).get(key)


def _confidence(status: str, best_priority: int) -> str:
    if status == "reconciled":
        return "high"
    if status == "unresolved":
        return "low"
    # single_source
    return "medium" if best_priority <= 2 else "low"


def reconcile_events(candidates: Iterable[dict[str, Any]], tolerance_minutes: int = 1) -> list[dict[str, Any]]:
    """Cluster candidate event rows into canonical events with a reconciliation verdict.

    Each candidate dict should carry at least: source_name, match_id, event_type, team_id, minute.
    Optional: player_id, provider_event_id, provider_match_id, and an `attrs` dict for type-specific
    fields (player_off_id, red_type, kickoff_utc, ...). Cross-source provider_event_id matches are
    honored first; otherwise clustering is by (match_id, event_type, team_id) within minute tolerance.
    """
    cand = sorted((dict(c) for c in candidates), key=_sort_key)
    clusters: list[list[dict[str, Any]]] = []

    for c in cand:
        placed = False
        pid = c.get("provider_event_id")
        for cl in clusters:
            same_group = (
                str(cl[0].get("match_id")) == str(c.get("match_id"))
                and str(cl[0].get("event_type")) == str(c.get("event_type"))
                and str(cl[0].get("team_id")) == str(c.get("team_id"))
            )
            # exact provider_event_id match (e.g. same provider re-fetch) joins regardless of minute
            id_match = pid is not None and any(x.get("provider_event_id") == pid for x in cl)
            anchor = int(cl[0].get("minute") or 0)
            within = abs(int(c.get("minute") or 0) - anchor) <= tolerance_minutes
            if same_group and (id_match or within):
                cl.append(c)
                placed = True
                break
        if not placed:
            clusters.append([c])

    results: list[dict[str, Any]] = []
    for cl in clusters:
        etype = str(cl[0].get("event_type"))
        sources = sorted({str(x.get("source_name")) for x in cl})
        best = min(cl, key=lambda x: (priority(str(x.get("source_name"))), str(x.get("source_name"))))
        best_priority = priority(str(best.get("source_name")))

        # detect identity-attribute disagreement across sources (only non-null values count)
        disagreements: dict[str, list] = {}
        for attr in _IDENTITY_ATTRS.get(etype, ()):
            vals = sorted({str(_attr(x, attr)) for x in cl if _attr(x, attr) is not None})
            if len(vals) > 1:
                disagreements[attr] = vals
        # minute spread is recorded (informational); within-tolerance is not itself a conflict
        minutes = sorted({int(x.get("minute") or 0) for x in cl})
        if len(minutes) > 1:
            disagreements.setdefault("_minute_spread", minutes)

        has_conflict = bool({k: v for k, v in disagreements.items() if not k.startswith("_")})
        if has_conflict:
            status = "unresolved"
        elif len(sources) >= 2:
            status = "reconciled"
        else:
            status = "single_source"

        canonical = {
            "match_id": best.get("match_id"),
            "event_type": etype,
            "team_id": best.get("team_id"),
            "minute": best.get("minute"),
            "player_id": _attr(best, "player_id"),
            "canonical_source": best.get("source_name"),
            "contributing_sources": sources,
            "reconciliation_status": status,
            "source_confidence": _confidence(status, best_priority),
            "provider_disagreement": disagreements,
            "is_critical": is_critical(etype),
            # critical + unresolved => must be excluded from approved in-play features
            "approved_feature_eligible": not (is_critical(etype) and status == "unresolved"),
            "raw_versions": cl,  # every raw version preserved
        }
        results.append(canonical)

    results.sort(key=lambda r: (str(r["match_id"]), str(r["event_type"]), int(r["minute"] or 0),
                                str(r["team_id"])))
    return results
