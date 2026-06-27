"""Territory features: thirds, final-third / box entries, channels, deep progression, field-tilt.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

All features are computed in the orientation-free `attacking_x` frame (each team attacks toward 120),
using per-team attacking direction inferred in canonical_events.attacking_direction. A team whose
direction is unknown contributes `unknown`-flagged territory (handled by quality.py) -- positions are
never re-oriented by assumption.

Definitions (canonical 120x80 frame):
  thirds            : own (x<40), middle (40<=x<80), attacking (x>=80) by attacking_x of on-ball events.
  final_third_entry : a pass/carry whose START is outside the final third and END is inside (x>=80).
  box_entry         : a pass/carry whose START is outside the box and END inside the 18-yard box.
  channels          : lateral split of attacking-third touches into left/center/right by y.
  deep_progression  : pass/carry END located in the attacking sixth (x>=100) excluding the box edge.
  field_tilt        : share of final-third on-ball actions that belong to a team (possession-tilt proxy).
"""
from __future__ import annotations

from . import canonical_events as CE
from . import contracts as C

_PROGRESS_KINDS = {CE.KIND_PASS, CE.KIND_CARRY}
_TOUCH_KINDS = {CE.KIND_PASS, CE.KIND_CARRY, CE.KIND_DRIBBLE, CE.KIND_SHOT, CE.KIND_BALL_RECEIPT}
DEEP_X = 100.0  # attacking sixth threshold


def _third(ax: float) -> str:
    if ax < C.PITCH_LENGTH / 3.0:
        return "own"
    if ax < 2.0 * C.PITCH_LENGTH / 3.0:
        return "middle"
    return "attacking"


def _channel(y: float) -> str:
    if y < C.LEFT_CHANNEL_Y:
        return "left"
    if y < C.RIGHT_CHANNEL_Y:
        return "center"
    return "right"


def _in_box(ax: float, y: float) -> bool:
    return ax >= C.BOX_X and C.BOX_Y_LOW <= y <= C.BOX_Y_HIGH


def territory_for_team(canon: list, team_id: int, direction, opp_id=None) -> dict:
    """Accumulate territory counters for `team_id`. `direction` is +1/-1 or None.

    Returns a dict of integer counters plus a `_direction_known` flag so the quality layer can mark
    territory as available_verified vs unknown for this team/match."""
    thirds = {"own": 0, "middle": 0, "attacking": 0}
    channels = {"left": 0, "center": 0, "right": 0}
    ft_entries = 0
    box_entries = 0
    deep_progressions = 0
    final_third_touches = 0
    n_located = 0

    for e in canon:
        if e.team_id != team_id:
            continue
        ax = CE.attacking_x(e.x, direction)
        if ax is None:
            continue
        n_located += 1
        if e.kind in _TOUCH_KINDS:
            thirds[_third(ax)] += 1
            if ax >= C.FINAL_THIRD_X:
                final_third_touches += 1
                if e.y is not None:
                    channels[_channel(e.y)] += 1
        # progression-based entries need an end_location
        if e.kind in _PROGRESS_KINDS and e.end_location is not None:
            ex = CE.attacking_x(e.end_location[0], direction)
            ey = e.end_location[1]
            if ex is None:
                continue
            if ax < C.FINAL_THIRD_X <= ex:
                ft_entries += 1
            if not _in_box(ax, e.y if e.y is not None else -1) and _in_box(ex, ey):
                box_entries += 1
            if ex >= DEEP_X:
                deep_progressions += 1

    return {
        "team_id": team_id,
        "thirds_own": thirds["own"],
        "thirds_middle": thirds["middle"],
        "thirds_attacking": thirds["attacking"],
        "channel_left": channels["left"],
        "channel_center": channels["center"],
        "channel_right": channels["right"],
        "final_third_entries": ft_entries,
        "box_entries": box_entries,
        "deep_progressions": deep_progressions,
        "final_third_touches": final_third_touches,
        "n_located_events": n_located,
        "_direction_known": direction is not None,
    }


def field_tilt(canon: list, home_id, away_id, dir_home, dir_away) -> dict:
    """Field-tilt = share of final-third on-ball touches belonging to each team. Returns home share in
    [0,1] plus the raw counts; None when neither team has located final-third touches."""
    h = territory_for_team(canon, home_id, dir_home)["final_third_touches"] if home_id is not None else 0
    a = territory_for_team(canon, away_id, dir_away)["final_third_touches"] if away_id is not None else 0
    tot = h + a
    return {
        "home_final_third_touches": h,
        "away_final_third_touches": a,
        "home_field_tilt": (h / tot) if tot > 0 else None,
    }
