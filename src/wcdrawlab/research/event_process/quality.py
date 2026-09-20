"""Source-quality + leakage assessment for a match's canonical event stream.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Produces a SourceQualityReport that classifies, per canonical capability, whether the source supported
it (available_verified / available_partial / unavailable / unknown) for THIS match. The classification
is evidence-based: it inspects what fields the canonical events actually carry, rather than assuming
a provider's nominal capabilities. This is what prevents a missing field from being silently treated
as 0 downstream -- consumers read the quality flag alongside the value."""
from __future__ import annotations

from . import canonical_events as CE
from . import contracts as C


def assess_match(canon: list, trace: C.SourceTrace, directions: dict) -> C.SourceQualityReport:
    rep = C.SourceQualityReport(provider=trace.provider, source_match_id=trace.source_match_id)

    has_possession = any(e.possession is not None for e in canon)
    rep.set("possession_structure", C.AVAILABLE_VERIFIED if has_possession else C.UNAVAILABLE)

    # territory depends on inferable attacking direction per team
    n_dir_known = sum(1 for v in directions.values() if v is not None)
    if n_dir_known >= 2:
        terr_q = C.AVAILABLE_VERIFIED
    elif n_dir_known == 1:
        terr_q = C.AVAILABLE_PARTIAL
    else:
        terr_q = C.UNKNOWN
    for cap in ("territory_thirds", "channels", "deep_progression", "field_tilt"):
        rep.set(cap, terr_q, None if terr_q == C.AVAILABLE_VERIFIED else "attacking direction not fully inferable")

    has_endloc = any(e.end_location is not None for e in canon if e.kind in (CE.KIND_PASS, CE.KIND_CARRY))
    rep.set("box_entries", C.AVAILABLE_VERIFIED if (has_endloc and n_dir_known >= 2)
            else (C.AVAILABLE_PARTIAL if has_endloc else C.UNAVAILABLE))

    has_play_pattern = any(e.play_pattern for e in canon)
    rep.set("attack_phase", C.AVAILABLE_VERIFIED if has_play_pattern else C.UNAVAILABLE)
    has_counter = any(e.play_pattern == "From Counter" for e in canon)
    rep.set("counter_proxy", C.AVAILABLE_PARTIAL,
            "counter via play_pattern + regain heuristic" if has_counter else "no explicit counter pattern present")

    rep.set("possession_to_shot_chain", C.AVAILABLE_VERIFIED if has_possession else C.UNAVAILABLE)

    n_pressure = sum(1 for e in canon if e.kind == CE.KIND_PRESSURE)
    rep.set("pressure", C.AVAILABLE_VERIFIED if n_pressure > 0 else C.UNAVAILABLE)
    n_counterpress = sum(1 for e in canon if e.counterpress)
    rep.set("counterpress_proxy",
            C.AVAILABLE_VERIFIED if n_counterpress > 0 else (C.AVAILABLE_PARTIAL if n_pressure > 0 else C.UNAVAILABLE),
            "uses provider counterpress flag" if n_counterpress > 0 else "proxied from pressures")

    rep.set("recoveries", C.AVAILABLE_VERIFIED if any(e.kind == CE.KIND_BALL_RECOVERY for e in canon) else C.UNAVAILABLE)
    rep.set("turnovers", C.AVAILABLE_VERIFIED if any(e.kind in (CE.KIND_MISCONTROL, CE.KIND_DISPOSSESSED) for e in canon) else C.UNAVAILABLE)
    has_bc = any(e.kind in (CE.KIND_BLOCK, CE.KIND_CLEARANCE) for e in canon)
    rep.set("blocks_clearances", C.AVAILABLE_VERIFIED if has_bc else C.UNAVAILABLE)

    shots = [e for e in canon if e.kind == CE.KIND_SHOT]
    rep.set("shot_events", C.AVAILABLE_VERIFIED if shots else C.UNAVAILABLE)
    n_xg = sum(1 for e in shots if (e.raw.get("shot") or {}).get("statsbomb_xg") is not None)
    if not shots:
        rep.set("shot_xg", C.UNAVAILABLE)
    elif n_xg == len(shots):
        rep.set("shot_xg", C.AVAILABLE_VERIFIED)
    elif n_xg > 0:
        rep.set("shot_xg", C.AVAILABLE_PARTIAL, f"xg present on {n_xg}/{len(shots)} shots")
    else:
        rep.set("shot_xg", C.UNAVAILABLE, "no xg on any shot")
    n_loc = sum(1 for e in shots if e.location is not None)
    rep.set("shot_location", C.AVAILABLE_VERIFIED if (shots and n_loc == len(shots))
            else (C.AVAILABLE_PARTIAL if n_loc > 0 else C.UNAVAILABLE))
    n_ff = sum(1 for e in shots if (e.raw.get("shot") or {}).get("freeze_frame"))
    rep.set("shot_freeze_frame", C.AVAILABLE_VERIFIED if (shots and n_ff == len(shots))
            else (C.AVAILABLE_PARTIAL if n_ff > 0 else C.UNAVAILABLE))
    rep.set("big_chance_proxy", C.AVAILABLE_PARTIAL, "transparent xg/geometry rule; no provider big_chance flag")

    rep.set("match_state", C.AVAILABLE_VERIFIED if any(
        (e.raw.get("shot") or {}).get("outcome", {}).get("name") == "Goal" or
        e.kind in (CE.KIND_OWN_GOAL_FOR, CE.KIND_OWN_GOAL_AGAINST) for e in canon) or shots else C.AVAILABLE_VERIFIED)

    has_cards = any(((e.raw.get("foul_committed") or {}).get("card")) or
                    ((e.raw.get("bad_behaviour") or {}).get("card")) for e in canon)
    rep.set("cards", C.AVAILABLE_VERIFIED if has_cards else C.AVAILABLE_PARTIAL,
            None if has_cards else "no cards in this match (field supported, none occurred)")
    return rep


def leakage_check(canon_at_t: list, t_minute: int) -> dict:
    """Assert a truncated stream obeys the leakage contract. Returns a dict of booleans; all True == ok."""
    minutes_ok = all(e.minute <= t_minute for e in canon_at_t)
    regulation_ok = all(e.period in (1, 2) and e.minute <= 90 for e in canon_at_t)
    return {
        "all_at_or_before_t": minutes_ok,
        "regulation_only": regulation_ok,
        "all_ok": minutes_ok and regulation_ok,
        "t_minute": t_minute,
        "n_events": len(canon_at_t),
    }
