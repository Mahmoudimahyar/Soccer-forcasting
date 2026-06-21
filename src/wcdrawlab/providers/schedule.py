"""Quota-aware fetch scheduling (pure, deterministic — no network, no polling loop).

Encodes the free-tier-safe policy:
  - lineups: once per match in the T-90..T-60 window (target T-75)
  - standings: once after a match is finished
  - events/statistics: only when live state changed, or once at final whistle (never continuous)
Priority when the daily budget is tight: lineups > standings > events.
`plan_fetches` returns the work-list capped at the remaining budget; it does NOT consume the budget
(the executor consumes on actual fetch).
"""
from __future__ import annotations

from datetime import datetime

from wcdrawlab.providers.interface import QuotaBudget

LINEUP = "lineup"
STANDINGS = "standings"
EVENTS = "events"

_PRIORITY = {LINEUP: 1, STANDINGS: 2, EVENTS: 3}


def plan_fetches(states: list[dict], budget: QuotaBudget, now: datetime) -> list[tuple]:
    """states: list of dicts with keys match_id, kickoff_utc (datetime), status
    ('scheduled'|'live'|'finished'), optional state_changed (bool), fetched (iterable of done types)."""
    candidates: list[tuple[int, object, str]] = []
    for s in states:
        mid = s["match_id"]
        ko = s["kickoff_utc"]
        status = s.get("status", "scheduled")
        fetched = set(s.get("fetched", []))
        mins_to_ko = (ko - now).total_seconds() / 60.0

        if LINEUP not in fetched and 60.0 <= mins_to_ko <= 90.0:
            candidates.append((_PRIORITY[LINEUP], mid, LINEUP))
        if status == "finished" and STANDINGS not in fetched:
            candidates.append((_PRIORITY[STANDINGS], mid, STANDINGS))
        # events: on live state change, OR once at final; never continuous
        if status == "live" and s.get("state_changed") and EVENTS not in fetched:
            candidates.append((_PRIORITY[EVENTS], mid, EVENTS))
        if status == "finished" and EVENTS not in fetched:
            candidates.append((_PRIORITY[EVENTS], mid, EVENTS))

    candidates.sort(key=lambda c: (c[0], str(c[1]), c[2]))
    rem = budget.remaining()
    return [(mid, ft) for _, mid, ft in candidates[:rem]]
