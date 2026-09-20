"""Phase 1: provider-aware canonical match-result semantics for API-Football.

KEY FIX (own_goal_semantics): API-Football reports the `team` field on an Own Goal event as the BENEFICIARY
(the team credited with the goal), NOT the team that put it in their own net. Therefore own goals are credited
to `team` DIRECTLY, exactly like normal goals — no inversion. The prior pilot's 90% reconciliation was caused
by inverting own goals.

Separation rules (never mix):
  - regulation: goal events with 0 < elapsed <= 90 (stoppage time is elapsed==90 with `extra`).
  - extra_time: goal events with 90 < elapsed <= 120.
  - penalty_shootout: taken from the OFFICIAL score.penalty field (authoritative), never from events, never a
    regulation/next-goal target.
Official regulation truth = score.fulltime; after-ET = score.extratime; shootout = score.penalty.
research_only.
"""
from __future__ import annotations

PROVIDER_SEMANTICS_VERSION = "api_football_result_v1"


def _credit(team_id, home_id, away_id):
    """Credit a goal to the team in the event's `team` field (own goals already beneficiary-attributed)."""
    if team_id == home_id:
        return (1, 0)
    if team_id == away_id:
        return (0, 1)
    return (0, 0)


def derive_window_score(events, home_id, away_id, lo, hi):
    """Event-derived (home, away) for goals with lo < elapsed <= hi. Own + normal goals credited to `team`."""
    h = a = 0
    for e in events:
        if (e.get("type") or "").lower() != "goal":
            continue
        detail = (e.get("detail") or "").lower()
        if "missed" in detail or "cancel" in detail:   # missed/cancelled penalties are not goals
            continue
        el = (e.get("time") or {}).get("elapsed")
        if el is None or not (lo < el <= hi):
            continue
        dh, da = _credit((e.get("team") or {}).get("id"), home_id, away_id)
        h += dh
        a += da
    return h, a


def _g(d, side):
    return (d or {}).get(side)


def canonical_result(fixture, events):
    """Build the provider-aware canonical result record + reconcile event-regulation vs official regulation."""
    f = fixture.get("fixture", {})
    teams = fixture.get("teams", {})
    score = fixture.get("score", {}) or {}
    home_id = teams.get("home", {}).get("id")
    away_id = teams.get("away", {}).get("id")
    ft = score.get("fulltime", {}) or {}
    et = score.get("extratime", {}) or {}
    pen = score.get("penalty", {}) or {}
    has_et = _g(et, "home") is not None
    has_pen = _g(pen, "home") is not None

    reg_h, reg_a = derive_window_score(events, home_id, away_id, 0, 90)
    et_h, et_a = derive_window_score(events, home_id, away_id, 90, 120)

    off_reg_h, off_reg_a = _g(ft, "home"), _g(ft, "away")
    final_result_type = "penalty_shootout" if has_pen else ("after_extra_time" if has_et else "regulation")

    # reconcile event-derived regulation vs official regulation (score.fulltime)
    status = "exact" if (off_reg_h is not None and reg_h == off_reg_h and reg_a == off_reg_a) else "mismatch"
    exc = None
    if status == "mismatch":
        exc = classify_exception(events, fixture, (reg_h, reg_a), (off_reg_h, off_reg_a), has_et, has_pen)

    return {
        "provider_fixture_id": f.get("id"),
        "home_id": home_id, "away_id": away_id,
        "official_regulation_home_goals": off_reg_h, "official_regulation_away_goals": off_reg_a,
        "official_after_extra_time_home_goals": _g(et, "home"), "official_after_extra_time_away_goals": _g(et, "away"),
        "penalty_shootout_home_goals": _g(pen, "home"), "penalty_shootout_away_goals": _g(pen, "away"),
        "final_result_type": final_result_type,
        "event_derived_regulation_home_goals": reg_h, "event_derived_regulation_away_goals": reg_a,
        "event_derived_extra_time_home_goals": et_h, "event_derived_extra_time_away_goals": et_a,
        "reconciliation_status": status, "reconciliation_exception_type": exc,
        "provider_semantics_version": PROVIDER_SEMANTICS_VERSION,
    }


def classify_exception(events, fixture, ev_reg, off_reg, has_et, has_pen):
    """Classify a regulation mismatch into one of the predeclared exception types."""
    # ordering check
    last = -1
    ordering_bad = False
    for e in events:
        el = (e.get("time") or {}).get("elapsed")
        if el is not None:
            if el < last:
                ordering_bad = True
            last = el
    # duplicate check (same type/detail/player/elapsed)
    seen = set(); dup = False
    for e in events:
        k = ((e.get("type") or "").lower(), (e.get("detail") or "").lower(),
             (e.get("player") or {}).get("id"), (e.get("time") or {}).get("elapsed"))
        if k in seen:
            dup = True
        seen.add(k)
    has_own = any("own" in (e.get("detail") or "").lower() for e in events if (e.get("type") or "").lower() == "goal")
    has_var = any((e.get("type") or "").lower() == "var" for e in events)
    if off_reg[0] is None:
        return "fixture_metadata_mismatch"
    # heuristics in priority order
    if has_var and abs((ev_reg[0] + ev_reg[1]) - (off_reg[0] + off_reg[1])) >= 1:
        return "VAR_cancelled_or_corrected_goal"
    if has_pen and not has_et:
        return "penalty_shootout_separation"
    if has_et:
        return "extra_time_score_separation"
    if has_own:
        return "own_goal_semantics"
    if dup:
        return "duplicate_event"
    if ordering_bad:
        return "provider_event_ordering_only"
    if (ev_reg[0] + ev_reg[1]) < (off_reg[0] + off_reg[1]):
        return "missing_event"
    return "unresolved_provider_disagreement"
