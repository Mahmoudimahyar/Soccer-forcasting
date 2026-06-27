"""Causal event-process snapshot feature engine (StatsBomb open-data event model).

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.

This module turns a single match's *raw StatsBomb event list* into:
  1. a deterministic schedule of CAUSAL snapshot times, and
  2. a leakage-safe feature vector at each snapshot time t.

LEAKAGE CONTRACT (the central invariant, also restated in contracts.py):
  * A snapshot at clock-minute t uses ONLY events with match-clock minute <= t. The clock is the
    StatsBomb absolute `minute` (period 2 begins at minute 45), tie-broken by `second` and `index`.
  * Regulation only: period in (1, 2). For regulation TARGETS we additionally require t <= 90 and we
    never place a snapshot after regulation full-time. Extra-time (period >= 3) and shootouts are
    excluded from regulation state; a `pre_extra_time` snapshot is allowed strictly at the regulation
    boundary (events minute <= 90 only).
  * No final score, no match totals, no later substitution, no future event leaks into a snapshot.

NO IMPUTATION-AS-ZERO: a structurally absent source field is flagged (available_verified /
available_partial / unavailable / unknown) on a per-match SourceQualityReport, never silently 0. The
numeric feature vector still carries 0 for "this thing did not happen yet" (a genuine count), which is
distinct from "the source cannot express this thing" (carried by the quality report).

Pure functions only: recomputed from the event list every call (idempotent, no hidden accumulation),
so a snapshot at t is provably independent of any event after t.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from . import contracts as C

ENGINE_VERSION = "event_process_snapshot_features_v1"

# --- canonical regulation / clock constants ------------------------------------------------------
REGULATION_MINUTE = 90
PERIOD_FIRST_HALF = 1
PERIOD_SECOND_HALF = 2
HALFTIME_MINUTE = 45  # StatsBomb 2nd-half events start at absolute minute 45

# Fixed clock snapshots (deterministic; HT == 45). Documented, outcome-independent.
FIXED_SNAPSHOT_MINUTES = [0, 5, 10, 15, 20, 25, 30, 45, 50, 55, 60, 65, 70, 75, 80, 85]

# Recent-event window widths (in minutes of match clock). `None` is the special "current half" and
# "match-to-date" windows handled explicitly.
ROLLING_WINDOWS_MIN = [1, 2, 5, 10, 15]  # 1min ~ "last 60s"; 2/5/10/15 as specified

# StatsBomb shot outcome that is a goal.
SB_GOAL = "Goal"
# StatsBomb own-goal credited-to-team event type (the BENEFICIARY side); the conceding-side mirror is
# "Own Goal Against" which we must NOT also count (would double count).
SB_OWN_GOAL_FOR = "Own Goal For"
SB_OWN_GOAL_AGAINST = "Own Goal Against"
# Card names (foul_committed.card.name / bad_behaviour.card.name).
CARD_YELLOW = "Yellow Card"
CARD_SECOND_YELLOW = "Second Yellow"
CARD_RED = "Red Card"
SENDING_OFF = {CARD_SECOND_YELLOW, CARD_RED}

# StatsBomb event type names used by the engine.
T_SHOT = "Shot"
T_PASS = "Pass"
T_CARRY = "Carry"
T_PRESSURE = "Pressure"
T_BALL_RECOVERY = "Ball Recovery"
T_INTERCEPTION = "Interception"
T_DISPOSSESSED = "Dispossessed"
T_MISCONTROL = "Miscontrol"
T_BLOCK = "Block"
T_CLEARANCE = "Clearance"
T_FOUL = "Foul Committed"
T_BAD_BEHAVIOUR = "Bad Behaviour"
T_SUB = "Substitution"
T_STARTING_XI = "Starting XI"
T_HALF_START = "Half Start"
T_HALF_END = "Half End"


# =================================================================================================
# clock helpers
# =================================================================================================
def event_clock(ev: dict) -> Optional[float]:
    """Absolute regulation match-clock in minutes (float) for an event, or None if unknown.

    StatsBomb `minute` is already absolute across halves; we add fractional seconds for ordering and
    fine-grained windows. Returns None when minute is missing (event is then excluded, never imputed).
    """
    m = ev.get("minute")
    if m is None:
        return None
    s = ev.get("second") or 0
    return float(m) + float(s) / 60.0


def is_regulation_event(ev: dict) -> bool:
    """True iff the event is in regulation play (period 1 or 2). ET/shootout (period >= 3) excluded."""
    p = ev.get("period")
    return p in (PERIOD_FIRST_HALF, PERIOD_SECOND_HALF)


def _safe_team_id(ev: dict) -> Optional[int]:
    t = ev.get("team")
    return t.get("id") if isinstance(t, dict) else None


def _type_name(ev: dict) -> Optional[str]:
    t = ev.get("type")
    return t.get("name") if isinstance(t, dict) else None


def _card_name(ev: dict) -> Optional[str]:
    """Return the card name attached to a foul/bad-behaviour event, else None."""
    fc = ev.get("foul_committed") or {}
    c = fc.get("card")
    if isinstance(c, dict) and c.get("name"):
        return c.get("name")
    bb = ev.get("bad_behaviour") or {}
    c = bb.get("card")
    if isinstance(c, dict) and c.get("name"):
        return c.get("name")
    return None


# =================================================================================================
# match preparation
# =================================================================================================
@dataclass
class MatchContext:
    """Static, leakage-free match identity derived from Starting XI / event metadata only."""
    source_match_id: str
    home_team_id: Optional[int]
    away_team_id: Optional[int]
    home_team_name: Optional[str]
    away_team_name: Optional[str]
    n_events: int
    max_regulation_minute: float
    has_extra_time: bool
    starting_xi_ok: bool


def prepare_match(events: list[dict], source_match_id: str,
                  home_team_id: Optional[int] = None,
                  away_team_id: Optional[int] = None) -> MatchContext:
    """Derive a leakage-free MatchContext. Home/away are taken from the explicit ids when provided
    (e.g. from the api<->statsbomb bridge); otherwise inferred from the two Starting XI events in
    documented order (first listed == home, matching StatsBomb open-data convention)."""
    teams: list[tuple[int, str]] = []
    for ev in events:
        if _type_name(ev) == T_STARTING_XI:
            t = ev.get("team") or {}
            if t.get("id") is not None:
                teams.append((t.get("id"), t.get("name")))
    starting_xi_ok = len(teams) >= 2
    h_id, a_id = home_team_id, away_team_id
    h_name = a_name = None
    if starting_xi_ok:
        if h_id is None:
            h_id = teams[0][0]
        if a_id is None:
            a_id = teams[1][0]
        names = {tid: tn for tid, tn in teams}
        h_name = names.get(h_id)
        a_name = names.get(a_id)
    max_reg = 0.0
    has_et = False
    for ev in events:
        p = ev.get("period")
        if p in (PERIOD_FIRST_HALF, PERIOD_SECOND_HALF):
            ck = event_clock(ev)
            if ck is not None and ck > max_reg:
                max_reg = ck
        elif isinstance(p, int) and p >= 3:
            has_et = True
    return MatchContext(
        source_match_id=str(source_match_id),
        home_team_id=h_id, away_team_id=a_id,
        home_team_name=h_name, away_team_name=a_name,
        n_events=len(events),
        max_regulation_minute=round(max_reg, 3),
        has_extra_time=has_et,
        starting_xi_ok=starting_xi_ok,
    )


# =================================================================================================
# event-triggered snapshot schedule (deterministic, causal)
# =================================================================================================
def _is_goal_event(ev: dict, team_id: int) -> bool:
    tn = _type_name(ev)
    if tn == T_SHOT:
        out = (ev.get("shot") or {}).get("outcome") or {}
        return out.get("name") == SB_GOAL and _safe_team_id(ev) == team_id
    if tn == SB_OWN_GOAL_FOR:
        return _safe_team_id(ev) == team_id
    return False


def _is_any_goal(ev: dict) -> bool:
    tn = _type_name(ev)
    if tn == T_SHOT:
        out = (ev.get("shot") or {}).get("outcome") or {}
        return out.get("name") == SB_GOAL
    return tn == SB_OWN_GOAL_FOR


def _is_box_entry(ev: dict) -> bool:
    """Pass or carry whose END location enters the attacking penalty box (canonical frame)."""
    tn = _type_name(ev)
    end = None
    if tn == T_PASS:
        end = (ev.get("pass") or {}).get("end_location")
    elif tn == T_CARRY:
        end = (ev.get("carry") or {}).get("end_location")
    if not (isinstance(end, (list, tuple)) and len(end) >= 2):
        return False
    x, y = end[0], end[1]
    return x >= C.BOX_X and C.BOX_Y_LOW <= y <= C.BOX_Y_HIGH


def _is_corner(ev: dict) -> bool:
    if _type_name(ev) != T_PASS:
        return False
    t = (ev.get("pass") or {}).get("type") or {}
    return t.get("name") == "Corner"


def _is_nonzero_xg_shot(ev: dict) -> bool:
    if _type_name(ev) != T_SHOT:
        return False
    xg = (ev.get("shot") or {}).get("statsbomb_xg")
    return isinstance(xg, (int, float)) and xg > 0.0


def event_trigger_minutes(events: list[dict]) -> list[tuple[float, str]]:
    """Deterministic list of (clock_minute, trigger_reason) for event-triggered snapshots, in
    regulation only. Triggers: after every goal / nonzero-xG shot / box-entry / corner / sub /
    sending-off. Each returns the clock at the triggering event (snapshot 'after' == includes that
    event, see snapshot_at semantics). Pure/deterministic ordering by (clock, index)."""
    out: list[tuple[float, str]] = []
    ordered = sorted(
        [e for e in events if is_regulation_event(e) and event_clock(e) is not None],
        key=lambda e: (event_clock(e), e.get("index", 0)),
    )
    for ev in ordered:
        ck = event_clock(ev)
        if ck > REGULATION_MINUTE:
            continue
        if _is_any_goal(ev):
            out.append((ck, "goal"))
        elif _is_nonzero_xg_shot(ev):
            out.append((ck, "nonzero_xg_shot"))
        elif _is_box_entry(ev):
            out.append((ck, "box_entry"))
        elif _is_corner(ev):
            out.append((ck, "corner"))
        elif _type_name(ev) == T_SUB:
            out.append((ck, "substitution"))
        elif _card_name(ev) in SENDING_OFF:
            out.append((ck, "sending_off"))
    return out


def snapshot_schedule(events: list[dict], ctx: MatchContext) -> list[dict]:
    """Full deterministic snapshot schedule for a match. Each entry:
        {minute, reason, kind}  with kind in {clock, event, pre_extra_time}
    Regulation-only; never after regulation full-time for regulation targets. De-duplicated by
    (rounded minute) preferring event reasons; a single `pre_extra_time` snapshot at the regulation
    boundary is added only when the match actually has extra-time."""
    sched: dict[float, dict] = {}

    # fixed clock snapshots that actually occurred (<= observed regulation length, capped at 90)
    last = min(REGULATION_MINUTE, math.floor(ctx.max_regulation_minute)) if ctx.max_regulation_minute else REGULATION_MINUTE
    for m in FIXED_SNAPSHOT_MINUTES:
        if m <= last:
            key = float(m)
            sched[key] = {"minute": float(m), "reason": "clock", "kind": "clock"}

    # event-triggered snapshots
    for ck, reason in event_trigger_minutes(events):
        # round to 3dp key; event reason wins over a colliding clock snapshot
        key = round(ck, 3)
        sched[key] = {"minute": round(ck, 3), "reason": reason, "kind": "event"}

    # pre-extra-time snapshot: strictly at the regulation boundary, only when ET exists
    if ctx.has_extra_time:
        key = float(REGULATION_MINUTE)
        if key not in sched:
            sched[key] = {"minute": float(REGULATION_MINUTE), "reason": "pre_extra_time", "kind": "pre_extra_time"}
        else:
            # keep existing reason but mark that ET follows (still a regulation-bounded snapshot)
            sched[key]["pre_extra_time"] = True

    return [sched[k] for k in sorted(sched.keys())]


# =================================================================================================
# causal event slicing
# =================================================================================================
def events_up_to(events: list[dict], t: float) -> list[dict]:
    """Return regulation events with clock-minute <= t, ordered by (clock, index). THE leakage gate:
    every feature consumes only this slice. Events after t are provably excluded."""
    sliced = [
        e for e in events
        if is_regulation_event(e) and (event_clock(e) is not None) and event_clock(e) <= t + 1e-9
    ]
    sliced.sort(key=lambda e: (event_clock(e), e.get("index", 0)))
    return sliced


# =================================================================================================
# feature families
# =================================================================================================
def _both_sides(d: dict, h_id, a_id, base: str, vh, va):
    d[f"{base}_home"] = vh
    d[f"{base}_away"] = va
    d[f"{base}_diff"] = (vh - va) if (vh is not None and va is not None) else None


def _window_slice(sliced: list[dict], t: float, width: Optional[float], current_half: bool):
    """Sub-slice of `sliced` for a recent-event window. `width` minutes back from t, OR current-half
    if current_half=True (events since the half that contains t began), OR full match-to-date when
    width is None and current_half is False."""
    if current_half:
        half_start = HALFTIME_MINUTE if t >= HALFTIME_MINUTE else 0.0
        return [e for e in sliced if event_clock(e) >= half_start - 1e-9]
    if width is None:
        return sliced
    lo = t - width
    return [e for e in sliced if event_clock(e) >= lo - 1e-9]


def _possession_counts(evs: list[dict], h_id, a_id):
    """Count completed-pass/carry possession-action events per team (a possession proxy that does not
    require ball-clock; deterministic and provider-light)."""
    ph = pa = 0
    for e in evs:
        tn = _type_name(e)
        if tn in (T_PASS, T_CARRY):
            tid = _safe_team_id(e)
            if tn == T_PASS:
                # only completed passes (no outcome == completed in StatsBomb)
                if (e.get("pass") or {}).get("outcome") is not None:
                    continue
            if tid == h_id:
                ph += 1
            elif tid == a_id:
                pa += 1
    return ph, pa


def _territory_thirds(evs: list[dict], h_id, a_id):
    """Count actions whose location is in the attacking final third, per team (territory proxy)."""
    th = ta = 0
    for e in evs:
        loc = e.get("location")
        if not (isinstance(loc, (list, tuple)) and len(loc) >= 2):
            continue
        x = loc[0]
        tid = _safe_team_id(e)
        if x is None:
            continue
        if x >= C.FINAL_THIRD_X:
            if tid == h_id:
                th += 1
            elif tid == a_id:
                ta += 1
    return th, ta


def _box_entries(evs: list[dict], h_id, a_id):
    bh = ba = 0
    for e in evs:
        if _is_box_entry(e):
            tid = _safe_team_id(e)
            if tid == h_id:
                bh += 1
            elif tid == a_id:
                ba += 1
    return bh, ba


def _transitions(evs: list[dict], h_id, a_id):
    """Recoveries/interceptions (regains) and turnovers (dispossessed/miscontrol) per team."""
    rec_h = rec_a = to_h = to_a = 0
    for e in evs:
        tn = _type_name(e)
        tid = _safe_team_id(e)
        if tn in (T_BALL_RECOVERY, T_INTERCEPTION):
            if tid == h_id:
                rec_h += 1
            elif tid == a_id:
                rec_a += 1
        elif tn in (T_DISPOSSESSED, T_MISCONTROL):
            if tid == h_id:
                to_h += 1
            elif tid == a_id:
                to_a += 1
    return rec_h, rec_a, to_h, to_a


def _set_pieces(evs: list[dict], h_id, a_id):
    """Corners and (proxy) attacking free-kick deliveries per team."""
    ch = ca = fkh = fka = 0
    for e in evs:
        if _type_name(e) != T_PASS:
            continue
        ptype = ((e.get("pass") or {}).get("type") or {}).get("name")
        tid = _safe_team_id(e)
        if ptype == "Corner":
            if tid == h_id:
                ch += 1
            elif tid == a_id:
                ca += 1
        elif ptype == "Free Kick":
            if tid == h_id:
                fkh += 1
            elif tid == a_id:
                fka += 1
    return ch, ca, fkh, fka


def _shots_and_xg(evs: list[dict], h_id, a_id):
    """Per-team shot count, shots-on-target, cumulative xG (sum of statsbomb_xg over shots present)."""
    sh = sa = soth = sota = 0
    xgh = xga = 0.0
    xg_present = False
    for e in evs:
        if _type_name(e) != T_SHOT:
            continue
        tid = _safe_team_id(e)
        shot = e.get("shot") or {}
        out = (shot.get("outcome") or {}).get("name")
        on_target = out in (SB_GOAL, "Saved", "Saved To Post")
        xg = shot.get("statsbomb_xg")
        if isinstance(xg, (int, float)):
            xg_present = True
        if tid == h_id:
            sh += 1
            soth += 1 if on_target else 0
            if isinstance(xg, (int, float)):
                xgh += xg
        elif tid == a_id:
            sa += 1
            sota += 1 if on_target else 0
            if isinstance(xg, (int, float)):
                xga += xg
    return sh, sa, soth, sota, round(xgh, 5), round(xga, 5), xg_present


def _goals(evs: list[dict], h_id, a_id):
    gh = ga = 0
    for e in evs:
        if _is_goal_event(e, h_id):
            gh += 1
        elif _is_goal_event(e, a_id):
            ga += 1
    return gh, ga


def _cards(evs: list[dict], h_id, a_id):
    yh = ya = rh = ra = 0
    for e in evs:
        cn = _card_name(e)
        if cn is None:
            continue
        tid = _safe_team_id(e)
        home = tid == h_id
        if cn == CARD_YELLOW:
            yh += home
            ya += not home
        elif cn in SENDING_OFF:
            rh += home
            ra += not home
    return yh, ya, rh, ra


def _subs(evs: list[dict], h_id, a_id):
    sh = sa = 0
    for e in evs:
        if _type_name(e) == T_SUB:
            tid = _safe_team_id(e)
            if tid == h_id:
                sh += 1
            elif tid == a_id:
                sa += 1
    return sh, sa


def _time_since_last_shot(evs: list[dict], t: float, h_id, a_id):
    """Minutes since last shot (any team / per side); None if no shot yet (NOT zero)."""
    last_any = last_h = last_a = None
    for e in evs:
        if _type_name(e) != T_SHOT:
            continue
        ck = event_clock(e)
        tid = _safe_team_id(e)
        last_any = ck if last_any is None or ck > last_any else last_any
        if tid == h_id:
            last_h = ck if last_h is None or ck > last_h else last_h
        elif tid == a_id:
            last_a = ck if last_a is None or ck > last_a else last_a
    f = lambda x: round(t - x, 3) if x is not None else None
    return f(last_any), f(last_h), f(last_a)


def _time_since_major_chance(evs: list[dict], t: float, thresh: float = 0.15):
    """Minutes since last 'major chance' (shot with xG >= thresh). None if none yet."""
    last = None
    for e in evs:
        if _type_name(e) != T_SHOT:
            continue
        xg = (e.get("shot") or {}).get("statsbomb_xg")
        if isinstance(xg, (int, float)) and xg >= thresh:
            ck = event_clock(e)
            last = ck if last is None or ck > last else last
    return round(t - last, 3) if last is not None else None


# =================================================================================================
# snapshot assembly
# =================================================================================================
def snapshot_features(events: list[dict], ctx: MatchContext, t: float, reason: str = "clock") -> dict:
    """Compute the full leakage-safe feature vector at clock-minute t. Home is `ctx.home_team_id`.

    Every value is derived from events_up_to(events, t) ONLY. `*_diff` is home-minus-away. Counts of
    "did not happen yet" are genuine 0; structural source absence is reported separately by
    source_quality_report (not here)."""
    h_id, a_id = ctx.home_team_id, ctx.away_team_id
    sliced = events_up_to(events, t)
    f: dict[str, Any] = {
        "snapshot_minute": round(float(t), 3),
        "snapshot_reason": reason,
        "remaining_regulation_min": round(max(0.0, REGULATION_MINUTE - t), 3),
        "period": PERIOD_FIRST_HALF if t < HALFTIME_MINUTE else PERIOD_SECOND_HALF,
        "is_halftime": abs(t - HALFTIME_MINUTE) < 1e-6,
        "n_events_observed": len(sliced),
    }

    # ---- game state (score / cards / subs / players on pitch) ----
    gh, ga = _goals(sliced, h_id, a_id)
    _both_sides(f, h_id, a_id, "goals", gh, ga)
    f["score_state"] = "H" if gh > ga else ("A" if ga > gh else "level")
    yh, ya, rh, ra = _cards(sliced, h_id, a_id)
    _both_sides(f, h_id, a_id, "yellow", yh, ya)
    _both_sides(f, h_id, a_id, "sendoff", rh, ra)
    # players on pitch: 11 minus sending-offs (subs do not reduce count). diff +ve => home advantage.
    f["players_home"] = 11 - rh
    f["players_away"] = 11 - ra
    f["players_diff"] = (11 - rh) - (11 - ra)
    sh_, sa_ = _subs(sliced, h_id, a_id)
    _both_sides(f, h_id, a_id, "subs_used", sh_, sa_)

    # ---- possession ----
    ph, pa = _possession_counts(sliced, h_id, a_id)
    tot = ph + pa
    f["poss_actions_home"] = ph
    f["poss_actions_away"] = pa
    f["poss_share_home"] = round(ph / tot, 5) if tot else None
    f["poss_share_diff"] = round((ph - pa) / tot, 5) if tot else None

    # ---- territory ----
    th, ta = _territory_thirds(sliced, h_id, a_id)
    ttot = th + ta
    _both_sides(f, h_id, a_id, "final_third_actions", th, ta)
    f["field_tilt_home"] = round(th / ttot, 5) if ttot else None  # share of final-third actions
    bh, ba = _box_entries(sliced, h_id, a_id)
    _both_sides(f, h_id, a_id, "box_entries", bh, ba)

    # ---- transition ----
    rec_h, rec_a, to_h, to_a = _transitions(sliced, h_id, a_id)
    _both_sides(f, h_id, a_id, "recoveries", rec_h, rec_a)
    _both_sides(f, h_id, a_id, "turnovers", to_h, to_a)

    # ---- set-piece ----
    ch, ca, fkh, fka = _set_pieces(sliced, h_id, a_id)
    _both_sides(f, h_id, a_id, "corners", ch, ca)
    _both_sides(f, h_id, a_id, "att_free_kicks", fkh, fka)

    # ---- chance quality (cumulative) ----
    nsh, nsa, soth, sota, xgh, xga, xg_present = _shots_and_xg(sliced, h_id, a_id)
    _both_sides(f, h_id, a_id, "shots", nsh, nsa)
    _both_sides(f, h_id, a_id, "shots_on_target", soth, sota)
    _both_sides(f, h_id, a_id, "cum_xg", xgh, xga)
    f["cum_xg_total"] = round(xgh + xga, 5)
    f["xg_present"] = bool(xg_present)
    # time-since features (None == not happened yet, NOT zero)
    ts_any, ts_h, ts_a = _time_since_last_shot(sliced, t, h_id, a_id)
    f["min_since_last_shot_any"] = ts_any
    f["min_since_last_shot_home"] = ts_h
    f["min_since_last_shot_away"] = ts_a
    f["min_since_major_chance"] = _time_since_major_chance(sliced, t)

    # ---- rolling chance windows + momentum/acceleration ----
    # xG accumulated within last 2/5/10/15 min, current half, match-to-date (the latter == cum_xg).
    for w in ROLLING_WINDOWS_MIN:
        ws = _window_slice(sliced, t, float(w), current_half=False)
        _, _, _, _, wxgh, wxga, _ = _shots_and_xg(ws, h_id, a_id)
        wnsh, wnsa = 0, 0
        for e in ws:
            if _type_name(e) == T_SHOT:
                tid = _safe_team_id(e)
                wnsh += tid == h_id
                wnsa += tid == a_id
        f[f"xg_last{w}m_home"] = wxgh
        f[f"xg_last{w}m_away"] = wxga
        f[f"xg_last{w}m_diff"] = round(wxgh - wxga, 5)
        f[f"shots_last{w}m_home"] = wnsh
        f[f"shots_last{w}m_away"] = wnsa
    # current-half xG
    hs = _window_slice(sliced, t, None, current_half=True)
    _, _, _, _, hxgh, hxga, _ = _shots_and_xg(hs, h_id, a_id)
    f["xg_current_half_home"] = hxgh
    f["xg_current_half_away"] = hxga
    f["xg_current_half_diff"] = round(hxgh - hxga, 5)
    # momentum = xG-diff rate over last 10m; acceleration = (last5 rate) - (prior 5..10 rate)
    f["xg_momentum_diff_10m"] = round(f["xg_last10m_diff"] / 10.0, 6)
    prior5 = _window_slice(sliced, t - 5.0, 5.0, current_half=False) if t >= 5.0 else []
    _, _, _, _, p5h, p5a, _ = _shots_and_xg(prior5, h_id, a_id)
    rate_last5 = f["xg_last5m_diff"] / 5.0
    rate_prev5 = (p5h - p5a) / 5.0
    f["xg_acceleration_diff"] = round(rate_last5 - rate_prev5, 6)

    return f


# =================================================================================================
# targets (regulation only; computed from FULL match but never fed back into snapshot features)
# =================================================================================================
def regulation_final(events: list[dict], ctx: MatchContext) -> Optional[dict]:
    """Regulation full-time W/D/L target from goals at minute <= 90. Returns None if no Starting XI /
    teams resolved. Targets live in a SEPARATE table; they are never an input to snapshot_features."""
    if ctx.home_team_id is None or ctx.away_team_id is None:
        return None
    final = events_up_to(events, REGULATION_MINUTE)
    gh, ga = _goals(final, ctx.home_team_id, ctx.away_team_id)
    wdl = "H" if gh > ga else ("A" if ga > gh else "D")
    return {"reg_home_goals": gh, "reg_away_goals": ga, "target_wdl": wdl}


def next_goal_after(events: list[dict], ctx: MatchContext, t: float) -> dict:
    """Next regulation goal after snapshot t (target for next-goal models). 'side' in
    {home, away, none}; 'within_*' booleans for horizon variants. Computed from events strictly
    after t and <= 90 (full match used for labelling only)."""
    h_id, a_id = ctx.home_team_id, ctx.away_team_id
    after = [e for e in events if is_regulation_event(e) and event_clock(e) is not None
             and t + 1e-9 < event_clock(e) <= REGULATION_MINUTE]
    after.sort(key=lambda e: (event_clock(e), e.get("index", 0)))
    side = "none"
    ck_next = None
    for e in after:
        if _is_goal_event(e, h_id):
            side, ck_next = "home", event_clock(e)
            break
        if _is_goal_event(e, a_id):
            side, ck_next = "away", event_clock(e)
            break
    out = {"next_goal_side": side, "next_goal_minute": round(ck_next, 3) if ck_next is not None else None}
    return out


def scoring_in_window(events: list[dict], ctx: MatchContext, t: float, horizon: int) -> dict:
    """Did each side score within (t, t+horizon] (capped at 90)? Target for near-term scoring models."""
    h_id, a_id = ctx.home_team_id, ctx.away_team_id
    hi = min(REGULATION_MINUTE, t + horizon)
    win = [e for e in events if is_regulation_event(e) and event_clock(e) is not None
           and t + 1e-9 < event_clock(e) <= hi]
    gh, ga = _goals(win, h_id, a_id)
    return {
        f"home_scores_next{horizon}m": int(gh > 0),
        f"away_scores_next{horizon}m": int(ga > 0),
        f"any_goal_next{horizon}m": int((gh + ga) > 0),
    }


# =================================================================================================
# source-quality report (per match; never imputes absence as 0)
# =================================================================================================
def source_quality_report(events: list[dict], ctx: MatchContext) -> C.SourceQualityReport:
    """Roll up which canonical capabilities THIS match's source actually supported. Flags follow
    contracts.QUALITY_FLAGS. Anything the StatsBomb schema cannot express for this match is
    `unavailable`; partially-present (e.g. xG on only some shots) is `available_partial`."""
    rep = C.SourceQualityReport(provider="statsbomb_open", source_match_id=ctx.source_match_id)
    types = {_type_name(e) for e in events}
    has_loc = any(isinstance(e.get("location"), (list, tuple)) for e in events)
    shots = [e for e in events if _type_name(e) == T_SHOT]
    n_shot = len(shots)
    n_xg = sum(1 for e in shots if isinstance((e.get("shot") or {}).get("statsbomb_xg"), (int, float)))
    n_ff = sum(1 for e in shots if (e.get("shot") or {}).get("freeze_frame"))

    def flag(present_full, present_partial=False):
        if present_full:
            return C.AVAILABLE_VERIFIED
        if present_partial:
            return C.AVAILABLE_PARTIAL
        return C.UNAVAILABLE

    rep.set("possession_structure", flag(T_PASS in types or T_CARRY in types))
    rep.set("territory_thirds", flag(has_loc))
    rep.set("box_entries", flag(has_loc and (T_PASS in types or T_CARRY in types)))
    rep.set("channels", flag(has_loc))
    rep.set("deep_progression", flag(has_loc and T_PASS in types))
    rep.set("field_tilt", flag(has_loc))
    rep.set("attack_phase", flag(T_PASS in types))
    rep.set("counter_proxy", flag(T_CARRY in types or T_BALL_RECOVERY in types))
    rep.set("possession_to_shot_chain", flag(n_shot > 0 and (T_PASS in types)))
    rep.set("pressure", flag(T_PRESSURE in types))
    rep.set("counterpress_proxy", flag(T_PRESSURE in types, present_partial=True))
    rep.set("recoveries", flag(T_BALL_RECOVERY in types or T_INTERCEPTION in types))
    rep.set("turnovers", flag(T_DISPOSSESSED in types or T_MISCONTROL in types))
    rep.set("blocks_clearances", flag(T_BLOCK in types or T_CLEARANCE in types))
    rep.set("shot_events", flag(n_shot > 0))
    rep.set("shot_xg", flag(n_shot > 0 and n_xg == n_shot,
                            present_partial=(0 < n_xg < n_shot)))
    rep.set("shot_location", flag(n_shot > 0 and all(isinstance(e.get("location"), (list, tuple)) for e in shots),
                                  present_partial=(0 < sum(1 for e in shots if isinstance(e.get("location"), (list, tuple))) < n_shot)))
    rep.set("shot_freeze_frame", flag(n_shot > 0 and n_ff == n_shot,
                                      present_partial=(0 < n_ff < n_shot)))
    rep.set("big_chance_proxy", flag(n_xg > 0, present_partial=(n_shot > 0 and n_xg == 0)))
    rep.set("match_state", flag(ctx.starting_xi_ok))
    rep.set("cards", flag(T_FOUL in types or T_BAD_BEHAVIOUR in types))
    return rep


# =================================================================================================
# match completeness (for the completeness table)
# =================================================================================================
def match_completeness(events: list[dict], ctx: MatchContext) -> dict:
    """Per-match structural-completeness record. Honest flags, never imputed."""
    n_half_start = sum(1 for e in events if _type_name(e) == T_HALF_START)
    n_half_end = sum(1 for e in events if _type_name(e) == T_HALF_END)
    n_shot = sum(1 for e in events if _type_name(e) == T_SHOT)
    n_xg = sum(1 for e in events if _type_name(e) == T_SHOT
               and isinstance((e.get("shot") or {}).get("statsbomb_xg"), (int, float)))
    return {
        "source_match_id": ctx.source_match_id,
        "n_events": ctx.n_events,
        "starting_xi_ok": ctx.starting_xi_ok,
        "home_team_id": ctx.home_team_id,
        "away_team_id": ctx.away_team_id,
        "max_regulation_minute": ctx.max_regulation_minute,
        "has_extra_time": ctx.has_extra_time,
        "n_half_start_events": n_half_start,
        "n_half_end_events": n_half_end,
        "n_shots": n_shot,
        "n_shots_with_xg": n_xg,
        "xg_coverage": (
            "available_verified" if (n_shot > 0 and n_xg == n_shot)
            else ("available_partial" if (0 < n_xg < n_shot)
                  else ("unavailable" if n_shot > 0 else "unknown"))
        ),
        "regulation_clock_ok": bool(ctx.max_regulation_minute >= 80.0),
        "engine_version": ENGINE_VERSION,
    }
