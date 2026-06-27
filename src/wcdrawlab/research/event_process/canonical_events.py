"""Provider-neutral canonical event model + StatsBomb open-data adapter.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Every downstream extractor (possession, territory, attacks, pressure, chance_quality, snapshots)
consumes the canonical event stream produced here -- never raw provider JSON. The canonical model
normalizes:
  * timing onto a single regulation match clock (minute/second, period),
  * locations onto the canonical 120x80 pitch frame,
  * a small, stable `kind` vocabulary,
  * `attacking_x` so that every team always attacks towards x=120 (orientation-free downstream).

Raw provider bytes are hashed (SourceTrace.source_sha256) for traceability but NEVER embedded in any
tracked artifact. Fields the source does not carry are left as None and flagged by the quality module;
they are never imputed as 0.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from . import contracts as C

PROVIDER_STATSBOMB = "statsbomb_open"

# Canonical event-kind vocabulary (small + stable). Provider-specific names map onto these.
KIND_PASS = "pass"
KIND_CARRY = "carry"
KIND_SHOT = "shot"
KIND_DRIBBLE = "dribble"
KIND_PRESSURE = "pressure"
KIND_BALL_RECOVERY = "ball_recovery"
KIND_INTERCEPTION = "interception"
KIND_BLOCK = "block"
KIND_CLEARANCE = "clearance"
KIND_DUEL = "duel"
KIND_FOUL_COMMITTED = "foul_committed"
KIND_FOUL_WON = "foul_won"
KIND_GOAL_KEEPER = "goal_keeper"
KIND_MISCONTROL = "miscontrol"
KIND_DISPOSSESSED = "dispossessed"
KIND_DRIBBLED_PAST = "dribbled_past"
KIND_BALL_RECEIPT = "ball_receipt"
KIND_SUBSTITUTION = "substitution"
KIND_OWN_GOAL_AGAINST = "own_goal_against"
KIND_OWN_GOAL_FOR = "own_goal_for"
KIND_BAD_BEHAVIOUR = "bad_behaviour"
KIND_HALF_START = "half_start"
KIND_HALF_END = "half_end"
KIND_STARTING_XI = "starting_xi"
KIND_OTHER = "other"

_SB_TYPE_TO_KIND = {
    "Pass": KIND_PASS,
    "Carry": KIND_CARRY,
    "Shot": KIND_SHOT,
    "Dribble": KIND_DRIBBLE,
    "Pressure": KIND_PRESSURE,
    "Ball Recovery": KIND_BALL_RECOVERY,
    "Interception": KIND_INTERCEPTION,
    "Block": KIND_BLOCK,
    "Clearance": KIND_CLEARANCE,
    "Duel": KIND_DUEL,
    "Foul Committed": KIND_FOUL_COMMITTED,
    "Foul Won": KIND_FOUL_WON,
    "Goal Keeper": KIND_GOAL_KEEPER,
    "Miscontrol": KIND_MISCONTROL,
    "Dispossessed": KIND_DISPOSSESSED,
    "Dribbled Past": KIND_DRIBBLED_PAST,
    "Ball Receipt*": KIND_BALL_RECEIPT,
    "Substitution": KIND_SUBSTITUTION,
    "Own Goal Against": KIND_OWN_GOAL_AGAINST,
    "Own Goal For": KIND_OWN_GOAL_FOR,
    "Bad Behaviour": KIND_BAD_BEHAVIOUR,
    "Half Start": KIND_HALF_START,
    "Half End": KIND_HALF_END,
    "Starting XI": KIND_STARTING_XI,
}

# Set-piece play patterns -> canonical attack phase (StatsBomb play_pattern.name).
_SB_PLAY_PATTERN_PHASE = {
    "Regular Play": C.PHASE_OPEN_PLAY,
    "From Counter": C.PHASE_COUNTER,
    "From Free Kick": C.PHASE_FREE_KICK,
    "From Corner": C.PHASE_CORNER,
    "From Throw In": C.PHASE_THROW_IN,
    "From Goal Kick": C.PHASE_GOAL_KICK,
    "From Keeper": C.PHASE_KEEPER,
    "From Kick Off": C.PHASE_KICK_OFF,
    "Other": C.PHASE_OTHER,
}


@dataclass
class CanonicalEvent:
    """One provider-neutral event on the regulation match clock.

    All locations are in the canonical 120x80 frame. `attacking_x` re-expresses the x-coordinate so
    the acting team is always attacking towards 120 (i.e. attacking_x = x for the home-oriented frame
    and 120 - x for the opponent), making every territory feature orientation-free.
    """
    idx: int
    period: int
    minute: int
    second: int
    elapsed: float          # absolute regulation seconds from kickoff of period 1
    kind: str
    type_name: str          # provider-native type name (traceability)
    team_id: Optional[int]
    team_name: Optional[str]
    player_id: Optional[int]
    possession: Optional[int]
    possession_team_id: Optional[int]
    play_pattern: Optional[str]
    location: Optional[tuple]      # (x, y) canonical frame, or None
    end_location: Optional[tuple]  # (x, y) for pass/carry/shot, or None
    under_pressure: bool
    counterpress: bool
    duration: Optional[float]
    raw: dict               # the provider event dict (in-memory only; never serialized to artifacts)

    # convenience accessors -----------------------------------------------------------------------
    @property
    def x(self) -> Optional[float]:
        return self.location[0] if self.location else None

    @property
    def y(self) -> Optional[float]:
        return self.location[1] if self.location else None


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _minute_clock(period: int, minute: Optional[int], second: Optional[int]) -> float:
    """Absolute regulation seconds. StatsBomb `minute` already counts continuously across the half
    boundary (2nd half starts at minute 45), so we use it directly and clamp seconds defensively."""
    m = minute if minute is not None else 0
    s = second if second is not None else 0
    return float(m) * 60.0 + float(s)


def _loc(v) -> Optional[tuple]:
    if isinstance(v, (list, tuple)) and len(v) >= 2 and v[0] is not None and v[1] is not None:
        return (float(v[0]), float(v[1]))
    return None


def from_statsbomb(events: list, source_match_id: str, source_sha256: str,
                   trace_extra: Optional[dict] = None):
    """Adapt a StatsBomb open-data event array into (canonical_events, SourceTrace, home/away ids).

    Team orientation: StatsBomb locations are already from the acting team's attacking perspective is
    NOT true -- StatsBomb fixes the coordinate frame per match (home team attacks 0->120 in period 1
    and flips in period 2 is also NOT modeled by SB; SB keeps a single frame for the whole match).
    StatsBomb open-data uses a *single fixed frame for the whole match*: the location is the literal
    pitch position, and a team's own/attacking direction must be inferred. We therefore compute
    `attacking_x` per event so that downstream territory features are direction-free, by detecting each
    team's attacking direction from its own shot/goal end-locations (falls back to None if unknown)."""
    canon: list[CanonicalEvent] = []
    team_ids = []
    for e in events:
        tn = (e.get("team") or {}).get("name")
        tid = (e.get("team") or {}).get("id")
        if tid is not None and tid not in team_ids:
            team_ids.append(tid)
        type_name = (e.get("type") or {}).get("name") or "Unknown"
        kind = _SB_TYPE_TO_KIND.get(type_name, KIND_OTHER)
        period = int(e.get("period") or 0)
        ce = CanonicalEvent(
            idx=int(e.get("index") or 0),
            period=period,
            minute=int(e.get("minute") or 0),
            second=int(e.get("second") or 0),
            elapsed=_minute_clock(period, e.get("minute"), e.get("second")),
            kind=kind,
            type_name=type_name,
            team_id=tid,
            team_name=tn,
            player_id=(e.get("player") or {}).get("id"),
            possession=e.get("possession"),
            possession_team_id=(e.get("possession_team") or {}).get("id"),
            play_pattern=(e.get("play_pattern") or {}).get("name"),
            location=_loc(e.get("location")),
            end_location=_canon_end_location(e, kind),
            under_pressure=bool(e.get("under_pressure")),
            counterpress=bool(e.get("counterpress")),
            duration=e.get("duration"),
            raw=e,
        )
        canon.append(ce)

    home_id = team_ids[0] if len(team_ids) >= 1 else None
    away_id = team_ids[1] if len(team_ids) >= 2 else None

    trace = C.SourceTrace(
        provider=PROVIDER_STATSBOMB,
        source_match_id=str(source_match_id),
        source_sha256=source_sha256,
        n_source_events=len(events),
        **(trace_extra or {}),
    )
    return canon, trace, (home_id, away_id)


def _canon_end_location(e: dict, kind: str) -> Optional[tuple]:
    if kind == KIND_PASS:
        return _loc((e.get("pass") or {}).get("end_location"))
    if kind == KIND_CARRY:
        return _loc((e.get("carry") or {}).get("end_location"))
    if kind == KIND_SHOT:
        el = (e.get("shot") or {}).get("end_location")
        return _loc(el) if el else None
    return None


def attacking_direction(canon: list, team_id: int) -> Optional[int]:
    """Infer a team's attacking direction (+1 attacking toward x=120, -1 toward x=0) from its own
    shots' x-locations. StatsBomb open-data keeps one fixed frame for the whole match. Returns None
    when there are no shots to disambiguate (caller must treat territory as `unknown`, not assume)."""
    xs = []
    for ce in canon:
        if ce.kind == KIND_SHOT and ce.team_id == team_id and ce.x is not None:
            xs.append(ce.x)
    if not xs:
        return None
    mean_x = sum(xs) / len(xs)
    # shots are overwhelmingly taken in the attacking half; >60 => attacking toward 120
    return 1 if mean_x >= C.PITCH_LENGTH / 2.0 else -1


def attacking_x(x: Optional[float], direction: Optional[int]) -> Optional[float]:
    """Re-express x so the acting team is always attacking toward 120. None if either input is None."""
    if x is None or direction is None:
        return None
    return x if direction == 1 else (C.PITCH_LENGTH - x)


def load_statsbomb_match(path: str | Path, trace_extra: Optional[dict] = None):
    """Read a StatsBomb event JSON file -> (canonical_events, SourceTrace, (home_id, away_id)).

    The raw bytes are hashed for traceability; the parsed JSON is held in-memory only.
    """
    p = Path(path)
    b = p.read_bytes()
    sha = sha256_bytes(b)
    events = json.loads(b.decode("utf-8"))
    match_id = p.stem
    return from_statsbomb(events, match_id, sha, trace_extra=trace_extra)
