"""Chance-quality layer: per-shot xG / outcome / type / location / distance / angle / big-chance proxy.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Each shot is normalized to a canonical record. xG is taken from the provider when present
(available_verified) and left None otherwise (NEVER imputed as 0 -- quality.py flags shot_xg as
available_partial/unavailable accordingly). Distance/angle are pure geometry from the shot location;
the big-chance proxy is a transparent rule (close central shot, or high xG, or clear-cut freeze-frame)
and is flagged available_partial because no provider 'big_chance' boolean exists in StatsBomb open data.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

from . import canonical_events as CE
from . import contracts as C

# big-chance proxy thresholds (transparent, documented; not a provider field)
BIG_CHANCE_XG = 0.30
BIG_CHANCE_DIST = 12.0      # metres-ish in SB units from goal centre
GOAL_MOUTH_HALF_WIDTH = 3.66  # half of a 7.32m goal, in SB length units (~yard-scaled)


@dataclass
class ShotRecord:
    idx: int
    minute: int
    second: int
    elapsed: float
    period: int
    team_id: Optional[int]
    player_id: Optional[int]
    location: Optional[tuple]
    xg: Optional[float]
    xg_available: bool
    outcome: Optional[str]
    is_goal: bool
    shot_type: Optional[str]       # Open Play / Free Kick / Penalty / Corner ...
    body_part: Optional[str]
    technique: Optional[str]
    first_time: Optional[bool]
    distance: Optional[float]
    angle: Optional[float]         # radians subtended by the goal mouth from the shot location
    under_pressure: bool
    has_freeze_frame: bool
    big_chance_proxy: bool
    play_pattern: Optional[str]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["location"] = list(self.location) if self.location else None
        return d


def _distance_angle(loc: Optional[tuple], direction) -> tuple[Optional[float], Optional[float]]:
    """Geometry to the attacked goal. Uses attacking_x so direction-unknown -> (None, None)."""
    if loc is None:
        return None, None
    ax = CE.attacking_x(loc[0], direction)
    y = loc[1]
    if ax is None or y is None:
        return None, None
    dx = C.OPP_GOAL_X - ax
    dy = y - C.GOAL_CENTER_Y
    dist = math.hypot(dx, dy)
    # angle subtended by the goal mouth (left/right posts) from the shot point
    p1y = C.GOAL_CENTER_Y - GOAL_MOUTH_HALF_WIDTH
    p2y = C.GOAL_CENTER_Y + GOAL_MOUTH_HALF_WIDTH
    a1 = math.atan2(p1y - y, dx if dx != 0 else 1e-9)
    a2 = math.atan2(p2y - y, dx if dx != 0 else 1e-9)
    angle = abs(a1 - a2)
    return dist, angle


def shot_record(e, direction=None) -> ShotRecord:
    sh = e.raw.get("shot") or {}
    xg = sh.get("statsbomb_xg")
    outcome = (sh.get("outcome") or {}).get("name")
    stype = (sh.get("type") or {}).get("name")
    dist, angle = _distance_angle(e.location, direction)
    has_ff = bool(sh.get("freeze_frame"))
    big = False
    if xg is not None and xg >= BIG_CHANCE_XG:
        big = True
    elif dist is not None and dist <= BIG_CHANCE_DIST and angle is not None and angle >= 0.35:
        big = True
    return ShotRecord(
        idx=e.idx, minute=e.minute, second=e.second, elapsed=e.elapsed, period=e.period,
        team_id=e.team_id, player_id=e.player_id, location=e.location,
        xg=float(xg) if xg is not None else None,
        xg_available=xg is not None,
        outcome=outcome, is_goal=(outcome == "Goal"),
        shot_type=stype,
        body_part=(sh.get("body_part") or {}).get("name"),
        technique=(sh.get("technique") or {}).get("name"),
        first_time=sh.get("first_time"),
        distance=dist, angle=angle,
        under_pressure=e.under_pressure,
        has_freeze_frame=has_ff,
        big_chance_proxy=big,
        play_pattern=e.play_pattern,
    )


def shots_for_match(canon: list, directions: Optional[dict] = None) -> list:
    out = []
    for e in canon:
        if e.kind != CE.KIND_SHOT:
            continue
        d = (directions or {}).get(e.team_id)
        out.append(shot_record(e, d))
    return out


def team_chance_summary(shots: list, team_id: int) -> dict:
    """Aggregate chance-quality for a team: shots, xG sum (only over shots with xG), goals, big chances.
    xg_sum is None-safe: it sums only shots where xg_available, and reports the covered count so callers
    never read a partial xG sum as a full one."""
    t = [s for s in shots if s.team_id == team_id]
    with_xg = [s for s in t if s.xg_available]
    xg_sum = sum(s.xg for s in with_xg) if with_xg else None
    return {
        "team_id": team_id,
        "shots": len(t),
        "shots_on_target": sum(1 for s in t if s.outcome in ("Goal", "Saved")),
        "goals": sum(1 for s in t if s.is_goal),
        "xg_sum": xg_sum,
        "xg_shots_covered": len(with_xg),
        "big_chances": sum(1 for s in t if s.big_chance_proxy),
        "shots_in_box": sum(1 for s in t if s.distance is not None and s.distance <= 18.0),
    }
