"""Transition structure: turnovers, recoveries, regain location, transition-to-shot proxies.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

A *transition* is a change of the team in possession. We derive, per team, the count of regains
(recoveries + interceptions + opponent miscontrols/dispossessions), turnovers conceded, and a
fast-transition proxy: a regain followed by that team reaching the final third within a short event /
time window inside the same possession. Built on canonical events + extracted possessions, never raw
JSON. Direction-dependent geometry degrades to `unknown` (handled by quality.py) when a team's
attacking direction cannot be inferred."""
from __future__ import annotations

from . import canonical_events as CE
from . import contracts as C
from . import possession as POSS

_REGAIN_KINDS = {CE.KIND_BALL_RECOVERY, CE.KIND_INTERCEPTION}
_LOSS_KINDS = {CE.KIND_MISCONTROL, CE.KIND_DISPOSSESSED}


def transition_counts(canon: list, team_id: int, direction=None) -> dict:
    """Per-team regain/turnover counters and regain-location split (defensive/middle/attacking third).

    A regain in the team's own (defensive) third that begins a possession is the raw material for a
    counter/fast-transition; we expose the location split so attacks.py can build the proxy."""
    regains = turnovers = 0
    regain_def = regain_mid = regain_att = 0
    counterpress_regains = 0
    for e in canon:
        if e.team_id != team_id:
            continue
        if e.kind in _REGAIN_KINDS:
            regains += 1
            if e.counterpress:
                counterpress_regains += 1
            ax = CE.attacking_x(e.x, direction)
            if ax is not None:
                if ax < C.PITCH_LENGTH / 3.0:
                    regain_def += 1
                elif ax < 2.0 * C.PITCH_LENGTH / 3.0:
                    regain_mid += 1
                else:
                    regain_att += 1
        if e.kind in _LOSS_KINDS:
            turnovers += 1
    return {
        "team_id": team_id,
        "regains": regains,
        "turnovers": turnovers,
        "regains_def_third": regain_def,
        "regains_mid_third": regain_mid,
        "regains_att_third": regain_att,
        "counterpress_regains": counterpress_regains,
        "_direction_known": direction is not None,
    }


def fast_transitions(possessions: list, team_id: int) -> dict:
    """Count fast-transition possessions for a team using the possession-level transition flag and a
    short-duration regain-to-progression heuristic. Returns counts + how many reached a shot."""
    n_trans = 0
    n_trans_shot = 0
    for p in possessions:
        if p.team_id != team_id:
            continue
        if p.is_transition:
            n_trans += 1
            if p.ended_in_shot:
                n_trans_shot += 1
    return {"team_id": team_id, "fast_transitions": n_trans, "fast_transition_shots": n_trans_shot}
