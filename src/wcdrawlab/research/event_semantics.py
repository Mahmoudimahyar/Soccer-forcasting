"""Provider-aware canonical event interpretation (derived layer only; never mutates raw payloads).

Different providers encode own goals differently:
  - API-Football: the Own Goal event's `team` field is the BENEFICIARY (the team credited the goal);
    the scoring team == reported team (NO inversion). The player belongs to the opponent.
  - A hypothetical "scorer-encoding" provider reports the SCORER's team on an own goal; there the
    scoring team is the opponent.
We make the rule explicit, versioned, and FAIL CLOSED when a provider's own-goal semantics are unknown.

Standard goals: scoring team == reported team. Cards/subs/VAR never change score state. Disallowed
(VAR-cancelled) goals are type='Var' in API-Football and are naturally excluded.
"""
from __future__ import annotations

SEMANTICS_VERSION = "own-goal-semantics-v1 (2026-06-21)"

# How each provider encodes the `team` field on an OWN GOAL event.
#   "beneficiary" -> reported team is the team credited the goal (scoring team = reported)
#   "scorer"      -> reported team is the scorer's team (scoring team = opponent)
PROVIDER_OWN_GOAL_SEMANTICS = {
    "api_football": "beneficiary",
    # Example alternative provider (used in tests); add real providers explicitly + versioned.
    "example_scorer_provider": "scorer",
}


def _opponent(team, home, away):
    return away if team == home else home


def interpret_event(raw: dict, home_team: str, away_team: str, provider: str) -> dict:
    """Return a canonical event record. `raw` is a provider event with type/detail/team/time."""
    etype = raw.get("type")
    detail = str(raw.get("detail") or "")
    tfield = raw.get("team")
    reported = tfield.get("name") if isinstance(tfield, dict) else tfield
    minute = (raw.get("time") or {}).get("elapsed")
    rec = {
        "event_team_id_as_reported": reported,
        "beneficiary_team_id": None,
        "player_team_id_if_known": None,
        "scoring_team_id": None,
        "own_goal_flag": False,
        "is_goal": False,
        "provider_name": provider,
        "provider_semantics_version": SEMANTICS_VERSION,
        "minute": minute,
        "derived_state_quality_status": "ok",
    }
    if etype != "Goal":
        return rec  # cards, subs, VAR, etc. never change score state
    if "Missed" in detail:  # missed penalty is not a goal
        return rec
    if detail == "Own Goal":
        rec["own_goal_flag"] = True
        sem = PROVIDER_OWN_GOAL_SEMANTICS.get(provider)
        if sem is None:
            rec["derived_state_quality_status"] = "unknown_own_goal_semantics"  # FAIL CLOSED
            return rec  # scoring_team_id stays None -> excluded from state
        if sem == "beneficiary":
            rec["beneficiary_team_id"] = reported
            rec["scoring_team_id"] = reported
            rec["player_team_id_if_known"] = _opponent(reported, home_team, away_team)
        elif sem == "scorer":
            rec["player_team_id_if_known"] = reported
            rec["scoring_team_id"] = _opponent(reported, home_team, away_team)
            rec["beneficiary_team_id"] = _opponent(reported, home_team, away_team)
        else:
            rec["derived_state_quality_status"] = "unknown_own_goal_semantics"
            return rec
        rec["is_goal"] = True
        return rec
    # standard goal
    rec["scoring_team_id"] = reported
    rec["beneficiary_team_id"] = reported
    rec["player_team_id_if_known"] = reported
    rec["is_goal"] = True
    return rec


def score_from_events(events: list[dict], home_team: str, away_team: str, provider: str,
                      up_to_minute: int | None = None) -> dict:
    """Derive (home, away) score from events using only goals known by up_to_minute (causal).
    Pure function -> idempotent (recomputes from the list; no accumulation). Reports a quality
    status of 'degraded' if any goal had unknown own-goal semantics (excluded, fail-closed)."""
    gh = ga = 0
    degraded = False
    for raw in events:
        c = interpret_event(raw, home_team, away_team, provider)
        if c["derived_state_quality_status"] != "ok":
            degraded = True
            continue
        if not c["is_goal"]:
            continue
        if up_to_minute is not None and (c["minute"] is None or c["minute"] > up_to_minute):
            continue
        if c["scoring_team_id"] == home_team:
            gh += 1
        elif c["scoring_team_id"] == away_team:
            ga += 1
        else:
            degraded = True  # scoring team not recognized
    return {"home": gh, "away": ga, "quality_status": "degraded" if degraded else "ok"}
