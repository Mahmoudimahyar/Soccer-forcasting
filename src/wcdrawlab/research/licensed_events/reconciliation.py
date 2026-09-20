"""Provider-neutral reconciliation (Phase 3): score reconciliation (own-goal beneficiary, shootout separate),
event dedup, idempotent corrections, and cross-provider event reconciliation. Deterministic."""
from __future__ import annotations

from collections import defaultdict

GOAL_TYPES = {"goal", "penalty_scored"}


def reconcile_score(events):
    """Compute (home_goals, away_goals) from regulation+ET goals. own_goal credits the OTHER team. Shootout
    goals are kept SEPARATE (not added to the regulation score)."""
    home = away = 0
    for e in events:
        if e.period == "shootout":
            continue
        t = e.event_type
        if t in GOAL_TYPES:
            if e.team_id == e.home_team_id:
                home += 1
            elif e.team_id == e.away_team_id:
                away += 1
        elif t == "own_goal":
            # beneficiary is the opponent of the scoring team
            if e.team_id == e.home_team_id:
                away += 1
            elif e.team_id == e.away_team_id:
                home += 1
    return home, away


def dedupe_events(events):
    """Drop duplicate events by (canonical_match_id, event_type, player_id, match_clock_s, period)."""
    seen = set()
    out = []
    for e in events:
        key = (e.canonical_match_id, e.event_type, e.player_id, e.match_clock_s, e.period)
        if key in seen:
            e.duplicate_status = "duplicate"
            continue
        seen.add(key)
        e.duplicate_status = "unique"
        out.append(e)
    return out


def apply_corrections(events):
    """Idempotent: a 'corrected'/'retracted' event supersedes the original sharing the same event key.
    Re-applying the same correction yields the same result (annotation, not mutation of identity)."""
    by_key = {}
    order = []
    for e in events:
        key = (e.canonical_match_id, e.event_type, e.player_id, e.period)
        if key not in by_key:
            order.append(key)
        # later correction wins; retracted removes
        prev = by_key.get(key)
        if prev is None or e.correction_status in ("corrected", "retracted"):
            by_key[key] = e
    return [by_key[k] for k in order if by_key[k].correction_status != "retracted"]


def cross_provider_reconcile(events_a, events_b, clock_tol=30.0):
    """Match events across two providers by (event_type, team, ~match_clock). Returns agreements + conflicts."""
    idx_b = defaultdict(list)
    for e in events_b:
        idx_b[(e.event_type, e.team_id)].append(e)
    agree, only_a, conflict = [], [], []
    used = set()
    for a in events_a:
        cands = idx_b.get((a.event_type, a.team_id), [])
        m = None
        for b in cands:
            if id(b) in used:
                continue
            if a.match_clock_s is not None and b.match_clock_s is not None and abs(a.match_clock_s - b.match_clock_s) <= clock_tol:
                m = b
                break
        if m is None:
            only_a.append(a)
        else:
            used.add(id(m))
            if a.player_id and m.player_id and a.player_id != m.player_id:
                conflict.append((a, m))
            else:
                agree.append((a, m))
    only_b = [b for b in events_b if id(b) not in used]
    return {"agree": agree, "conflict": conflict, "only_a": only_a, "only_b": only_b}
