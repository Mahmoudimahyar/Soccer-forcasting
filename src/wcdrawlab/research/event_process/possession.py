"""Possession-structure extraction from canonical events.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

A *possession* is a contiguous run of events sharing the same provider `possession` index (StatsBomb
groups a team's spell on the ball, including the opponent's defensive/pressure actions that occur
during it). For each possession we derive id/team/start/end/duration/action-count/outcome and classify
turnover vs recovery vs transition. All timing is on the regulation clock; callers that need
leakage-safe truncation pass already-truncated events.

No source field is imputed as 0: if `possession` indices are absent the extractor returns an empty
list and the quality module flags `possession_structure=unavailable`.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from . import canonical_events as CE
from . import contracts as C

# Outcome classification for a possession's terminal on-ball event by the possessing team.
OUTCOME_SHOT = "shot"
OUTCOME_GOAL = "goal"
OUTCOME_TURNOVER = "turnover"      # lost the ball to the opponent (miscontrol/dispossessed/failed action)
OUTCOME_FOUL_WON = "foul_won"
OUTCOME_FOUL_CONCEDED = "foul_conceded"
OUTCOME_OUT_OF_PLAY = "out_of_play"
OUTCOME_HALF_END = "half_end"
OUTCOME_UNKNOWN = "unknown"

# events that count as on-ball "actions" by the possessing team
_ONBALL = {CE.KIND_PASS, CE.KIND_CARRY, CE.KIND_DRIBBLE, CE.KIND_SHOT}


@dataclass
class Possession:
    possession_id: int
    team_id: Optional[int]
    start_idx: int
    end_idx: int
    start_elapsed: float
    end_elapsed: float
    duration: float
    period: int
    start_minute: int
    n_events: int
    n_actions: int          # on-ball actions by the possessing team
    n_passes: int
    n_carries: int
    reached_final_third: bool
    reached_box: bool
    ended_in_shot: bool
    ended_in_goal: bool
    outcome: str
    started_by_recovery: bool   # possession began with a recovery/interception (regain)
    is_transition: bool         # regain in own half that progressed quickly upfield (counter proxy)
    play_pattern: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _terminal_outcome(team_id, evs) -> tuple[str, bool, bool]:
    """Classify the terminal outcome of a possession. Returns (outcome, ended_in_shot, ended_in_goal)."""
    ended_shot = ended_goal = False
    # scan the possessing team's own-ball events from the end
    own = [e for e in evs if e.team_id == team_id]
    for e in reversed(own):
        if e.kind == CE.KIND_SHOT:
            ended_shot = True
            sh = (e.raw.get("shot") or {})
            if (sh.get("outcome") or {}).get("name") == "Goal":
                ended_goal = True
            return (OUTCOME_GOAL if ended_goal else OUTCOME_SHOT, ended_shot, ended_goal)
        if e.kind in (CE.KIND_MISCONTROL, CE.KIND_DISPOSSESSED):
            return (OUTCOME_TURNOVER, False, False)
        if e.kind == CE.KIND_FOUL_WON:
            return (OUTCOME_FOUL_WON, False, False)
        if e.kind == CE.KIND_FOUL_COMMITTED:
            return (OUTCOME_FOUL_CONCEDED, False, False)
    # no decisive own event -> infer from last event in possession
    if evs and evs[-1].kind == CE.KIND_HALF_END:
        return (OUTCOME_HALF_END, False, False)
    return (OUTCOME_UNKNOWN, False, False)


def extract_possessions(canon: list, directions: Optional[dict] = None) -> list:
    """Group canonical events into possessions.

    `directions` maps team_id -> attacking direction (+1/-1) for orientation-free territory checks.
    If None or a team's direction is unknown, territory reached-flags fall back to the raw frame's
    far-third / box geometry only when location exists (never invented)."""
    by_poss: dict[int, list] = {}
    order: list[int] = []
    for e in canon:
        pid = e.possession
        if pid is None:
            continue
        if pid not in by_poss:
            by_poss[pid] = []
            order.append(pid)
        by_poss[pid].append(e)

    out: list[Possession] = []
    for pid in order:
        evs = by_poss[pid]
        # possessing team = provider possession_team (fallback: most common team)
        pteam = evs[0].possession_team_id
        if pteam is None:
            from collections import Counter
            pteam = Counter(e.team_id for e in evs if e.team_id is not None).most_common(1)
            pteam = pteam[0][0] if pteam else None
        own = [e for e in evs if e.team_id == pteam]
        direction = (directions or {}).get(pteam)

        reached_ft = reached_box = False
        for e in own:
            ax = CE.attacking_x(e.x, direction)
            if ax is not None:
                if ax >= C.FINAL_THIRD_X:
                    reached_ft = True
                if ax >= C.BOX_X and (e.y is not None and C.BOX_Y_LOW <= e.y <= C.BOX_Y_HIGH):
                    reached_box = True

        outcome, ended_shot, ended_goal = _terminal_outcome(pteam, evs)
        first = evs[0]
        last = evs[-1]
        started_recovery = first.kind in (CE.KIND_BALL_RECOVERY, CE.KIND_INTERCEPTION) or \
            (first.play_pattern in ("From Counter",))
        # transition/counter proxy: possession flagged 'From Counter' OR regain in own half that
        # reached the final third within the possession.
        own_half_start = False
        if first.x is not None and direction is not None:
            own_half_start = CE.attacking_x(first.x, direction) < C.PITCH_LENGTH / 2.0
        is_transition = (first.play_pattern == "From Counter") or (started_recovery and own_half_start and reached_ft)

        out.append(Possession(
            possession_id=pid,
            team_id=pteam,
            start_idx=first.idx,
            end_idx=last.idx,
            start_elapsed=first.elapsed,
            end_elapsed=last.elapsed,
            duration=max(0.0, last.elapsed - first.elapsed),
            period=first.period,
            start_minute=first.minute,
            n_events=len(evs),
            n_actions=sum(1 for e in own if e.kind in _ONBALL),
            n_passes=sum(1 for e in own if e.kind == CE.KIND_PASS),
            n_carries=sum(1 for e in own if e.kind == CE.KIND_CARRY),
            reached_final_third=reached_ft,
            reached_box=reached_box,
            ended_in_shot=ended_shot,
            ended_in_goal=ended_goal,
            outcome=outcome,
            started_by_recovery=bool(started_recovery),
            is_transition=bool(is_transition),
            play_pattern=first.play_pattern,
        ))
    return out
