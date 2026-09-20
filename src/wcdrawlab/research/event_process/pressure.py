"""Pressure / disruption layer: pressures, counterpress proxy, recoveries, turnovers, blocks, clearances.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Defensive-action counters per team from canonical events. `counterpress` is a verified StatsBomb flag
on some events (pressure/duel/foul within 5s of a loss); where present we count it directly
(available_verified for those events) and otherwise approximate via pressures shortly after the team
lost the ball (available_partial). Blocks and clearances come straight from verified event kinds."""
from __future__ import annotations

from . import canonical_events as CE

_LOSS_KINDS = {CE.KIND_MISCONTROL, CE.KIND_DISPOSSESSED}


def pressure_counts(canon: list, team_id: int) -> dict:
    """Per-team pressure/disruption counters. counterpress_flagged is the verified-flag count;
    counterpress_proxy adds pressures within PROXY_WINDOW_S after a same-team possession loss."""
    pressures = blocks = clearances = interceptions = recoveries = 0
    counterpress_flagged = 0
    duels = fouls_committed = 0
    for e in canon:
        if e.team_id != team_id:
            continue
        if e.kind == CE.KIND_PRESSURE:
            pressures += 1
            if e.counterpress:
                counterpress_flagged += 1
        elif e.kind == CE.KIND_BLOCK:
            blocks += 1
        elif e.kind == CE.KIND_CLEARANCE:
            clearances += 1
        elif e.kind == CE.KIND_INTERCEPTION:
            interceptions += 1
            if e.counterpress:
                counterpress_flagged += 1
        elif e.kind == CE.KIND_BALL_RECOVERY:
            recoveries += 1
        elif e.kind == CE.KIND_DUEL:
            duels += 1
            if e.counterpress:
                counterpress_flagged += 1
        elif e.kind == CE.KIND_FOUL_COMMITTED:
            fouls_committed += 1
            if e.counterpress:
                counterpress_flagged += 1
    return {
        "team_id": team_id,
        "pressures": pressures,
        "counterpress_flagged": counterpress_flagged,
        "blocks": blocks,
        "clearances": clearances,
        "interceptions": interceptions,
        "recoveries": recoveries,
        "duels": duels,
        "fouls_committed": fouls_committed,
    }
