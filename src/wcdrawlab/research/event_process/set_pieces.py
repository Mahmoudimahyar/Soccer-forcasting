"""Set-piece extraction: corners, free-kicks, throw-ins, penalties + their shot conversion.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Counts set-piece *origins* (a pass/shot whose pass.type or shot.type marks it as a set piece, or a
possession that begins From Corner/Free Kick/Throw In) and links each to whether the resulting
possession produced a shot. Every counter is sourced from verified provider fields (pass.type,
shot.type, play_pattern); none are imputed."""
from __future__ import annotations

from . import canonical_events as CE
from . import contracts as C
from . import possession as POSS
from . import attacks as ATT


def set_piece_counts(canon: list, possessions: list, team_id: int) -> dict:
    """Per-team set-piece origin counts + shots-from-set-piece, split by type."""
    corners = free_kicks = throw_ins = penalties = goal_kicks = 0
    # origins from explicit pass types
    for e in canon:
        if e.team_id != team_id or e.kind != CE.KIND_PASS:
            continue
        ptype = ((e.raw.get("pass") or {}).get("type") or {}).get("name")
        if ptype == "Corner":
            corners += 1
        elif ptype == "Free Kick":
            free_kicks += 1
        elif ptype == "Throw-in":
            throw_ins += 1
        elif ptype == "Goal Kick":
            goal_kicks += 1
    # penalties from shot.type
    for e in canon:
        if e.team_id == team_id and e.kind == CE.KIND_SHOT:
            if ((e.raw.get("shot") or {}).get("type") or {}).get("name") == "Penalty":
                penalties += 1

    # shots originating from set-piece possessions
    sp_shots = 0
    corner_shots = fk_shots = 0
    for p in possessions:
        if p.team_id != team_id or not p.ended_in_shot:
            continue
        ph = ATT.possession_phase(p)
        if ph == C.PHASE_CORNER:
            corner_shots += 1
            sp_shots += 1
        elif ph == C.PHASE_FREE_KICK:
            fk_shots += 1
            sp_shots += 1
        elif ph in (C.PHASE_THROW_IN, C.PHASE_PENALTY):
            sp_shots += 1

    return {
        "team_id": team_id,
        "corners": corners,
        "free_kicks": free_kicks,
        "throw_ins": throw_ins,
        "goal_kicks": goal_kicks,
        "penalties": penalties,
        "set_piece_shots": sp_shots,
        "corner_shots": corner_shots,
        "free_kick_shots": fk_shots,
    }
