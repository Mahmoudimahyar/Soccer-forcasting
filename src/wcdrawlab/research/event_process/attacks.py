"""Attack-phase classification and possession->shot / box-entry chains.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

Classifies the attack phase of each shot and of each possession (open-play / set-piece variants /
counter / sustained), and builds the possession->shot and possession->box-entry chain counts per team.
Phase comes from the canonical play_pattern (provider-verified) with a 'sustained' vs 'counter' proxy
derived from possession length/duration -- the proxy is flagged available_partial by quality.py, never
presented as a verified source field.

Open-play phase taxonomy used here:
  open_play_sustained : open-play possession with >= SUSTAINED_ACTIONS on-ball actions.
  open_play_counter   : possession flagged From Counter, or a quick regain-to-shot transition.
  open_play_direct    : short open-play possession that still reached a shot (direct attack).
"""
from __future__ import annotations

from . import canonical_events as CE
from . import contracts as C
from . import possession as POSS

SUSTAINED_ACTIONS = 6      # on-ball actions threshold for a "sustained" build-up
SUSTAINED_DURATION = 12.0  # seconds

# canonical set-piece phases (subset of contracts vocabulary that originate a fresh attack)
SET_PIECE_PHASES = {C.PHASE_CORNER, C.PHASE_FREE_KICK, C.PHASE_THROW_IN, C.PHASE_GOAL_KICK}


def shot_phase(shot_event) -> str:
    """Canonical attack phase for a single shot, from play_pattern + shot.type (penalty)."""
    sh = shot_event.raw.get("shot") or {}
    stype = (sh.get("type") or {}).get("name")
    if stype == "Penalty":
        return C.PHASE_PENALTY
    if stype == "Free Kick":
        return C.PHASE_FREE_KICK
    if stype == "Corner":
        return C.PHASE_CORNER
    pp = CE._SB_PLAY_PATTERN_PHASE.get(shot_event.play_pattern or "", C.PHASE_UNKNOWN)
    return pp if pp != C.PHASE_OPEN_PLAY else C.PHASE_OPEN_PLAY


def possession_phase(p: "POSS.Possession") -> str:
    """Canonical phase for a whole possession with sustained/counter/direct open-play refinement."""
    base = CE._SB_PLAY_PATTERN_PHASE.get(p.play_pattern or "", C.PHASE_UNKNOWN)
    if base in SET_PIECE_PHASES:
        return base
    if base == C.PHASE_PENALTY:
        return C.PHASE_PENALTY
    if base == C.PHASE_COUNTER or p.is_transition:
        return "open_play_counter"
    if base in (C.PHASE_OPEN_PLAY, C.PHASE_KICK_OFF, C.PHASE_KEEPER, C.PHASE_GOAL_KICK):
        if p.n_actions >= SUSTAINED_ACTIONS or p.duration >= SUSTAINED_DURATION:
            return "open_play_sustained"
        if p.ended_in_shot:
            return "open_play_direct"
        return C.PHASE_OPEN_PLAY
    return base if base != C.PHASE_UNKNOWN else C.PHASE_UNKNOWN


def attack_chains_for_team(canon: list, possessions: list, team_id: int) -> dict:
    """Per-team chain counters: possessions, possession->shot, possession->box-entry, by phase."""
    phase_counts: dict[str, int] = {}
    phase_shots: dict[str, int] = {}
    n_poss = poss_to_shot = poss_to_box = 0
    set_piece_shots = open_play_shots = counter_shots = 0

    for p in possessions:
        if p.team_id != team_id:
            continue
        n_poss += 1
        ph = possession_phase(p)
        phase_counts[ph] = phase_counts.get(ph, 0) + 1
        if p.ended_in_shot:
            poss_to_shot += 1
            phase_shots[ph] = phase_shots.get(ph, 0) + 1
            if ph in SET_PIECE_PHASES or ph == C.PHASE_PENALTY:
                set_piece_shots += 1
            elif ph == "open_play_counter":
                counter_shots += 1
            else:
                open_play_shots += 1
        if p.reached_box:
            poss_to_box += 1

    return {
        "team_id": team_id,
        "n_possessions": n_poss,
        "possessions_to_shot": poss_to_shot,
        "possessions_to_box": poss_to_box,
        "set_piece_shots": set_piece_shots,
        "open_play_shots": open_play_shots,
        "counter_shots": counter_shots,
        "phase_counts": phase_counts,
        "phase_shots": phase_shots,
    }
