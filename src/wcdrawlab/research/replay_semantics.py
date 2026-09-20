"""Provider-aware 2022 World Cup replay event semantics (Offline Hardening Phase 1 / Section 7B).

API-Football event shape: each event has type in {Goal, Card, subst, Var}, a `detail`, a `team`, and a
`time.elapsed` (+ optional `extra`). Semantics enforced:
  - goals: type Goal; detail Normal Goal / Penalty / Own Goal. OWN GOAL: API-Football records `team` as
    the BENEFICIARY (no inversion). A Var 'Goal cancelled' nullifies a same-minute same-team goal.
  - regulation+ET score uses minute <= 120; PENALTY SHOOTOUT is separate (never folded into the score).
  - cards: red = 'Red Card' or 'Second Yellow card'.
Pure functions; deterministic; no I/O, no network.
"""
from __future__ import annotations


def _minute(e):
    t = e.get("time", {}) or {}
    return int(t.get("elapsed") or 0) + int(t.get("extra") or 0)


def dedupe_events(events):
    """Remove EXACT-duplicate provider events (same type/detail/team/minute/player). Order-preserving."""
    seen = set(); out = []
    for e in events:
        key = (e.get("type"), e.get("detail"), (e.get("team") or {}).get("name"),
               _minute(e), (e.get("player") or {}).get("id"))
        if key in seen:
            continue
        seen.add(key); out.append(e)
    return out


def reconcile_goals(events, home_team, away_team, max_minute=120):
    """Regulation+ET goals per team, honoring own-goal beneficiary + VAR cancellations. Excludes shootout."""
    cancelled = {(_minute(e), (e.get("team") or {}).get("name"))
                 for e in events if e.get("type") == "Var"
                 and "cancel" in str(e.get("detail", "")).lower()}
    score = {home_team: 0, away_team: 0}
    for e in events:
        if e.get("type") != "Goal":
            continue
        m = _minute(e)
        if m > max_minute:
            continue  # shootout / out-of-window
        team = (e.get("team") or {}).get("name")
        if (m, team) in cancelled:
            continue  # VAR-disallowed
        if team in score:
            score[team] += 1   # own-goal team = beneficiary (no inversion)
    return score


def shootout_score(fixture_score):
    """Penalty-shootout score kept SEPARATE from regulation/ET. Returns (home, away) or None."""
    pen = (fixture_score or {}).get("penalty") or {}
    if pen.get("home") is None and pen.get("away") is None:
        return None
    return (int(pen.get("home") or 0), int(pen.get("away") or 0))


def count_cards(events, home_team, away_team):
    out = {home_team: {"yellow": 0, "red": 0, "second_yellow": 0},
           away_team: {"yellow": 0, "red": 0, "second_yellow": 0}}
    for e in events:
        if e.get("type") != "Card":
            continue
        team = (e.get("team") or {}).get("name")
        if team not in out:
            continue
        d = str(e.get("detail", ""))
        if d == "Yellow Card":
            out[team]["yellow"] += 1
        elif d == "Second Yellow card":
            out[team]["second_yellow"] += 1; out[team]["red"] += 1
        elif d == "Red Card":
            out[team]["red"] += 1
    return out


def count_subs(events, home_team, away_team):
    out = {home_team: 0, away_team: 0}
    for e in events:
        if e.get("type") == "subst" and (e.get("team") or {}).get("name") in out:
            out[(e.get("team") or {}).get("name")] += 1
    return out


def is_chronological(events):
    """Event minutes must be non-decreasing (provider order sanity)."""
    mins = [_minute(e) for e in events]
    return all(mins[i] <= mins[i + 1] for i in range(len(mins) - 1))


def no_future_event_in_decision(events, decision_minute):
    """Events strictly after the decision minute must not be present in that decision's state window."""
    return [e for e in events if _minute(e) > decision_minute]


def reconcile_match(events, home_team, away_team, fixture_final, fixture_score=None):
    """Compare reconciled regulation+ET goals to the provider's reported final; classify match quality."""
    rec = reconcile_goals(events, home_team, away_team)
    rep_h, rep_a = int(fixture_final.get("home") or 0), int(fixture_final.get("away") or 0)
    so = shootout_score(fixture_score)
    exact = (rec[home_team] == rep_h and rec[away_team] == rep_a)
    return {
        "home_team": home_team, "away_team": away_team,
        "recon_home": rec[home_team], "recon_away": rec[away_team],
        "reported_home": rep_h, "reported_away": rep_a,
        "shootout": so, "reconciles_exact": exact,
        # chronology is INFORMATIONAL: providers group events by type, so the raw list is often not
        # minute-monotonic even when the score reconciles exactly. The release gate keys on score
        # exactness; chronology is reported for transparency, not used to fail a match.
        "chronological": is_chronological(events),
        "quality_status": "ok" if exact else "exception",
    }
